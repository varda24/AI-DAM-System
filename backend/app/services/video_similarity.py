from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
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

DEFAULT_SAMPLE_COUNT = 8
HASH_SIZE = 16


@dataclass
class VideoFingerprint:
    asset_id: int
    frame_hashes: list[str]
    duration_seconds: float | None
    width: int | None
    height: int | None


def is_video_asset(asset: Asset) -> bool:
    if asset.file_type == "video":
        return True

    if asset.extension:
        return asset.extension.lower() in VIDEO_EXTENSIONS

    return False


def _average_hash(frame: np.ndarray) -> str | None:
    """
    Generate a simple perceptual average hash.

    The frame is converted to grayscale and resized to a small,
    normalized representation. This makes the fingerprint reasonably
    tolerant of resolution and compression differences.
    """
    try:
        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY,
        )

        resized = cv2.resize(
            gray,
            (HASH_SIZE, HASH_SIZE),
            interpolation=cv2.INTER_AREA,
        )

        average = float(resized.mean())

        bits = resized >= average

        return "".join(
            "1" if bit else "0"
            for bit in bits.flatten()
        )

    except Exception:
        return None


def _hamming_distance(
    first: str,
    second: str,
) -> int:
    if len(first) != len(second):
        return max(len(first), len(second))

    return sum(
        a != b
        for a, b in zip(first, second)
    )


def _hash_similarity(
    first: str,
    second: str,
) -> float:
    if not first or not second:
        return 0.0

    distance = _hamming_distance(
        first,
        second,
    )

    maximum = max(
        len(first),
        len(second),
    )

    if maximum == 0:
        return 0.0

    return max(
        0.0,
        1.0 - (distance / maximum),
    )


def _sample_frame_positions(
    frame_count: int,
    sample_count: int,
) -> list[int]:
    if frame_count <= 0:
        return []

    if sample_count <= 1:
        return [0]

    actual_count = min(
        sample_count,
        frame_count,
    )

    positions = np.linspace(
        0,
        frame_count - 1,
        actual_count,
    )

    return sorted(
        {
            int(round(position))
            for position in positions
        }
    )


def fingerprint_video(
    asset: Asset,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
) -> VideoFingerprint:
    """
    Create a frame-based fingerprint for one video.

    Only the requested video file is opened.
    """
    video_path = Path(asset.path)

    if not video_path.exists():
        raise FileNotFoundError(
            f"Video file does not exist: {video_path}"
        )

    if not video_path.is_file():
        raise ValueError(
            f"Video path is not a file: {video_path}"
        )

    capture = cv2.VideoCapture(
        str(video_path)
    )

    try:
        if not capture.isOpened():
            raise ValueError(
                "OpenCV could not open the video."
            )

        frame_count = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
            or 0
        )

        fps = float(
            capture.get(
                cv2.CAP_PROP_FPS
            )
            or 0
        )

        width = int(
            capture.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
            or 0
        )

        height = int(
            capture.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
            or 0
        )

        duration = None

        if frame_count > 0 and fps > 0:
            duration = frame_count / fps

        positions = _sample_frame_positions(
            frame_count=frame_count,
            sample_count=sample_count,
        )

        frame_hashes: list[str] = []

        for position in positions:
            capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                position,
            )

            success, frame = capture.read()

            if not success or frame is None:
                continue

            frame_hash = _average_hash(frame)

            if frame_hash:
                frame_hashes.append(frame_hash)

        if not frame_hashes:
            raise ValueError(
                "Could not extract usable frames from the video."
            )

        return VideoFingerprint(
            asset_id=asset.id,
            frame_hashes=frame_hashes,
            duration_seconds=duration,
            width=width if width > 0 else None,
            height=height if height > 0 else None,
        )

    finally:
        capture.release()


def compare_fingerprints(
    first: VideoFingerprint,
    second: VideoFingerprint,
) -> float:
    """
    Compare two frame-based video fingerprints.

    Each sampled frame from the first video is matched against
    the closest frame from the second video. The final score is
    the average of those best matches.
    """
    if not first.frame_hashes or not second.frame_hashes:
        return 0.0

    scores: list[float] = []

    for first_hash in first.frame_hashes:
        best_score = max(
            _hash_similarity(
                first_hash,
                second_hash,
            )
            for second_hash in second.frame_hashes
        )

        scores.append(best_score)

    if not scores:
        return 0.0

    return float(
        sum(scores) / len(scores)
    )


def _duration_similarity(
    first: float | None,
    second: float | None,
) -> float:
    if first is None or second is None:
        return 0.5

    if first <= 0 or second <= 0:
        return 0.5

    difference = abs(first - second)
    maximum = max(first, second)

    return max(
        0.0,
        1.0 - (difference / maximum),
    )


def _dimension_similarity(
    first_width: int | None,
    first_height: int | None,
    second_width: int | None,
    second_height: int | None,
) -> float:
    if not all(
        value is not None
        for value in (
            first_width,
            first_height,
            second_width,
            second_height,
        )
    ):
        return 0.5

    first_ratio = first_width / first_height
    second_ratio = second_width / second_height

    ratio_difference = abs(
        first_ratio - second_ratio
    )

    return max(
        0.0,
        1.0 - ratio_difference,
    )


def compare_videos(
    first: VideoFingerprint,
    second: VideoFingerprint,
) -> float:
    """
    Produce a weighted video similarity score.

    Frame similarity is the dominant signal. Duration and aspect
    ratio provide supporting signals.
    """
    frame_score = compare_fingerprints(
        first,
        second,
    )

    duration_score = _duration_similarity(
        first.duration_seconds,
        second.duration_seconds,
    )

    dimension_score = _dimension_similarity(
        first.width,
        first.height,
        second.width,
        second.height,
    )

    score = (
        frame_score * 0.75
        + duration_score * 0.15
        + dimension_score * 0.10
    )

    return max(
        0.0,
        min(1.0, score),
    )


def _candidate_videos(
    db: Session,
    asset_ids: Iterable[int] | None = None,
) -> list[Asset]:
    query = select(Asset).where(
        Asset.source == "local_pc",
        Asset.is_missing.is_(False),
    )

    if asset_ids:
        query = query.where(
            Asset.id.in_(list(asset_ids))
        )

    assets = list(
        db.scalars(query).all()
    )

    return [
        asset
        for asset in assets
        if is_video_asset(asset)
    ]


def detect_similar_videos(
    db: Session,
    asset_ids: Iterable[int] | None = None,
    threshold: float = 0.80,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
) -> dict:
    """
    Compare a selected set of videos and return similarity groups.

    This intentionally does not analyze every indexed video unless
    the caller explicitly requests that behavior.
    """
    assets = _candidate_videos(
        db=db,
        asset_ids=asset_ids,
    )

    fingerprints: dict[
        int,
        VideoFingerprint
    ] = {}

    errors: list[dict] = []

    for asset in assets:
        try:
            fingerprints[asset.id] = fingerprint_video(
                asset=asset,
                sample_count=sample_count,
            )
        except Exception as exc:
            errors.append(
                {
                    "asset_id": asset.id,
                    "name": asset.name,
                    "error": str(exc),
                }
            )

    groups: list[dict] = []
    assigned: set[int] = set()

    for index, first_asset in enumerate(assets):
        if first_asset.id in assigned:
            continue

        first_fingerprint = fingerprints.get(
            first_asset.id
        )

        if first_fingerprint is None:
            continue

        members = [
            {
                "asset_id": first_asset.id,
                "name": first_asset.name,
                "path": first_asset.path,
                "size_bytes": first_asset.size_bytes,
                "similarity": 1.0,
            }
        ]

        for second_asset in assets[index + 1:]:
            if second_asset.id in assigned:
                continue

            second_fingerprint = fingerprints.get(
                second_asset.id
            )

            if second_fingerprint is None:
                continue

            similarity = compare_videos(
                first=first_fingerprint,
                second=second_fingerprint,
            )

            if similarity >= threshold:
                members.append(
                    {
                        "asset_id": second_asset.id,
                        "name": second_asset.name,
                        "path": second_asset.path,
                        "size_bytes": second_asset.size_bytes,
                        "similarity": round(
                            similarity * 100,
                            2,
                        ),
                    }
                )

        if len(members) >= 2:
            group_size = sum(
                int(member["size_bytes"] or 0)
                for member in members
            )

            largest_member = max(
                members,
                key=lambda member: int(
                    member["size_bytes"] or 0
                ),
            )

            recoverable = (
                group_size
                - int(
                    largest_member["size_bytes"]
                    or 0
                )
            )

            groups.append(
                {
                    "group_id": len(groups) + 1,
                    "member_count": len(members),
                    "potential_savings_bytes": recoverable,
                    "members": members,
                }
            )

            assigned.update(
                member["asset_id"]
                for member in members
            )

    total_savings = sum(
        int(group["potential_savings_bytes"])
        for group in groups
    )

    return {
        "videos_checked": len(assets),
        "fingerprints_created": len(fingerprints),
        "similar_groups": groups,
        "group_count": len(groups),
        "potential_savings_bytes": total_savings,
        "errors": errors,
        "threshold": threshold,
    }