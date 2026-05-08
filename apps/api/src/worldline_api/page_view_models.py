from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .models import Case, CouncilSession, Evidence, Mainline, Report, RiskFactor, Signal, SourceRecord, Task, WorldState, WorldlineNode

PAGE_IDS = {
    "city",
    "risk",
    "data",
    "evidence",
    "mainline",
    "worldline",
    "council",
    "brief",
    "memory",
    "library",
    "config",
}

PAGE_TITLES = {
    "city": "城市态势感知",
    "risk": "主题态势驾驶舱",
    "data": "数据 / 信号检索工作台",
    "evidence": "风险事件详情与证据复核",
    "mainline": "主线建模确认",
    "worldline": "平行世界推演观察器",
    "council": "多主体研判",
    "brief": "推演完成汇报",
    "memory": "复盘知识沉淀",
    "library": "主题 / 案例库",
    "config": "数据源与模型配置",
}


def build_page_view(bundle: dict[str, Any], page: str, mainlines: list[Mainline]) -> dict[str, Any]:
    if page not in PAGE_IDS:
        raise HTTPException(status_code=404, detail=f"page {page} not found")

    case: Case = bundle["case"]
    sources: list[SourceRecord] = bundle["source_records"]
    signals: list[Signal] = bundle["signals"]
    evidence: list[Evidence] = bundle["evidence"]
    factors: list[RiskFactor] = bundle["risk_factors"]
    world_state: WorldState | None = bundle["world_state"]
    nodes: list[WorldlineNode] = bundle["worldline_nodes"]
    council_sessions: list[CouncilSession] = bundle["council_sessions"]
    report: Report | None = bundle["report"]
    tasks: list[Task] = bundle["tasks"]
    pages = case.payload.get("pages", {})
    page_payload = pages.get(page, {})
    scenario = _scenario(case)
    active_mainline = mainlines[0] if mainlines else bundle.get("mainline")
    latest_council = council_sessions[-1] if council_sessions else None

    common_raw = {
        "case": _case(case),
        "active_mainline": _mainline_item(active_mainline) if active_mainline else None,
        "latest_council": _council_session(latest_council) if latest_council else None,
        "report": _report(report) if report else None,
        "tasks": [_task(task) for task in tasks],
        "counts": {
            "sources": len(sources),
            "accepted_sources": len([source for source in sources if source.accepted]),
            "signals": len(signals),
            "evidence": len(evidence),
            "risk_factors": len(factors),
            "mainlines": len(mainlines),
            "nodes": len(nodes),
            "tasks": len(tasks),
        },
    }

    builders = {
        "city": lambda: _city(case, sources, signals, pages),
        "risk": lambda: _risk(case, sources, signals, evidence, factors, mainlines, pages),
        "data": lambda: _data(signals, evidence, active_mainline, pages),
        "evidence": lambda: _evidence(case, evidence, factors, pages),
        "mainline": lambda: _mainline(signals, evidence, factors, mainlines, active_mainline, pages),
        "worldline": lambda: _worldline(case, world_state, nodes, latest_council, pages),
        "council": lambda: _council(case, nodes, evidence, latest_council, pages),
        "brief": lambda: _brief(case, report, tasks, latest_council, nodes, pages),
        "memory": lambda: _memory(case, report, tasks, pages),
        "library": lambda: _library(case, pages),
        "config": lambda: _config(case, sources, pages),
    }
    built = builders[page]()
    return {
        "case_id": case.id,
        "page": page,
        "title": PAGE_TITLES[page],
        "subtitle": page_payload.get("subtitle", scenario["subtitle"]),
        "nav": _nav(case.id),
        "metrics": built["metrics"],
        "sections": built["sections"],
        "actions": built.get("actions", []),
        "raw": {**common_raw, **built.get("raw", {})},
    }


def _city(case: Case, sources: list[SourceRecord], signals: list[Signal], pages: dict[str, Any]) -> dict[str, Any]:
    accepted = [source for source in sources if source.accepted]
    hot_signals = sorted(signals, key=lambda signal: signal.scores.get("onlineHeat", 0), reverse=True)[:8]
    return {
        "metrics": [
            {"label": "数据源在线", "value": f"{len(accepted)}/{len(sources)}", "tone": "blue"},
            {"label": "当前热度", "value": max([s.scores.get("onlineHeat", 0) for s in signals] or [0]), "tone": "red"},
            {"label": "同城讨论", "value": pages.get("city", {}).get("discussion_count", "28,560"), "tone": "green"},
            {"label": "视频/直播", "value": pages.get("city", {}).get("video_count", 236), "tone": "amber"},
        ],
        "sections": [
            {"id": "map", "title": "城市事件热力雷达", "kind": "map", "items": [_signal(signal) for signal in hot_signals]},
            {"id": "layers", "title": "图层控制", "kind": "chips", "items": pages.get("city", {}).get("layers", ["热点事件", "升温事件", "视频/直播事件", "我关注的"])},
            {"id": "hot", "title": "当前热度榜（实时）", "kind": "signals", "items": [_signal(signal) for signal in hot_signals]},
            {"id": "source-status", "title": "数据源状态", "kind": "sources", "items": [_source(source) for source in sources[:12]]},
        ],
        "raw": {"city": pages.get("city", {})},
    }


def _risk(case: Case, sources: list[SourceRecord], signals: list[Signal], evidence: list[Evidence], factors: list[RiskFactor], mainlines: list[Mainline], pages: dict[str, Any]) -> dict[str, Any]:
    selected = sorted(signals, key=lambda signal: signal.scores.get("mainlineRisk", 0), reverse=True)
    return {
        "metrics": [
            {"label": "主题热度", "value": max([s.scores.get("onlineHeat", 0) for s in signals] or [0]), "tone": "red"},
            {"label": "传播速度", "value": pages.get("risk", {}).get("spread_speed", "+16%"), "tone": "amber"},
            {"label": "可信来源", "value": len([source for source in sources if source.accepted]), "tone": "blue"},
            {"label": "待复核信号", "value": len([item for item in evidence if item.status != "confirmed_fact"]), "tone": "green"},
        ],
        "sections": [
            {"id": "sources", "title": "主题信号来源", "kind": "sources", "items": [_source(source) for source in sources[:10]]},
            {"id": "phase", "title": "主题传播阶段判断", "kind": "timeline", "items": pages.get("risk", {}).get("phases", ["萌芽出现", "小范围讨论", "同城讨论升温", "跨圈层扩散"])},
            {"id": "map", "title": "传播路径与扩散地图", "kind": "graph", "items": pages.get("risk", {}).get("path", ["现场视频", "家属诉求", "同城平台", "政务回应"])},
            {"id": "sentiment", "title": "同城情绪与立场", "kind": "sentiment", "items": pages.get("risk", {}).get("sentiment", [{"label": "负向/不满", "value": 62}, {"label": "中立/观望", "value": 26}, {"label": "支持/理解", "value": 9}])},
            {"id": "candidates", "title": "候选主线", "kind": "mainlines", "items": [_mainline_item(item) for item in mainlines]},
            {"id": "review", "title": "需要复核的信号", "kind": "signals", "items": [_signal(signal) for signal in selected[:8]]},
            {"id": "variables", "title": "需要关注的关键变量", "kind": "factors", "items": [_factor(factor) for factor in factors[:8]]},
        ],
        "actions": [{"id": "enter-mainline", "label": "进入主线建模", "to_page": "mainline"}, {"id": "review-evidence", "label": "转入证据复核", "to_page": "evidence"}],
    }


def _data(signals: list[Signal], evidence: list[Evidence], mainline: Mainline | None, pages: dict[str, Any]) -> dict[str, Any]:
    selected_ids = set((mainline.payload if mainline else {}).get("signals", []))
    selected = [signal for signal in signals if signal.id in selected_ids]
    return {
        "metrics": [
            {"label": "候选数据", "value": len(signals), "tone": "blue"},
            {"label": "已选数据", "value": len(selected), "tone": "green"},
            {"label": "支撑证据", "value": len(evidence), "tone": "amber"},
            {"label": "证据缺口", "value": len((mainline.payload if mainline else {}).get("evidence_gaps", [])), "tone": "red"},
        ],
        "sections": [
            {"id": "filters", "title": "数据源与条件筛选", "kind": "filters", "items": pages.get("data", {}).get("filters", ["当前：全部接口", "优先级", "区域", "标签", "可信度"])},
            {"id": "signals", "title": "数据 / 信号检索工作台", "kind": "signal-table", "items": [_signal(signal) for signal in signals]},
            {"id": "draft", "title": "当前主线草稿包", "kind": "draft", "items": [_signal(signal) for signal in selected], "meta": _mainline_item(mainline) if mainline else None},
            {"id": "detail", "title": "选中数据详情", "kind": "detail", "items": [_evidence_item(item) for item in evidence[:8]]},
            {"id": "recommend", "title": "相关数据推荐", "kind": "signals", "items": [_signal(signal) for signal in signals[:6]]},
        ],
    }


def _evidence(case: Case, evidence: list[Evidence], factors: list[RiskFactor], pages: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": [
            {"label": "证据总量", "value": len(evidence), "tone": "blue"},
            {"label": "已确认", "value": len([item for item in evidence if item.status == "confirmed_fact"]), "tone": "green"},
            {"label": "待复核", "value": len([item for item in evidence if item.status != "confirmed_fact"]), "tone": "amber"},
            {"label": "敏感证据", "value": len([item for item in evidence if item.sensitivity != "normal"]), "tone": "red"},
        ],
        "sections": [
            {"id": "overview", "title": "事件概览", "kind": "facts", "items": pages.get("evidence", {}).get("overview", [_scenario(case)["summary"]])},
            {"id": "timeline", "title": "事件时间线", "kind": "timeline", "items": pages.get("evidence", {}).get("timeline", ["09:12 现场信号出现", "10:20 首次回应", "11:32 进入复核"])},
            {"id": "chain", "title": "证据链", "kind": "evidence", "items": [_evidence_item(item) for item in evidence]},
            {"id": "score", "title": "风险评分", "kind": "factors", "items": [_factor(factor) for factor in factors]},
            {"id": "review", "title": "人工复核", "kind": "actions", "items": [{"label": "确认并进入推演"}, {"label": "调整风险等级"}, {"label": "退回观察"}]},
        ],
    }


def _mainline(signals: list[Signal], evidence: list[Evidence], factors: list[RiskFactor], mainlines: list[Mainline], active: Mainline | None, pages: dict[str, Any]) -> dict[str, Any]:
    payload = active.payload if active else {}
    return {
        "metrics": [
            {"label": "输入数据包", "value": len(signals), "tone": "blue"},
            {"label": "候选主线", "value": len(mainlines), "tone": "green"},
            {"label": "证据缺口", "value": len(payload.get("evidence_gaps", [])), "tone": "red"},
            {"label": "建模完成度", "value": f"{round((active.confidence if active else 0) * 100)}%", "tone": "amber"},
        ],
        "sections": [
            {"id": "clusters", "title": "信号簇识别", "kind": "factors", "items": [_factor(factor) for factor in factors[:8]]},
            {"id": "candidates", "title": "候选主线池", "kind": "mainlines", "items": [_mainline_item(item) for item in mainlines]},
            {"id": "graph", "title": "主线结构图谱画布", "kind": "graph", "items": payload.get("support_points", [])},
            {"id": "evidence", "title": "主线解释", "kind": "evidence", "items": [_evidence_item(item) for item in evidence[:10]]},
            {"id": "gaps", "title": "证据缺口与人工确认项", "kind": "chips", "items": payload.get("evidence_gaps", [])},
        ],
        "actions": [{"id": "confirm-mainline", "label": "确认主线并生成推演输入", "object_id": active.id if active else None}],
        "raw": {"active_mainline": _mainline_item(active) if active else None, "mainline_controls": pages.get("mainline", {})},
    }


def _worldline(case: Case, state: WorldState | None, nodes: list[WorldlineNode], council: CouncilSession | None, pages: dict[str, Any]) -> dict[str, Any]:
    current = next((node for node in nodes if node.payload.get("needsCouncil")), nodes[0] if nodes else None)
    return {
        "metrics": [
            {"label": "节点总数", "value": len(nodes), "tone": "blue"},
            {"label": "当前风险", "value": current.risk if current else 0, "tone": "red"},
            {"label": "当前概率", "value": f"{current.probability if current else 0}%", "tone": "amber"},
            {"label": "研判状态", "value": council.status if council else "未运行", "tone": "green"},
        ],
        "sections": [
            {"id": "state", "title": "世界状态输入包", "kind": "facts", "items": [_world_state(state)] if state else []},
            {"id": "nodes", "title": "24-72h 世界线分支", "kind": "nodes", "items": [_node(node) for node in nodes]},
            {"id": "current", "title": "当前选中 / Current node", "kind": "detail", "items": [_node(current)] if current else []},
            {"id": "council", "title": "多主体研判 Beta", "kind": "council", "items": _council_agents(case, council, pages)},
            {"id": "next", "title": "下一步动作", "kind": "actions", "items": [{"label": "启动多主体研判"}, {"label": "仅作为普通假设继续推演"}]},
        ],
        "raw": {"current_node": _node(current) if current else None},
    }


def _council(case: Case, nodes: list[WorldlineNode], evidence: list[Evidence], council: CouncilSession | None, pages: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": [
            {"label": "研判轮次", "value": len(council.payload.get("rounds", [1])) if council else 1, "tone": "blue"},
            {"label": "参与主体", "value": len(_council_agents(case, council, pages)), "tone": "green"},
            {"label": "输入证据", "value": len(evidence), "tone": "amber"},
            {"label": "当前节点", "value": next((node.branch for node in nodes if node.payload.get("needsCouncil")), "C"), "tone": "red"},
        ],
        "sections": [
            {"id": "context", "title": "当前主线与节点", "kind": "nodes", "items": [_node(node) for node in nodes if node.payload.get("needsCouncil")]},
            {"id": "agents", "title": "参与主体", "kind": "agents", "items": _council_agents(case, council, pages)},
            {"id": "delta", "title": "演变变化面板", "kind": "delta", "items": (council.payload.get("branch_changes", []) if council else pages.get("council", {}).get("branch_changes", []))},
            {"id": "pressure", "title": "假设压力测试", "kind": "pressure-tests", "items": (council.payload.get("pressure_tests", []) if council else [])},
            {"id": "evidence", "title": "输入证据", "kind": "evidence", "items": [_evidence_item(item) for item in evidence[:10]]},
        ],
        "actions": [{"id": "run-pressure-test", "label": "运行压力测试"}, {"id": "apply-council", "label": "将结果注入世界线并重跑"}],
    }


def _brief(case: Case, report: Report | None, tasks: list[Task], council: CouncilSession | None, nodes: list[WorldlineNode], pages: dict[str, Any]) -> dict[str, Any]:
    report_payload = report.payload if report else {}
    return {
        "metrics": [
            {"label": "使用数据", "value": pages.get("brief", {}).get("data_count", 128), "tone": "blue"},
            {"label": "使用证据", "value": pages.get("brief", {}).get("evidence_count", 68), "tone": "green"},
            {"label": "参与主体", "value": len(_council_agents(case, council, pages)), "tone": "amber"},
            {"label": "任务", "value": len(tasks), "tone": "red"},
        ],
        "sections": [
            {"id": "summary", "title": "推演结果摘要", "kind": "report", "items": [_report(report)] if report else []},
            {"id": "timeline", "title": "关键时间节点与路径回看", "kind": "nodes", "items": [_node(node) for node in nodes]},
            {"id": "council", "title": "多方主体研判结论", "kind": "agents", "items": _council_agents(case, council, pages)},
            {"id": "actions", "title": "建议行动方案", "kind": "tasks", "items": [_task(task) for task in tasks]},
            {"id": "docs", "title": "研判报告与文档", "kind": "docs", "items": report_payload.get("documents", pages.get("brief", {}).get("documents", []))},
            {"id": "watch", "title": "后续监测重点", "kind": "watch", "items": pages.get("brief", {}).get("watch", [])},
        ],
        "actions": [{"id": "confirm-report", "label": "确认报告", "object_id": report.id if report else None}, {"id": "create-task", "label": "创建任务"}],
    }


def _memory(case: Case, report: Report | None, tasks: list[Task], pages: dict[str, Any]) -> dict[str, Any]:
    memory = pages.get("memory", {})
    return {
        "metrics": memory.get("metrics", [{"label": "案例ID", "value": "CM-001"}, {"label": "预测命中", "value": "0.74"}, {"label": "待入库", "value": 4}]),
        "sections": [
            {"id": "summary", "title": "案例复盘摘要", "kind": "report", "items": [_report(report)] if report else []},
            {"id": "compare", "title": "预测与现实结果对比", "kind": "facts", "items": memory.get("compare", [])},
            {"id": "path", "title": "扩散路径沉淀", "kind": "graph", "items": memory.get("path", [])},
            {"id": "templates", "title": "前因信号模板", "kind": "chips", "items": memory.get("templates", [])},
            {"id": "updates", "title": "待更新知识项", "kind": "tasks", "items": memory.get("updates", [_task(task) for task in tasks])},
        ],
        "actions": [{"id": "save-draft", "label": "保存草稿"}, {"id": "submit-review", "label": "提交审阅"}, {"id": "confirm-ingest", "label": "确认入库并更新模型"}],
    }


def _library(case: Case, pages: dict[str, Any]) -> dict[str, Any]:
    library = pages.get("library", {})
    return {
        "metrics": library.get("metrics", [{"label": "案例", "value": 1286}, {"label": "模板", "value": 342}, {"label": "召回命中率", "value": "0.78"}]),
        "sections": [
            {"id": "filters", "title": "检索与筛选", "kind": "filters", "items": library.get("filters", ["公共服务", "同城升温", "历史相似", "高命中"])},
            {"id": "taxonomy", "title": "主题分类树", "kind": "chips", "items": library.get("taxonomy", [])},
            {"id": "cases", "title": "相似案例", "kind": "library-cases", "items": library.get("cases", [])},
            {"id": "detail", "title": "案例详情", "kind": "detail", "items": library.get("detail", [])},
            {"id": "patterns", "title": "可复用模式", "kind": "chips", "items": library.get("patterns", [])},
            {"id": "apply", "title": "召回应用建议", "kind": "actions", "items": library.get("apply", [{"label": "加入当前主题"}, {"label": "应用到当前推演"}])},
        ],
    }


def _config(case: Case, sources: list[SourceRecord], pages: dict[str, Any]) -> dict[str, Any]:
    config = pages.get("config", {})
    return {
        "metrics": config.get("metrics", [{"label": "数据源", "value": len(sources)}, {"label": "标签覆盖率", "value": "83%"}, {"label": "待审批", "value": 6}]),
        "sections": [
            {"id": "status", "title": "系统接入状态", "kind": "facts", "items": config.get("status", [])},
            {"id": "sources", "title": "数据源列表", "kind": "sources", "items": [_source(source) for source in sources]},
            {"id": "quality", "title": "数据源质量监控", "kind": "sources", "items": [_source(source) for source in sources[:8]]},
            {"id": "params", "title": "核心模型参数", "kind": "config", "items": config.get("params", [])},
            {"id": "weights", "title": "信号权重配置", "kind": "config", "items": config.get("weights", [])},
            {"id": "safety", "title": "安全与合规边界", "kind": "facts", "items": config.get("safety", [])},
            {"id": "changes", "title": "配置变更日志", "kind": "timeline", "items": config.get("changes", [])},
        ],
        "actions": [{"id": "run-regression", "label": "运行回归测试"}, {"id": "submit-approval", "label": "提交审批并发布"}],
    }


def _nav(case_id: str) -> list[dict[str, str]]:
    return [{"page": page, "label": PAGE_TITLES[page], "path": f"/cases/{case_id}/{page}"} for page in PAGE_IDS]


def _scenario(case: Case) -> dict[str, str]:
    if case.scenario_type == "community_public_service":
        return {
            "subtitle": "社区停水响应信任风险",
            "summary": "围绕停水恢复时间、责任窗口和居民集中咨询的公共服务风险链路。",
        }
    return {
        "subtitle": "青澜中学事件回应与同城情绪升温",
        "summary": "围绕学生坠楼事实、证据保全、家属沟通、隐私保护和线下秩序的高强度事件链路。",
    }


def _case(case: Case) -> dict[str, Any]:
    return {"id": case.id, "slug": case.slug, "title": case.title, "scenario_type": case.scenario_type, "status": case.status, "payload": case.payload}


def _source(source: SourceRecord) -> dict[str, Any]:
    return {
        "id": source.id,
        "name": source.source_name,
        "source_id": source.source_id,
        "access_mode": source.access_mode,
        "status": source.status,
        "trust": source.trust,
        "accepted": source.accepted,
        "blocked_reason": source.blocked_reason,
        "payload": source.payload,
    }


def _signal(signal: Signal) -> dict[str, Any]:
    return {
        "id": signal.id,
        "title": signal.title,
        "summary": signal.summary,
        "priority": signal.priority,
        "region_id": signal.region_id,
        "status": signal.status,
        "scores": signal.scores,
        "tags": signal.payload.get("tags", []),
        "payload": signal.payload,
    }


def _evidence_item(item: Evidence) -> dict[str, Any]:
    return {
        "id": item.id,
        "signal_id": item.signal_id,
        "title": item.title,
        "excerpt": item.masked_excerpt,
        "source": item.source,
        "credibility": item.credibility,
        "status": item.status,
        "sensitivity": item.sensitivity,
        "payload": item.payload,
    }


def _factor(factor: RiskFactor) -> dict[str, Any]:
    return {"id": factor.id, "name": factor.name, "category": factor.category, "confidence": factor.confidence, "status": factor.status, "payload": factor.payload}


def _mainline_item(item: Mainline | None) -> dict[str, Any] | None:
    if not item:
        return None
    return {"id": item.id, "title": item.title, "confidence": item.confidence, "status": item.status, "payload": item.payload}


def _world_state(state: WorldState | None) -> dict[str, Any] | None:
    if not state:
        return None
    return {"id": state.id, "title": state.title, "status": state.status, "payload": state.payload}


def _node(node: WorldlineNode | None) -> dict[str, Any] | None:
    if not node:
        return None
    return {"id": node.id, "title": node.title, "branch": node.branch, "probability": node.probability, "risk": node.risk, "status": node.status, "payload": node.payload}


def _council_agents(case: Case, council: CouncilSession | None, pages: dict[str, Any]) -> list[dict[str, Any]]:
    if council and council.payload.get("agents"):
        return list(council.payload["agents"])
    return pages.get("council", {}).get("agents", _default_agents(case))


def _default_agents(case: Case) -> list[dict[str, Any]]:
    if case.scenario_type == "community_public_service":
        roles = ["居民", "物业服务方", "供水单位", "街道属地", "热线坐席", "本地媒体", "社区网格"]
    else:
        roles = ["家属与亲属共同体", "校方", "教育主管部门", "属地街道", "平台安全", "本地媒体", "同城公众"]
    return [
        {
            "role": role,
            "stance": "要求证据、节奏和边界更清晰",
            "reaction": f"{role} 对当前节点保持压力测试态度。",
            "support_point_delta": {"trust": -0.06, "evidence_completeness": 0.04},
            "branch_probability_delta": {"C": 0.03},
            "evidence_refs": [],
            "uncertainty": "多主体研判为压力测试，不代表事实认定。",
            "blocked_claims": ["unsupported claim: assigning individual blame without confirmed evidence"] if role in {"居民", "同城公众"} else [],
        }
        for role in roles
    ]


def _report(report: Report | None) -> dict[str, Any] | None:
    if not report:
        return None
    return {"id": report.id, "title": report.title, "human_confirmed": report.human_confirmed, "status": report.status, "payload": report.payload}


def _task(task: Task) -> dict[str, Any]:
    return {"id": task.id, "title": task.title, "owner": task.owner, "due_label": task.due_label, "status": task.status, "payload": task.payload}


def _council_session(council: CouncilSession | None) -> dict[str, Any] | None:
    if not council:
        return None
    return {"id": council.id, "case_id": council.case_id, "node_id": council.node_id, "hypothesis": council.hypothesis, "status": council.status, "payload": council.payload}
