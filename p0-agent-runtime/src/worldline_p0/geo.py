from math import radians, sin, cos, asin, sqrt


def load_places(gazetteer_payload):
    return gazetteer_payload.get("places", [])


def resolve_place(record, places):
    hint = (record.get("location_hint") or "").lower()
    text = " ".join(
        [
            record.get("title") or "",
            record.get("text") or "",
            " ".join(record.get("media", {}).get("ocr_text", [])),
            record.get("media", {}).get("asr_text", ""),
        ]
    ).lower()
    for place in places:
        name = place.get("name", "")
        if name.lower() in hint or name.lower() in text:
            return place
    if places:
        return places[0]
    return {"name": "unknown", "region_id": "unknown", "lon": 0.0, "lat": 0.0}


def haversine_km(a, b):
    lon1, lat1 = a
    lon2, lat2 = b
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))
