from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.image_analysis import ImageAnalysis

EVENT_RULES = {
    "College Event": {"keywords": {"college", "campus", "classroom", "student", "students", "school", "university"}, "minimum": 4},
    "Travel": {"keywords": {"travel", "airport", "airplane", "train", "road", "tourist", "trip"}, "minimum": 4},
    "Vacation": {"keywords": {"beach", "ocean", "mountain", "hotel", "pool", "resort", "tourist"}, "minimum": 4},
    "Birthday": {"keywords": {"birthday", "cake", "party", "celebration", "balloon"}, "minimum": 3},
    "Wedding": {"keywords": {"wedding", "bride", "groom", "ceremony", "dress", "party"}, "minimum": 4},
}


def _get_image_text(analysis: ImageAnalysis) -> set[str]:
    words = set()
    if analysis.caption:
        words.update(analysis.caption.lower().split())
    if analysis.category:
        words.add(analysis.category.lower())
    if analysis.tags:
        words.update(tag.strip().lower() for tag in analysis.tags.split(",") if tag.strip())
    return words


def _calculate_confidence(match_count: int, asset_count: int) -> float:
    keyword_score = min(match_count / 3, 1.0)
    volume_score = min(asset_count / 20, 1.0)
    return round(min(0.65 * keyword_score + 0.35 * volume_score, 0.98), 2)


def generate_event_suggestions(db: Session) -> dict:
    rows = db.execute(
        select(ImageAnalysis, Asset)
        .join(Asset, Asset.id == ImageAnalysis.asset_id)
        .where(Asset.is_missing.is_(False), Asset.file_type == "image")
    ).all()

    suggestions = []
    for event_name, rule in EVENT_RULES.items():
        matched = []
        for analysis, asset in rows:
            keyword_matches = _get_image_text(analysis).intersection(rule["keywords"])
            if keyword_matches:
                matched.append({"asset": asset, "keywords": keyword_matches})

        if len(matched) < rule["minimum"]:
            continue

        assets = {item["asset"].id: item["asset"] for item in matched}
        keywords = set()
        for item in matched:
            keywords.update(item["keywords"])

        suggestions.append({
            "name": event_name,
            "type": "event",
            "description": f"Possible {event_name.lower()} based on AI image analysis.",
            "asset_count": len(assets),
            "confidence": _calculate_confidence(len(keywords), len(assets)),
            "matched_keywords": sorted(keywords),
            "asset_ids": list(assets.keys()),
        })

    return {"total_suggestions": len(suggestions), "suggestions": suggestions}


def generate_time_clusters(db: Session) -> list[dict]:
    assets = db.scalars(
        select(Asset)
        .where(Asset.file_type == "image", Asset.is_missing.is_(False), Asset.modified_at.is_not(None))
        .order_by(Asset.modified_at.asc())
    ).all()
    if not assets:
        return []

    clusters = []
    current = [assets[0]]
    for asset in assets[1:]:
        previous = current[-1]
        if previous.modified_at and asset.modified_at and asset.modified_at - previous.modified_at <= timedelta(hours=6):
            current.append(asset)
        else:
            if len(current) >= 4:
                clusters.append(current)
            current = [asset]
    if len(current) >= 4:
        clusters.append(current)

    result = []
    for index, cluster in enumerate(clusters, start=1):
        first_date = cluster[0].modified_at
        last_date = cluster[-1].modified_at
        result.append({
            "name": f"Photo Event {index}",
            "type": "time_cluster",
            "description": "Images captured or modified within a short time period.",
            "asset_count": len(cluster),
            "confidence": 0.55,
            "start_time": first_date.isoformat() if first_date else None,
            "end_time": last_date.isoformat() if last_date else None,
            "asset_ids": [asset.id for asset in cluster],
        })
    return result


def generate_all_suggestions(db: Session) -> dict:
    suggestions = generate_event_suggestions(db)["suggestions"]
    suggestions.extend(generate_time_clusters(db))
    return {"total_suggestions": len(suggestions), "suggestions": suggestions}
