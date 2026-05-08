from collections import defaultdict
from datetime import datetime, timezone

from .extractors import (
    extract_narratives,
    extract_tags,
    merge_record_text,
    score_fact_credibility,
    score_heat,
    score_mainline_risk,
)
from .geo import load_places, resolve_place
from .io import read_json
from .policy import is_source_allowed


def run_p0_pipeline(source_registry_path, records_path, gazetteer_path):
    registry = read_json(source_registry_path)
    records_payload = read_json(records_path)
    gazetteer = read_json(gazetteer_path)
    return build_p0_bundle(registry, records_payload, gazetteer)


def build_p0_bundle(registry, records_payload, gazetteer):
    sources = {source["id"]: source for source in registry.get("sources", [])}
    places = load_places(gazetteer)

    accepted = []
    blocked = []
    for record in records_payload.get("records", []):
        source = sources.get(record.get("source_id"), {})
        if is_source_allowed(source):
            accepted.append({**record, "_source": source})
        else:
            blocked.append({**record, "_source": source})

    signals = build_signals(accepted, places)
    map_layers = build_map_layers(signals)
    mainlines = build_mainlines(signals)
    world_states = build_world_states(mainlines, signals)
    worldline_nodes = build_worldline_nodes(mainlines)
    council_results = build_council_results(worldline_nodes)
    reports = build_reports(mainlines, council_results)

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "collection": {
            "accepted_count": len(accepted),
            "blocked_count": len(blocked),
            "blocked_records": [
                {
                    "id": item.get("id"),
                    "source_id": item.get("source_id"),
                    "reason": "source_not_allowed_for_p0",
                }
                for item in blocked
            ],
        },
        "signals": signals,
        "mapLayers": map_layers,
        "mainlines": mainlines,
        "worldStates": world_states,
        "worldlineNodes": worldline_nodes,
        "councilResults": council_results,
        "reports": reports,
    }


def build_signals(records, places):
    buckets = defaultdict(list)
    for record in records:
        place = resolve_place(record, places)
        bucket_key = (place.get("region_id"), _topic_key(record))
        buckets[bucket_key].append((record, place))

    signals = []
    for index, ((region_id, topic_key), items) in enumerate(buckets.items(), start=1):
        records_only = [item[0] for item in items]
        place = items[0][1]
        text = " ".join(merge_record_text(record) for record in records_only)
        tags = extract_tags(text)
        narratives = extract_narratives(text)
        heat = score_heat(_merge_metrics(records_only))
        trust = max(float(record.get("_source", {}).get("trust", 0.5)) for record in records_only)
        credibility = score_fact_credibility(trust, records_only)
        mainline_risk = score_mainline_risk(set(tags), heat, credibility)
        signal_id = f"SIG-P0-{index:03d}"
        signals.append(
            {
                "id": signal_id,
                "caseId": "CASE-P0-001",
                "mainlineId": "ML-P0-001",
                "priority": _priority(mainline_risk),
                "title": _signal_title(topic_key, records_only),
                "summary": _summary(text),
                "source": " / ".join(sorted({record["_source"].get("name", record.get("source_id")) for record in records_only})),
                "sourceType": "multi-source",
                "regionId": region_id,
                "tags": tags,
                "narrativeFrames": narratives,
                "confidence": round(credibility / 100, 2),
                "status": "selected_for_mainline",
                "time": min(record.get("published_at", "") for record in records_only if record.get("published_at")),
                "geo": {
                    "coordinates": [place.get("lon"), place.get("lat")],
                    "featureType": "event-point",
                    "impactRadiusKm": max(1, min(8, int(mainline_risk // 18) + 1)),
                },
                "scores": {
                    "onlineHeat": heat,
                    "factCredibility": credibility,
                    "mainlineRisk": mainline_risk,
                },
                "why": _why(tags, narratives),
                "evidence": [
                    {
                        "source": record["_source"].get("name", record.get("source_id")),
                        "rawId": record.get("id"),
                        "excerpt": _summary(merge_record_text(record), limit=140),
                        "credibility": _credibility_label(float(record["_source"].get("trust", 0.5))),
                    }
                    for record in records_only
                ],
            }
        )
    return sorted(signals, key=lambda item: item["scores"]["mainlineRisk"], reverse=True)


def build_map_layers(signals):
    event_features = []
    heat_features = []
    for signal in signals:
        lon, lat = signal["geo"]["coordinates"]
        score = signal["scores"]["mainlineRisk"]
        event_features.append(
            {
                "type": "Feature",
                "id": signal["id"],
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "featureId": signal["id"],
                    "regionId": signal["regionId"],
                    "featureType": "event-point",
                    "title": signal["title"],
                    "summary": signal["summary"],
                    "mainlineId": signal["mainlineId"],
                    "riskScore": score,
                    "signalCount": len(signal["evidence"]),
                    "source": signal["source"],
                    "time": signal["time"],
                    "confidence": signal["confidence"],
                },
            }
        )
        heat_features.append(
            {
                "type": "Feature",
                "id": f"HEAT-{signal['id']}",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "regionId": signal["regionId"],
                    "weight": score,
                    "radiusKm": signal["geo"]["impactRadiusKm"],
                    "sourceSignalId": signal["id"],
                },
            }
        )
    return {
        "eventPoints": {"type": "FeatureCollection", "features": event_features},
        "heatZones": {"type": "FeatureCollection", "features": heat_features},
    }


def build_mainlines(signals):
    if not signals:
        return []
    support_points = sorted({tag for signal in signals for tag in signal["tags"]})
    evidence_gaps = _evidence_gaps(support_points)
    confidence = round(sum(signal["confidence"] for signal in signals) / len(signals), 2)
    return [
        {
            "id": "ML-P0-001",
            "caseId": "CASE-P0-001",
            "title": "P0 network signal risk mainline",
            "status": "world_state_ready",
            "signals": [signal["id"] for signal in signals],
            "triggerClusters": sorted({frame for signal in signals for frame in signal["narrativeFrames"]}),
            "supportPoints": support_points,
            "evidenceGaps": evidence_gaps,
            "confidence": confidence,
        }
    ]


def build_world_states(mainlines, signals):
    if not mainlines:
        return []
    mainline = mainlines[0]
    top_signal = signals[0]
    return [
        {
            "id": "WS-P0-001",
            "mainlineId": mainline["id"],
            "title": "P0 opinion world state",
            "status": "world_state_ready",
            "inputs": mainline["signals"],
            "currentHeat": top_signal["scores"]["onlineHeat"],
            "factCredibility": top_signal["scores"]["factCredibility"],
            "mainlineRisk": top_signal["scores"]["mainlineRisk"],
            "dominantNarratives": mainline["triggerClusters"],
            "evidenceGaps": mainline["evidenceGaps"],
            "humanConfirmationRequired": True,
        }
    ]


def build_worldline_nodes(mainlines):
    if not mainlines:
        return []
    risk = min(95, int(mainlines[0]["confidence"] * 100))
    return [
        {"id": "NODE-P0-S0", "title": "Signals collected and normalized", "step": 0, "branch": "root", "probability": 100, "risk": max(20, risk - 20)},
        {"id": "NODE-P0-C1", "title": "Response gap keeps narrative rising", "step": 1, "branch": "C", "probability": max(35, risk), "risk": min(95, risk + 18), "needsCouncil": True},
        {"id": "NODE-P0-D1", "title": "Evidence and response tasks reduce uncertainty", "step": 1, "branch": "D", "probability": max(20, 100 - risk), "risk": max(25, risk - 22)},
    ]


def build_council_results(nodes):
    selected = next((node for node in nodes if node.get("needsCouncil")), None)
    if not selected:
        return []
    return [
        {
            "id": "COUNCIL-P0-001",
            "nodeId": selected["id"],
            "status": "ready_to_inject",
            "hypothesis": "If response remains vague while evidence gaps persist, how do stakeholder reactions change?",
            "pivotChanges": [
                {"name": "stakeholder_trust", "delta": -0.14},
                {"name": "evidence_completeness", "delta": -0.08},
                {"name": "online_heat", "delta": 0.16},
                {"name": "offline_attention", "delta": 0.1},
            ],
            "branchChanges": [
                {"branch": "C", "from": max(30, selected["probability"] - 8), "to": selected["probability"]},
                {"branch": "D", "from": 100 - selected["probability"], "to": max(15, 100 - selected["probability"] - 6)},
            ],
            "summary": "Council simulation treats agent output as pressure testing only. It raises the risk path when trust and evidence gaps remain unresolved.",
            "requiresHumanConfirmation": True,
        }
    ]


def build_reports(mainlines, council_results):
    if not mainlines:
        return []
    return [
        {
            "id": "REPORT-P0-001",
            "caseId": "CASE-P0-001",
            "mainlineId": mainlines[0]["id"],
            "finalJudgement": "P0 bundle generated a reviewable mainline, world state, council result, and action tasks. High-risk claims require human confirmation.",
            "tasks": [
                {"id": "TASK-P0-001", "title": "Verify source links and original evidence", "owner": "data-review", "due": "2h", "status": "suggested"},
                {"id": "TASK-P0-002", "title": "Fill evidence gaps before formal reporting", "owner": "analyst", "due": "4h", "status": "suggested"},
                {"id": "TASK-P0-003", "title": "Monitor heat, narrative, and response changes", "owner": "monitoring", "due": "continuous", "status": "suggested"},
            ],
        }
    ]


def _topic_key(record):
    text = merge_record_text(record).lower()
    if "school" in text:
        return "school-accountability"
    if "hospital" in text:
        return "medical-accountability"
    if "worker" in text or "salary" in text:
        return "labor-dispute"
    return "public-risk"


def _merge_metrics(records):
    merged = defaultdict(int)
    for record in records:
        for key, value in (record.get("metrics") or {}).items():
            merged[key] += int(value or 0)
    return merged


def _signal_title(topic_key, records):
    if len(records) == 1:
        return records[0].get("title") or topic_key
    return f"{topic_key} ({len(records)} records)"


def _summary(text, limit=220):
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _priority(score):
    if score >= 80:
        return "P0"
    if score >= 60:
        return "P1"
    return "P2"


def _credibility_label(trust):
    if trust >= 0.8:
        return "A"
    if trust >= 0.6:
        return "B"
    return "C"


def _why(tags, narratives):
    return (
        "The signal is promoted because it combines "
        + ", ".join(tags[:4])
        + " with narrative frames "
        + ", ".join(narratives[:4])
        + "."
    )


def _evidence_gaps(support_points):
    gaps = []
    if "evidence_gap" in support_points:
        gaps.append("original_evidence_chain")
    if "response_gap" in support_points or "trust_break" in support_points:
        gaps.append("official_response_timeline")
    if "offline_gathering" in support_points:
        gaps.append("offline_status_confirmation")
    return gaps or ["human_review_required"]
