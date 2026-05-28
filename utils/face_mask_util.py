"""
人脸遮罩叠加工具
将 YOLO 识别的人脸遮罩视频叠加到原始视频上，用于遮盖人脸后传给对人脸敏感的模型
"""
import os
import subprocess
import threading
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _log_ffmpeg_error(proc, stderr_chunks):
    """读取 ffmpeg stderr 并记录错误日志"""
    try:
        proc.stdin.close()
    except Exception:
        pass
    proc.wait(timeout=5)
    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
    logger.error(f"ffmpeg 进程异常退出, returncode={proc.returncode}, stderr: {stderr[:1000]}")


def overlay_face_mask(
    original_video: str,
    mask_video: str,
    output_video: str,
    mask_color: Tuple[int, int, int] = (0, 0, 0),
    mask_alpha: float = 1.0,
    threshold: int = 128,
    ffmpeg_path: Optional[str] = None,
    ffprobe_path: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    将人脸遮罩视频叠加到原始视频上

    Args:
        original_video: 原始视频路径（带有人脸的视频）
        mask_video: 遮罩视频路径（YOLO 识别的人脸方框，白色区域为遮罩）
        output_video: 输出视频路径
        mask_color: 遮罩颜色 (B, G, R)，默认黑色 (0, 0, 0)
        mask_alpha: 遮罩透明度 (0.0-1.0)，值越大遮罩越不透明，默认 0.85
        threshold: 遮罩阈值 (0-255)，高于此值的像素被视为遮罩区域，默认 128
        ffmpeg_path: ffmpeg 可执行文件路径，为 None 时从配置读取
        ffprobe_path: ffprobe 可执行文件路径，为 None 时从配置读取

    Returns:
        Tuple[bool, Optional[str], Optional[str]]:
            - 是否成功
            - 输出文件路径（成功时）
            - 错误信息（失败时）
    """
    import cv2
    import numpy as np

    if ffmpeg_path is None or ffprobe_path is None:
        from config.config_util import get_config_value, resolve_bin_path
        from utils.project_path import get_project_root
        app_dir = get_project_root()
        if ffmpeg_path is None:
            ffmpeg_path = resolve_bin_path(
                get_config_value("bin", "ffmpeg", default="ffmpeg"), app_dir
            )
        if ffprobe_path is None:
            ffprobe_path = resolve_bin_path(
                get_config_value("bin", "ffprobe", default="ffprobe"), app_dir
            )

    if not os.path.exists(original_video):
        return False, None, f"原始视频不存在: {original_video}"
    if not os.path.exists(mask_video):
        return False, None, f"遮罩视频不存在: {mask_video}"

    os.makedirs(os.path.dirname(os.path.abspath(output_video)), exist_ok=True)

    temp_audio = output_video + ".audio.aac"
    cap_orig = None
    cap_mask = None
    ffmpeg_proc = None

    try:
        has_audio = _extract_audio(ffmpeg_path, ffprobe_path, original_video, temp_audio)

        cap_orig = cv2.VideoCapture(original_video)
        cap_mask = cv2.VideoCapture(mask_video)

        if not cap_orig.isOpened():
            return False, None, f"无法打开原始视频: {original_video}"
        if not cap_mask.isOpened():
            return False, None, f"无法打开遮罩视频: {mask_video}"

        fps = 24  # 固定 24fps，与 RunningHub 保持一致
        width = int(cap_orig.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap_orig.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap_orig.get(cv2.CAP_PROP_FRAME_COUNT))

        mask_w = int(cap_mask.get(cv2.CAP_PROP_FRAME_WIDTH))
        mask_h = int(cap_mask.get(cv2.CAP_PROP_FRAME_HEIGHT))
        mask_total = int(cap_mask.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(
            f"原始视频: {width}x{height}, {fps}fps, {total_frames} 帧 | "
            f"遮罩视频: {mask_w}x{mask_h}, {mask_total} 帧"
        )

        # 通过 ffmpeg stdin pipe 直接写入原始帧，避免 OpenCV VideoWriter 编码兼容问题
        ffmpeg_cmd = [
            ffmpeg_path, "-y",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{width}x{height}",
            "-r", str(fps),
            "-i", "pipe:0",
        ]
        if has_audio:
            ffmpeg_cmd += ["-i", temp_audio, "-c:a", "aac", "-b:a", "128k", "-shortest"]
        else:
            ffmpeg_cmd += ["-an"]
        ffmpeg_cmd += [
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_video,
        ]

        stderr_chunks = []

        def _drain_stderr():
            while True:
                chunk = ffmpeg_proc.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks.append(chunk)

        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        drain_thread = threading.Thread(target=_drain_stderr, daemon=True)
        drain_thread.start()

        frame_idx = 0
        masked_count = 0
        empty_count = 0

        while True:
            ret_orig, frame = cap_orig.read()
            if not ret_orig:
                break

            # ffmpeg 可能因 -shortest 提前结束（音频比视频短），检查进程状态
            if ffmpeg_proc.poll() is not None:
                logger.info(f"ffmpeg 已提前结束 (returncode={ffmpeg_proc.returncode})，停止写帧")
                break

            ret_mask, mask_frame = cap_mask.read()
            if not ret_mask:
                cap_mask.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret_mask, mask_frame = cap_mask.read()
                if not ret_mask:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    try:
                        ffmpeg_proc.stdin.write(rgb.tobytes())
                    except BrokenPipeError:
                        break
                    frame_idx += 1
                    empty_count += 1
                    continue

            if mask_frame.shape[:2] != frame.shape[:2]:
                mask_frame = cv2.resize(mask_frame, (width, height))

            mask_gray = cv2.cvtColor(mask_frame, cv2.COLOR_BGR2GRAY)
            mask_binary = mask_gray > threshold
            pixel_count = int(np.sum(mask_binary))

            result = frame.copy()
            result[mask_binary] = (
                frame[mask_binary] * (1.0 - mask_alpha)
                + np.array(mask_color, dtype=np.float32) * mask_alpha
            ).astype(np.uint8)
            rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            try:
                ffmpeg_proc.stdin.write(rgb.tobytes())
            except BrokenPipeError:
                break

            if pixel_count > 0:
                masked_count += 1
            else:
                empty_count += 1

            frame_idx += 1
            if frame_idx % 100 == 0:
                logger.info(f"已处理 {frame_idx}/{total_frames} 帧")

        cap_orig.release()
        cap_mask.release()
        cap_orig = None
        cap_mask = None

        ffmpeg_proc.stdin.close()
        try:
            ffmpeg_proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg 编码超时（300秒），强制终止")
            ffmpeg_proc.kill()
            ffmpeg_proc.wait()
        drain_thread.join(timeout=5)

        logger.info(f"帧处理完成，共 {frame_idx} 帧，有遮罩: {masked_count}，无遮罩: {empty_count}")

        if ffmpeg_proc.returncode != 0:
            stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
            logger.error(f"ffmpeg 编码失败: {stderr[:500]}")
            return False, None, "ffmpeg 编码失败"

        logger.info(f"人脸遮罩叠加完成: {output_video}")
        return True, output_video, None

    except Exception as e:
        logger.error(f"人脸遮罩叠加异常: {e}", exc_info=True)
        return False, None, f"人脸遮罩叠加异常: {e}"
    finally:
        if cap_orig is not None:
            cap_orig.release()
        if cap_mask is not None:
            cap_mask.release()
        if ffmpeg_proc is not None:
            try:
                if ffmpeg_proc.stdin:
                    ffmpeg_proc.stdin.close()
                ffmpeg_proc.kill()
                ffmpeg_proc.wait()
            except Exception:
                pass
        try:
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
        except Exception:
            pass


def _extract_audio(
    ffmpeg_path: str,
    ffprobe_path: str,
    video_path: str,
    audio_path: str,
) -> bool:
    """从视频中提取音频，返回是否包含音频"""
    try:
        probe_cmd = [
            ffprobe_path, "-v", "quiet",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            video_path,
        ]
        probe_result = subprocess.run(
            probe_cmd, capture_output=True, text=True, timeout=30
        )
        has_audio = "audio" in probe_result.stdout

        if not has_audio:
            logger.info("原始视频无音频，跳过音频提取")
            return False

        cmd = [
            ffmpeg_path, "-y", "-i", video_path,
            "-vn", "-acodec", "aac", "-b:a", "128k",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning(f"提取音频失败: {result.stderr[:200]}")
            return False

        logger.info(f"音频已提取: {audio_path}")
        return True

    except Exception as e:
        logger.warning(f"提取音频异常: {e}")
        return False
