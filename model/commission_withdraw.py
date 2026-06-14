"""
CommissionWithdraw Model - Database operations for commission_withdraw table
佣金提现申请表

设计要点：
- 不存储提现金额（amount）；某提现单金额 = commission_log 中 withdraw_no=本单 的 SUM(commission_amount)。
- 仅记录提现单的状态流转（待审核 / 已打款 / 已驳回）。
- 全额提现：申请即关联当前全部可用 commission_log 记录（冻结），打款确认，驳回解冻。
"""
from typing import Optional, Dict, Any, List
from .database import execute_query, execute_insert
import logging

logger = logging.getLogger(__name__)


class CommissionWithdraw:
    """CommissionWithdraw model class - 佣金提现申请"""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.withdraw_no = kwargs.get('withdraw_no')
        self.inviter_id = kwargs.get('inviter_id')
        self.status = kwargs.get('status', 0)
        self.apply_note = kwargs.get('apply_note')
        self.reject_reason = kwargs.get('reject_reason')
        self.reviewer_id = kwargs.get('reviewer_id')
        self.reviewed_at = kwargs.get('reviewed_at')
        self.paid_at = kwargs.get('paid_at')
        self.create_at = kwargs.get('create_at')
        self.update_at = kwargs.get('update_at')
        # 金额不落表，展示时由 service 通过 commission_log 聚合注入
        self.amount = kwargs.get('amount')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'withdraw_no': self.withdraw_no,
            'inviter_id': self.inviter_id,
            'amount': float(self.amount) if self.amount is not None else None,
            'status': self.status,
            'apply_note': self.apply_note,
            'reject_reason': self.reject_reason,
            'reviewer_id': self.reviewer_id,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'create_at': self.create_at.isoformat() if self.create_at else None,
            'update_at': self.update_at.isoformat() if self.update_at else None,
        }


class CommissionWithdrawModel:
    """CommissionWithdraw database operations"""

    # status
    STATUS_PENDING = 0    # 待审核
    STATUS_PAID = 1       # 已打款
    STATUS_REJECTED = 2   # 已驳回

    @staticmethod
    def create(withdraw_no: str, inviter_id: int, apply_note: Optional[str] = None) -> int:
        """
        创建提现申请单（status=待审核）

        Returns:
            Inserted record ID
        """
        sql = """
            INSERT INTO commission_withdraw (withdraw_no, inviter_id, status, apply_note)
            VALUES (%s, %s, %s, %s)
        """
        try:
            wid = execute_insert(sql, (
                withdraw_no, inviter_id,
                CommissionWithdrawModel.STATUS_PENDING, apply_note
            ))
            logger.info(f"Created commission withdraw: no={withdraw_no}, inviter={inviter_id}")
            return wid
        except Exception as e:
            logger.error(f"Failed to create commission withdraw: {e}")
            raise

    @staticmethod
    def get_by_withdraw_no(withdraw_no: str) -> Optional[CommissionWithdraw]:
        """根据提现单号获取"""
        sql = "SELECT * FROM commission_withdraw WHERE withdraw_no = %s"
        try:
            result = execute_query(sql, (withdraw_no,), fetch_one=True)
            return CommissionWithdraw(**result) if result else None
        except Exception as e:
            logger.error(f"Failed to get withdraw by no {withdraw_no}: {e}")
            raise

    @staticmethod
    def get_by_id(record_id: int) -> Optional[CommissionWithdraw]:
        """根据ID获取"""
        sql = "SELECT * FROM commission_withdraw WHERE id = %s"
        try:
            result = execute_query(sql, (record_id,), fetch_one=True)
            return CommissionWithdraw(**result) if result else None
        except Exception as e:
            logger.error(f"Failed to get withdraw by id {record_id}: {e}")
            raise

    @staticmethod
    def list_by_inviter(inviter_id: int, limit: int = 20, offset: int = 0) -> List[CommissionWithdraw]:
        """根据邀请人ID分页获取提现单"""
        sql = """
            SELECT * FROM commission_withdraw
            WHERE inviter_id = %s
            ORDER BY create_at DESC
            LIMIT %s OFFSET %s
        """
        try:
            results = execute_query(sql, (inviter_id, limit, offset), fetch_all=True)
            return [CommissionWithdraw(**row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to list withdraws for inviter {inviter_id}: {e}")
            raise

    @staticmethod
    def count_by_inviter(inviter_id: int) -> int:
        """统计邀请人的提现单总数"""
        sql = "SELECT COUNT(*) as count FROM commission_withdraw WHERE inviter_id = %s"
        try:
            result = execute_query(sql, (inviter_id,), fetch_one=True)
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Failed to count withdraws for inviter {inviter_id}: {e}")
            raise

    @staticmethod
    def list_for_admin(status: Optional[int] = None, limit: int = 20, offset: int = 0) -> List[CommissionWithdraw]:
        """管理端分页查询提现单（可按状态过滤）"""
        sql = "SELECT * FROM commission_withdraw WHERE 1=1"
        params: List[Any] = []
        if status is not None:
            sql += " AND status = %s"
            params.append(status)
        sql += " ORDER BY create_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        try:
            results = execute_query(sql, tuple(params), fetch_all=True)
            return [CommissionWithdraw(**row) for row in results] if results else []
        except Exception as e:
            logger.error(f"Failed to list withdraws for admin: {e}")
            raise

    @staticmethod
    def count_for_admin(status: Optional[int] = None) -> int:
        """管理端统计提现单总数（可按状态过滤）"""
        sql = "SELECT COUNT(*) as count FROM commission_withdraw WHERE 1=1"
        params: List[Any] = []
        if status is not None:
            sql += " AND status = %s"
            params.append(status)
        try:
            result = execute_query(sql, tuple(params), fetch_one=True)
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Failed to count withdraws for admin: {e}")
            raise

    @staticmethod
    def update_to_paid(conn, withdraw_no: str, reviewer_id: int) -> int:
        """
        审核通过（已打款）。在事务内执行。
        带 WHERE status=0 CAS，防止重复/越权流转。
        """
        sql = """
            UPDATE commission_withdraw
            SET status = 1, reviewer_id = %s, reviewed_at = NOW(), paid_at = NOW()
            WHERE withdraw_no = %s AND status = 0
        """
        cursor = conn.cursor()
        return cursor.execute(sql, (reviewer_id, withdraw_no))

    @staticmethod
    def update_to_rejected(conn, withdraw_no: str, reviewer_id: int, reject_reason: Optional[str]) -> int:
        """
        审核驳回。在事务内执行。
        带 WHERE status=0 CAS，防止重复/越权流转。
        """
        sql = """
            UPDATE commission_withdraw
            SET status = 2, reviewer_id = %s, reviewed_at = NOW(), reject_reason = %s
            WHERE withdraw_no = %s AND status = 0
        """
        cursor = conn.cursor()
        return cursor.execute(sql, (reviewer_id, reject_reason, withdraw_no))


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `commission_withdraw` (
  `id` int NOT NULL AUTO_INCREMENT,
  `withdraw_no` varchar(64) NOT NULL COMMENT '提现单号',
  `inviter_id` int NOT NULL COMMENT '申请提现的邀请人ID',
  `status` tinyint NOT NULL DEFAULT 0 COMMENT '0-待审核 1-已打款 2-已驳回',
  `apply_note` varchar(500) DEFAULT NULL,
  `reject_reason` varchar(500) DEFAULT NULL,
  `reviewer_id` int DEFAULT NULL COMMENT '审核管理员ID',
  `reviewed_at` datetime DEFAULT NULL,
  `paid_at` datetime DEFAULT NULL,
  `create_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `update_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_withdraw_no` (`withdraw_no`),
  KEY `idx_inviter_create` (`inviter_id`,`create_at`),
  KEY `idx_status_create` (`status`,`create_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='佣金提现申请表';
"""
