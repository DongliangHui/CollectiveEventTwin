from __future__ import annotations

from typing import Any


def p0_fixtures() -> dict[str, Any]:
    return {
        "cases": [
            _campus_case(),
            _community_case(),
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
            "title": "校园坠亡与疑似欺凌引发线下聚集风险",
            "scenario_type": "campus_high_intensity",
            "payload": {
                "boundary": "Supports risk sensing and coordination only; it does not replace official investigation or legal findings.",
                "golden_node": "NODE-C3",
            },
        },
        "sources": [
            {"id": "SRC-CAMPUS-001", "source_id": "local-video-authorized", "source_name": "同城短视频授权样例", "access_mode": "authorized_export", "status": "active", "trust": 0.72},
            {"id": "SRC-CAMPUS-002", "source_id": "family-statement-upload", "source_name": "家属陈述人工上传", "access_mode": "manual_upload", "status": "active", "trust": 0.58},
            {"id": "SRC-CAMPUS-003", "source_id": "official-response-public", "source_name": "校方公开回应", "access_mode": "public_web", "status": "active", "trust": 0.88},
        ],
        "signals": [
            {
                "id": "SIG-001",
                "title": "校门口现场视频与家属聚集快速扩散",
                "summary": "授权样例显示校门口哭喊、警车、家属质问和围观画面，评论集中追问学校是否隐瞒。",
                "priority": "P0",
                "region_id": "campus-core",
                "scores": {"onlineHeat": 86, "factCredibility": 72, "mainlineRisk": 91},
                "tags": ["现场视频", "家属聚集", "回应缺口"],
            },
            {
                "id": "SIG-012",
                "title": "家属称此前已反馈且学生群出现欺凌说法",
                "summary": "家属陈述和学生群截图指向此前反馈与学校知情争议，但上下文仍需核验。",
                "priority": "P0",
                "region_id": "campus-core",
                "scores": {"onlineHeat": 68, "factCredibility": 58, "mainlineRisk": 82},
                "tags": ["责任归因", "证据缺口"],
            },
            {
                "id": "SIG-017",
                "title": "疑似涉事学生身份传播与网暴风险上升",
                "summary": "评论区出现 minor name: Zhang and class 7-3 等未成年人隐私线索，平台传播可能造成二次伤害。",
                "priority": "P0",
                "region_id": "online-spread",
                "scores": {"onlineHeat": 74, "factCredibility": 46, "mainlineRisk": 81},
                "tags": ["未成年人隐私", "网暴风险"],
            },
            {
                "id": "SIG-024",
                "title": "首轮回应被质疑过于笼统",
                "summary": "公开回应没有说明证据保全、家属沟通机制和下一次更新时间。",
                "priority": "P1",
                "region_id": "authority-response",
                "scores": {"onlineHeat": 61, "factCredibility": 88, "mainlineRisk": 73},
                "tags": ["回应可信度", "信任真空"],
            },
        ],
        "evidence": [
            ("EVD-001", "SIG-001", "同城短视频片段", "校门口出现家属聚集、哭喊和警车画面。", "同城短视频授权样例", "B", "propagation", "normal"),
            ("EVD-012", "SIG-012", "家属反馈陈述", "家属称曾多次反馈孩子被欺负，希望调取监控与沟通记录。", "人工上传", "C", "needs_review", "normal"),
            ("EVD-017", "SIG-017", "未成年人隐私扩散截图", "评论区出现 minor name: Zhang and class 7-3 等信息。", "平台风控样例", "B", "needs_review", "sensitive_person_minor"),
            ("EVD-024", "SIG-024", "首轮公开回应", "回应提到配合调查，但没有说明证据保全和后续更新时间。", "公开回应", "A", "confirmed_fact", "normal"),
        ],
        "factors": [
            ("RF-CAMPUS-DEATH", "死亡/高敏事实", "high_sensitivity_fact", 0.92, "confirmed", ["EVD-001"]),
            ("RF-CAMPUS-MINOR", "未成年人", "sensitive_person", 0.88, "confirmed", ["EVD-017"]),
            ("RF-CAMPUS-GATHERING", "家属到场与线下聚集", "offline_risk", 0.84, "confirmed", ["EVD-001"]),
            ("RF-CAMPUS-RESPONSE", "回应可信度缺口", "response_gap", 0.78, "confirmed", ["EVD-024"]),
            ("RF-CAMPUS-PRIVACY", "隐私曝光和网暴", "privacy", 0.74, "suggested", ["EVD-017"]),
        ],
        "mainline": {
            "id": mainline_id,
            "title": "校园死亡事件事实责任与线下风险主线",
            "confidence": 0.84,
            "status": "world_state_ready",
            "payload": {
                "signals": ["SIG-001", "SIG-012", "SIG-017", "SIG-024"],
                "support_points": ["事实主线", "责任归因", "情绪爆燃", "线下聚集", "未成年人保护"],
                "evidence_gaps": ["监控与报警记录", "家长此前反馈记录", "学生群截图上下文", "联合调查组时间表"],
            },
        },
        "world_state": {"id": "WS-001", "title": "校园死亡高烈度事件 World State", "status": "world_state_ready"},
        "nodes": [
            ("NODE-S0", "校内低可见信号流动", "root", 64, 52, False),
            ("NODE-C3", "回应不足导致责任叙事固化", "C", 58, 91, True),
            ("NODE-D4", "证据保全与联合调查压缩信任真空", "D", 31, 48, False),
        ],
        "agents": ["家属与亲属共同体", "校方", "学生群体", "教育主管与属地部门", "公众与媒体/KOL"],
        "report": {
            "id": "REPORT-001",
            "title": "校园高烈度事件 P0 决策简报",
            "draft_summary": "C 线“回应不足导致责任叙事固化”是主要风险路径，必须用证据保全、家属沟通、联合调查和隐私保护压缩信任真空。",
        },
        "tasks": [
            ("TASK-001", "固定死亡事实、报警记录、抢救记录与现场时间线", "事实核验组", "2h 内", "in_progress"),
            ("TASK-002", "封存监控、家校沟通记录、学生群截图和投诉记录", "证据保全组", "1h 内", "suggested"),
            ("TASK-004", "清理未成年人姓名、照片、班级等隐私扩散内容", "网信与平台协同组", "持续", "in_progress"),
        ],
    }


def _community_case() -> dict[str, Any]:
    case_id = "CASE-COMMUNITY-WATER-001"
    return {
        "case": {
            "id": case_id,
            "slug": "community-water-outage-trust-risk",
            "title": "社区停水维修解释不足引发信任风险",
            "scenario_type": "community_public_service",
            "payload": {"boundary": "Smoke fixture for factor-system generalization."},
        },
        "sources": [
            {"id": "SRC-WATER-001", "source_id": "forum-public", "source_name": "本地论坛公开帖", "access_mode": "public_web", "status": "active", "trust": 0.66},
            {"id": "SRC-WATER-002", "source_id": "manual-call-log", "source_name": "居民热线人工整理", "access_mode": "manual_upload", "status": "active", "trust": 0.74},
        ],
        "signals": [
            {
                "id": "SIG-WATER-001",
                "title": "停水维修公告解释不足引发集中咨询",
                "summary": "居民质疑停水时间、抢修责任和补偿机制不透明，公开论坛出现集体咨询组织迹象。",
                "priority": "P1",
                "region_id": "community-east",
                "scores": {"onlineHeat": 63, "factCredibility": 76, "mainlineRisk": 72},
                "tags": ["民生服务中断", "质疑不透明", "集体咨询"],
            },
            {
                "id": "SIG-WATER-002",
                "title": "物业与供水单位回应口径不一致",
                "summary": "物业、街道和供水单位公开说明存在时间差，居民将问题归因为责任不清。",
                "priority": "P1",
                "region_id": "community-east",
                "scores": {"onlineHeat": 54, "factCredibility": 70, "mainlineRisk": 67},
                "tags": ["责任归因", "回应不足"],
            },
        ],
        "evidence": [
            ("EVD-WATER-001", "SIG-WATER-001", "公开论坛帖子", "多名居民询问停水恢复时间，并讨论是否集中到物业咨询。", "本地论坛公开帖", "B", "propagation", "normal"),
            ("EVD-WATER-002", "SIG-WATER-002", "热线人工整理", "热线记录显示物业和供水单位对抢修完成时间说法不一致。", "居民热线人工整理", "B", "needs_review", "normal"),
        ],
        "factors": [
            ("RF-WATER-SERVICE", "民生服务中断", "public_service", 0.81, "confirmed", ["EVD-WATER-001"]),
            ("RF-WATER-TRANSPARENCY", "质疑不透明", "trust_break", 0.76, "confirmed", ["EVD-WATER-001"]),
            ("RF-WATER-RESPONSIBILITY", "责任归因到物业/街道/供水单位", "responsibility", 0.72, "suggested", ["EVD-WATER-002"]),
        ],
        "mainline": {
            "id": "ML-WATER-001",
            "title": "停水响应不透明与居民信任风险主线",
            "confidence": 0.73,
            "status": "world_state_ready",
            "payload": {
                "signals": ["SIG-WATER-001", "SIG-WATER-002"],
                "support_points": ["服务恢复", "责任解释", "居民信任", "线下咨询"],
                "evidence_gaps": ["抢修时间表", "责任主体说明", "下一次更新时间"],
            },
        },
        "world_state": {"id": "WS-WATER-001", "title": "社区停水信任风险 World State", "status": "world_state_ready"},
        "nodes": [
            ("NODE-WATER-S0", "居民咨询在线上聚集", "root", 70, 45, False),
            ("NODE-WATER-C1", "回应口径不一致导致集体咨询升级", "C", 46, 72, True),
            ("NODE-WATER-D1", "明确维修时间表和责任窗口降低不信任", "D", 42, 38, False),
        ],
        "agents": ["居民", "物业或服务单位", "街道/属地", "供水单位", "本地公众/媒体"],
        "report": {
            "id": "REPORT-WATER-001",
            "title": "社区停水信任风险 P0 决策简报",
            "draft_summary": "当前主要风险不是停水事实本身，而是维修时间和责任窗口不一致造成居民信任下降。",
        },
        "tasks": [
            ("TASK-WATER-001", "核实抢修完成时间并形成统一说明", "街道协调组", "2h 内", "suggested"),
            ("TASK-WATER-002", "建立物业与供水单位联合答疑窗口", "公共服务联络组", "4h 内", "suggested"),
            ("TASK-WATER-003", "监测论坛和热线中的集体咨询组织迹象", "值班监测组", "持续", "suggested"),
        ],
    }

