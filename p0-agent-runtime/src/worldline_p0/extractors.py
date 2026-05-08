RISK_KEYWORDS = {
    "death": "high_sensitivity_fact",
    "hidden": "trust_break",
    "question": "trust_break",
    "response": "response_gap",
    "evidence": "evidence_gap",
    "crowd": "offline_gathering",
    "gathering": "offline_gathering",
    "police": "offline_signal",
    "school": "school_responsibility",
    "family": "stakeholder_pressure",
    "minor": "minor_protection",
    "privacy": "privacy_risk",
}

NARRATIVE_KEYWORDS = {
    "hidden": "information_transparency",
    "response": "response_credibility",
    "evidence": "evidence_preservation",
    "family": "family_accountability",
    "school": "school_responsibility",
    "crowd": "offline_order",
}


def merge_record_text(record):
    media = record.get("media") or {}
    parts = [
        record.get("title") or "",
        record.get("text") or "",
        media.get("asr_text") or "",
        " ".join(media.get("ocr_text") or []),
        " ".join(media.get("scene_tags") or []),
    ]
    return " ".join(part for part in parts if part).strip()


def extract_tags(text):
    lower = text.lower()
    tags = []
    for keyword, tag in RISK_KEYWORDS.items():
        if keyword in lower and tag not in tags:
            tags.append(tag)
    return tags or ["general_attention"]


def extract_narratives(text):
    lower = text.lower()
    frames = []
    for keyword, frame in NARRATIVE_KEYWORDS.items():
        if keyword in lower and frame not in frames:
            frames.append(frame)
    return frames or ["general_risk"]


def score_heat(metrics):
    views = int(metrics.get("views", 0) or 0)
    comments = int(metrics.get("comments", 0) or 0)
    shares = int(metrics.get("shares", 0) or 0)
    raw = min(100, (views / 2000) + comments * 0.12 + shares * 0.18)
    return round(raw, 2)


def score_fact_credibility(source_trust, records):
    source_part = float(source_trust or 0.5) * 70
    evidence_part = min(30, len(records) * 9)
    return round(min(100, source_part + evidence_part), 2)


def score_mainline_risk(tags, heat, credibility):
    high_value_tags = {
        "high_sensitivity_fact",
        "trust_break",
        "offline_gathering",
        "response_gap",
        "privacy_risk",
        "minor_protection",
    }
    tag_part = len(high_value_tags.intersection(tags)) * 12
    return round(min(100, heat * 0.45 + credibility * 0.25 + tag_part), 2)
