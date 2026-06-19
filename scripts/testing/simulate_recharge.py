#!/usr/bin/env python3
"""
手工测试脚本：模拟用户充值成功（触发算力发放 + 邀请抽佣）

跳过微信支付的验签/解密，直接复刻 server.py 支付回调里"支付成功后"的处理：
    创建订单 → 标记已付 → 抽佣结算(CommissionService.settle) → 发放算力

用于端到端验证邀请抽佣链路（社区版/商业版、首充、有无邀请人、佣金比例、幂等）。

用法:
    # 列出可用套餐（不需要数据库）
    python scripts/testing/simulate_recharge.py --list-packages

    # 给 user_id=5 充值套餐 2（标准套餐），自动生成交易号
    python scripts/testing/simulate_recharge.py --user-id 5 --package-id 2

    # 用手机号指定用户
    python scripts/testing/simulate_recharge.py --phone 13800000000 --package-id 2

    # 指定交易号（同交易号重复执行不会重复发算力/抽佣 —— 验证幂等）
    python scripts/testing/simulate_recharge.py --user-id 5 --package-id 2 --transaction-id TEST_001

    # 预览，不实际写入
    python scripts/testing/simulate_recharge.py --user-id 5 --package-id 2 --dry-run

注意：
- 脚本直接操作业务库（读取 config 中的 database 配置），会产生真实的订单/算力/佣金记录。
- package_id=1 为首充福利，settle 内部判定不抽佣；脚本不模拟"首充重复购买降级为 4 算力"的边界（那是 server.py 回调里的逻辑）。
"""
import os
import sys
import argparse
import uuid

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 以下 import 仅常量（不连接数据库、不触发版本判定，避免 --list-packages 依赖 yaml 等）
from config.constant import RECHARGE_PACKAGES


def find_package(package_id):
    for pkg in RECHARGE_PACKAGES:
        if pkg['package_id'] == package_id:
            return pkg
    return None


def list_packages():
    print("=" * 56)
    print("可用充值套餐 (config/constant.py: RECHARGE_PACKAGES)")
    print("-" * 56)
    print(f"{'package_id':<12}{'算力':<10}{'价格(元)':<12}{'说明'}")
    for pkg in RECHARGE_PACKAGES:
        print(f"{pkg['package_id']:<12}{pkg['computing_power']:<10}{pkg['price']:<12}{pkg.get('description', '')}")
    print("-" * 56)
    print("提示: package_id=1 为首充福利（不参与抽佣）；其余套餐参与邀请抽佣。")
    print("=" * 56)


def mask_phone(phone):
    if not phone:
        return '-'
    p = str(phone)
    if len(p) >= 7:
        return p[:3] + '****' + p[-4:]
    return p


def simulate(args):
    # 延迟 import：这些模块会连接数据库（读取 config database 配置）
    from model.users import UsersModel
    from model.payment_orders import PaymentOrdersModel
    from model.computing_power import ComputingPowerModel
    from model.database import execute_query
    from perseids_server.services.computing_power_service import ComputingPowerService
    from enterprise.services.commission_service import CommissionService
    from model.commission_log import CommissionLogModel
    from config.strategy.edition_strategy import IS_COMMUNITY_EDITION

    package = find_package(args.package_id)
    if not package:
        print(f"[ERROR] package_id={args.package_id} 不存在，使用 --list-packages 查看可用套餐")
        sys.exit(1)

    # 解析用户
    if args.user_id:
        user = UsersModel.get_by_id(args.user_id)
        if not user:
            print(f"[ERROR] user_id={args.user_id} 不存在")
            sys.exit(1)
    elif args.phone:
        row = execute_query("SELECT id FROM users WHERE phone = %s", (args.phone,), fetch_one=True)
        if not row:
            print(f"[ERROR] phone={args.phone} 不存在")
            sys.exit(1)
        user = UsersModel.get_by_id(row['id'])
    else:
        print("[ERROR] 请用 --user-id 或 --phone 指定用户")
        sys.exit(1)

    user_id = user.id
    inviter_id = user.inviter_id
    inviter_rate = UsersModel.get_commission_rate(inviter_id) if inviter_id else None
    edition_label = '社区版(不抽佣)' if IS_COMMUNITY_EDITION else '商业版'

    transaction_id = args.transaction_id or f"SIM_{uuid.uuid4().hex[:16].upper()}"

    # 充值前算力
    cp_before = ComputingPowerModel.get_by_user_id(user_id)
    power_before = cp_before.computing_power if cp_before else 0
    # 邀请人充值前可用佣金
    inviter_available_before = CommissionLogModel.sum_available(inviter_id) if inviter_id else 0

    print("=" * 60)
    print("充值模拟（simulate_recharge）")
    print("-" * 60)
    print(f"版本           : {edition_label}")
    print(f"用户           : id={user_id}  phone={mask_phone(user.phone)}")
    if inviter_id:
        rate_pct = f"{float(inviter_rate or 0) * 100:.1f}%" if inviter_rate is not None else '未设置(0%)'
        print(f"邀请人         : id={inviter_id}  佣金比例={rate_pct}")
    else:
        print(f"邀请人         : 无（不会被抽佣，全额到账）")
    print(f"套餐           : package_id={package['package_id']}  {package.get('description', '')}")
    print(f"价格 / 原始算力: ¥{package['price']}  /  {package['computing_power']}")
    print(f"交易号         : {transaction_id}")
    print("-" * 60)

    if args.dry_run:
        print("[DRY-RUN] 预览模式，不实际写入数据库。")
        print("=" * 60)
        return

    # 1. 创建订单（status=0 待支付）
    order_id = f"SIMORD_{uuid.uuid4().hex[:14].upper()}"
    PaymentOrdersModel.create(
        order_id=order_id, user_id=user_id, package_id=package['package_id'],
        computing_power=package['computing_power'], price=package['price'],
        payment_type='NATIVE', platform='wechat', status=0,
        note='simulate_recharge 测试订单'
    )
    print(f"[1] 创建订单    : {order_id}  OK")

    # 2. 标记已付
    PaymentOrdersModel.update_paid(order_id, transaction_id)
    print(f"[2] 标记已付    : OK")

    # 3. 抽佣结算（与 server.py 支付回调完全一致）
    settle = CommissionService.settle(
        invitee_id=user_id, order_id=order_id, transaction_id=transaction_id,
        package_id=package['package_id'], order_amount=package['price'],
        computing_power=package['computing_power']
    )
    granted = settle.get('granted_computing_power', package['computing_power'])
    print(f"[3] 抽佣结算    : {settle.get('message')}  (到账算力={granted})")

    # 4. 发放算力（用打折后的 granted，与 server.py 一致）
    cp = ComputingPowerService.calculate_computing_power(
        user_id=user_id, computing_power=granted, behavior='increase',
        transaction_id=transaction_id, note=f"模拟充值 套餐{package['package_id']}"
    )
    print(f"[4] 发放算力    : {'OK' if cp.get('success') else 'FAIL - ' + cp.get('message', '')}")

    # 结果报告
    cp_after = ComputingPowerModel.get_by_user_id(user_id)
    power_after = cp_after.computing_power if cp_after else 0
    inviter_available_after = CommissionLogModel.sum_available(inviter_id) if inviter_id else 0

    print("-" * 60)
    print("✅ 完成")
    print(f"  被邀请人算力      : {power_before} → {power_after}  (+{power_after - power_before})")
    if inviter_id:
        delta = inviter_available_after - inviter_available_before
        print(f"  邀请人可用佣金    : ¥{inviter_available_before:.2f} → ¥{inviter_available_after:.2f}  (+¥{delta:.2f})")
    print(f"  抽佣明细(commission_log): 本次新增 {'1' if (inviter_id and settle.get('message') == '抽佣成功') else '0'} 条")
    print(f"  订单号            : {order_id}")
    print(f"  交易号            : {transaction_id}")
    if settle.get('message') == '已结算(幂等)' or settle.get('message') == '已结算(并发幂等)':
        print("  ⚠️ 该交易号此前已结算过，算力/佣金未重复发放（幂等生效）。")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='模拟用户充值成功（触发算力发放 + 邀请抽佣）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--user-id', type=int, help='被充值的用户 ID')
    parser.add_argument('--phone', type=str, help='被充值的用户手机号（与 --user-id 二选一）')
    parser.add_argument('--package-id', type=int, default=2, help='套餐 ID（默认 2；用 --list-packages 查看）')
    parser.add_argument('--transaction-id', type=str, help='自定义交易号（用于复测幂等；默认自动生成）')
    parser.add_argument('--list-packages', action='store_true', help='列出可用套餐后退出')
    parser.add_argument('--dry-run', action='store_true', help='预览，不实际写入数据库')
    args = parser.parse_args()

    if args.list_packages:
        list_packages()
        return

    if not args.user_id and not args.phone:
        parser.error('请用 --user-id 或 --phone 指定用户（或用 --list-packages 查看套餐）')

    simulate(args)


if __name__ == '__main__':
    main()
