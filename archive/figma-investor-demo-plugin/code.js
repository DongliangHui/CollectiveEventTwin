const W = 1440;
const H = 1024;

const C = {
  bg: { r: 0.965, g: 0.955, b: 0.935 },
  paper: { r: 0.992, g: 0.988, b: 0.976 },
  paper2: { r: 0.945, g: 0.938, b: 0.912 },
  ink: { r: 0.075, g: 0.088, b: 0.102 },
  muted: { r: 0.365, g: 0.392, b: 0.420 },
  faint: { r: 0.670, g: 0.690, b: 0.700 },
  line: { r: 0.835, g: 0.815, b: 0.770 },
  amber: { r: 0.825, g: 0.435, b: 0.115 },
  amberSoft: { r: 0.965, g: 0.855, b: 0.640 },
  red: { r: 0.660, g: 0.160, b: 0.125 },
  redSoft: { r: 0.965, g: 0.785, b: 0.730 },
  green: { r: 0.165, g: 0.455, b: 0.360 },
  greenSoft: { r: 0.780, g: 0.900, b: 0.850 },
  blue: { r: 0.165, g: 0.300, b: 0.440 },
  blueSoft: { r: 0.770, g: 0.850, b: 0.910 },
  black: { r: 0, g: 0, b: 0 },
  white: { r: 1, g: 1, b: 1 }
};

const DISCLAIMER = "Mock based on public sources. Human review required before external use.";

let fontRegular = { family: "Inter", style: "Regular" };
let fontMedium = { family: "Inter", style: "Medium" };
let fontSemi = { family: "Inter", style: "Semi Bold" };
let fontBold = { family: "Inter", style: "Bold" };

function solid(color, opacity = 1) {
  return [{ type: "SOLID", color, opacity }];
}

function shadow(opacity = 0.10, y = 10, blur = 24) {
  return [{
    type: "DROP_SHADOW",
    color: { r: 0.12, g: 0.10, b: 0.07, a: opacity },
    offset: { x: 0, y },
    radius: blur,
    spread: 0,
    visible: true,
    blendMode: "NORMAL"
  }];
}

function stroke(color = C.line, weight = 1) {
  return { strokes: solid(color), strokeWeight: weight };
}

async function pickFonts() {
  const fonts = await figma.listAvailableFontsAsync();
  const names = new Set(fonts.map(f => `${f.fontName.family}::${f.fontName.style}`));
  const firstFamily = (...families) => {
    for (const family of families) {
      if (fonts.some(f => f.fontName.family === family)) return family;
    }
    return fonts[0]?.fontName.family || "Inter";
  };
  const family = firstFamily("Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Source Han Sans CN", "Inter", "Arial");
  const style = s => names.has(`${family}::${s}`) ? s : (fonts.find(f => f.fontName.family === family)?.fontName.style || "Regular");
  fontRegular = { family, style: style("Regular") };
  fontMedium = { family, style: style("Medium") };
  fontSemi = { family, style: style("Semi Bold") };
  fontBold = { family, style: style("Bold") };
  await Promise.all([
    figma.loadFontAsync(fontRegular),
    figma.loadFontAsync(fontMedium),
    figma.loadFontAsync(fontSemi),
    figma.loadFontAsync(fontBold)
  ]);
}

function frame(name, x, y, w, h, fill = C.paper) {
  const n = figma.createFrame();
  n.name = name;
  n.resize(w, h);
  n.x = x;
  n.y = y;
  n.fills = solid(fill);
  n.clipsContent = false;
  return n;
}

function rect(parent, name, x, y, w, h, fill, radius = 8, strokeColor = null, effects = []) {
  const n = figma.createRectangle();
  n.name = name;
  n.resize(w, h);
  n.x = x;
  n.y = y;
  n.fills = solid(fill);
  n.cornerRadius = radius;
  if (strokeColor) {
    n.strokes = solid(strokeColor);
    n.strokeWeight = 1;
  }
  n.effects = effects;
  parent.appendChild(n);
  return n;
}

function line(parent, name, x1, y1, x2, y2, color = C.line, weight = 1) {
  const n = figma.createLine();
  n.name = name;
  n.x = x1;
  n.y = y1;
  n.resize(Math.max(1, Math.abs(x2 - x1)), 0);
  n.rotation = y2 === y1 ? 0 : 90;
  n.strokes = solid(color);
  n.strokeWeight = weight;
  parent.appendChild(n);
  return n;
}

function text(parent, name, x, y, w, value, size = 16, color = C.ink, font = fontRegular, lineHeight = 1.28) {
  const n = figma.createText();
  n.name = name;
  n.x = x;
  n.y = y;
  n.resize(w, 12);
  n.fontName = font;
  n.fontSize = size;
  n.lineHeight = { unit: "PIXELS", value: Math.round(size * lineHeight) };
  n.letterSpacing = { unit: "PIXELS", value: 0 };
  n.fills = solid(color);
  n.characters = value;
  n.textAutoResize = "HEIGHT";
  parent.appendChild(n);
  return n;
}

function label(parent, x, y, value, color = C.muted) {
  return text(parent, "Label / " + value, x, y, 320, value, 12, color, fontMedium, 1.2);
}

function pill(parent, x, y, value, fill, color = C.ink, w = null) {
  const width = w || Math.max(88, value.length * 7 + 26);
  rect(parent, "Pill / " + value, x, y, width, 28, fill, 14, null, []);
  const t = text(parent, "Pill Text / " + value, x + 13, y + 7, width - 26, value, 11, color, fontSemi, 1.0);
  return t;
}

function card(parent, name, x, y, w, h, title = null) {
  rect(parent, name, x, y, w, h, C.paper, 8, C.line, shadow(0.055, 6, 18));
  if (title) text(parent, name + " Title", x + 22, y + 18, w - 44, title, 15, C.ink, fontSemi, 1.2);
}

function metric(parent, x, y, w, title, value, sub, tone = "amber") {
  const tones = {
    amber: [C.amberSoft, C.amber],
    red: [C.redSoft, C.red],
    green: [C.greenSoft, C.green],
    blue: [C.blueSoft, C.blue]
  };
  const [soft, main] = tones[tone] || tones.amber;
  card(parent, "Metric / " + title, x, y, w, 128);
  rect(parent, "Metric Marker", x + 18, y + 20, 6, 88, main, 3);
  text(parent, "Metric Title", x + 36, y + 20, w - 54, title, 13, C.muted, fontMedium, 1.2);
  text(parent, "Metric Value", x + 36, y + 43, w - 54, value, 32, C.ink, fontBold, 1.05);
  text(parent, "Metric Sub", x + 36, y + 84, w - 54, sub, 12, C.muted, fontRegular, 1.25);
  rect(parent, "Metric Tint", x + w - 54, y + 20, 28, 28, soft, 14);
}

function button(parent, name, x, y, w, labelText, tone = "dark") {
  const fill = tone === "dark" ? C.ink : tone === "amber" ? C.amber : C.paper2;
  const color = tone === "dark" || tone === "amber" ? C.white : C.ink;
  const b = rect(parent, "Button / " + name, x, y, w, 42, fill, 8, tone === "light" ? C.line : null, []);
  text(parent, "Button Text / " + name, x + 16, y + 13, w - 32, labelText, 12, color, fontSemi, 1.0);
  return b;
}

function nav(parent, activeIndex) {
  const items = ["Brief", "Risk", "Evidence", "Scenario", "Agents", "Investor", "Report", "Transfer"];
  text(parent, "Brand", 56, 34, 360, "Risk Intelligence Twin / 风险智能推演平台", 17, C.ink, fontSemi, 1.1);
  text(parent, "Snapshot", 1070, 34, 315, "Snapshot 2026-04-25 12:00 Asia/Tokyo", 12, C.muted, fontRegular, 1.1);
  for (let i = 0; i < items.length; i++) {
    const x = 58 + i * 106;
    if (i === activeIndex) rect(parent, "Nav Active " + items[i], x - 10, 72, 86, 28, C.ink, 14);
    text(parent, "Nav " + items[i], x, 80, 78, items[i], 11, i === activeIndex ? C.white : C.muted, fontMedium, 1.0);
  }
  line(parent, "Top Divider", 56, 118, 1384, 118, C.line, 1);
}

function footer(parent) {
  text(parent, "Disclaimer", 56, 978, 560, DISCLAIMER, 11, C.muted, fontRegular, 1.1);
  text(parent, "Footer", 1190, 978, 195, "Static demo - not advice", 11, C.muted, fontRegular, 1.1);
}

function addReaction(node, destination) {
  node.reactions = [{
    trigger: { type: "ON_CLICK" },
    action: {
      type: "NODE",
      destinationId: destination.id,
      navigation: "NAVIGATE",
      transition: { type: "DISSOLVE", easing: { type: "EASE_OUT" }, duration: 0.25 },
      preserveScrollPosition: false
    }
  }];
}

function miniChart(parent, x, y, w, h, values, color = C.amber) {
  rect(parent, "Chart Area", x, y, w, h, C.paper2, 6, C.line);
  const step = w / (values.length - 1);
  for (let i = 0; i < values.length - 1; i++) {
    const x1 = x + i * step;
    const y1 = y + h - values[i] * h;
    const x2 = x + (i + 1) * step;
    const y2 = y + h - values[i + 1] * h;
    const l = figma.createLine();
    l.name = "Chart Segment";
    l.x = x1;
    l.y = y1;
    l.resize(Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2), 0);
    l.rotation = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
    l.strokes = solid(color);
    l.strokeWeight = 3;
    parent.appendChild(l);
  }
}

function riskMap(parent, x, y, w, h) {
  rect(parent, "Muted Gulf Map", x, y, w, h, { r: 0.910, g: 0.900, b: 0.870 }, 8, C.line);
  rect(parent, "Hormuz Heat Band", x + 208, y + 170, 210, 44, C.redSoft, 22, null);
  rect(parent, "Shipping Lane", x + 96, y + 244, 420, 18, C.blueSoft, 9, null);
  rect(parent, "Iran Coast", x + 70, y + 92, 250, 88, { r: 0.835, g: 0.820, b: 0.770 }, 34, null);
  rect(parent, "GCC Coast", x + 330, y + 282, 230, 70, { r: 0.860, g: 0.845, b: 0.790 }, 28, null);
  text(parent, "Map Label 1", x + 90, y + 118, 180, "Iran ports / 伊朗港口", 12, C.muted, fontMedium, 1.1);
  text(parent, "Map Label 2", x + 360, y + 305, 200, "GCC energy infra / 海湾能源设施", 12, C.muted, fontMedium, 1.1);
  text(parent, "Map Label 3", x + 244, y + 184, 220, "Hormuz chokepoint / 霍尔木兹", 13, C.red, fontSemi, 1.1);
  for (const p of [[210, 180], [260, 200], [338, 192], [396, 192], [470, 254], [532, 268]]) {
    rect(parent, "Risk Dot", x + p[0], y + p[1], 13, 13, C.amber, 7);
  }
}

function createBrief(x) {
  const f = frame("00 Narrative Brief", x, 0, W, H, C.bg);
  nav(f, 0);
  text(f, "Kicker", 56, 154, 420, "INVESTOR DEMO / 投资人演示路径", 13, C.amber, fontBold, 1.1);
  text(f, "Title", 56, 184, 760, "用公开源信号，把地缘风险变成可解释、可推演、可交付的投行工作台", 40, C.ink, fontBold, 1.16);
  text(f, "Subtitle", 58, 294, 760, "From public signals to evidence, scenarios, agent pressure-testing, market impact, and decision reports.", 18, C.muted, fontRegular, 1.35);

  card(f, "Story Spine", 56, 386, 840, 314, "8-10 minute story spine / 演示主线");
  const steps = [
    ["01", "发现风险", "Risk command workspace"],
    ["02", "解释风险", "Evidence chain and source confidence"],
    ["03", "推演路径", "Scenario sandbox with triggers"],
    ["04", "模拟立场", "Agent council pressure test"],
    ["05", "投资影响", "Cross-asset and transaction lens"],
    ["06", "报告交付", "Decision report and monitoring list"]
  ];
  for (let i = 0; i < steps.length; i++) {
    const sx = 88 + (i % 3) * 262;
    const sy = 442 + Math.floor(i / 3) * 106;
    rect(f, "Step Box", sx, sy, 230, 74, i === 0 ? C.ink : C.paper2, 8, C.line);
    text(f, "Step No", sx + 16, sy + 14, 40, steps[i][0], 20, i === 0 ? C.white : C.amber, fontBold, 1.0);
    text(f, "Step CN", sx + 60, sy + 12, 148, steps[i][1], 17, i === 0 ? C.white : C.ink, fontSemi, 1.0);
    text(f, "Step EN", sx + 60, sy + 38, 148, steps[i][2], 11, i === 0 ? C.paper2 : C.muted, fontRegular, 1.15);
  }

  card(f, "Boundary", 952, 154, 382, 236, "Product boundary / 产品边界");
  const boundaries = ["Public-source based mock", "Not military or investment advice", "No non-authorized intelligence", "Human review before external use"];
  boundaries.forEach((b, i) => {
    rect(f, "Boundary Tick", 984, 210 + i * 42, 9, 9, i < 2 ? C.amber : C.green, 4);
    text(f, "Boundary Text", 1006, 204 + i * 42, 280, b, 13, C.ink, fontMedium, 1.15);
  });

  card(f, "Core Metrics", 952, 426, 382, 274, "Demo anchors / 关键数据锚点");
  [["84/100", "Overall risk score"], ["69%", "7-day escalation probability"], ["5", "Hormuz vessels in 24h"], ["$105", "Brent crude mock range"]].forEach((m, i) => {
    const mx = 986 + (i % 2) * 168;
    const my = 486 + Math.floor(i / 2) * 88;
    text(f, "Anchor Value", mx, my, 118, m[0], 28, C.ink, fontBold, 1.0);
    text(f, "Anchor Label", mx, my + 38, 130, m[1], 11, C.muted, fontRegular, 1.15);
  });
  button(f, "Start Risk Workspace", 56, 742, 232, "Start demo / 进入驾驶舱", "dark");
  footer(f);
  return f;
}

function createRisk(x) {
  const f = frame("01 Risk Command Workspace", x, 0, W, H, C.bg);
  nav(f, 1);
  text(f, "Page Question", 56, 146, 520, "哪里正在形成系统性外溢风险？", 28, C.ink, fontBold, 1.1);
  text(f, "Page Question EN", 58, 184, 520, "Where is systemic spillover risk forming?", 14, C.muted, fontRegular, 1.2);
  metric(f, 56, 232, 300, "总体风险等级 / Overall", "橙色 84", "Risk score 84/100, trend rising", "amber");
  metric(f, 380, 232, 300, "7天再升级 / 7D escalation", "69%", "Confidence 0.76", "red");
  metric(f, 704, 232, 300, "霍尔木兹通航 / Hormuz", "5艘", "Past 24h vessels, severe restriction", "red");
  metric(f, 1028, 232, 300, "Brent 原油 / Oil", "$105", "High-volatility mock range", "amber");
  card(f, "Risk Map Card", 56, 392, 644, 416, "Risk geography / 风险地理");
  riskMap(f, 84, 446, 588, 300);
  pill(f, 86, 760, "Shipping lane pressure", C.redSoft, C.red, 176);
  pill(f, 280, 760, "Sanctions spillover", C.amberSoft, C.amber, 166);
  pill(f, 462, 760, "Energy inflation path", C.blueSoft, C.blue, 174);

  card(f, "Event List", 724, 392, 604, 416, "Active risk event / 当前主风险事件");
  rect(f, "Primary Event Highlight", 752, 448, 548, 132, C.paper2, 8, C.amber);
  text(f, "Event Title", 774, 470, 390, "美伊战争停火脆弱期下的霍尔木兹封锁与地区外溢风险", 18, C.ink, fontSemi, 1.2);
  text(f, "Event EN", 774, 524, 400, "US-Iran fragile ceasefire, Hormuz blockade, and spillover risk", 12, C.muted, fontRegular, 1.25);
  pill(f, 1178, 468, "Orange", C.amberSoft, C.amber, 86);
  text(f, "Event Metadata", 774, 552, 430, "72h probability 57% · 14D probability 76% · Manual review required", 12, C.muted, fontRegular, 1.1);
  [["IAEA access partial", "Nuclear verification gap"], ["34 ships turned back", "Blockade pressure"], ["40 entities/vessels", "Sanctions expansion"]].forEach((e, i) => {
    const y = 610 + i * 58;
    rect(f, "Signal Row", 752, y, 548, 44, C.paper, 6, C.line);
    text(f, "Signal A", 772, y + 10, 190, e[0], 13, C.ink, fontSemi, 1.1);
    text(f, "Signal B", 984, y + 10, 260, e[1], 12, C.muted, fontRegular, 1.1);
  });
  const b = button(f, "View Evidence", 1094, 742, 206, "View Evidence / 看证据链", "dark");
  footer(f);
  return { frame: f, primaryButton: b };
}

function createEvidence(x) {
  const f = frame("02 Event & Evidence Chain", x, 0, W, H, C.bg);
  nav(f, 2);
  text(f, "Page Question", 56, 146, 560, "系统为什么判断它有风险？", 28, C.ink, fontBold, 1.1);
  text(f, "Page Question EN", 58, 184, 620, "Why should an investor trust the risk judgment?", 14, C.muted, fontRegular, 1.2);

  card(f, "Event Summary", 56, 232, 420, 626, "Risk event object / 风险事件对象");
  text(f, "Event Name", 84, 292, 340, "美伊战争停火脆弱期下的霍尔木兹封锁与地区外溢风险", 22, C.ink, fontBold, 1.18);
  [["Stage", "停火脆弱期 / Fragile ceasefire"], ["Risk", "Orange · 84/100"], ["Impact", "Very high / 能源、航运、制裁"], ["Control", "Medium low / 可控性偏低"], ["Confidence", "0.78 · source-based mock"]].forEach((r, i) => {
    const y = 386 + i * 58;
    text(f, "Summary Key", 86, y, 96, r[0], 12, C.muted, fontMedium, 1.1);
    text(f, "Summary Value", 190, y - 2, 242, r[1], 15, C.ink, fontSemi, 1.15);
  });
  pill(f, 84, 714, "Manual review required", C.amberSoft, C.amber, 188);
  text(f, "Review Note", 84, 760, 336, "涉及军事再升级、核查结论、制裁合规和人道伤亡的数据必须标注置信度并复核。", 13, C.muted, fontRegular, 1.35);

  card(f, "Evidence", 500, 232, 464, 626, "Evidence chain / 证据链");
  const evid = [
    ["Reuters", "封锁全球化，34艘船被迫转向", "Tier A · T+1"],
    ["Reuters", "过去24小时仅5艘船通过霍尔木兹", "Tier A · T+1"],
    ["IAEA", "核查访问部分且存在争议", "Official · M+2"],
    ["US Treasury", "伊朗石油贸易与影子船队制裁扩大", "Official · T+1"],
    ["UK Commons", "霍尔木兹石油与LNG通道战略简报", "Parliamentary · T+1"]
  ];
  evid.forEach((e, i) => {
    const y = 292 + i * 92;
    rect(f, "Evidence Row", 528, y, 408, 70, C.paper2, 8, C.line);
    text(f, "Evidence Source", 548, y + 14, 88, e[0], 12, C.amber, fontBold, 1.1);
    text(f, "Evidence Text", 646, y + 12, 196, e[1], 13, C.ink, fontMedium, 1.2);
    text(f, "Evidence Tier", 846, y + 18, 74, e[2], 10, C.muted, fontRegular, 1.15);
  });

  card(f, "Conflict Vectors", 988, 232, 340, 626, "Risk vectors / 风险向量");
  [["封锁与通航权", 92, C.red], ["能源供应", 94, C.red], ["核查透明度", 86, C.amber], ["地区安全", 83, C.amber], ["制裁合规", 79, C.blue]].forEach((v, i) => {
    const y = 298 + i * 82;
    text(f, "Vector Label", 1016, y, 162, v[0], 14, C.ink, fontSemi, 1.1);
    text(f, "Vector Score", 1244, y, 42, String(v[1]), 17, v[2], fontBold, 1.0);
    rect(f, "Vector Bar BG", 1016, y + 30, 250, 8, C.paper2, 4);
    rect(f, "Vector Bar", 1016, y + 30, 250 * v[1] / 100, 8, v[2], 4);
  });
  const b = button(f, "Run Scenario", 1110, 794, 188, "Run Scenario / 进入推演", "dark");
  footer(f);
  return { frame: f, primaryButton: b };
}

function createScenario(x) {
  const f = frame("03 Scenario Sandbox", x, 0, W, H, C.bg);
  nav(f, 3);
  text(f, "Page Question", 56, 146, 620, "如果变量变化，风险会往哪条路径演化？", 28, C.ink, fontBold, 1.1);
  text(f, "Page Question EN", 58, 184, 640, "What happens if policy, maritime, and verification variables move?", 14, C.muted, fontRegular, 1.2);

  card(f, "Inputs", 56, 232, 352, 626, "Scenario inputs / 情景变量");
  [["Blockade intensity", "High · expanding"], ["Hormuz traffic", "1-10 vessels/day"], ["IAEA access", "Partial and contested"], ["Sanctions pace", "Large-scale"], ["Brent trigger", "> 110 watch"]].forEach((v, i) => {
    const y = 296 + i * 86;
    text(f, "Input Label", 88, y, 180, v[0], 13, C.muted, fontMedium, 1.1);
    text(f, "Input Value", 88, y + 24, 226, v[1], 17, C.ink, fontSemi, 1.05);
    rect(f, "Input Slider BG", 88, y + 54, 260, 8, C.paper2, 4);
    rect(f, "Input Slider Val", 88, y + 54, 180 + i * 12, 8, i < 2 ? C.red : C.amber, 4);
  });

  card(f, "Path Tree", 432, 232, 548, 626, "Evolution paths / 演化路径树");
  text(f, "Current", 462, 296, 160, "Current state", 13, C.muted, fontMedium, 1.0);
  rect(f, "Current Box", 462, 324, 200, 58, C.ink, 8);
  text(f, "Current Text", 482, 342, 160, "Fragile ceasefire\n停火脆弱期", 14, C.white, fontSemi, 1.15);
  const paths = [
    ["A", "Low-intensity long tail", "低烈度长期化", "42%", C.amber],
    ["B", "Negotiation sawtooth", "谈判拉锯", "31%", C.blue],
    ["C", "Maritime flashpoint", "海上事件触发升级", "19%", C.red],
    ["D", "Nuclear access break", "核查中断叙事上行", "8%", C.red]
  ];
  paths.forEach((p, i) => {
    const y = 430 + i * 88;
    line(f, "Path Connector", 560, 382, 590, y + 28, C.line, 1);
    rect(f, "Path Box " + p[0], 600, y, 330, 62, C.paper2, 8, C.line);
    text(f, "Path Name", 622, y + 12, 190, p[1], 14, C.ink, fontSemi, 1.1);
    text(f, "Path CN", 622, y + 34, 190, p[2], 12, C.muted, fontRegular, 1.1);
    text(f, "Path Prob", 864, y + 20, 48, p[3], 18, p[4], fontBold, 1.0);
  });

  card(f, "Delta", 1004, 232, 324, 626, "Impact delta / 风险变化");
  miniChart(f, 1034, 300, 262, 150, [0.45, 0.50, 0.58, 0.63, 0.70, 0.69, 0.76], C.amber);
  [["Energy CPI pass-through", "+ high"], ["Insurance withdrawal", "watch"], ["EM FX pressure", "medium-high"], ["Credit spread risk", "rising"]].forEach((r, i) => {
    const y = 504 + i * 58;
    rect(f, "Delta Row", 1034, y, 262, 42, C.paper2, 6, C.line);
    text(f, "Delta Key", 1050, y + 12, 150, r[0], 12, C.ink, fontMedium, 1.0);
    text(f, "Delta Val", 1210, y + 12, 70, r[1], 12, i === 0 ? C.red : C.amber, fontSemi, 1.0);
  });
  const b = button(f, "Start Agent Council", 1092, 794, 204, "Start Agent Council / 启动对话", "dark");
  footer(f);
  return { frame: f, primaryButton: b };
}

function createAgents(x) {
  const f = frame("04 Agent Council", x, 0, W, H, C.bg);
  nav(f, 4);
  text(f, "Page Question", 56, 146, 620, "各方会如何反应，冲突点在哪里？", 28, C.ink, fontBold, 1.1);
  text(f, "Page Question EN", 58, 184, 620, "How do stakeholders react before the decision is made?", 14, C.muted, fontRegular, 1.2);
  card(f, "Agent Cards", 56, 232, 330, 626, "Agent roles / 角色模拟");
  const agents = [
    ["US", "封锁作为谈判杠杆", C.blue],
    ["Iran", "主权与通航压力", C.amber],
    ["IAEA", "核查透明路线图", C.green],
    ["GCC", "能源设施与通航安全", C.blue],
    ["Market", "油价、保险、运费", C.red],
    ["Humanitarian", "停火合法性压力", C.amber]
  ];
  agents.forEach((a, i) => {
    const y = 292 + i * 78;
    rect(f, "Agent Row", 84, y, 274, 56, C.paper2, 8, C.line);
    rect(f, "Agent Dot", 104, y + 17, 22, 22, a[2], 11);
    text(f, "Agent Name", 142, y + 11, 90, a[0], 16, C.ink, fontBold, 1.0);
    text(f, "Agent Position", 142, y + 32, 178, a[1], 11, C.muted, fontRegular, 1.1);
  });

  card(f, "Dialogue", 410, 232, 560, 626, "Pressure-test dialogue / 压力测试对话");
  const messages = [
    ["Scenario", "If blockade remains high while IAEA access is only partial, markets price the ceasefire as fragile."],
    ["IAEA Agent", "A phased access roadmap would reduce uncertainty more than another general statement."],
    ["Energy Market Agent", "The key threshold is not headline rhetoric; it is daily Hormuz throughput and insurance availability."],
    ["GCC Agent", "Regional stability requires a maritime incident freeze mechanism in the next 72 hours."],
    ["System Extract", "Conflict points: blockade legitimacy, nuclear access, shipping rules. Consensus: a narrow maritime de-risking channel is feasible."]
  ];
  messages.forEach((m, i) => {
    const y = 292 + i * 100;
    rect(f, "Message", 438, y, 504, 74, i === 4 ? C.ink : C.paper2, 8, i === 4 ? null : C.line);
    text(f, "Msg Role", 458, y + 12, 130, m[0], 12, i === 4 ? C.amberSoft : C.amber, fontBold, 1.0);
    text(f, "Msg Body", 590, y + 12, 320, m[1], 12, i === 4 ? C.white : C.ink, fontRegular, 1.25);
  });

  card(f, "Synthesis", 994, 232, 334, 626, "System synthesis / 系统总结");
  [["Core conflicts", "封锁合法性、核查通道、通航规则"], ["Consensus space", "72小时海上事件冻结机制"], ["High-risk wording", "Ambiguous blockade expansion claims"], ["Revision", "Tie blockade adjustment to IAEA access nodes"]].forEach((s, i) => {
    const y = 302 + i * 112;
    text(f, "Synth Key", 1024, y, 220, s[0], 13, C.amber, fontBold, 1.0);
    text(f, "Synth Value", 1024, y + 26, 250, s[1], 15, C.ink, fontSemi, 1.25);
  });
  text(f, "Agent Boundary", 1024, 762, 252, "Agent outputs simulate roles from public-source patterns; they are not official positions.", 11, C.muted, fontRegular, 1.25);
  const b = button(f, "Open Investor Lens", 1110, 812, 186, "Open Investor Lens / 投行视角", "dark");
  footer(f);
  return { frame: f, primaryButton: b };
}

function createInvestor(x) {
  const f = frame("05 Investment Lens", x, 0, W, H, C.bg);
  nav(f, 5);
  text(f, "Page Question", 56, 146, 560, "这件事如何传导到市场和交易？", 28, C.ink, fontBold, 1.1);
  text(f, "Page Question EN", 58, 184, 600, "How does the risk transmit into portfolios, sectors, and deals?", 14, C.muted, fontRegular, 1.2);
  card(f, "Heatmap", 56, 232, 534, 626, "Cross-asset heatmap / 跨资产热力");
  const cols = ["Oil", "LNG", "Shipping", "Airlines", "EM FX", "Credit"];
  const rows = ["Base", "Hormuz <10", "IAEA suspended", "Sanctions +", "Incident"];
  cols.forEach((c, i) => text(f, "HM Col", 148 + i * 68, 292, 62, c, 11, C.muted, fontMedium, 1.0));
  rows.forEach((r, j) => text(f, "HM Row", 84, 328 + j * 66, 92, r, 11, C.muted, fontMedium, 1.0));
  for (let j = 0; j < rows.length; j++) {
    for (let i = 0; i < cols.length; i++) {
      const severity = (i + j) % 5;
      const fill = severity > 3 ? C.red : severity > 1 ? C.amber : C.green;
      rect(f, "HM Cell", 148 + i * 68, 322 + j * 66, 52, 42, fill, 6);
    }
  }
  text(f, "HM Note", 84, 720, 438, "Heatmap uses mock stress signals: Brent, freight, insurance, credit spreads, and emerging-market currency pressure.", 12, C.muted, fontRegular, 1.35);

  card(f, "Exposure", 616, 232, 348, 626, "Sector exposure / 行业暴露");
  [["Airlines", 88, C.red], ["Petrochemicals", 64, C.amber], ["Shipping insurers", 91, C.red], ["Defense", 38, C.green], ["Renewables", 46, C.blue], ["Trade finance", 79, C.amber]].forEach((e, i) => {
    const y = 300 + i * 76;
    text(f, "Exp Name", 646, y, 140, e[0], 13, C.ink, fontSemi, 1.0);
    rect(f, "Exp BG", 646, y + 28, 240, 8, C.paper2, 4);
    rect(f, "Exp Val", 646, y + 28, 240 * e[1] / 100, 8, e[2], 4);
    text(f, "Exp Score", 900, y + 20, 36, String(e[1]), 15, e[2], fontBold, 1.0);
  });

  card(f, "Transaction Flags", 990, 232, 338, 626, "Deal red flags / 交易红旗");
  [["P0", "Counterparty exposure to shadow fleet"], ["P0", "Sanctioned refinery or vessel linkage"], ["P1", "Insurance exclusion on Gulf route"], ["P1", "Force majeure in Asian refinery supply"], ["P2", "FX and margin sensitivity not priced"]].forEach((fla, i) => {
    const y = 302 + i * 86;
    rect(f, "Flag Row", 1020, y, 276, 58, C.paper2, 8, C.line);
    text(f, "Flag P", 1040, y + 18, 34, fla[0], 14, fla[0] === "P0" ? C.red : C.amber, fontBold, 1.0);
    text(f, "Flag Text", 1086, y + 12, 176, fla[1], 12, C.ink, fontMedium, 1.2);
  });
  const b = button(f, "Generate Report", 1112, 794, 184, "Generate Report / 生成报告", "dark");
  footer(f);
  return { frame: f, primaryButton: b };
}

function createReport(x) {
  const f = frame("06 Decision Report", x, 0, W, H, C.bg);
  nav(f, 6);
  text(f, "Page Question", 56, 146, 560, "最终交付给决策会的是什么？", 28, C.ink, fontBold, 1.1);
  text(f, "Page Question EN", 58, 184, 600, "What is the decision-ready artifact?", 14, C.muted, fontRegular, 1.2);
  card(f, "Report Doc", 56, 232, 850, 626, "Structured intelligence report / 结构化研判报告");
  text(f, "Report Title", 92, 294, 620, "美伊战争停火脆弱期风险研判报告", 25, C.ink, fontBold, 1.1);
  text(f, "Report Status", 92, 334, 560, "Draft pending human review · Source-based mock · Version RPT-USIRAN-20260425-DEMO", 12, C.muted, fontRegular, 1.1);
  const sections = [
    ["Executive summary", "美国封锁全球化、霍尔木兹通航极低、核查不确定性和制裁升级共同构成高外溢风险。"],
    ["Key findings", "霍尔木兹是风险传导放大器；IAEA访问是连接军事、外交和市场溢价的关键变量。"],
    ["Recommended actions", "建立72小时海上事件冻结机制；发布通航白名单；推动IAEA阶段性访问路线图。"],
    ["Monitoring checklist", "通航船只、制裁名单、Brent > 110、保险拒保、IAEA访问安排、海湾设施警戒。"]
  ];
  sections.forEach((s, i) => {
    const y = 398 + i * 104;
    text(f, "Report Section", 92, y, 190, s[0], 14, C.amber, fontBold, 1.0);
    text(f, "Report Body", 306, y - 2, 520, s[1], 15, C.ink, fontRegular, 1.35);
    line(f, "Report Divider", 92, y + 76, 850, y + 76, C.line, 1);
  });

  card(f, "Review Queue", 934, 232, 394, 626, "Human review queue / 人工复核");
  [["REV-001", "停火有效性与执行机制"], ["REV-002", "霍尔木兹通航口径"], ["REV-003", "IAEA访问限制含义"], ["REV-004", "第三国制裁影响范围"], ["REV-005", "油价二阶影响"], ["REV-006", "人道伤亡核验状态"]].forEach((r, i) => {
    const y = 296 + i * 72;
    rect(f, "Review Row", 964, y, 334, 48, C.paper2, 8, C.line);
    text(f, "Review ID", 984, y + 15, 68, r[0], 12, C.amber, fontBold, 1.0);
    text(f, "Review Item", 1064, y + 12, 190, r[1], 13, C.ink, fontMedium, 1.15);
  });
  const b = button(f, "Transferability", 1078, 794, 220, "Transferability / 迁移能力", "dark");
  footer(f);
  return { frame: f, primaryButton: b };
}

function createTransfer(x) {
  const f = frame("07 Transferability", x, 0, W, H, C.bg);
  nav(f, 7);
  text(f, "Page Question", 56, 146, 720, "这不是单一场景工具，而是一套风险推演操作系统", 28, C.ink, fontBold, 1.1);
  text(f, "Page Question EN", 58, 184, 720, "The same operating model transfers from geopolitical risk to social risk governance.", 14, C.muted, fontRegular, 1.2);

  card(f, "Mapping", 56, 232, 816, 626, "Capability mapping / 能力迁移");
  const map = [
    ["Public signals", "公开源外交、航运、能源、制裁数据", "热线、网格、公开舆情、项目材料"],
    ["Risk event object", "霍尔木兹封锁与地区外溢风险", "小区改造集中诉求风险"],
    ["Evidence chain", "Reuters, IAEA, Treasury, Commons", "工单、网格上报、历史案例、公告"],
    ["Scenario sandbox", "封锁强度、IAEA访问、制裁节奏", "公告、沟通会、补偿说明、施工安排"],
    ["Agent council", "国家、机构、市场、人道组织", "居民、街道、施工方、媒体、调解专家"],
    ["Decision report", "投资影响与72小时监测清单", "沟通建议与处置复核清单"]
  ];
  text(f, "Col1", 90, 292, 170, "Capability", 12, C.muted, fontBold, 1.0);
  text(f, "Col2", 304, 292, 230, "Geopolitical demo", 12, C.muted, fontBold, 1.0);
  text(f, "Col3", 580, 292, 230, "Social governance transfer", 12, C.muted, fontBold, 1.0);
  map.forEach((m, i) => {
    const y = 334 + i * 72;
    rect(f, "Map Row", 84, y, 742, 52, i % 2 ? C.paper : C.paper2, 8, C.line);
    text(f, "Map A", 104, y + 15, 160, m[0], 13, C.ink, fontBold, 1.0);
    text(f, "Map B", 304, y + 12, 226, m[1], 12, C.muted, fontRegular, 1.2);
    text(f, "Map C", 580, y + 12, 210, m[2], 12, C.muted, fontRegular, 1.2);
  });

  card(f, "Closing", 906, 232, 422, 626, "Investor takeaway / 投资人判断点");
  text(f, "Takeaway 1", 940, 300, 320, "核心价值不是“模型很聪明”，而是把风险发现、解释、推演、压力测试和报告交付连成闭环。", 22, C.ink, fontBold, 1.28);
  text(f, "Takeaway 2", 940, 456, 314, "The platform turns uncertain events into auditable workflows for analysts, investors, and decision teams.", 15, C.muted, fontRegular, 1.35);
  [["Credible", "evidence-linked"], ["Actionable", "scenario paths"], ["Governed", "human review"], ["Extensible", "cross-domain"]].forEach((t, i) => {
    const y = 574 + i * 54;
    rect(f, "Takeaway Dot", 940, y + 6, 10, 10, i < 2 ? C.amber : C.green, 5);
    text(f, "Takeaway Key", 966, y, 98, t[0], 14, C.ink, fontBold, 1.0);
    text(f, "Takeaway Val", 1076, y, 156, t[1], 13, C.muted, fontRegular, 1.0);
  });
  footer(f);
  return f;
}

async function main() {
  await pickFonts();

  let page = figma.root.children.find(p => p.name === "Investor Demo - Risk Intelligence Twin");
  if (!page) page = figma.createPage();
  page.name = "Investor Demo - Risk Intelligence Twin";
  await figma.setCurrentPageAsync(page);
  for (const child of [...page.children]) child.remove();
  page.backgrounds = solid(C.bg);

  const gap = 180;
  const brief = createBrief(0);
  const risk = createRisk(W + gap);
  const evidence = createEvidence((W + gap) * 2);
  const scenario = createScenario((W + gap) * 3);
  const agents = createAgents((W + gap) * 4);
  const investor = createInvestor((W + gap) * 5);
  const report = createReport((W + gap) * 6);
  const transfer = createTransfer((W + gap) * 7);

  addReaction(brief.findOne(n => n.name === "Button / Start Risk Workspace"), risk.frame);
  addReaction(risk.primaryButton, evidence.frame);
  addReaction(evidence.primaryButton, scenario.frame);
  addReaction(scenario.primaryButton, agents.frame);
  addReaction(agents.primaryButton, investor.frame);
  addReaction(investor.primaryButton, report.frame);
  addReaction(report.primaryButton, transfer);

  figma.viewport.scrollAndZoomIntoView([brief]);
  return figma.closePlugin("Investor demo prototype generated: 8 linked frames.");
}

main().catch(err => {
  figma.closePlugin("Failed to generate investor demo: " + err.message);
});
