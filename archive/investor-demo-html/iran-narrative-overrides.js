(function () {
  const page = location.pathname.split("/").pop() || "risk-dashboard.html";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const palette = { blue: "#2f6df6", green: "#18a873", amber: "#d78925", red: "#df4b54", violet: "#7f63c9" };

  const commonTerms = [
    ["XX市风险主控台", "WORLDLINE OBSERVER"],
    ["城市总体现状", "区域风险总览"],
    ["城市总体风险等级", "地缘总体风险等级"],
    ["城市风险指数", "区域风险指数"],
    ["城市空间态势图", "中东空间态势图"],
    ["城市态势摘要", "区域态势摘要"],
    ["城市更新补偿争议主线", "霍尔木兹通航受限与能源外溢主线"],
    ["城市更新 / 老旧小区改造", "美伊冲突 / 霍尔木兹通航风险"],
    ["美伊冲突 / 霍尔木兹通航风险补偿争议", "美伊冲突 / 霍尔木兹封锁风险"],
    ["霍尔木兹通航风险补偿争议", "霍尔木兹封锁风险"],
    ["补偿争议", "封锁风险"],
    ["补偿支点", "通航稳定性支点"],
    ["补偿方案", "通航方案"],
    ["补偿、护航与知情权讨论", "临检、护航与通航权讨论"],
    ["约 4200 户潜在相关", "约 42 艘油轮/商船潜在相关"],
    ["3 个港口，约 4200 户", "3 条关键航线，约 42 艘船舶"],
    ["航运社群公共项目争议", "海峡通航与安全管控争议"],
    ["城市更新", "霍尔木兹通航"],
    ["老旧小区改造", "海峡通航限制"],
    ["补偿标准不一致", "临检标准不明确"],
    ["补偿测算", "临检与护航规则"],
    ["补偿口径", "临检口径"],
    ["补偿公平", "通航公平"],
    ["补偿", "通航"],
    ["居民代表", "船东代表"],
    ["居民群体", "能源进口方"],
    ["居民", "船东"],
    ["街道/社区", "伊朗决策层"],
    ["街道", "伊朗决策层"],
    ["社区", "航运社群"],
    ["主管部门", "美国安全决策"],
    ["施工方/企业", "海湾国家"],
    ["施工方", "海湾国家"],
    ["施工扰民", "通航受限"],
    ["施工", "护航"],
    ["工期成本", "供应与成本"],
    ["停工", "停航"],
    ["政府", "多方协调方"],
    ["各部门口径", "各方口径"],
    ["小范围说明会", "船东与保险方沟通"],
    ["小范围说明", "船东沟通"],
    ["发布解释型 FAQ", "发布护航与临检规则说明"],
    ["申诉入口", "通报入口"],
    ["航运航运信号", "航运信号"],
    ["航运航运媒体", "航运媒体"],
    ["航运社群群", "船东论坛"],
    ["护航护航边界", "护航边界"],
    ["旧改", "霍尔木兹"],
    ["历史投诉", "历史相似前兆"],
    ["园区员工集中询问工资发放日期", "红海船东集中讨论绕航成本"],
    ["企业侧正式回应缺失", "航运公司公开口径不足"],
    ["劳资压力", "绕航压力"],
    ["薪资发放", "绕航成本"],
    ["企业回应", "船东回应"],
    ["某中学家长群出现核查周边安全隐患讨论", "IAEA 核查窗口推迟引发核查可达性讨论"],
    ["短时升温，现实反馈不足", "机构表态升温，现场核查证据不足"],
    ["核查安全", "核查争议"],
    ["家长市场预期", "机构可信度"],
    ["周边安全", "核查窗口"],
    ["枢纽区晚高峰滞留被多个账号转发", "红海绕航等待被多个船东账号转发"],
    ["视频异常与航运信号咨询需要对齐", "AIS 异常与船东报价需要对齐"],
    ["交通出行", "航运通道"],
    ["客流异常", "船舶等待"],
    ["港口排队体验出现跨院区相似表达", "海湾港口排队体验出现跨航线相似表达"],
    ["影响区域级民生服务感知", "影响区域级航运服务感知"],
    ["医疗服务", "港口服务"],
    ["就诊体验", "排队体验"],
    ["多个市场摊主讨论进货价短时波动", "多个交易员讨论 Brent 风险溢价短时波动"],
    ["价格话题集中但线下库存稳定", "价格话题集中但现货供应尚未异常"],
    ["民生价格", "能源价格"],
    ["供给预期", "供应预期"],
    ["价格波动", "风险溢价"],
    ["低洼点排水井附近出现短时积水反馈", "海湾基地周边出现短时防空戒备反馈"],
    ["天气触发型信号，尚未形成连片影响", "军事戒备型信号，尚未形成连片外溢"],
    ["区域韧性", "基地安全"],
    ["低洼点", "海湾基地"],
    ["排水能力", "防空压力"],
    ["FAQ 与说明会", "规则说明与沟通窗口"],
    ["FAQ", "规则说明"],
    ["说明会", "沟通窗口"],
    ["公开测算规则与依据", "公开临检与护航依据"],
    ["建立反馈渠道与时间表", "建立通报渠道与时间表"],
    ["一线解释", "执行口径"],
    ["线下询问", "船东询问"],
    ["主体上涌讨论发酵", "船东论坛讨论发酵"],
    ["通航方法", "通航规则"],
    ["正在核实", "正在协调护航"],
    ["网格/基层", "航运保险"],
    ["网格员", "航运保险"],
    ["网格", "航运保险"],
    ["人群", "主体"],
    ["围挡", "护航边界"],
    ["线下反馈", "AIS 实测反馈"],
    ["现场反馈", "AIS 实测反馈"],
    ["公告版本", "声明版本"],
    ["官方回应、线下反馈、视频点位", "护航边界、通航率、核查窗口"],
    ["媒体/自媒体", "能源市场"],
    ["自媒体", "能源市场"],
    ["市场观察者", "市场观察"],
    ["12345热线", "公开航运与市场信号"],
    ["12345 航运信号咨询", "AIS 航运信号咨询"],
    ["12345", "AIS"],
    ["AIS 工单", "AIS 片段"],
    ["官方回应、AIS 实测反馈、视频点位", "护航边界、通航率、核查窗口"],
    ["网络上报", "公开视频/论坛上报"],
    ["项目公告/文件", "机构声明/文件"],
    ["尚未完成最终测算", "尚未明确最终护航边界"],
    ["工期和成本", "供应和成本"],
    ["12345 工单", "AIS / 航运报价"],
    ["热线", "航运信号"],
    ["短视频", "公开视频/卫星"],
    ["社区群", "船东论坛"],
    ["学校", "核查机构"],
    ["校园", "核查"],
    ["医院", "港口"],
    ["工业园", "海湾基地"],
    ["城东区", "霍尔木兹"],
    ["城北区", "红海"],
    ["城中区", "波斯湾"],
    ["城西区", "黎以边境"],
    ["城南区", "也门沿岸"],
    ["开发区", "海湾基地"],
    ["地铁事件", "霍尔木兹事件"],
    ["票价上涨争议发酵", "保险费率上调争议发酵"],
    ["票价上涨", "保险费率上调"],
    ["票价争议", "保险费率争议"],
    ["网友情绪升温", "航运市场预期升温"],
    ["学生群体讨论升温", "能源进口方讨论升温"],
    ["交通拥堵反馈增加", "绕航成本反馈增加"],
    ["媒体报道增加", "航运媒体报道增加"],
    ["官方回应开始", "G7 护航讨论出现"],
    ["官方说明发布", "护航机制说明发布"],
    ["相关话题冲上热搜", "能源价格风险溢价"],
    ["群体不满升级，线下聚集风险", "临检扩大，通航限制升级风险"],
    ["线下聚集", "通航受限"],
    ["小规模抗议局部聚集", "局部航道拥堵"],
    ["抗议扩大化持续发酵", "封锁预期持续发酵"],
    ["舆情逐步降温恢复稳定", "通航预期逐步恢复"],
    ["舆情扩散", "风险外溢"],
    ["舆情", "市场预期"],
    ["信息透明度", "通航透明度"],
    ["信息公开", "规则公开"],
    ["公平预期", "通航稳定预期"],
    ["小区", "港口"],
    ["群体", "主体"],
    ["全城", "中东主战区"],
    ["城市", "区域"]
  ];

  const cleanupTerms = [
    ["护航护航边界", "护航边界"],
    ["航运航运信号", "航运信号"],
    ["航运航运媒体", "航运媒体"],
    ["某中学家长群出现校园核查窗口隐患讨论", "IAEA 核查窗口推迟引发可达性讨论"],
    ["校园核查窗口隐患", "核查窗口可达性"],
    ["线下问询", "船东问询"],
    ["输入篮", "输入池"],
    ["补齐 规则说明", "补齐规则说明"],
    ["加强执行口径统一口径", "统一海上执行口径"],
    ["霍尔木兹通航 / 旧改", "霍尔木兹通航 / 海峡管控"],
    ["霍尔木兹通航/旧改", "霍尔木兹通航/海峡管控"],
    ["伊朗决策层旧改相关信号", "伊朗决策层海峡管控相关信号"],
    ["补偿纠纷主线", "封锁风险主线"],
    ["海湾基地区绕航压力", "海湾基地绕航压力"],
    ["园区薪资延误传闻是否属实，企业未官方回应", "海湾基地后勤压力传闻是否属实，需确认机构声明"]
  ];

  function replaceText(root = document.body) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const parent = node.parentElement;
        if (!parent || ["SCRIPT", "STYLE", "NOSCRIPT"].includes(parent.tagName)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    let node;
    while ((node = walker.nextNode())) {
      let value = node.nodeValue;
      commonTerms.forEach(([from, to]) => {
        if (value.includes(from) && !value.includes(to)) value = value.split(from).join(to);
      });
      cleanupTerms.forEach(([from, to]) => {
        value = value.split(from).join(to);
      });
      node.nodeValue = value;
    }
    $$("input, textarea").forEach(el => {
      ["value", "placeholder", "title", "aria-label"].forEach(attr => {
        const current = attr === "value" ? el.value : el.getAttribute(attr);
        if (!current) return;
        let next = current;
        commonTerms.forEach(([from, to]) => {
          if (next.includes(from) && !next.includes(to)) next = next.split(from).join(to);
        });
        cleanupTerms.forEach(([from, to]) => {
          next = next.split(from).join(to);
        });
        if (attr === "value") el.value = next;
        else el.setAttribute(attr, next);
      });
    });
    document.title = document.title.replace("城市更新补偿争议", "霍尔木兹通航受限").replace("XX市", "WORLDLINE OBSERVER");
  }

  function toast(message) {
    const el = $("#toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => el.classList.remove("show"), 1800);
  }

  function setHTML(selector, html) {
    const el = $(selector);
    if (el) el.innerHTML = html;
  }

  function setText(selector, text) {
    const el = $(selector);
    if (el) el.textContent = text;
  }

  function injectLayoutFixes() {
    if (document.getElementById("iran-narrative-layout-fixes")) return;
    const style = document.createElement("style");
    style.id = "iran-narrative-layout-fixes";
    style.textContent = `
      /* Data hub: keep the retrieval/table area readable after Iran narrative replacement. */
      .metrics {
        gap: 10px !important;
        padding-top: 9px !important;
        padding-bottom: 9px !important;
      }
      .metric {
        min-height: 78px !important;
        padding: 10px 11px !important;
        overflow: hidden;
      }
      .metric label {
        white-space: normal !important;
        line-height: 1.2 !important;
        min-height: 14px;
      }
      .metric b {
        margin-top: 5px !important;
        font-size: 22px !important;
        line-height: 1.04 !important;
      }
      .metric p {
        margin-top: 4px !important;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        overflow: hidden;
        white-space: normal;
        line-height: 1.22 !important;
      }
      .workspace {
        grid-template-columns: 280px minmax(720px, 1fr) 370px !important;
      }
      .source-list {
        margin-top: 8px !important;
      }
      .source-card {
        min-height: 64px !important;
        grid-template-columns: minmax(0, 1fr) auto !important;
        align-items: start !important;
      }
      .source-card span {
        min-width: 0;
      }
      .source-card b,
      .source-card small {
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .source-card b {
        white-space: nowrap;
      }
      .source-card small {
        display: -webkit-box !important;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
      }
      .search-panel {
        grid-template-columns: minmax(0, 1.45fr) minmax(250px, .75fr) !important;
        align-items: stretch;
        padding: 11px 12px !important;
      }
      .search-box .title,
      .search-panel .title {
        min-width: 0;
      }
      .search-line input {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .strategy {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
      }
      .strategy div {
        min-width: 0;
        overflow: hidden;
      }
      .table-head,
      .signal-row {
        grid-template-columns: 48px minmax(250px, 1.7fr) minmax(84px, .62fr) minmax(68px, .5fr) minmax(76px, .56fr) 52px 66px !important;
        gap: 8px !important;
      }
      .table-head {
        padding-left: 10px !important;
        padding-right: 10px !important;
      }
      .table-body {
        padding-left: 10px !important;
        padding-right: 10px !important;
      }
      .signal-row {
        min-height: 66px !important;
        padding: 8px 0 !important;
      }
      .signal-row > span {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .signal-row > span:nth-child(2) b,
      .signal-row > span:nth-child(2) small {
        display: -webkit-box !important;
        -webkit-box-orient: vertical;
        overflow: hidden;
        white-space: normal;
      }
      .signal-row > span:nth-child(2) b {
        -webkit-line-clamp: 2;
        font-size: 12px !important;
        line-height: 1.32 !important;
      }
      .signal-row > span:nth-child(2) small {
        -webkit-line-clamp: 2;
        margin-top: 3px !important;
        line-height: 1.25 !important;
      }
      .signal-row > span:nth-child(n+3) {
        font-size: 10.5px;
        line-height: 1.35;
        word-break: keep-all;
      }
      .table-body {
        overflow: auto !important;
        scrollbar-width: none;
      }
      .table-body::-webkit-scrollbar {
        display: none;
      }
      .center {
        grid-template-rows: 158px minmax(0, 1fr) 174px !important;
        overflow: hidden !important;
      }
      .search-panel {
        grid-template-columns: minmax(0, 1.12fr) minmax(430px, .88fr) !important;
        padding: 10px 12px !important;
        align-items: start !important;
      }
      .search-panel .title {
        margin-bottom: 6px !important;
        align-items: center !important;
      }
      .search-box {
        gap: 7px !important;
      }
      .search-line input {
        height: 36px !important;
      }
      .tag-row {
        max-height: 58px !important;
        overflow: hidden !important;
      }
      .strategy div {
        min-height: 40px !important;
        padding: 6px 8px !important;
      }
      .table-panel {
        grid-template-rows: auto minmax(0, 1fr) 42px !important;
      }
      .table-body {
        display: grid !important;
        align-content: start !important;
      }
      .table-foot {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 12px;
        padding: 8px 12px;
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-size: 11px;
        font-weight: 900;
        background: rgba(255,253,247,.62);
      }
      .pager {
        display: flex;
        gap: 6px;
        align-items: center;
      }
      .pager button {
        min-width: 26px;
        height: 26px;
        display: grid;
        place-items: center;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel-solid);
        color: var(--muted);
        font-size: 11px;
        font-weight: 900;
      }
      .pager button.active {
        background: var(--ink);
        border-color: var(--ink);
        color: #fff;
      }
      .bottom-panel {
        min-height: 0 !important;
        overflow: hidden !important;
      }
      .mini-card {
        min-height: 0 !important;
        overflow: hidden !important;
        padding: 10px 12px !important;
      }

      /* Mainline builder: prevent long mainline/retrieval text from crushing the grid. */
      .logic-title {
        grid-template-columns: minmax(0, 1fr) !important;
        gap: 4px !important;
      }
      .logic-title b {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .logic-title span {
        white-space: normal !important;
        line-height: 1.35;
      }
      .retrieval {
        grid-template-columns: minmax(0, 1.25fr) minmax(230px, .85fr) minmax(230px, .85fr) !important;
        align-items: stretch;
      }
      .query-box,
      .recommend-list,
      #strategyList {
        min-width: 0;
      }
      #recommendList > button,
      .recommend-row {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) 42px !important;
        gap: 8px;
        align-items: center;
        min-height: 34px;
        padding: 6px 8px;
        border: 1px solid rgba(216,205,188,.76);
        border-radius: 9px;
        background: rgba(255,253,247,.7);
        font-size: 11px;
        text-align: left;
      }
      #recommendList > button span:first-child,
      .recommend-row span:first-child {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #recommendList > button b,
      .recommend-row b {
        color: var(--ink);
        font-size: 10px;
        text-align: right;
        white-space: nowrap;
      }
      #strategyList {
        display: grid;
        gap: 7px;
      }
      #strategyList span {
        min-width: 0;
        line-height: 1.35;
      }
      .mainline-card header span:first-child {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      /* Decision brief: restore document/task/watch row styling when generated from override data. */
      #docs > button,
      #tasks > button {
        width: 100%;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 8px;
        align-items: center;
        min-height: 40px;
        padding: 8px;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: rgba(255,253,247,.68);
        color: var(--ink);
        text-align: left;
        font: inherit;
        font-size: 12px;
      }
      #docs > button span,
      #tasks > button span {
        min-width: 0;
        display: grid;
        gap: 3px;
      }
      #docs > button span,
      #tasks > button small {
        color: var(--muted);
        font-size: 11px;
        font-weight: 800;
      }
      #docs > button b,
      #tasks > button b {
        color: var(--ink);
        font-size: 12px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #docs > button em,
      #tasks > button em {
        min-height: 26px;
        display: inline-grid;
        place-items: center;
        padding: 0 8px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel-solid);
        color: var(--ink);
        font-style: normal;
        font-size: 11px;
        font-weight: 900;
        white-space: nowrap;
      }
      #watch {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      #watch > span {
        min-height: 34px;
        display: grid;
        align-items: center;
        padding: 7px 9px;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: rgba(255,253,247,.68);
        color: var(--ink);
        font-size: 11px;
        font-weight: 900;
      }
    `;
    document.head.appendChild(style);
  }

  function overrideDataHub() {
    const sources = [
      { id: "all", name: "全部接口信号", desc: "公开源、AIS、市场与机构摘要", count: 12486, health: "98%", coverage: "中东主战区", tone: "blue" },
      { id: "ais", name: "AIS / 航运报价", desc: "船舶等待、绕航报价、保险条款", count: 3280, health: "96%", coverage: "霍尔木兹 / 红海", tone: "red" },
      { id: "market", name: "能源与跨资产市场", desc: "Brent、油轮股、CDS、汇率避险", count: 2116, health: "94%", coverage: "全球市场", tone: "amber" },
      { id: "official", name: "官方与机构声明", desc: "G7、IAEA、海湾国家、军方声明", count: 936, health: "91%", coverage: "多方主体", tone: "green" },
      { id: "media", name: "新闻 / 论坛 / 社媒", desc: "新闻、船东论坛、能源社群", count: 6154, health: "89%", coverage: "舆论与市场预期", tone: "violet" }
    ];
    const signals = [
      {
        id: "SIG-001", p: "P0", tone: "red", sourceId: "ais", title: "IRGC 临检扩大与霍尔木兹通航风险升温",
        sub: "AIS 等待船舶增加，船东论坛讨论保险拒保条款", source: "AIS / 船东论坛", area: "霍尔木兹", tag: "通航受限", sim: "0.91", action: "加入草稿",
        why: "该信号同时命中通航稳定性、航运保险风险和能源风险溢价三个支点，并且在船舶等待、保险报价、论坛讨论三个渠道重复出现，适合作为主线起点。",
        excerpts: [["AIS 船舶状态", "霍尔木兹东向油轮等待时间较前一日上升约 22%", "A"], ["船东论坛", "多名运营方提到“War Risk Premium”重新报价", "B"], ["保险摘要", "部分承保方要求重新确认航线风险", "B"]],
        recs: [["同航线相似信号", "14 条"], ["通航受限同标签", "23 条"], ["保险费率原文片段", "8 条"]]
      },
      {
        id: "SIG-006", p: "P1", tone: "amber", sourceId: "media", title: "红海绕航讨论升温，船东重新评估好望角路径",
        sub: "论坛与市场评论同时出现绕航成本测算", source: "船东论坛 / 新闻", area: "红海", tag: "航运成本", sim: "0.78", action: "补证后加入",
        why: "该信号可以解释成本外溢路径，但目前仍缺少实际改航比例和保险条款原文，适合作为辅助支点。",
        excerpts: [["论坛片段", "讨论焦点从“是否绕航”转为“绕航几天与额外燃油成本”", "B"], ["市场评论", "红海风险被纳入油轮运价预期", "B"]],
        recs: [["同区域近 24 小时", "8 条"], ["航运保险同标签", "11 条"], ["历史红海袭击前兆", "2 条"]]
      },
      {
        id: "SIG-012", p: "P1", tone: "violet", sourceId: "official", title: "IAEA 核查窗口推迟，制裁合法性争议升温",
        sub: "核查可达性下降与制裁节奏讨论同时出现", source: "IAEA / 官方声明", area: "伊朗核设施", tag: "核查争议", sim: "0.83", action: "加入草稿",
        why: "该信号连接军事打击后果、核查可达性和制裁合法性，是从安全风险转向政策风险的重要支点。",
        excerpts: [["IAEA 摘要", "核查访问窗口被推迟，原因仍需复核", "A"], ["外交评论", "多方讨论制裁节奏是否会提前", "B"]],
        recs: [["同机构声明", "6 条"], ["核查争议同标签", "13 条"], ["制裁历史前兆", "4 条"]]
      },
      {
        id: "SIG-017", p: "P1", tone: "red", sourceId: "official", title: "黎以边境火箭弹频率上升，北部战线外溢",
        sub: "边境事件与代理人组织表态出现同向变化", source: "以色列 / 黎巴嫩事件", area: "黎以边境", tag: "代理人外溢", sim: "0.87", action: "加入草稿",
        why: "该信号说明冲突不只停留在海峡通航，还可能牵引多线战区压力，影响世界线的高风险分支。",
        excerpts: [["边境事件", "火箭弹与拦截记录较前一周期上升", "B"], ["组织表态", "代理人组织措辞转向更强硬", "B"]],
        recs: [["同主体事件", "10 条"], ["北部战线支点", "7 条"], ["以军部署相关", "5 条"]]
      },
      {
        id: "SIG-024", p: "P2", tone: "green", sourceId: "official", title: "G7 护航机制讨论出现，封锁预期短线降温",
        sub: "护航讨论压低极端封锁概率，但短期临检不确定性仍在", source: "G7 / 海湾国家", area: "波斯湾", tag: "外交缓和", sim: "0.72", action: "观察",
        why: "该信号是降温支点，能够解释部分概率从极端封锁转向持续拉锯，但仍需确认机制边界和执行时间表。",
        excerpts: [["G7 声明", "讨论海峡护航与能源安全协调", "A"], ["海湾评论", "关注护航边界是否覆盖高风险水域", "B"]],
        recs: [["同会议声明", "5 条"], ["海湾国家表态", "9 条"], ["护航机制历史案例", "3 条"]]
      }
    ];
    const tags = ["全部", "同渠道", "同标签", "同区域", "关键词", "近24小时", "高价值前兆", "待人工复核"];
    let activeSource = "all";
    let activeTag = "全部";
    let selectedId = "SIG-001";
    let draftCount = 7;

    function selected() {
      return signals.find(item => item.id === selectedId) || signals[0];
    }
    function visibleSignals() {
      return signals.filter(item => activeSource === "all" || item.sourceId === activeSource);
    }
    function renderMetrics() {
      const data = [
        ["接口原始数据", "12,486", "已完成初始清洗", "blue"],
        ["高价值前兆", "76", "相似度 0.80 以上", "red"],
        ["待人工复核", "42", "事实边界待确认", "amber"],
        ["视频/卫星/AIS", "486", "点位校正中", "violet"],
        ["主线草稿", draftCount, "可进入主线建模", "green"],
        ["字段完整度", "91%", "地点/时间/主体可用", "blue"]
      ];
      setHTML("#metrics", data.map(m => `
        <button class="metric" style="--tone:${palette[m[3]]}">
          <label>${m[0]}</label><b>${m[1]}</b><p>${m[2]}</p>
        </button>`).join(""));
      $$("#metrics .metric").forEach((btn, index) => btn.addEventListener("click", () => {
        activeTag = index === 1 ? "高价值前兆" : index === 2 ? "待人工复核" : "全部";
        renderSearch();
        renderSignals();
        toast(`已按「${btn.querySelector("label").textContent}」联动筛选`);
      }));
    }
    function renderSources() {
      setHTML("#sourceList", sources.map(s => `
        <button class="source-card ${activeSource === s.id ? "active" : ""}" data-source="${s.id}" style="--tone:${palette[s.tone]}">
          <span><b>${s.name}</b><small>${s.desc}</small></span>
          <span><em>${s.count.toLocaleString()}</em><small>${s.health} · ${s.coverage}</small></span>
        </button>`).join(""));
      $$(".source-card").forEach(btn => btn.addEventListener("click", () => {
        activeSource = btn.dataset.source;
        $("#queryInput") && ($("#queryInput").value = `${sources.find(s => s.id === activeSource).name} ${activeTag} 近24小时`);
        renderSources();
        renderSignals();
        renderStrategy();
      }));
    }
    function renderSearch() {
      setHTML("#tagRow", tags.map(t => `<button class="${activeTag === t ? "active" : ""}" data-tag="${t}">${t}</button>`).join(""));
      setHTML("#taxonomy", ["地点", "组织", "事件类型", "风险语义", "情绪", "时间窗口", "航线", "影响资产"].map(t => `<span>${t}</span>`).join(""));
      setHTML("#draftChips", ["SIG-001", "SIG-012", "SIG-017", "AIS 片段", "G7 声明", "保险报价", "IAEA 摘要"].map(t => `<span>${t}</span>`).join(""));
      setText("#draftCount", String(draftCount));
      $$("#tagRow button").forEach(btn => btn.addEventListener("click", () => {
        activeTag = btn.dataset.tag;
        $("#queryInput") && ($("#queryInput").value = `${activeTag} 霍尔木兹 通航 风险`);
        renderSearch();
        renderStrategy();
      }));
      $("#searchBtn") && ($("#searchBtn").onclick = () => {
        renderSignals();
        toast("已按当前关键词刷新相似信号列表");
      });
    }
    function renderStrategy() {
      const src = sources.find(s => s.id === activeSource) || sources[0];
      setHTML("#strategy", [
        ["主数据源", src.name],
        ["抓取方式", activeTag],
        ["相似阈值", "0.68 以上"],
        ["去重规则", "同源转发降权"]
      ].map(row => `<div><b>${row[0]}</b>${row[1]}</div>`).join(""));
      setHTML("#qualityList", [
        ["地点字段", "96%"],
        ["时间字段", "94%"],
        ["主体识别", "88%"],
        ["异常率", "2.7%"]
      ].map(row => `<span><strong>${row[0]}</strong><em>${row[1]}</em></span>`).join(""));
    }
    function renderSignals() {
      const rows = visibleSignals();
      setHTML("#signalTable", rows.map(s => `
        <button class="signal-row ${s.id === selectedId ? "active" : ""}" data-id="${s.id}" style="--tone:${palette[s.tone]}">
          <span class="badge">${s.p}</span>
          <span><b>${s.title}</b><small>${s.sub}</small></span>
          <span>${s.source}</span><span>${s.area}</span><span>${s.tag}</span><span class="score">${s.sim}</span><span>${s.action}</span>
        </button>`).join(""));
      setText("#resultSummary", `当前显示 1-${rows.length} / 共 42 条候选信号，已按相似度与证据完整度排序`);
      $$(".signal-row").forEach(row => row.addEventListener("click", () => {
        selectedId = row.dataset.id;
        renderSignals();
        renderDetail();
      }));
    }
    function renderDetail() {
      const s = selected();
      setText("#selectedId", s.id);
      setText("#detailTitle", s.title);
      setText("#detailSub", `${s.source} · ${s.area} · ${s.tag} · 相似度 ${s.sim}`);
      setText("#detailWhy", s.why);
      setHTML("#evidenceRows", s.excerpts.map(e => `<div class="evidence-row"><span>${e[0]}：${e[1]}</span><strong>可信度 ${e[2]}</strong></div>`).join(""));
      setHTML("#recommendRows", s.recs.map(r => `<button class="recommend-row"><span>${r[0]}</span><strong>${r[1]}</strong></button>`).join(""));
    }
    renderMetrics();
    renderSources();
    renderSearch();
    renderStrategy();
    renderSignals();
    renderDetail();
    $("#addDraft") && ($("#addDraft").onclick = () => {
      draftCount += 1;
      renderMetrics();
      renderSearch();
      toast(`${selected().id} 已加入主线草稿`);
    });
  }

  function overrideMainlineBuilder() {
    const mainlines = [
      ["ML-001", "霍尔木兹通航受限与能源外溢主线", "待确认", "red", "由临检扩大、保险拒保、油轮等待三类支点形成", "0.88"],
      ["ML-002", "红海袭击与绕航成本主线", "补证中", "amber", "由袭击讨论、绕航报价、船东论坛形成早期聚合", "0.79"],
      ["ML-003", "IAEA 核查受阻与制裁争议主线", "观察", "violet", "核查窗口推迟与制裁节奏形成政策风险支线", "0.74"],
      ["ML-004", "黎以北部战线外溢主线", "待确认", "red", "火箭弹频率、边境部署、代理人表态共振", "0.82"]
    ];
    const nodeLabels = [
      ["起点信号", "IRGC 临检范围扩大"],
      ["同渠道证据", "AIS 等待船舶增加"],
      ["相邻信号", "保险费率重新报价"],
      ["关键支点", "通航规则边界不清"],
      ["关键支点", "能源风险溢价上升"],
      ["证据缺口", "真实通航率与军方边界"],
      ["确认主线", "生成 World State 输入"]
    ];
    setText("#logicTitle", "霍尔木兹通航受限与能源外溢主线");
    $$(".logic-title span").forEach(el => { el.textContent = "系统路径：信号聚合 → 支点提取 → 证据缺口 → 人工确认"; });
    $$(".node").forEach((node, index) => {
      if (!nodeLabels[index]) return;
      const [b, p] = nodeLabels[index];
      const bold = $("b", node);
      const text = $("p", node) || Array.from(node.querySelectorAll("span")).filter(span => !span.classList.contains("score")).pop();
      if (bold) bold.textContent = b;
      if (text) text.textContent = p;
    });
    setHTML("#mainlineList", mainlines.map((m, index) => `
      <button class="mainline-card ${index === 0 ? "active" : ""}" style="--tone:${palette[m[3]]}">
        <header><span>${m[1]}</span><span class="state" style="--tone:${palette[m[3]]}">${m[2]}</span></header>
        <p>${m[4]}</p>
        <footer><span>${m[0]}</span><b>${m[5]}</b></footer>
      </button>`).join(""));
    setHTML("#sourceStack", [
      ["接口信号池", "来自数据检索页加入的 7 条证据", "blue"],
      ["系统成线建议", "语义相似、时间连续、区域聚集", "red"],
      ["人工草稿", "分析师手动补入的证据片段", "green"]
    ].map(s => `<button class="source-card" style="--tone:${palette[s[2]]}"><span><b>${s[0]}</b><small>${s[1]}</small></span><span><em>可用</em></span></button>`).join(""));
    setHTML("#queryHints", ["同航线", "同主体", "关键词", "同区域", "近24小时"].map((t, i) => `<button class="${i === 0 ? "active" : ""}">${t}</button>`).join(""));
    setHTML("#recommendList", [
      ["补充 AIS 等待船舶原始片段", "优先"],
      ["补充保险费率报价原文", "优先"],
      ["补充 G7 护航机制边界", "建议"],
      ["剔除重复转发的论坛摘要", "降权"]
    ].map(r => `<button><span>${r[0]}</span><b>${r[1]}</b></button>`).join(""));
    setHTML("#strategyList", [
      ["聚合逻辑", "同一航线 + 同一时间窗 + 风险语义共现"],
      ["影响对象", "航运保险、能源市场、海湾安全、制裁节奏"],
      ["不确定性", "真实临检边界、护航落地时间、IAEA 核查窗口"],
      ["下一步", "带缺口确认后进入世界线推演"]
    ].map(r => `<span><b>${r[0]}</b>${r[1]}</span>`).join(""));
    setHTML("#detail", `
      <div class="title">主线解释 <span>ML-001</span></div>
      <h2>为什么这些信号能组成一条主线？</h2>
      <p>临检扩大是起点，AIS 等待和保险报价是同方向证据，G7 护航讨论说明外部主体已经开始响应；这些线索共同指向“通航稳定性下降 → 能源风险溢价上升 → 市场与政策风险外溢”。</p>
      <div class="explain-grid">
        <div><b>数据依据</b><span>AIS、船东论坛、G7 声明、IAEA 摘要</span></div>
        <div><b>聚合逻辑</b><span>时间连续、区域聚集、支点共现</span></div>
        <div><b>影响对象</b><span>油轮、保险、能源、制裁、海湾基地</span></div>
        <div><b>人工确认项</b><span>护航边界和真实通航率仍需复核</span></div>
      </div>`);
    setHTML("#evidenceSuggest", ["补真实通航率", "补保险报价原文", "补 G7 护航边界"].map(t => `<button>${t}<span>优先</span></button>`).join(""));
    setHTML("#relatedSuggest", ["红海绕航成本主线", "IAEA 核查争议主线"].map(t => `<button>${t}<span>可关联</span></button>`).join(""));
    setHTML("#mergeSuggest", ["论坛重复转发", "同源新闻转载"].map(t => `<button>${t}<span>建议降权</span></button>`).join(""));
    $("#confirmBtn") && ($("#confirmBtn").onclick = () => {
      toast("已生成霍尔木兹 World State 输入包");
      window.setTimeout(() => { location.href = "worldline-observer.html?mainlineId=hormuz-blockade"; }, 500);
    });
  }

  function overrideDecisionBrief() {
    setHTML(".hero-text", `
      <h1>推演完成：霍尔木兹通航受限与能源外溢</h1>
      <p>最终研判：当前主线未完全缓和，C 线“通航限制升级”仍是主要风险路径。若护航边界、临检规则和 IAEA 核查窗口不能快速明确，未来 24-72 小时仍存在二次升温可能。</p>`);
    setHTML("#actionList", [
      ["1", "发布护航范围与临检规则说明，明确船东可执行口径", "高", "red"],
      ["2", "补充 AIS 等待船舶与保险报价样本，压缩误判空间", "高", "red"],
      ["3", "建立 G7 / 海湾国家护航行动监测表，每 6 小时更新", "中-高", "amber"],
      ["4", "跟踪 IRGC 措辞、红海袭击讨论和 IAEA 核查窗口", "中", "amber"],
      ["5", "将能源、航运保险、北部战线三类支点加入 72h 监测", "中", "blue"]
    ].map(a => `<div class="action-row" style="--tone:${palette[a[3]]}"><i>${a[0]}</i><span><b>${a[1]}</b><p>影响支点：通航稳定性、保险风险、能源溢价、政策不确定性</p></span><span class="stars">${a[2]}</span></div>`).join(""));
    setHTML("#docs", [
      ["世界线推演结果报告 PDF", "10:30"],
      ["多方主体研判纪要 PDF", "10:28"],
      ["霍尔木兹证据链分册 PDF", "10:25"],
      ["行动建议清单 DOCX", "10:30"],
      ["董事会简报 PPTX", "10:31"]
    ].map(d => `<div class="doc-row"><span><b>${d[0]}</b><br>生成于 ${d[1]}</span><button data-export="${d[0]}">单个导出</button></div>`).join(""));
    setHTML("#tasks", [
      ["护航规则说明", "安全研究组", "24h 内", "待确认"],
      ["AIS 与保险样本补证", "数据组", "12h 内", "执行中"],
      ["红海绕航成本跟踪", "航运组", "48h 内", "已完成"],
      ["IAEA 核查窗口监测", "政策组", "持续跟踪", "未开始"]
    ].map(t => `<div class="task-row ${t[3] === "已完成" ? "done" : ""}"><span><b>${t[0]}</b><br>${t[1]} · ${t[2]} · ${t[3]}</span><button data-task="${t[0]}">${t[3] === "已完成" ? "已完成" : "更新"}</button></div>`).join(""));
    setHTML("#watch", ["霍尔木兹通航率", "War Risk Premium", "Brent 风险溢价", "IAEA 核查窗口", "G7 护航措辞", "红海袭击频率"].map(t => `<div class="watch-row"><span><b>${t}</b><br>后续跟踪指标</span><strong>跟踪中</strong></div>`).join(""));
    $$("#docs [data-export]").forEach(btn => btn.addEventListener("click", () => toast(`已生成导出任务：${btn.dataset.export}`)));
    $("#exportAllDocs") && ($("#exportAllDocs").onclick = () => toast("已生成批量导出任务：5 份文档"));
    $$("#tasks [data-task]").forEach(btn => btn.addEventListener("click", () => {
      btn.textContent = "已更新";
      btn.closest(".task-row")?.classList.add("done");
      toast(`任务状态已更新：${btn.dataset.task}`);
    }));
  }

  function overrideWorkflow() {
    setHTML(".hero-text", `
      <h1>从中东风险信号到世界线推演，再到研判闭环</h1>
      <p>主案例：美伊冲突、霍尔木兹通航、红海航运、能源市场、IAEA 核查与多方主体反应。页面保留静态工作台结构，前端以接口返回数据的方式组织展示。</p>`);
    replaceText();
  }

  function overrideWorldlineCopy() {
    replaceText();
    const q1 = $("#sideCouncilQuestion");
    if (q1) q1.placeholder = "例如：如果 G7 只发布“正在协调护航”的模糊回应，会如何影响霍尔木兹后续路径？";
    const q2 = $("#councilQuestion");
    if (q2) q2.placeholder = "例如：如果护航机制没有说明临检边界，伊朗、美国、海湾国家、船东和能源市场会如何反应？";
  }

  function overrideSignalFactory() {
    replaceText();
    setText("#factoryTitle", "信号工厂 · 中东风险信号分诊");
    setText("#caseLabel", "当前案例：美伊冲突与霍尔木兹封锁风险");
  }

  function run() {
    document.documentElement.dataset.iranPage = page;
    if (["data-hub.html", "mainline-builder.html"].includes(page)) {
      injectLayoutFixes();
    }
    replaceText();
    if (page === "data-hub.html") overrideDataHub();
    if (page === "mainline-builder.html") overrideMainlineBuilder();
    if (page === "decision-brief.html") overrideDecisionBrief();
    if (page === "workflow-overview.html") overrideWorkflow();
    if (page === "worldline-observer.html" || page === "agent-council.html") overrideWorldlineCopy();
    if (page === "signal-factory.html" || page === "event-detail-evidence.html" || page === "index.html" || page === "risk-dashboard.html") overrideSignalFactory();
    replaceText();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
  document.addEventListener("click", () => window.setTimeout(replaceText, 20), true);
})();
