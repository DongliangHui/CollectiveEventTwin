from __future__ import annotations

from typing import Any


def p0_fixtures() -> dict[str, Any]:
    return {
        "cases": [
            _expand_campus_case(_campus_case()),
            _expand_community_case(_community_case()),
        ],
        "blocked_sources": [
            {
                "id": "SRC-BLOCKED-001",
                "case_id": "CASE-CAMPUS-001",
                "source_id": "private-group-forward",
                "source_name": "Private group forward",
                "access_mode": "private_chat",
                "status": "active",
                "trust": 0.1,
                "payload": {"note": "Compliance negative fixture; must not enter processing chain."},
            }
        ],
    }


def _campus_case() -> dict[str, Any]:
    case_id = "CASE-CAMPUS-001"
    mainline_id = "ML-001"
    return {
        "case": {
            "id": case_id,
            "slug": "campus-death-high-intensity",
            "title": "Campus death and suspected bullying collective risk",
            "scenario_type": "campus_high_intensity",
            "payload": {
                "boundary": "Risk sensing and coordination only; not an official investigation or legal finding.",
                "golden_node": "NODE-C3",
                "primary_metric": "time_to_confirmed_brief",
            },
        },
        "sources": [
            {
                "id": "SRC-CAMPUS-001",
                "source_id": "local-video-authorized",
                "source_name": "Authorized short-video export",
                "access_mode": "authorized_export",
                "status": "active",
                "trust": 0.72,
            },
            {
                "id": "SRC-CAMPUS-002",
                "source_id": "family-statement-upload",
                "source_name": "Manual family statement upload",
                "access_mode": "manual_upload",
                "status": "active",
                "trust": 0.58,
            },
            {
                "id": "SRC-CAMPUS-003",
                "source_id": "official-response-public",
                "source_name": "Official public response",
                "access_mode": "public_web",
                "status": "active",
                "trust": 0.88,
            },
        ],
        "signals": [
            {
                "id": "SIG-001",
                "title": "Gate video and family gathering spread quickly",
                "summary": "Authorized sample shows family questions, emergency vehicles, and bystander discussion at the campus gate.",
                "priority": "P0",
                "region_id": "campus-core",
                "scores": {"onlineHeat": 86, "factCredibility": 72, "mainlineRisk": 91},
                "tags": ["field-video", "family-gathering", "response-gap"],
            },
            {
                "id": "SIG-012",
                "title": "Family claims prior feedback and bullying context",
                "summary": "Manual statements point to prior feedback and school awareness dispute; context still needs verification.",
                "priority": "P0",
                "region_id": "campus-core",
                "scores": {"onlineHeat": 68, "factCredibility": 58, "mainlineRisk": 82},
                "tags": ["responsibility", "evidence-gap"],
            },
            {
                "id": "SIG-017",
                "title": "Minor identity exposure and online harassment risk rises",
                "summary": "Comments include minor name: Zhang and class 7-3, creating secondary harm risk.",
                "priority": "P0",
                "region_id": "online-spread",
                "scores": {"onlineHeat": 74, "factCredibility": 46, "mainlineRisk": 81},
                "tags": ["minor-privacy", "harassment-risk"],
            },
            {
                "id": "SIG-024",
                "title": "First response is viewed as too vague",
                "summary": "Public response does not explain evidence preservation, family communication, or the next update time.",
                "priority": "P1",
                "region_id": "authority-response",
                "scores": {"onlineHeat": 61, "factCredibility": 88, "mainlineRisk": 73},
                "tags": ["response-credibility", "trust-vacuum"],
            },
        ],
        "evidence": [
            (
                "EVD-001",
                "SIG-001",
                "Authorized gate video segment",
                "Campus gate shows family gathering, crying, and emergency vehicles.",
                "Authorized short-video export",
                "B",
                "propagation",
                "normal",
            ),
            (
                "EVD-012",
                "SIG-012",
                "Family feedback statement",
                "Family says they repeatedly reported bullying and asks for camera footage and communication records.",
                "Manual upload",
                "C",
                "needs_review",
                "normal",
            ),
            (
                "EVD-017",
                "SIG-017",
                "Minor privacy spread screenshot",
                "Comment thread includes minor name: Zhang and class 7-3.",
                "Platform safety sample",
                "B",
                "needs_review",
                "sensitive_person_minor",
            ),
            (
                "EVD-024",
                "SIG-024",
                "First public response",
                "Response says investigation support is ongoing, but omits evidence preservation and next update time.",
                "Official public response",
                "A",
                "confirmed_fact",
                "normal",
            ),
        ],
        "factors": [
            ("RF-CAMPUS-DEATH", "Death or severe harm", "high_sensitivity_fact", 0.92, "confirmed", ["EVD-001"]),
            ("RF-CAMPUS-MINOR", "Minor involved", "sensitive_person", 0.88, "confirmed", ["EVD-017"]),
            ("RF-CAMPUS-GATHERING", "Family on-site gathering", "offline_risk", 0.84, "confirmed", ["EVD-001"]),
            ("RF-CAMPUS-RESPONSE", "Response credibility gap", "response_gap", 0.78, "confirmed", ["EVD-024"]),
            ("RF-CAMPUS-PRIVACY", "Privacy exposure and harassment", "privacy", 0.74, "suggested", ["EVD-017"]),
        ],
        "mainline": {
            "id": mainline_id,
            "title": "Campus accountability narrative and offline escalation risk",
            "confidence": 0.84,
            "status": "world_state_ready",
            "payload": {
                "signals": ["SIG-001", "SIG-012", "SIG-017", "SIG-024"],
                "support_points": [
                    "fact timeline",
                    "responsibility attribution",
                    "emotion ignition",
                    "offline gathering",
                    "minor protection",
                ],
                "evidence_gaps": [
                    "camera and emergency records",
                    "prior family feedback records",
                    "student-group screenshot context",
                    "joint-investigation timeline",
                ],
            },
        },
        "world_state": {"id": "WS-001", "title": "Campus high-intensity event World State", "status": "world_state_ready"},
        "nodes": [
            ("NODE-S0", "Low-visibility campus signal drift", "root", 64, 52, False),
            ("NODE-C3", "Vague response hardens the accountability narrative", "C", 58, 91, True),
            ("NODE-D4", "Evidence preservation and joint investigation compress the trust vacuum", "D", 31, 48, False),
        ],
        "report": {
            "id": "REPORT-001",
            "title": "Campus high-intensity event P0 decision brief",
            "draft_summary": (
                "Branch C is the primary risk path: vague response hardens the accountability narrative. "
                "Mitigation requires evidence preservation, family communication, joint investigation, and privacy protection."
            ),
        },
        "tasks": [
            ("TASK-001", "Fix fact, emergency, and on-site timeline records", "fact-verification", "2h", "in_progress"),
            ("TASK-002", "Preserve cameras, family-school records, and student-group screenshots", "evidence-preservation", "1h", "suggested"),
            ("TASK-004", "Reduce minor name, photo, and class exposure across platforms", "privacy-response", "ongoing", "in_progress"),
        ],
    }


def _community_case() -> dict[str, Any]:
    case_id = "CASE-COMMUNITY-WATER-001"
    return {
        "case": {
            "id": case_id,
            "slug": "community-water-outage-trust-risk",
            "title": "Community water outage response trust risk",
            "scenario_type": "community_public_service",
            "payload": {"boundary": "Smoke fixture for factor-system generalization."},
        },
        "sources": [
            {
                "id": "SRC-WATER-001",
                "source_id": "forum-public",
                "source_name": "Local public forum post",
                "access_mode": "public_web",
                "status": "active",
                "trust": 0.66,
            },
            {
                "id": "SRC-WATER-002",
                "source_id": "manual-call-log",
                "source_name": "Manual hotline summary",
                "access_mode": "manual_upload",
                "status": "active",
                "trust": 0.74,
            },
        ],
        "signals": [
            {
                "id": "SIG-WATER-001",
                "title": "Water outage notice causes concentrated consultation",
                "summary": "Residents question recovery time, repair responsibility, and transparent compensation rules.",
                "priority": "P1",
                "region_id": "community-east",
                "scores": {"onlineHeat": 63, "factCredibility": 76, "mainlineRisk": 72},
                "tags": ["public-service", "trust-risk", "collective-consultation"],
            },
            {
                "id": "SIG-WATER-002",
                "title": "Service providers give inconsistent response windows",
                "summary": "Property office, street office, and utility provider statements differ on timing and responsibility.",
                "priority": "P1",
                "region_id": "community-east",
                "scores": {"onlineHeat": 54, "factCredibility": 70, "mainlineRisk": 67},
                "tags": ["responsibility", "response-gap"],
            },
        ],
        "evidence": [
            (
                "EVD-WATER-001",
                "SIG-WATER-001",
                "Public forum thread",
                "Multiple residents ask about water recovery time and discuss visiting the property office together.",
                "Local public forum post",
                "B",
                "propagation",
                "normal",
            ),
            (
                "EVD-WATER-002",
                "SIG-WATER-002",
                "Manual hotline summary",
                "Hotline record shows inconsistent completion times from property and water provider.",
                "Manual hotline summary",
                "B",
                "needs_review",
                "normal",
            ),
        ],
        "factors": [
            ("RF-WATER-SERVICE", "Public service interruption", "public_service", 0.81, "confirmed", ["EVD-WATER-001"]),
            ("RF-WATER-TRANSPARENCY", "Transparency concern", "trust_break", 0.76, "confirmed", ["EVD-WATER-001"]),
            ("RF-WATER-RESPONSIBILITY", "Unclear responsibility window", "responsibility", 0.72, "suggested", ["EVD-WATER-002"]),
        ],
        "mainline": {
            "id": "ML-WATER-001",
            "title": "Water outage response transparency and resident trust risk",
            "confidence": 0.73,
            "status": "world_state_ready",
            "payload": {
                "signals": ["SIG-WATER-001", "SIG-WATER-002"],
                "support_points": ["service recovery", "responsibility explanation", "resident trust", "offline consultation"],
                "evidence_gaps": ["repair timeline", "responsible entity statement", "next update time"],
            },
        },
        "world_state": {"id": "WS-WATER-001", "title": "Community water outage trust-risk World State", "status": "world_state_ready"},
        "nodes": [
            ("NODE-WATER-S0", "Residents gather consultation threads online", "root", 70, 45, False),
            ("NODE-WATER-C1", "Inconsistent response window increases group consultation", "C", 46, 72, True),
            ("NODE-WATER-D1", "Clear timeline and responsibility window reduce distrust", "D", 42, 38, False),
        ],
        "report": {
            "id": "REPORT-WATER-001",
            "title": "Community water outage trust-risk P0 decision brief",
            "draft_summary": (
                "The main risk is not the outage itself, but the inconsistent repair window and responsibility explanation. "
                "A single update channel and repair timeline are required."
            ),
        },
        "tasks": [
            ("TASK-WATER-001", "Verify repair completion timeline and publish one response window", "street-coordination", "2h", "suggested"),
            ("TASK-WATER-002", "Create joint Q&A channel for property and water provider", "public-service-liaison", "4h", "suggested"),
            ("TASK-WATER-003", "Monitor forum and hotline for group consultation signals", "monitoring", "ongoing", "suggested"),
        ],
    }


def _expand_campus_case(case: dict[str, Any]) -> dict[str, Any]:
    case["case"].setdefault("payload", {})["pages"] = _campus_pages()

    for index in range(4, 38):
        case["sources"].append(
            {
                "id": f"SRC-CAMPUS-{index:03d}",
                "source_id": f"campus-public-feed-{index:03d}",
                "source_name": f"Campus authorized public feed {index:03d}",
                "access_mode": "public_web" if index % 3 else "authorized_export",
                "status": "active",
                "trust": round(0.55 + (index % 9) * 0.04, 2),
                "payload": {"channel": ["short-video", "local-forum", "official", "field-note"][index % 4]},
            }
        )

    region_cycle = ["campus-core", "online-spread", "authority-response"]
    tag_cycle = [
        ["field-video", "response-gap"],
        ["family-gathering", "evidence-gap"],
        ["minor-privacy", "harassment-risk"],
        ["response-credibility", "trust-vacuum"],
    ]
    for index in range(1, 39):
        case["signals"].append(
            {
                "id": f"SIG-AUX-{index:03d}",
                "title": f"Campus supporting signal {index:03d}",
                "summary": "Supporting campus signal for topic heat, evidence review, mainline construction, and worldline projection.",
                "priority": "P0" if index <= 12 else "P1",
                "region_id": region_cycle[index % len(region_cycle)],
                "scores": {
                    "onlineHeat": 52 + (index * 7) % 43,
                    "factCredibility": 48 + (index * 5) % 45,
                    "mainlineRisk": 57 + (index * 3) % 39,
                },
                "tags": tag_cycle[index % len(tag_cycle)],
                "status": "selected_for_mainline" if index <= 7 else "needs_review",
            }
        )

    signal_ids = [signal["id"] for signal in case["signals"]]
    for index in range(1, 65):
        signal_id = signal_ids[index % len(signal_ids)]
        sensitive = index % 17 == 0
        case["evidence"].append(
            (
                f"EVD-AUX-{index:03d}",
                signal_id,
                f"Supporting evidence item {index:03d}",
                (
                    "Masked sensitive supporting excerpt for a minor-related discussion."
                    if sensitive
                    else f"Supporting excerpt {index:03d} links public signal, timeline, source credibility, and review status."
                ),
                "Authorized P0 evidence seed",
                ["A", "B", "C"][index % 3],
                "needs_review" if index % 4 else "confirmed_fact",
                "sensitive_person_minor" if sensitive else "normal",
            )
        )

    factor_templates = [
        ("FACT-TIMELINE", "Fact timeline uncertainty", "evidence_gap"),
        ("FAMILY-COMM", "Family communication window", "response_gap"),
        ("PRIVACY-SPREAD", "Privacy leakage spread", "privacy"),
        ("FIELD-ORDER", "Field order pressure", "offline_risk"),
        ("MEDIA-AMPLIFY", "Local media amplification", "propagation"),
        ("TRUST-VACUUM", "Trust vacuum", "trust_break"),
    ]
    for index in range(1, 19):
        suffix, name, category = factor_templates[index % len(factor_templates)]
        case["factors"].append((f"RF-CAMPUS-{suffix}-{index:02d}", name, category, round(0.55 + (index % 8) * 0.05, 2), "suggested", [case["evidence"][index % len(case["evidence"])][0]]))

    primary = case["mainline"]
    case["mainlines"] = [primary]
    mainline_titles = [
        "现场视频扩散与回应缺口主线",
        "证据保全与责任争议主线",
        "隐私外泄与不实搬运主线",
        "家属沟通窗口与信任修复主线",
        "线下秩序与平台处置主线",
        "联合调查节奏与下一次通报主线",
    ]
    for index, title in enumerate(mainline_titles, start=2):
        case["mainlines"].append(
            {
                "id": f"ML-CAMPUS-{index:03d}",
                "title": title,
                "confidence": round(0.61 + index * 0.03, 2),
                "status": "confirmed" if index == 2 else "draft",
                "payload": {
                    "signals": [signal["id"] for signal in case["signals"][index : index + 7]],
                    "support_points": ["事实时间线", "证据保全", "回应可信度", "隐私保护", "线下秩序"],
                    "evidence_gaps": ["监控连续轨迹", "家属核验时间表", "证据保全清单"],
                },
            }
        )

    case["nodes"].extend(
        [
            ("NODE-A1", "Evidence list and family verification window reduce heat", "A", 41, 39, False),
            ("NODE-B2", "Low-intensity dispute continues around investigation boundary", "B", 28, 56, False),
            ("NODE-C4", "Privacy leakage and vague response create secondary rise", "C", 21, 87, True),
            ("NODE-D5", "External attention increases tail risk", "D", 10, 72, False),
        ]
    )
    case["tasks"].extend(
        [
            ("TASK-005", "Publish evidence preservation checklist", "joint-investigation", "2h", "suggested"),
            ("TASK-006", "Open family verification appointment window", "family-liaison", "4h", "suggested"),
            ("TASK-007", "Run platform privacy suppression checklist", "platform-safety", "ongoing", "in_progress"),
            ("TASK-008", "Prepare next response time and scope", "communications", "2h", "suggested"),
        ]
    )
    return case


def _expand_community_case(case: dict[str, Any]) -> dict[str, Any]:
    case["case"].setdefault("payload", {})["pages"] = _community_pages()
    for index in range(3, 11):
        case["sources"].append(
            {
                "id": f"SRC-WATER-{index:03d}",
                "source_id": f"community-public-feed-{index:03d}",
                "source_name": f"Community service public feed {index:03d}",
                "access_mode": "public_web" if index % 2 else "manual_upload",
                "status": "active",
                "trust": round(0.58 + (index % 5) * 0.05, 2),
            }
        )
    for index in range(3, 13):
        case["signals"].append(
            {
                "id": f"SIG-WATER-{index:03d}",
                "title": f"Water service response signal {index:03d}",
                "summary": "Resident consultation, repair timeline, responsibility explanation, and response-window signal.",
                "priority": "P1",
                "region_id": "community-east",
                "scores": {"onlineHeat": 42 + index * 3, "factCredibility": 62 + index, "mainlineRisk": 51 + index * 2},
                "tags": ["public-service", "trust-risk", "response-gap"],
                "status": "needs_review",
            }
        )
    signal_ids = [signal["id"] for signal in case["signals"]]
    for index in range(3, 15):
        case["evidence"].append(
            (
                f"EVD-WATER-{index:03d}",
                signal_ids[index % len(signal_ids)],
                f"Water service evidence {index:03d}",
                "Public service evidence links repair progress, resident questions, and response consistency.",
                "Community public feed",
                "B",
                "needs_review" if index % 3 else "confirmed_fact",
                "normal",
            )
        )
    for index in range(4, 9):
        case["factors"].append((f"RF-WATER-AUX-{index:02d}", f"Community trust factor {index}", "trust_break", round(0.55 + index * 0.03, 2), "suggested", [case["evidence"][index % len(case["evidence"])][0]]))
    primary = case["mainline"]
    case["mainlines"] = [
        primary,
        {
            "id": "ML-WATER-002",
            "title": "Repair timeline and unified response channel",
            "confidence": 0.68,
            "status": "draft",
            "payload": {"signals": [signal["id"] for signal in case["signals"][:5]], "support_points": ["repair timeline", "single response channel"], "evidence_gaps": ["provider repair record"]},
        },
        {
            "id": "ML-WATER-003",
            "title": "Resident consultation pressure and trust recovery",
            "confidence": 0.64,
            "status": "draft",
            "payload": {"signals": [signal["id"] for signal in case["signals"][4:9]], "support_points": ["resident trust", "field consultation"], "evidence_gaps": ["next update time"]},
        },
    ]
    case["nodes"].extend(
        [
            ("NODE-WATER-A1", "Unified update channel reduces consultation pressure", "A", 38, 31, False),
            ("NODE-WATER-B1", "Repair delay creates low-intensity repeated questions", "B", 24, 52, False),
        ]
    )
    return case


def _campus_pages() -> dict[str, Any]:
    return {
        "city": {"discussion_count": "28,560", "video_count": 236, "layers": ["热点事件", "升温事件", "视频/直播事件", "我关注的"]},
        "risk": {
            "spread_speed": "+16%",
            "phases": ["萌芽出现", "小范围讨论", "同城讨论升温", "跨圈层扩散", "持续发酵"],
            "path": ["现场视频", "家属诉求", "同城平台", "学生群截图", "本地媒体", "政务回应"],
        },
        "brief": {
            "data_count": 128,
            "evidence_count": 68,
            "documents": ["世界线推演结果报告 PDF", "多方主体研判纪要 PDF", "处置建议单 DOCX", "世界线简报 PPTX"],
            "watch": ["校门口聚集人数变化", "证据保全关键词热度", "隐私外泄内容处置量", "家属信任", "信息透明度", "线下聚集风险"],
        },
        "memory": {
            "compare": ["预测主路径 A线 40%", "实际路径 A/B 之间", "命中度 0.74", "偏差类型 低估拉锯"],
            "path": ["现场视频", "家属诉求", "情绪聚合", "跨平台搬运", "核验窗口缓释"],
            "templates": ["现场视频 + 证据缺口", "评论集中追问监控/时间线", "同城占比超过 70%", "未成年人隐私二次搬运"],
        },
        "library": {
            "taxonomy": ["公共服务", "学校/回应/窗口", "交通出行", "社区治理", "城市管理", "舆情热点"],
            "cases": ["校园坠楼事件回应与同城情绪升温", "校园通报边界与家长负向评论", "道路施工噪声引发社区讨论"],
            "patterns": ["事实缺口 -> 责任叙事固化", "阶段回应可缓释，但需核验窗口", "高热切片不等于完整事实"],
        },
        "config": {
            "params": ["破圈概率阈值 0.58", "同城占比阈值 70%", "情绪升温窗口 30min", "高影响人工确认 开启"],
            "weights": ["短视频传播强度 0.22", "同城评论占比 0.18", "官方回应覆盖度 0.16", "历史相似命中 0.14"],
            "safety": ["高风险结论必须人工确认", "未成年人信息默认脱敏", "私域来源不可进入处理链"],
            "changes": ["v2.4.1 生产", "v2.4.2 待发布", "v2.5.0 草稿"],
        },
    }


def _community_pages() -> dict[str, Any]:
    return {
        "city": {"discussion_count": "4,860", "video_count": 18, "layers": ["公共服务", "居民咨询", "维修进度", "热线反馈"]},
        "risk": {"spread_speed": "+7%", "phases": ["居民咨询", "社区讨论", "责任窗口不一致", "统一回应"], "path": ["停水通知", "居民追问", "物业窗口", "供水单位", "街道协调"]},
        "brief": {"data_count": 42, "evidence_count": 14, "documents": ["社区服务响应简报 PDF", "责任窗口说明 DOCX"], "watch": ["恢复供水时间", "热线重复咨询", "物业窗口反馈", "居民信任"]},
        "memory": {"compare": ["预测主路径 B线", "实际路径 低烈度拉锯", "命中度 0.69"], "path": ["停水通知", "居民咨询", "联合回应"], "templates": ["公共服务中断 + 回应窗口不一致"]},
        "library": {"taxonomy": ["公共服务", "社区治理", "物业服务"], "cases": ["物业停水争议与社区投诉聚合", "地铁延误解释不足引发持续追问"], "patterns": ["单一回应窗口降低重复咨询"]},
        "config": {"params": ["服务恢复阈值 2h", "重复咨询阈值 30条"], "weights": ["热线重复咨询 0.18", "物业回应一致性 0.16"], "safety": ["不指向个人责任", "公开来源优先"]},
    }
