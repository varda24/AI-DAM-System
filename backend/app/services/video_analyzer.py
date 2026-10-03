from datetime import datetime, timezone
from pathlib import Path

import cv2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.video_analysis import VideoAnalysis


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".m4v",
    ".wmv",
    ".flv",
    ".mpeg",
    ".mpg",
    ".3gp",
}


def is_video_asset(asset: Asset) -> bool:
    """Return True when the indexed asset is a supported video."""
    if asset.file_type == "video":
        return True

    if asset.extension:
        return asset.extension.lower() in VIDEO_EXTENSIONS

    return False


def _codec_from_fourcc(fourcc: float) -> str | None:
    """Convert OpenCV's FOURCC value into a readable codec string."""
    try:
        value = int(fourcc)

        chars = [
            chr(value & 0xFF),
            chr((value >> 8) & 0xFF),
            chr((value >> 16) & 0xFF),
            chr((value >> 24) & 0xFF),
        ]

        codec = "".join(chars).strip("\x00 ")

        if not codec:
            return None

        return codec

    except (TypeError, ValueError):
        return None


def _thumbnail_directory() -> Path:
    """
    Store generated thumbnails outside the user's original files.

    Thumbnails are application-generated data and should not be mixed
    into the indexed source directories.
    """
    directory = Path.home() / "AI-DAM-Thumbnails"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _generate_thumbnail(
    video_path: Path,
    asset_id: int,
) -> str | None:
    """Generate a JPEG thumbnail from approximately the first frame."""
    capture = cv2.VideoCapture(str(video_path))

    try:
        if not capture.isOpened():
            return None

        total_frames = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        )

        fps = float(
            capture.get(cv2.CAP_PROP_FPS) or 0
        )

        # Prefer a frame around 1 second into the video.
        if total_frames > 0 and fps > 0:
            target_frame = min(
                total_frames - 1,
                max(0, int(fps)),
            )

            capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                target_frame,
            )

        success, frame = capture.read()

        if not success or frame is None:
            capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                0,
            )

            success, frame = capture.read()

        if not success or frame is None:
            return None

        thumbnail_path = (
            _thumbnail_directory()
            / f"asset-{asset_id}.jpg"
        )

        written = cv2.imwrite(
            str(thumbnail_path),
            frame,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                85,
            ],
        )

        if not written:
            return None

        return str(thumbnail_path)

    finally:
        capture.release()


def analyze_video(
    db: Session,
    asset_id: int,
) -> VideoAnalysis:
    """
    Analyze one indexed video.

    The source filesystem is accessed only for the requested asset.
    """

    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id
        )
    )

    if asset is None:
        raise ValueError(
            f"Asset {asset_id} was not found."
        )

    if not is_video_asset(asset):
        raise ValueError(
            f"Asset {asset_id} is not a supported video."
        )

    existing = db.scalar(
        select(VideoAnalysis).where(
            VideoAnalysis.asset_id == asset_id
        )
    )

    if existing is None:
        analysis = VideoAnalysis(
            asset_id=asset_id,
        )

        db.add(analysis)

    else:
        analysis = existing

    video_path = Path(asset.path)

    if not video_path.exists():
        analysis.status = "missing"
        analysis.error_message = (
            "Video file does not exist."
        )
        analysis.analyzed_at = datetime.now(
            timezone.utc
        )

        db.commit()
        db.refresh(analysis)

        return analysis

    if not video_path.is_file():
        analysis.status = "invalid"
        analysis.error_message = (
            "Indexed video path is not a file."
        )
        analysis.analyzed_at = datetime.now(
            timezone.utc
        )

        db.commit()
        db.refresh(analysis)

        return analysis

    capture = cv2.VideoCapture(str(video_path))

    try:
        if not capture.isOpened():
            analysis.status = "invalid"
            analysis.error_message = (
                "OpenCV could not open the video."
            )
            analysis.analyzed_at = datetime.now(
                timezone.utc
            )

            db.commit()
            db.refresh(analysis)

            return analysis

        frame_count = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        )

        fps = float(
            capture.get(cv2.CAP_PROP_FPS) or 0
        )

        width = int(
            capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
        )

        height = int(
            capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
        )

        fourcc = capture.get(
            cv2.CAP_PROP_FOURCC
        )

        codec = _codec_from_fourcc(fourcc)

        duration = None

        if frame_count > 0 and fps > 0:
            duration = frame_count / fps

        analysis.frame_count = (
            frame_count if frame_count > 0 else None
        )

        analysis.fps = (
            fps if fps > 0 else None
        )

        analysis.width = (
            width if width > 0 else None
        )

        analysis.height = (
            height if height > 0 else None
        )

        analysis.duration_seconds = duration
        analysis.video_codec = codec

    finally:
        capture.release()

    try:
        thumbnail = _generate_thumbnail(
            video_path=video_path,
            asset_id=asset.id,
        )

        if thumbnail:
            analysis.thumbnail_path = thumbnail

    except Exception as exc:
        analysis.error_message = (
            f"Thumbnail generation failed: {exc}"
        )

    analysis.status = "analyzed"
    analysis.analyzed_at = datetime.now(
        timezone.utc
    )

    db.commit()
    db.refresh(analysis)

    return analysis