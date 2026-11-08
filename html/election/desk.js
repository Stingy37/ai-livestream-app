/* US midterms 2026 election desk (html/election-desk.html). Contract: docs/ELECTION.md "Page contract".
   Everything on screen during a scene comes from that scene's snapshot; desk.json feeds only the persistent chrome. */
"use strict";
const Q = new URLSearchParams(location.search);
const LANG = ["es", "ja", "zh"].includes(Q.get("lang")) ? Q.get("lang") : "es";
const STILL = Q.get("still");
const DEMO = Q.has("demo") || !!STILL;
const MOCK_ONLY = Q.get("demo") === "mock";
let INSTANT = false;
const $ = id => document.getElementById(id);
const STAGE = $("stage");
STAGE.classList.add("lang-" + LANG);
document.documentElement.lang = { es: "es", ja: "ja", zh: "zh-Hans" }[LANG];

/* =====================================================================  strings  */
const ET_OFF = -5, JST_OFF = 9, BJT_OFF = 8;     // fixed offsets: DST ended Nov 1 (docs/ELECTION.md)
const T = {
  es: {
    live: "EN VIVO", brandA: "ELECCIONES", brandB: "EE.UU. 2026", crawl: "AHORA",
    disc: "Guion escrito con IA y leído por una voz sintética. Resultados no oficiales de las oficinas electorales estatales. Sin afiliación con ningún medio, campaña ni gobierno.",
    test: "DATOS DE PRUEBA · TEST DATA",
    pcL1: s => `URNAS ${s}`, pcL2: tm => `CIERRAN ${tm} ET`, allL1: "TODAS LAS URNAS", allL2: "CERRADAS",
    hr: "HR", min: "MIN", sec: "SEG",
    senate: "Senado", usSenate: "Senado de EE.UU.", raceWord: "SENADO",
    stripOpen: tm => `CIERRE ${tm} ET`, stripNoCount: "SIN CONTEO OFICIAL", stripDecl: "AP DECLARÓ", ofTotal22: "DEL TOTAL 2022",
    balSenate: "SENADO", forMaj: "PARA MAYORÍA", dems: "DEMÓCRATAS", reps: "REPUBLICANOS", inds: "INDEP.", indsLong: "INDEPENDIENTES",
    notUp: "NO EN JUEGO", apShort: "AP",
    ahead: n => `${n} DE VENTAJA`, seatHeld: "ESCAÑO ACTUAL", special: "ELECCIÓN ESPECIAL", incumbent: "TITULAR",
    unofficial: "Resultados no oficiales", stale: "fuente sin cambios desde entonces", asOf: tm => `a las ${tm} ET`, precincts: (a, b, p) => `Precintos: ${a} de ${b} (${p}%)`,
    meterCap: "CONTADO VS. TOTAL 2022", pollsCloseAt: tm => `Las urnas cierran ${/^1:/.test(tm) ? "a la" : "a las"} ${tm} ET`, pollsClosedAt: tm => `Las urnas cerraron ${/^1:/.test(tm) ? "a la" : "a las"} ${tm} ET`, legend: "Leyenda", noCount: "Aún no hay conteo oficial publicado",
    president: "Presidente", counted22: p => `<b>${p}%</b> del total de 2022 contado`,
    vlSub: "Votos contados vs. 2022", vlTotal: "TOTAL DE LAS INTERMEDIAS 2022", vlCounted: "CONTADOS HASTA AHORA", vlPct: "DEL TOTAL DE 2022",
    vlList: "MÁS LEJOS DE SU TOTAL DE 2022", vlListBig: "MAYORES CONDADOS: CONTADO VS. 2022", vlListBigD: "MAYORES DISTRITOS: CONTADO VS. 2022", vlColPct: "% DE 2022", vlCol22: "TOTAL 2022", vlLegend: "Contado vs. 2022", vlBase: "base de comparación",
    cCounted: p => `<b>${p}%</b> de su total de 2022 contado`, c2024: "2024", c2022: n => `Total 2022: <b>${n}</b>`,
    margin: "Ventaja del líder", margin24: "Ventaja en 2024", noVotes: "Sin votos aún", tie: "Empate",
    senPrev: y => `${y} · SENADO`, pres24: "2024 · PRESIDENTE",
    senTitle: s => `Senadores de EE.UU. · ${s}`, senators: "Senadores actuales", seatUp: "1 ESCAÑO EN JUEGO", upIn: "EN JUEGO EN 2026", notUpTag: "NO EN JUEGO", nextUp: y => `PRÓXIMA: ${y}`,
    since: y => `DESDE ${y}`, running: "SE PRESENTA", notRunning: "NO SE PRESENTA", prevSeat: y => `ESTE ESCAÑO EN ${y}`, prevSrc: y => `Resultado oficial certificado de ${y}`,
    candTitle: s => `${s} · Candidatos al Senado`, bg: "Trayectoria", pos: "Propuestas (según el candidato)", age: a => `${a} años`,
    pcK: "CIERRE DE URNAS", pcS2: "CIERRAN LAS URNAS", pcSince: "DESDE EL CIERRE", pcDetail: (a, b) => { const al = t => (/^1:/.test(t) ? "a la" : "a las"); return a === b ? `Todas las urnas del estado cierran ${al(a)} <b>${a} ET</b>.` : `La mayor parte del estado cierra ${al(a)} <b>${a} ET</b>; las últimas urnas, ${al(b)} <b>${b} ET</b>.`; },
    rcvShort: "Voto por orden de preferencia: esta noche se cuentan las primeras preferencias.",
    seatNow: p => `Escaño actual: <b>${p}</b>`,
    natTitle: "Senado 2026: carreras en juego", seatsUp: n => `${n} ESCAÑOS EN JUEGO`, natScene: "Panorama nacional",
    lgNoRace: "Sin elección al Senado", lgOpen: "Urnas abiertas", lgClosed: "Urnas cerradas / conteo", lgDecl: "Declarado por AP (D / R)", lgFeat: "Carreras destacadas",
    stOpen: "URNAS ABIERTAS", stClosed: "URNAS CERRADAS", stCounting: "CONTEO", stDecl: "AP DECLARÓ",
    balTitle: "Control del Senado", undecided: n => `${n} CARRERAS SIN DECIDIR`, notUpPlus: (a, b) => `${a} NO EN JUEGO + ${b} AP`, majority: "PARA LA MAYORÍA",
    lgHold: "No en juego en 2026", lgApDecl: "Declarado por AP", lgUnd: "Sin decidir",
    balSrc: "Escaños: senadores que no están en juego + carreras declaradas por la agencia AP (citada de reportes de prensa).",
    racesTitle: "Carreras clave del Senado", leads: "LIDERA",
    schedTitle: "Cierre de urnas (hora del Este)", schedIn: "EN", schedSrc: "Horas oficiales de cierre de cada estado.",
    calledBy: "Declaraciones de ganador: The Associated Press",
  },
  ja: {
    live: "ライブ", brandA: "米中間選挙", brandB: "2026", crawl: "速報",
    disc: "原稿はAIが作成し、合成音声で読み上げています。数字は各州選挙当局の非公式開票結果です。報道機関・陣営・政府とは無関係です。",
    test: "テストデータ · TEST DATA",
    pcL1: s => `${s} 投票締切`, pcL2: tm => `米東部 ${tm}`, allL1: "全州で投票", allL2: "締め切り",
    hr: "時間", min: "分", sec: "秒",
    senate: "上院", usSenate: "米上院", raceWord: "上院",
    stripOpen: tm => `締切 米東部${tm}`, stripNoCount: "公式集計 未公表", stripDecl: "AP通信が報道", ofTotal22: "集計済み 2022年比",
    balSenate: "上院", forMaj: "過半数", dems: "民主党", reps: "共和党", inds: "無所属", indsLong: "無所属",
    notUp: "非改選", apShort: "AP",
    ahead: n => `${n}票リード`, seatHeld: "現在の議席", special: "補欠選挙", incumbent: "現職",
    unofficial: "非公式開票結果", stale: "以降の更新なし", asOf: tm => `米東部時間 ${tm} 時点`, precincts: (a, b, p) => `報告済み投票区 ${a} / ${b}（${p}%）`,
    meterCap: "集計済み 2022年比", pollsCloseAt: tm => `投票締め切り 米東部時間 ${tm}`, pollsClosedAt: tm => `米東部時間 ${tm} に投票締め切り`, legend: "凡例", noCount: "公式の集計はまだ公表されていません",
    president: "大統領選", counted22: p => `集計済み 2022年比 <b>${p}%</b>`,
    vlSub: "集計済み票数 2022年比", vlTotal: "2022年中間選挙の総票数", vlCounted: "これまでの集計", vlPct: "2022年の総数に対する割合",
    vlList: "2022年の総数に最も届いていない郡", vlListBig: "主要な郡の集計状況（2022年比）", vlListBigD: "主要な選挙区の集計状況（2022年比）", vlColPct: "2022年比", vlCol22: "2022年総数", vlLegend: "集計済み 2022年比", vlBase: "比較の基準",
    cCounted: p => `集計済み 2022年比 <b>${p}%</b>`, c2024: "2024年", c2022: n => `2022年の総数 <b>${n}</b>`,
    margin: "首位との差", margin24: "2024年の差", noVotes: "集計なし", tie: "同数",
    senPrev: y => `${y}年 上院選`, pres24: "2024年 大統領選",
    senTitle: s => `米上院議員 · ${s}`, senators: "現職の上院議員", seatUp: "改選 1議席", upIn: "2026年改選", notUpTag: "非改選", nextUp: y => `非改選（次は${y}年）`,
    since: y => `${y}年から`, running: "立候補", notRunning: "不出馬", prevSeat: y => `この議席の${y}年選挙`, prevSrc: y => `${y}年の確定公式結果`,
    candTitle: s => `${s} 上院選 候補者`, bg: "経歴", pos: "主張（本人の発言・公約より）", age: a => `${a}歳`,
    pcK: "投票締め切り", pcS2: "投票締め切り", pcSince: "締め切りから", pcDetail: (a, b) => a === b ? `州全体の投票締め切りは<b>米東部時間 ${a}</b>。` : `州の大部分は<b>米東部時間 ${a}</b>、最後の投票所は<b>${b}</b>に締め切り。`,
    rcvShort: "優先順位付き投票：今夜の数字は第1希望の票です。",
    seatNow: p => `現在の議席：<b>${p}</b>`,
    natTitle: "2026年 上院選の構図", seatsUp: n => `改選 ${n}議席`, natScene: "全米の情勢",
    lgNoRace: "上院選なし", lgOpen: "投票中", lgClosed: "投票締め切り・集計中", lgDecl: "AP通信が当選確実と報道（民 / 共）", lgFeat: "注目の選挙区",
    stOpen: "投票中", stClosed: "締め切り", stCounting: "集計中", stDecl: "AP報道",
    balTitle: "上院の勢力", undecided: n => `未確定 ${n}議席`, notUpPlus: (a, b) => `非改選${a} + AP${b}`, majority: "過半数",
    lgHold: "非改選", lgApDecl: "AP通信が当選確実と報道", lgUnd: "未確定",
    balSrc: "議席数：非改選の議員＋AP通信が当選確実と報じた選挙（報道より引用）。",
    racesTitle: "注目の上院選", leads: "リード",
    schedTitle: "投票締め切り（米東部時間）", schedIn: "あと", schedSrc: "各州の公式な投票締め切り時刻。",
    calledBy: "判定：AP通信",
  },
  zh: {
    live: "直播", brandA: "2026", brandB: "美国中期选举", crawl: "快讯",
    disc: "本节目由AI撰稿、合成语音播报。数据为各州选举机构公布的非正式计票结果。与任何新闻机构、竞选阵营或政府无关。",
    test: "测试数据 · TEST DATA",
    pcL1: s => `${s} 投票截止`, pcL2: tm => `美东 ${tm}`, allL1: "各州投票", allL2: "均已截止",
    hr: "时", min: "分", sec: "秒",
    senate: "参议院", usSenate: "美国参议院", raceWord: "参议院",
    stripOpen: tm => `美东${tm}截止`, stripNoCount: "尚无官方计票", stripDecl: "美联社宣布", ofTotal22: "已计票 / 2022年",
    balSenate: "参议院", forMaj: "过半", dems: "民主党", reps: "共和党", inds: "无党派", indsLong: "无党派",
    notUp: "非改选", apShort: "AP",
    ahead: n => `领先 ${n} 票`, seatHeld: "现任席位", special: "补选", incumbent: "现任",
    unofficial: "非官方结果", stale: "此后暂无更新", asOf: tm => `截至美东时间 ${tm}`, precincts: (a, b, p) => `已报告选区 ${a} / ${b}（${p}%）`,
    meterCap: "已计票 / 2022年总数", pollsCloseAt: tm => `美东时间 ${tm} 投票截止`, pollsClosedAt: tm => `投票已于美东时间 ${tm} 截止`, legend: "图例", noCount: "尚未公布官方计票",
    president: "总统选举", counted22: p => `已计票 = 2022年总数的 <b>${p}%</b>`,
    vlSub: "已计票数 对比 2022年", vlTotal: "2022年中期选举总票数", vlCounted: "目前已计票", vlPct: "占2022年总数",
    vlList: "距2022年总票数差距最大的县", vlListBig: "主要大县计票进度（对比2022年）", vlListBigD: "主要选区计票进度（对比2022年）", vlColPct: "占2022年", vlCol22: "2022年总数", vlLegend: "已计票 / 2022年", vlBase: "比较基准",
    cCounted: p => `已计票 = 2022年的 <b>${p}%</b>`, c2024: "2024年", c2022: n => `2022年总数 <b>${n}</b>`,
    margin: "领先幅度", margin24: "2024年差距", noVotes: "尚无票数", tie: "平票",
    senPrev: y => `${y}年 参议院`, pres24: "2024年 总统",
    senTitle: s => `美国参议员 · ${s}`, senators: "现任参议员", seatUp: "1席改选", upIn: "2026年改选", notUpTag: "非改选", nextUp: y => `非改选（下次${y}年）`,
    since: y => `${y}年起`, running: "参选", notRunning: "不参选", prevSeat: y => `该席位${y}年选举`, prevSrc: y => `${y}年官方认证结果`,
    candTitle: s => `${s} 参议员候选人`, bg: "背景", pos: "政见（据候选人本人表述）", age: a => `${a}岁`,
    pcK: "投票截止", pcS2: "投票截止", pcSince: "截止后", pcDetail: (a, b) => a === b ? `全州投票于<b>美东时间 ${a}</b>截止。` : `全州大部分地区<b>美东时间 ${a}</b>截止，最后一批投票站<b>${b}</b>截止。`,
    rcvShort: "排序复选制：今晚公布的是第一选择票数。",
    seatNow: p => `现任席位：<b>${p}</b>`,
    natTitle: "2026年参议院选举", seatsUp: n => `改选 ${n} 席`, natScene: "全国形势",
    lgNoRace: "无参议院选举", lgOpen: "投票中", lgClosed: "投票截止 / 计票中", lgDecl: "美联社宣布胜选（民 / 共）", lgFeat: "重点选区",
    stOpen: "投票中", stClosed: "已截止", stCounting: "计票中", stDecl: "美联社宣布",
    balTitle: "参议院席位", undecided: n => `${n}席未定`, notUpPlus: (a, b) => `非改选${a} + AP${b}`, majority: "过半数",
    lgHold: "2026年非改选", lgApDecl: "美联社宣布胜选", lgUnd: "未定",
    balSrc: "席位：非改选参议员 + 美联社宣布胜选的选区（引自新闻报道）。",
    racesTitle: "重点参议院选举", leads: "领先",
    schedTitle: "投票截止时间（美东时间）", schedIn: "还有", schedSrc: "各州官方投票截止时间。",
    calledBy: "胜选判定：美联社",
  },
}[LANG];
const PARTY_CHIP = { es: { DEM: "D", REP: "R", IND: "I", LIB: "L", GRN: "V" }, ja: { DEM: "民", REP: "共", IND: "無", LIB: "リ", GRN: "緑" },
                     zh: { DEM: "民", REP: "共", IND: "独", LIB: "自", GRN: "绿" } }[LANG];
const PARTY_WORD = { es: { DEM: "DEMÓCRATA", REP: "REPUBLICANO", IND: "INDEPENDIENTE" }, ja: { DEM: "民主党", REP: "共和党", IND: "無所属" },
                     zh: { DEM: "民主党", REP: "共和党", IND: "无党派" } }[LANG];
const INITIALS = { paxton: "KP", talarico: "JT", sullivan: "DS", sullivan_j: "DJS", peltola: "MP", marshall: "RM", hamilton: "AH", collins: "SC",
                   jackson: "TJ", husted: "JH", brown: "SB", elsayed: "AE", rogers: "MR" };

/* =====================================================================  utils  */
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtInt = n => (n == null || isNaN(n)) ? "" : Math.round(n).toLocaleString("en-US");
const fmtPct = p => (p == null || isNaN(p)) ? "" : (+p).toFixed(1);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const pt = p => ["DEM", "REP"].includes(p) ? p : (p ? "IND" : "IND");
const chip = p => PARTY_CHIP[p] || (p ? p[0] : "?");
const isCJK = s => /[぀-ヿ㐀-鿿]/.test(s || "");
function div(cls, html) { const d = document.createElement("div"); if (cls) d.className = cls; if (html != null) d.innerHTML = html; return d; }
function splitName(name) {
  name = String(name || "").trim();
  for (const sep of ["・", "·", "･", "•"]) if (name.includes(sep)) { const p = name.split(sep); return { first: p.slice(0, -1).join(sep), last: p[p.length - 1] }; }
  if (isCJK(name)) return { first: "", last: name };
  const parts = name.split(/\s+/); if (parts.length < 2) return { first: "", last: name };
  let k = parts.length - 1; if (/^(Jr\.?|Sr\.?|II|III|IV)$/i.test(parts[k]) && k > 1) k--;
  return { first: parts.slice(0, k).join(" "), last: parts.slice(k).join(" ") };
}
function initials(c) {
  if (c.key && INITIALS[c.key]) return INITIALS[c.key];
  const n = c.name || "";
  if (!isCJK(n)) { const s = splitName(n); return ((s.first[0] || "") + (s.last[0] || "")).toUpperCase() || "?"; }
  const s = splitName(n); return [...s.last][0] || "?";
}
/* times: ISO -> fixed-offset wall clock */
function wall(ms, off) { const d = new Date(ms + off * 3600e3); return { h: d.getUTCHours(), m: d.getUTCMinutes(), s: d.getUTCSeconds(), d }; }
const pad = n => String(n).padStart(2, "0");
function tET(iso, compact) {                // "9:00 PM" (es) / "21:00" (ja, zh); compact: "9P" / "21:00"
  const ms = typeof iso === "number" ? iso : Date.parse(iso); if (isNaN(ms)) return "";
  const w = wall(ms, ET_OFF);
  if (LANG === "es") { const h12 = (w.h % 12) || 12, ap = w.h < 12 ? "AM" : "PM"; return compact ? `${h12}${w.m ? ":" + pad(w.m) : ""}${ap[0]}` : `${h12}:${pad(w.m)} ${ap}`; }
  return `${w.h}:${pad(w.m)}`;
}
function srcLine(snap) {
  const parts = [esc(T.unofficial), "<b>" + esc(snap.source || "") + "</b>"]; if (snap.as_of) parts.push(esc(T.asOf(tET(snap.as_of))));
  return parts.join(" · ");
}
/* text fitting: never wrap; compress to 80 %, then shrink the font in 6 % steps (visual_style.md s3) */
function fitNode(n, avail) {
  if (!n || !(avail > 0)) return;
  n.style.transform = ""; n.style.fontSize = "";
  let w = n.scrollWidth; if (w <= avail) return;
  if (w * 0.8 <= avail) { n.style.transform = `scaleX(${(avail / w).toFixed(4)})`; return; }
  const fs0 = parseFloat(getComputedStyle(n).fontSize); let f = fs0;
  for (let i = 0; i < 12 && w * 0.8 > avail; i++) { f *= 0.94; n.style.fontSize = f.toFixed(1) + "px"; w = n.scrollWidth; }
  if (w > avail) n.style.transform = `scaleX(${(avail / w).toFixed(4)})`;
}
function fitAll(root) {
  root.querySelectorAll(".fit").forEach(n => {
    const p = n.parentElement; const cs = getComputedStyle(p);
    let avail = n.dataset.w ? +n.dataset.w : p.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    if (n.dataset.sub) avail -= [...p.children].filter(c => c !== n).reduce((a, c) => a + c.offsetWidth + 12, 0);
    fitNode(n, avail);
  });
}
/* fit a block of wrapped text into its box by shrinking the font */
function fitBlock(box, minPx) {
  let guard = 0; const items = box.querySelectorAll("li,h4");
  while (box.scrollHeight > box.clientHeight + 1 && guard++ < 14) {
    items.forEach(n => { const f = parseFloat(getComputedStyle(n).fontSize); if (f > (minPx || 15)) n.style.fontSize = (f * 0.94).toFixed(1) + "px"; });
  }
}
/* number roll-up (T3): 600 ms ease-out, tabular figures */
const ROLLS = new Set();
const easeOut = p => 1 - Math.pow(1 - p, 3);
function roll(n, to, fmt, opt) {
  opt = opt || {}; if (to == null || isNaN(to)) { n.innerHTML = ""; return; }
  const from = opt.from != null ? opt.from : 0;
  if (INSTANT) { n.innerHTML = fmt(to); return; }
  n.innerHTML = fmt(from); ROLLS.add({ n, from, to, fmt, t0: performance.now() + (opt.delay || 0), dur: opt.dur || 600 });
}
const fPct = v => `${(+v).toFixed(1)}<sup>%</sup>`;
const fInt = v => fmtInt(v);
function tickRolls(now) {
  for (const r of ROLLS) { const p = (now - r.t0) / r.dur; if (p < 0) continue; const e = p >= 1 ? 1 : easeOut(p); r.n.innerHTML = r.fmt(r.from + (r.to - r.from) * e); if (p >= 1) ROLLS.delete(r); }
}

/* =====================================================================  clock  */
let CLOCK_OFF = 0;
const now = () => Date.now() + CLOCK_OFF;

/* =====================================================================  geometry  */
const GEO = { us: null, st: {} };
function rewind(fc) {
  for (const f of fc.features || []) {
    const g = f.geometry; if (!g) continue;
    const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
    for (const poly of polys) if (d3.geoArea({ type: "Polygon", coordinates: poly }) > 2 * Math.PI) poly.forEach(r => r.reverse());
  }
  return fc;
}
async function getJSON(url) { const r = await fetch(url, { cache: "no-store" }); if (!r.ok) throw new Error(url + " " + r.status); return r.json(); }
async function loadUS() { if (!GEO.us) { GEO.us = rewind(await getJSON("election/geo/us-states.json")); GEO.usById = new Map(GEO.us.features.map(f => [f.properties.id, f])); } return GEO.us; }
async function loadState(st, path) {
  if (!GEO.st[st]) GEO.st[st] = getJSON(path || `election/geo/${st}.json`).then(rewind).catch(e => { console.warn("geo", st, e); return { type: "FeatureCollection", features: [] }; });
  return GEO.st[st];
}
function projState(st, extent, feat) {
  const p = st === "AK" ? d3.geoConicEqualArea().rotate([154, 0]).center([-2, 58.5]).parallels([55, 65])
                        : d3.geoConicEqualArea().rotate([96, 0]).center([-0.6, 38.7]).parallels([29.5, 45.5]);
  return p.fitExtent(extent, feat);
}
const RAMP = { DEM: ["#0A3C99", "#1F6FD1", "#7FB0EE", "#C6DBF7"], REP: ["#A3000D", "#D0142E", "#F07E86", "#F8C9CC"], IND: ["#3E4350", "#5B5F6B", "#8D919B", "#BFC2C9"] };
const NODATA = "#8A8F9C", TIE = "#9AA3B5";
function ramp(p, m) { const R = RAMP[pt(p)]; if (m == null || isNaN(m)) return NODATA; if (m === 0) return TIE; return m >= 20 ? R[0] : m >= 10 ? R[1] : m >= 5 ? R[2] : R[3]; }
const VL_RAMP = ["#5d5a48", "#8d7f3c", "#bba433", "#F1DD20"];
function vlColor(p) { if (p == null || isNaN(p) || p <= 0) return NODATA; return p >= 75 ? VL_RAMP[3] : p >= 50 ? VL_RAMP[2] : p >= 25 ? VL_RAMP[1] : VL_RAMP[0]; }
const SVGNS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs, parent) { const e = document.createElementNS(SVGNS, tag); for (const k in attrs || {}) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }

/* A state map: neighbours, units (counties / districts) and the state outline, in stage coordinates. */
async function stateMap(snap, opt) {
  const st = snap.state; await loadUS();
  const sfeat = GEO.usById.get(st); const units = await loadState(st, snap.units && snap.units.geo && snap.units.geo.replace(/^\/?/, ""));
  const extent = opt.extent; const P = projState(st, extent, sfeat); const path = d3.geoPath(P);
  const wrap = div("mapwrap"); const svg = svgEl("svg", { width: 1920, height: 840, viewBox: "0 0 1920 840" }); wrap.appendChild(svg);
  if (opt.neighbours !== false) {
    const g = svgEl("g", { class: "nb" }, svg);
    for (const f of GEO.us.features) {
      if (f.properties.id === st) continue; const b = path.bounds(f);
      if (!(b[1][0] > -40 && b[0][0] < 1960 && b[1][1] > -40 && b[0][1] < 880)) continue;
      svgEl("path", { d: path(f) }, g);
    }
  }
  const gu = svgEl("g", { class: "units" }, svg); const els = new Map(), feats = new Map();
  for (const f of units.features) {
    const id = f.properties.id; const e = svgEl("path", { d: path(f), fill: opt.fill ? opt.fill(id) : "#59637d" }, gu); els.set(id, e); feats.set(id, f);
  }
  const outline = path(sfeat);
  svgEl("path", { d: outline, class: "souter" }, svg); svgEl("path", { d: outline, class: "souter2" }, svg);
  const dim = div("dim"); wrap.appendChild(dim);
  const fx = svgEl("svg", { width: 1920, height: 840, viewBox: "0 0 1920 840" }); wrap.appendChild(fx);
  return { wrap, svg, fx, P, path, els, feats, sfeat, extent, units };
}
function setZoom(wrap, k, tx, ty, dur) {
  wrap.classList.add("anim"); wrap.style.transition = (dur && !INSTANT) ? `transform ${dur}ms var(--e-io)` : "none";
  wrap.style.transform = (k === 1 && !tx && !ty) ? "" : `translate(${tx.toFixed(1)}px,${ty.toFixed(1)}px) scale(${k.toFixed(4)})`;
  wrap._z = { k, tx, ty }; clearTimeout(wrap._zt);
  wrap._zt = setTimeout(() => { wrap.classList.remove("anim"); wrap.style.setProperty("--k", k); }, INSTANT ? 0 : (dur || 0) + 60);
  if (INSTANT) { wrap.classList.remove("anim"); wrap.style.setProperty("--k", k); }
}
function zoomBox(wrap, b, target, kmin, kmax, dur) {
  const bw = Math.max(1, b[1][0] - b[0][0]), bh = Math.max(1, b[1][1] - b[0][1]);
  const k = clamp(Math.min(target.w / bw, target.h / bh), kmin, kmax);
  const cx = (b[0][0] + b[1][0]) / 2, cy = (b[0][1] + b[1][1]) / 2;
  setZoom(wrap, k, target.x + target.w / 2 - k * cx, target.y + target.h / 2 - k * cy, dur);
  return wrap._z;
}
const toScreen = (z, p) => [z.k * p[0] + z.tx, z.k * p[1] + z.ty];
/* the focus stroke (CNN double stroke) drawn in the map's top layer, constant on-screen width at the target zoom */
function focusPath(m, id, k, fill) {
  m.fx.innerHTML = ""; if (!id || !m.els.has(id)) return;
  const d = m.els.get(id).getAttribute("d");
  svgEl("path", { d, fill: "none", stroke: "#000", "stroke-width": (10 / k).toFixed(2), "stroke-linejoin": "round" }, m.fx);
  svgEl("path", { d, fill: fill || m.els.get(id).getAttribute("fill"), stroke: "#fff", "stroke-width": (6 / k).toFixed(2), "stroke-linejoin": "round" }, m.fx);
}
/* callout box + leader line, placed beside a screen-space anchor inside a free region */
function placeCallout(vis, box, line, anchor, region, sb) {
  box.style.left = "0px"; box.style.top = "0px";
  const W = box.offsetWidth, H = box.offsetHeight; const gap = 44;
  const bx0 = sb ? sb[0][0] : anchor[0] - 20, bx1 = sb ? sb[1][0] : anchor[0] + 20;
  let x = bx1 + gap, side = 1;
  if (x + W > region.x1) { x = bx0 - gap - W; side = -1; }
  if (x < region.x0) { x = clamp(anchor[0] + gap, region.x0, region.x1 - W); side = 1; }
  const y = clamp(anchor[1] - H / 2, region.y0, region.y1 - H);
  box.style.left = x + "px"; box.style.top = y + "px"; box.style.transformOrigin = side > 0 ? "0 50%" : "100% 50%";
  const ex = side > 0 ? x : x + W, ey = clamp(anchor[1], y + 12, y + H - 12);
  const dx = ex - anchor[0], dy = ey - anchor[1]; const len = Math.hypot(dx, dy);
  line.style.left = anchor[0] + "px"; line.style.top = anchor[1] + "px"; line.style.width = len + "px";
  line.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
  let dot = vis.querySelector(".cdot"); if (!dot) { dot = div("cdot"); vis.appendChild(dot); }
  dot.style.left = anchor[0] + "px"; dot.style.top = anchor[1] + "px"; dot.classList.add("on");
}
const screenBox = (z, b) => [toScreen(z, b[0]), toScreen(z, b[1])];
const cap1 = s => (LANG === "es" && s) ? String(s).charAt(0).toUpperCase() + String(s).slice(1) : s;
function unitName(snap, id) {
  const r = (snap.units && snap.units.rows || []).find(x => x.id === id); if (r && r.name) return cap1(r.name);
  const f = GEO.st[snap.state + "_f"] && GEO.st[snap.state + "_f"].get(id); return f ? f.properties.name : id;
}

/* =====================================================================  components  */
function monoHTML(c, extra) {
  const p = pt(c.party);
  return `<div class="mono p-${p}"><span class="ini">${esc(initials(c))}</span><span class="pl">${esc(chip(p))}</span>${extra || ""}</div>`;
}
function wallTitle(main, year, sub, d) {
  return `<div class="wt"><div class="t wipe" style="--d:${d || 0}ms"><span class="fit" data-w="1100">${esc(main)}${year ? `<i>${esc(year)}</i>` : ""}</span></div><br>` +
         (sub ? `<div class="s bl" style="--d:${(d || 0) + 220}ms">${esc(sub)}</div>` : "") + `</div>`;
}
function wallRow(c, i, avail, opt) {
  opt = opt || {}; const p = pt(c.party); const s = splitName(c.name || c.short);
  const st = avail ? `<div class="st rise" style="--d:${534 + i * 60}ms"><div class="v num" data-roll="${c.votes != null ? c.votes : ""}"></div><div class="p num" data-rollp="${c.pct != null ? c.pct : ""}"></div></div>`
                   : `<div class="st none rise" style="--d:${534 + i * 60}ms">${opt.msg ? `<div class="msg">${esc(opt.msg)}</div>` : ""}</div>`;
  return `<div class="wrow p-${p} bi" style="--d:${480 + i * 60}ms" data-key="${esc(c.key || "")}">${monoHTML(c)}
    <div class="nm"><div class="f"><span class="fit">${esc(s.first)}</span></div><div class="l"><span class="fit">${esc(s.last)}</span></div></div>${st}</div>`;
}
function startRolls(root, delay) {
  root.querySelectorAll("[data-roll]").forEach(n => { const v = n.dataset.roll; if (v !== "") roll(n, +v, fInt, { delay }); else n.innerHTML = ""; });
  root.querySelectorAll("[data-rollp]").forEach(n => { const v = n.dataset.rollp; if (v !== "") roll(n, +v, fPct, { delay }); else n.innerHTML = ""; });
}
function meterHTML(pct, cap) {
  const lit = pct == null ? 0 : clamp(Math.round(pct / 10), pct > 0 ? 1 : 0, 10);
  return `<div class="meter"><div class="row"><div class="val num">${pct == null ? "–" : fmtPct(pct)}<small>%</small></div><div class="segs">${
    Array.from({ length: 10 }, (_, i) => `<i class="${i < lit ? "lit" : ""}"></i>`).join("")}</div></div><div class="cap">${esc(cap)}</div></div>`;
}
function seatParty(snap) { const s = (snap.senators || []).find(x => x.up); return s ? (s.party_label || PARTY_WORD[s.party] || s.party) : ""; }
function legendRamp(title, parties) {
  return `<div class="lh">${esc(title)}</div>` + parties.map(p => `<div class="li"><span class="ramp">${RAMP[p].map(c => `<i style="background:${c}"></i>`).join("")}</span><span>${esc(PARTY_WORD[p] || p)}</span></div>`).join("") +
    `<div class="li"><span class="sw" style="background:${NODATA}"></span><span>${esc(T.noVotes)}</span></div>` +
    `<div class="li" style="font-size:17px;color:#aeb4c4"><span>≥20 · 10–20 · 5–10 · &lt;5 pts</span></div>`;
}
const onCard = snap => { const c = snap.candidates || []; const f = c.filter(x => x.on_card !== false); return (f.length ? f : c).slice(0, 4); };
const isAvail = snap => !!(snap.results_available && snap.phase !== "preview");
const previewMsg = snap => snap.phase === "preview" ? T.pollsCloseAt(tET(snap.poll_close && snap.poll_close.last_et)) : T.noCount;

/* =====================================================================  visuals  */
const V = {};
const MAP_TARGET = { x: 1020, y: 200, w: 380, h: 340 };    // where a focused unit lands (right of the board)

/* ---------- st_results: CNN board ---------- */
V.st_results = async (snap) => {
  const el = div("vis v-results"); const avail = isAvail(snap); const cands = onCard(snap);
  const rows = cands.map((c, i) => {
    const s = splitName(c.name); const p = pt(c.party);
    return `<div class="brow p-${p} bi" style="--d:${534 + i * 60}ms;position:relative" data-key="${esc(c.key)}">${monoHTML(c)}
      <div class="plate"><div class="names"><div class="f"><span class="fit" data-sub="1">${esc(s.first)}</span>${c.incumbent ? `<span class="itag">${esc(T.incumbent)}</span>` : ""}</div>
      <div class="l"><span class="fit">${esc(s.last)}</span></div></div>
      ${avail ? `<div class="num">${c.ahead_by ? `<div class="ahead">${esc(T.ahead(fmtInt(c.ahead_by)))}</div>` : ""}<div class="votes" data-roll="${c.votes != null ? c.votes : ""}"></div></div>` : ""}</div>
      <div class="pct ${avail ? "" : "none"}">${avail ? `<span data-rollp="${c.pct != null ? c.pct : ""}"></span>` : ""}</div>
      <i class="rdim"></i></div>`;
  }).join("");
  const prec = snap.precincts && snap.precincts.total ? T.precincts(fmtInt(snap.precincts.reporting), fmtInt(snap.precincts.total), fmtPct(100 * snap.precincts.reporting / snap.precincts.total)) : "";
  const cv = snap.counted_vs_2022 || {};
  el.innerHTML = `<div class="board">
    <div class="hd wipe" style="--d:0ms"><div class="tab"><b>${esc(snap.state)}</b><span>2026</span></div><div class="nm"><span class="fit">${esc(snap.state_name)}</span></div>
      <div class="seat"><div class="c">${esc(snap.special ? T.special : T.seatHeld)}</div><div class="v">${esc(seatParty(snap))}</div></div></div>
    <div class="body"><div class="bl" style="--d:400ms"><span class="tag">${esc(T.usSenate)}</span>${snap.special ? `<span class="tag sp">${esc(T.special)}</span>` : ""}</div>
      <div class="brows">${rows}</div>
      ${avail ? "" : `<div class="msg fadein" style="--d:900ms">${esc(previewMsg(snap))}</div>`}
      ${snap.rcv_note ? `<div class="rcv fadein" style="--d:1000ms">${esc(snap.rcv_note)}</div>` : ""}
      ${snap.call ? `<div class="call fadein" style="--d:1000ms"><b>${esc(snap.call.text || "")}</b><br>${esc(snap.call.credit || "")}</div>` : ""}
      <div class="ft fadein" style="--d:1200ms"><div class="src">${avail ? srcLine(snap) : esc(snap.source || "")}${prec ? "<br>" + esc(prec) : ""}</div>
        ${avail ? meterHTML(cv.pct, T.meterCap) : ""}</div></div></div>`;
  const board = el.querySelector(".board");
  return {
    el,
    layout() { const h = board.offsetHeight; board.style.top = Math.max(40, Math.round(40 + (786 - h) / 2)) + "px"; },
    enter() { startRolls(el, 1000); },
    focus(f) { const br = el.querySelector(".brows"); br.classList.toggle("hasfocus", !!f && !!br.querySelector(`[data-key="${CSS.escape(f)}"]`));
      br.querySelectorAll(".brow").forEach(r => r.classList.toggle("focus", r.dataset.key === f)); },
  };
};

/* ---------- county-style map visuals (st_counties / st_votes_left / st_history) share this ---------- */
async function mapVisual(snap, kind) {
  const el = div("vis v-" + kind); const avail = isAvail(snap); const st = snap.state;
  const rows = new Map((snap.units && snap.units.rows || []).map(r => [r.id, r]));
  const hist = (snap.history && snap.history.units) || {};
  const cands = snap.candidates || []; const partyOf = k => (cands.find(c => c.key === k) || {}).party;
  const showHist = kind === "st_history" || (kind === "st_counties" && !avail);
  const fill = kind === "st_votes_left" ? (id => { const r = rows.get(id); return vlColor(r && r.counted_vs_2022_pct); })
             : showHist ? (id => { const h = hist[id]; return h ? ramp(h.winner, h.margin_pts) : NODATA; })
             : (id => { const r = rows.get(id); return (r && r.total && r.leader) ? ramp(partyOf(r.leader), r.margin_pts) : NODATA; });
  const ak = st === "AK";
  const ext = ak ? [[kind === "st_votes_left" ? 780 : 700, 90], [1490, 770]] : kind === "st_votes_left" ? [[790, 70], [1840, 815]] : [[700, 70], [1840, 815]];
  const m = await stateMap(snap, { extent: ext, fill });
  el.appendChild(m.wrap);
  GEO.st[st + "_f"] = m.feats;
  /* Anchorage inset (Alaska house districts there are tiny) */
  let inset = null;
  if (ak) {
    const box = kind === "st_votes_left" ? { x: 1520, y: 120, w: 320, h: 380 } : { x: 1510, y: 120, w: 330, h: 400 };
    const anc = m.units.features.filter(f => { const c = d3.geoCentroid(f), b = d3.geoBounds(f); return c[0] > -150.1 && c[0] < -149.7 && c[1] > 61.08 && c[1] < 61.30 && (b[1][0] - b[0][0]) < 0.4; });
    if (anc.length) {
      const fc = { type: "FeatureCollection", features: anc };
      const P2 = projState("AK", [[box.x + 12, box.y + 34], [box.x + box.w - 12, box.y + box.h - 10]], fc); const path2 = d3.geoPath(P2);
      const idiv = div("inset"); idiv.style.cssText = `left:${box.x}px;top:${box.y}px;width:${box.w}px;height:${box.h}px`;
      idiv.innerHTML = `<div class="it">Anchorage</div>`; el.appendChild(idiv);
      const isvg = svgEl("svg", { width: 1920, height: 840, viewBox: "0 0 1920 840", style: "position:absolute;left:0;top:0;z-index:4;pointer-events:none;overflow:visible" });
      const g = svgEl("g", { class: "units" }, isvg); const iels = new Map();
      for (const f of anc) iels.set(f.properties.id, svgEl("path", { d: path2(f), fill: fill(f.properties.id) }, g));
      const fxg = svgEl("g", {}, isvg); el.appendChild(isvg);
      const b = d3.geoPath(m.P).bounds(fc); const r = svgEl("rect", { x: b[0][0] - 4, y: b[0][1] - 4, width: b[1][0] - b[0][0] + 8, height: b[1][1] - b[0][1] + 8, fill: "none", stroke: "#fff", "stroke-width": 2 }, m.svg);
      inset = { ids: new Set(anc.map(f => f.properties.id)), path2, iels, fxg, box, rect: r };
    }
  }
  /* left panel */
  const nm = snap.state_name; let html = "";
  const h24 = snap.history && snap.history.pres2024 || {};
  const histRows = () => {
    const a = [{ key: "_d", name: h24.dem_name, party: "DEM", votes: h24.dem, pct: h24.dem_pct }, { key: "_r", name: h24.rep_name, party: "REP", votes: h24.rep, pct: h24.rep_pct }];
    return a.sort((x, y) => (y.pct || 0) - (x.pct || 0));
  };
  const monoParty = r => Object.assign({}, r, { key: "", name: r.name });
  if (kind === "st_counties") {
    html += avail ? wallTitle(nm, "2026", snap.race_label) : wallTitle(nm, "2024", T.president);
    const list = avail ? onCard(snap).slice(0, 2) : histRows().map(monoParty);
    html += `<div class="wrows" style="top:262px">${list.map((c, i) => wallRow(c, i, true)).join("")}
      <div class="wnote fadein" style="--d:1150ms">${avail ? T.counted22(fmtPct(snap.counted_vs_2022 && snap.counted_vs_2022.pct)) : esc(previewMsg(snap))}</div>
      ${avail && snap.precincts && snap.precincts.total ? `<br><div class="wnote fadein" style="--d:1200ms">${esc(T.precincts(fmtInt(snap.precincts.reporting), fmtInt(snap.precincts.total), fmtPct(100 * snap.precincts.reporting / snap.precincts.total)))}</div>` : ""}
      ${snap.rcv_note && avail ? `<br><div class="wnote fadein" style="--d:1250ms;white-space:normal;width:592px;font-size:21px">${esc(snap.rcv_note)}</div>` : ""}</div>`;
    html += `<div class="srcline fadein" style="position:absolute;left:80px;top:${ak ? 800 : 800}px;--d:1300ms">${avail ? srcLine(snap) : esc(T.c2024 + " · " + T.president)}</div>`;
    html += `<div class="legend fadein" style="left:${ak ? 1530 : 1560}px;top:${ak ? 560 : 600}px;--d:1300ms">${legendRamp(showHist ? T.margin24 : T.margin, ["DEM", "REP"])}</div>`;
  } else if (kind === "st_history") {
    html += `<div class="htitle">${wallTitle(nm, "2024", T.president)}</div>`;
    const hr = histRows();
    html += `<div class="wrows hrows" style="top:262px">${hr.map((c, i) => wallRow(monoParty(c), i, true)).join("")}</div>`;
    const sp = snap.history && snap.history.sen_prev;
    if (sp) {
      const cells = [{ n: sp.dem_name, p: sp.dem_pct, party: sp.dem_is_independent ? "IND" : "DEM" }, { n: sp.rep_name, p: sp.rep_pct, party: "REP" }].sort((a, b) => (b.p || 0) - (a.p || 0));
      html += `<div class="hcols fadein" style="top:560px;--d:1100ms"><div class="hcol"><div class="hh">${esc(T.senPrev(sp.year))}</div>${cells.map((c, i) =>
        `<div class="hcell p-${c.party} ${i === 0 ? "win" : ""}"><div class="n">${esc(splitName(c.n).last)}</div><div class="p">${fmtPct(c.p)}%</div></div>`).join("")}</div></div>`;
    }
    html += `<div class="legend fadein" style="left:${ak ? 1530 : 1560}px;top:${ak ? 560 : 600}px;--d:1300ms">${legendRamp(T.margin24, ["DEM", "REP"])}</div>`;
    html += `<div class="ctx" style="position:absolute;z-index:6;font:500 24px var(--f-sans);color:#fff;text-shadow:0 2px 4px #000;white-space:nowrap;opacity:0;transition:opacity 250ms linear"></div>`;
  } else {   /* st_votes_left */
    html += wallTitle(nm, "2026", T.vlSub);
    const cv = Object.assign({}, snap.counted_vs_2022 || {});
    if (!cv.total2022) { const sum = [...rows.values()].reduce((a, r) => a + (r.total2022 || r.turnout2022 || 0), 0); if (sum) cv.total2022 = sum; }
    const unitWord = snap.units && snap.units.type === "house_district" ? "d" : "c";
    if (avail) {
      const pc = cv.pct;
      html += `<div class="vlpanel"><div class="vlbig bi" style="--d:520ms"><span class="eq">=</span><span class="nb" data-rollp="${pc != null ? pc : ""}"></span></div>
        <div class="vlcap bi" style="--d:580ms">${esc(T.vlPct)}</div>
        <div class="vlbar rise" style="--d:640ms"><i style="transform:scaleX(${clamp((pc || 0) / 100, 0, 1)})"></i></div>
        <div class="vltwo bi" style="--d:700ms"><div class="vlb"><div class="lb"><span class="dot"></span>${esc(T.vlCounted)}</div><div class="nb" data-roll="${cv.counted != null ? cv.counted : ""}"></div></div>
          <div class="vlb"><div class="lb">${esc(T.vlTotal)}</div><div class="nb" data-roll="${cv.total2022 || ""}"></div></div></div>
        ${snap.precincts && snap.precincts.total ? `<div class="srcline" style="margin-top:8px">${esc(T.precincts(fmtInt(snap.precincts.reporting), fmtInt(snap.precincts.total), fmtPct(100 * snap.precincts.reporting / snap.precincts.total)))}</div>` : ""}</div>`;
      let list;
      if (Array.isArray(snap.votes_left) && snap.votes_left.length) {
        list = snap.votes_left.slice(0, 6).map(x => { const r = rows.get(x.id) || {}; return { id: x.id, name: x.name || r.name || x.short || unitName(snap, x.id),
          pct: x.pct != null ? x.pct : x.counted_vs_2022_pct, counted: x.counted, total2022: x.total2022 }; });
      } else {
        const gap = r => { const t22 = r.total2022 || r.turnout2022 || ((r.counted_vs_2022_pct > 0) ? r.total * 100 / r.counted_vs_2022_pct : null); return t22 == null ? -1 : t22 - (r.total || 0); };
        list = [...rows.values()].filter(r => r.counted_vs_2022_pct != null || r.total2022 || r.turnout2022).sort((a, b) => gap(b) - gap(a)).slice(0, 6)
          .map(r => ({ id: r.id, name: r.name, pct: r.counted_vs_2022_pct, total2022: r.total2022 || r.turnout2022 }));
      }
      const listTitle = Array.isArray(snap.votes_left) && snap.votes_left.length ? (unitWord === "d" ? T.vlListBigD : T.vlListBig) : T.vlList;
      html += `<div class="vllist fadein" style="--d:1150ms"><h5>${esc(listTitle)}</h5><div class="vlh"><span></span><span>${esc(T.vlColPct)}</span><span>${esc(T.vlCol22)}</span></div>${list.map(r => `<div class="vlr" data-id="${esc(r.id || "")}"><span class="n"><span class="fit">${esc(cap1(r.name))}</span></span><span class="bar"><i style="width:${clamp(r.pct || 0, 0, 100)}%"></i></span><span class="p">${r.pct != null ? fmtPct(r.pct) + "%" : "–"}</span><span class="t">${r.total2022 ? fmtInt(r.total2022) : ""}</span></div>`).join("")}</div>`;
    } else {
      html += `<div class="vlpanel">${cv.total2022 ? `<div class="vltwo bi" style="--d:560ms"><div class="vlb"><div class="lb">${esc(T.vlTotal)}</div><div class="nb" data-roll="${cv.total2022}"></div><div class="cap">${esc(T.vlBase)}</div></div></div>` : ""}
        <div class="vlmsg bi" style="--d:640ms"><span class="fit" data-w="700">${esc(previewMsg(snap))}</span></div></div>`;
    }
    html += `<div class="srcline fadein" style="position:absolute;left:80px;top:804px;--d:1300ms">${avail ? srcLine(snap) : esc(snap.source || "")}</div>`;
    html += `<div class="legend fadein" style="left:${ak ? 1560 : 1590}px;top:${ak ? 540 : 640}px;--d:1300ms"><div class="lh">${esc(T.vlLegend)}</div>${
      [["≥75%", VL_RAMP[3]], ["50–75%", VL_RAMP[2]], ["25–50%", VL_RAMP[1]], ["<25%", VL_RAMP[0]], [T.noVotes, NODATA]].map(([l, c]) => `<div class="li"><span class="sw" style="background:${c}"></span><span>${esc(l)}</span></div>`).join("")}</div>`;
  }
  const panel = div("", html); while (panel.firstChild) el.appendChild(panel.firstChild);
  const callout = div("callout"), line = div("leader"); el.appendChild(line); el.appendChild(callout);
  const hrowsData = kind === "st_history" ? histRows() : null;
  let cur = null;
  function calloutHTML(id) {
    const r = rows.get(id) || {}; const h = hist[id]; const name = cap1(r.name) || unitName(snap, id);
    let s = `<div class="h">${esc(name)}</div>`;
    if (kind === "st_votes_left") {
      s += r.counted_vs_2022_pct != null ? `<div class="x">${T.cCounted(fmtPct(r.counted_vs_2022_pct))}</div>` : `<div class="x">${esc(avail ? T.noVotes : previewMsg(snap))}</div>`;
      if (avail && r.total != null) s += `<div class="x">${esc(T.vlCounted)}: <b>${fmtInt(r.total)}</b></div>`;
      if (r.total2022 || r.turnout2022) s += `<div class="x">${T.c2022(fmtInt(r.total2022 || r.turnout2022))}</div>`;
    } else if (kind === "st_counties" && avail) {
      const tot = r.total || 0;
      const list = onCard(snap).slice(0, 2).map(c => ({ c, v: (r.votes || {})[c.key] || 0 })).sort((a, b) => b.v - a.v);
      if (tot) s += list.map(({ c, v }) => `<div class="r p-${pt(c.party)}"><span class="ch">${esc(chip(pt(c.party)))}</span><span class="n">${esc(c.short || splitName(c.name).last)}</span><span class="v">${fmtInt(v)}</span><span class="p">${fmtPct(100 * v / tot)}%</span></div>`).join("");
      s += `<div class="x">${r.counted_vs_2022_pct != null && tot ? T.cCounted(fmtPct(r.counted_vs_2022_pct)) : esc(T.noVotes)}</div>`;
    }
    if (h && h.pres2024 && kind !== "st_votes_left") {
      const a = [[h24.dem_name, h.pres2024.dem_pct], [h24.rep_name, h.pres2024.rep_pct]].sort((x, y) => (y[1] || 0) - (x[1] || 0));
      s += kind === "st_history" && !avail ? "" : "";
      s += `<div class="x"><b>${esc(T.c2024)}</b> · ${a.map(([n, p]) => `${esc(n)} ${fmtPct(p)}%`).join(" · ")}</div>`;
    }
    return s;
  }
  function setRowsTo(list, statewide) {   /* st_history: swap the board between statewide and one county */
    el.querySelectorAll(".hrows .wrow").forEach((w, i) => {
      const it = list[i]; if (!it) return; const v = w.querySelector(".v"), p = w.querySelector(".p");
      const from = parseFloat(p.dataset.cur || p.dataset.rollp || 0);
      roll(p, it.pct, fPct, { from }); p.dataset.cur = it.pct;
      v.innerHTML = statewide ? fmtInt(it.votes) : "";
    });
  }
  return {
    el,
    enter() { startRolls(el, 1000); el.querySelectorAll(".hrows .p").forEach(p => p.dataset.cur = p.dataset.rollp); },
    reset() { this.focus(null, true); },
    focus(id, quick) {
      if (id === cur) return; cur = id;
      const vl = el.querySelector(".vllist"); if (vl) { vl.classList.toggle("hasfocus", !!(id && vl.querySelector(`[data-id="${CSS.escape(id)}"]`))); vl.querySelectorAll(".vlr").forEach(r => r.classList.toggle("focus", r.dataset.id === id)); }
      const valid = id && (m.els.has(id));
      callout.classList.remove("on"); line.classList.remove("on"); const dot0 = el.querySelector(".cdot"); if (dot0) dot0.classList.remove("on");
      const ctx = el.querySelector(".ctx"); if (ctx) ctx.style.opacity = 0;
      if (inset) inset.fxg.innerHTML = "";
      if (!valid) {
        if (inset) { el.querySelectorAll(".inset, .inset + svg").forEach(n => n.style.opacity = 1); inset.rect.style.opacity = 1; }
        m.wrap.classList.remove("focused"); m.fx.innerHTML = ""; setZoom(m.wrap, 1, 0, 0, quick ? 0 : 750);
        if (kind === "st_history") { const t = el.querySelector(".htitle .t .fit"); if (t) { t.innerHTML = `${esc(nm)}<i>2024</i>`; fitAll(el.querySelector(".htitle")); } setRowsTo(hrowsData, true); }
        return;
      }
      const inInset = inset && inset.ids.has(id);
      let anchor, sbox = null;
      if (inset) { const iv = el.querySelectorAll(".inset, .inset + svg"); iv.forEach(n => { n.style.transition = "opacity 250ms linear"; n.style.opacity = inInset ? 1 : 0; }); inset.rect.style.opacity = inInset ? 1 : 0; }
      if (inInset) {
        setZoom(m.wrap, 1, 0, 0, quick ? 0 : 750); m.wrap.classList.add("focused"); m.fx.innerHTML = "";
        const d = inset.path2(m.feats.get(id));
        svgEl("path", { d, fill: "none", stroke: "#000", "stroke-width": 9 }, inset.fxg);
        svgEl("path", { d, fill: inset.iels.get(id).getAttribute("fill"), stroke: "#fff", "stroke-width": 5 }, inset.fxg);
        const c = inset.path2.centroid(m.feats.get(id)); anchor = c;
      } else {
        const b = m.path.bounds(m.feats.get(id));
        const tgt = kind === "st_votes_left" ? { x: 1080, y: 200, w: 360, h: 320 } : MAP_TARGET;
        const z = zoomBox(m.wrap, b, tgt, 1.25, ak ? 2.2 : 3.4, quick ? 0 : 750);
        m.wrap.classList.add("focused"); focusPath(m, id, z.k);
        anchor = toScreen(z, m.path.centroid(m.feats.get(id))); sbox = screenBox(z, b);
      }
      const show = () => {
        if (cur !== id) return;
        if (kind === "st_history") {
          const h = hist[id]; const nm2 = unitName(snap, id);
          const t = el.querySelector(".htitle .t .fit"); if (t) { t.innerHTML = `${esc(nm2)}<i>2024</i>`; fitAll(el.querySelector(".htitle")); }
          if (h && h.pres2024) setRowsTo(hrowsData.map(r => ({ pct: r.party === "DEM" ? h.pres2024.dem_pct : h.pres2024.rep_pct })), false);
          if (ctx && h) {
            ctx.textContent = `${nm2} · 2024 ${chip(pt(h.winner))}+${fmtPct(h.margin_pts)}`;
            if (inInset) { ctx.style.left = (inset.box.x + 12) + "px"; ctx.style.top = (inset.box.y + inset.box.h - 40) + "px"; }
            else { const sb = sbox || [[anchor[0] - 20, anchor[1] - 20], [anchor[0] + 20, anchor[1] + 20]]; ctx.style.left = Math.min(sb[1][0] + 14, 1500) + "px"; ctx.style.top = Math.max(60, sb[0][1] - 6) + "px"; }
            ctx.style.opacity = 1; }
          return;
        }
        callout.innerHTML = calloutHTML(id);
        placeCallout(el, callout, line, anchor, { x0: kind === "st_votes_left" ? 760 : 690, x1: 1850, y0: 50, y1: 820 }, sbox);
        callout.classList.add("on"); line.classList.add("on");
      };
      if (quick || INSTANT) show(); else setTimeout(show, 760);
    },
  };
}
V.st_counties = s => mapVisual(s, "st_counties");
V.st_votes_left = s => mapVisual(s, "st_votes_left");
V.st_history = s => mapVisual(s, "st_history");

/* ---------- st_intro: national map zooms into the state ---------- */
V.st_intro = async (snap) => {
  const el = div("vis v-intro"); const st = snap.state; await loadUS();
  const PU = d3.geoAlbersUsa().fitExtent([[80, 60], [1840, 820]], GEO.us); const pu = d3.geoPath(PU);
  const nat = div("mapwrap"); const ns = svgEl("svg", { width: 1920, height: 840 }); nat.appendChild(ns);
  for (const f of GEO.us.features) svgEl("path", { d: pu(f) || "", fill: f.properties.id === st ? "#C9CED8" : "#2f3750", stroke: "#11162b", "stroke-width": 1.2 }, ns);
  el.appendChild(nat);
  const m = await stateMap(snap, { extent: [[720, 70], [1840, 815]], fill: () => "#4f5a78" });
  m.wrap.style.opacity = 0; el.appendChild(m.wrap);
  const b0 = pu.bounds(GEO.usById.get(st)), b1 = m.path.bounds(m.sfeat);
  const k = (b1[1][0] - b1[0][0]) / Math.max(1, b0[1][0] - b0[0][0]);
  const tx = b1[0][0] - k * b0[0][0], ty = b1[0][1] - k * b0[0][1];
  const cands = onCard(snap);
  const pc = snap.poll_close || {};
  const info = [];
  info.push(`<div class="a">${esc(snap.phase === "preview" ? T.pollsCloseAt(tET(pc.last_et)) : T.pollsClosedAt(tET(pc.last_et)))}</div>`);
  let b = pc.main_et && pc.last_et ? T.pcDetail(esc(tET(pc.main_et)), esc(tET(pc.last_et))) : "";
  const sp = seatParty(snap); if (sp) b += (b ? "<br>" : "") + T.seatNow(esc(sp));
  if (snap.rcv) b += "<br>" + esc(T.rcvShort);
  info.push(`<div class="b">${b}</div>`);
  el.insertAdjacentHTML("beforeend", wallTitle(snap.state_name, "2026", snap.race_label + (snap.special ? " · " + T.special : ""), 900) +
    `<div class="iplates" style="top:300px">${cands.map((c, i) => `<div class="ipl p-${pt(c.party)} bl" style="--d:${1100 + i * 80}ms"><div class="ch">${esc(chip(pt(c.party)))}</div><div class="n"><span class="fit" data-sub="1">${esc(c.short || splitName(c.name).last)}</span>${c.incumbent ? `<small>${esc(T.incumbent)}</small>` : ""}</div></div>`).join("")}</div>` +
    `<div class="iinfo fadein" style="top:${300 + cands.length * 84 + 30}px;--d:1350ms">${info.join("")}</div>`);
  return {
    el,
    enter() {
      if (INSTANT) { nat.style.opacity = 0; m.wrap.style.opacity = 1; return; }
      nat.style.transition = "none"; nat.style.transform = ""; nat.style.opacity = 1;
      m.wrap.style.transition = "none"; m.wrap.style.transform = `translate(${(-tx / k).toFixed(1)}px,${(-ty / k).toFixed(1)}px) scale(${(1 / k).toFixed(4)})`; m.wrap.style.opacity = 0;
      nat.classList.add("anim"); m.wrap.classList.add("anim"); void el.offsetWidth;
      setTimeout(() => {
        nat.style.transition = "transform 750ms var(--e-io), opacity 300ms linear 450ms"; nat.style.transform = `translate(${tx.toFixed(1)}px,${ty.toFixed(1)}px) scale(${k.toFixed(4)})`; nat.style.opacity = 0;
        m.wrap.style.transition = "transform 750ms var(--e-io), opacity 350ms linear 250ms"; m.wrap.style.transform = ""; m.wrap.style.opacity = 1;
        setTimeout(() => { nat.classList.remove("anim"); m.wrap.classList.remove("anim"); }, 820);
      }, 150);
    },
    focus() {},
  };
};

/* ---------- st_senators: ABC two-card ---------- */
V.st_senators = async (snap) => {
  const el = div("vis v-senators"); const sens = (snap.senators || []).slice(0, 2);
  const card = (s, i) => {
    const p = pt(s.party); const n = splitName(s.name);
    const chips = [`<span>${esc(s.party_label || PARTY_WORD[p] || p)}</span>`]; if (s.since) chips.push(`<span>${esc(T.since(s.since))}</span>`);
    if (s.up && s.running != null) chips.push(`<span>${esc(s.running ? T.running : T.notRunning)}</span>`);
    return `<div class="abc p-${p} bi" style="left:${i ? 982 : 80}px;--d:${534 + i * 80}ms" data-i="${i}"><div class="rail"></div><div class="bd">
      <div class="plate">${monoHTML({ name: s.name, party: p, key: s.key })}<div class="nn"><div class="f"><span class="fit">${esc(n.first)}</span></div><div class="l"><span class="fit">${esc(n.last)}</span></div></div></div>
      <div class="chips">${chips.join("")}</div>${s.note ? `<div class="note">${esc(s.note)}</div>` : ""}
      <div class="uptag ${s.up ? "up" : "no"}">${esc(s.up ? T.upIn : (s.next_election ? T.nextUp(s.next_election) : T.notUpTag))}</div></div></div>`;
  };
  const sp = snap.history && snap.history.sen_prev;
  let prev = "";
  if (sp) {
    const cells = [{ n: sp.dem_name, p: sp.dem_pct, party: sp.dem_is_independent ? "IND" : "DEM" }, { n: sp.rep_name, p: sp.rep_pct, party: "REP" }].sort((a, b) => (b.p || 0) - (a.p || 0));
    prev = `<div class="prevrow fadein" style="--d:1000ms"><div class="yr"><b>${esc(sp.year)}</b><span>${esc(T.prevSeat(sp.year))}</span></div>${cells.map(c =>
      `<div class="pc p-${c.party}"><div class="ch">${esc(chip(c.party))}</div><div class="n"><span class="fit">${esc(splitName(c.n).last)}</span></div><div class="p">${fmtPct(c.p)}%</div></div>`).join("")}</div>
      <div class="prevsrc srcline fadein" style="--d:1100ms">${esc(T.prevSrc(sp.year))}</div>`;
  }
  el.innerHTML = `<div class="abh"><div class="w wipe" style="--d:0ms"><span class="fit">${esc(T.senTitle(snap.state_name))}</span></div>
    <div class="g wipe" style="--d:200ms"><div class="a">${esc(T.senators)}</div><div class="b">${esc(snap.special ? T.special : T.seatUp)}</div></div></div>
    <div class="abcwrap">${sens.map(card).join("")}</div>${prev}`;
  return { el, enter() {}, focus(f) {
    const w = el.querySelector(".abcwrap"); const ok = f != null && f !== "" && w.querySelector(`[data-i="${f}"]`);
    w.classList.toggle("hasfocus", !!ok); w.querySelectorAll(".abc").forEach(c => c.classList.toggle("focus", ok && c.dataset.i === String(f)));
  } };
};

/* ---------- st_candidates: Fox-style cards ---------- */
V.st_candidates = async (snap) => {
  const el = div("vis v-cands"); const cards = (snap.cards || []).slice(0, 4); const n = Math.max(1, cards.length);
  const W = Math.min(820, Math.floor((1760 - (n - 1) * 40) / n));
  const card = (c, i) => {
    const p = pt(c.party); const role = [c.role, c.age ? T.age(c.age) : ""].filter(Boolean).join(" · ");
    return `<div class="fxc p-${p} bi" style="width:${W}px;--d:${534 + i * 80}ms" data-key="${esc(c.key)}"><div class="ph">
      <div class="mg">${esc(initials(c))}</div>
      <div class="pty">${esc(c.party_label || PARTY_WORD[p] || p)}${c.incumbent ? `<span class="itag">${esc(T.incumbent)}</span>` : ""}</div>
      <div class="role">${esc(role)}</div></div>
      <div class="np"><span class="fit">${esc(c.name)}</span></div></div>`;
  };
  /* focused candidate: a wide panel over the portrait row (facts + positions stay readable at TV size) */
  const info = c => {
    const p = pt(c.party); const role = [c.party_label || PARTY_WORD[p] || p, c.role, c.age ? T.age(c.age) : ""].filter(Boolean).join(" · ");
    return `<div class="fxinfo p-${p}" data-key="${esc(c.key)}"><div class="rail"></div><div class="ib">
      <div class="ih">${monoHTML(c)}<div><div class="in">${esc(c.name)}${c.incumbent ? `<span class="itag">${esc(T.incumbent)}</span>` : ""}</div><div class="ir">${esc(role)}</div></div></div>
      <div class="icols"><div class="icol a"><h4>${esc(T.bg)}</h4><ul>${(c.facts || []).slice(0, 3).map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>
        <div class="icol b"><h4>${esc(T.pos)}</h4><ul>${(c.positions || []).slice(0, 4).map(x => `<li>${esc(x)}</li>`).join("")}</ul></div></div></div></div>`;
  };
  el.innerHTML = `<div class="fxt wipe" style="--d:0ms"><span class="star">★</span><span class="fit" data-w="1500">${esc(T.candTitle(snap.state_name))}</span><span class="star">★</span></div><div class="fxband"></div>
    <div class="fxcards">${cards.map(card).join("")}${cards.map(info).join("")}</div>`;
  return {
    el, layout() { el.querySelectorAll(".fxinfo .icol").forEach(b => fitBlock(b, 19)); },
    enter() {},
    focus(f) { const w = el.querySelector(".fxcards"); const ok = f && w.querySelector(`.fxc[data-key="${CSS.escape(f)}"]`);
      w.classList.toggle("hasfocus", !!ok); w.querySelectorAll(".fxc,.fxinfo").forEach(c => c.classList.toggle("focus", !!ok && c.dataset.key === f)); },
  };
};

/* ---------- st_poll_close: countdown card ---------- */
function cdParts(ms) { const s = Math.max(0, Math.floor(ms / 1000)); return { h: Math.floor(s / 3600), m: Math.floor(s / 60) % 60, s: s % 60 }; }
V.st_poll_close = async (snap) => {
  const el = div("vis v-pc"); const pc = snap.poll_close || {}; const last = Date.parse(pc.last_et); const main = Date.parse(pc.main_et || pc.last_et);
  await loadUS();
  const m = await stateMap(snap, { extent: [[1240, 110], [1800, 760]], neighbours: false, fill: () => "#2E3270" });
  m.wrap.classList.add("fadein"); m.wrap.style.setProperty("--d", "500ms"); el.appendChild(m.wrap);
  const tm = tET(last); const ap = LANG === "es" ? tm.split(" ") : [tm, ""];
  el.insertAdjacentHTML("beforeend", `<div class="pcc"><div class="k bl" style="--d:100ms">${esc(T.pcK)}</div>
    <div class="s1 bl" style="--d:200ms"><span class="fit" data-w="1060">${esc(snap.state_name)}</span></div><div class="s2 bl" style="--d:300ms"><span class="fit" data-w="1060">${esc(T.pcS2)}</span></div>
    <div class="pcrow bi" style="--d:600ms"><div class="tm"><b>${esc(ap[0])}</b><span>${LANG === "es" ? `${esc(ap[1])}<br>ET` : (LANG === "ja" ? "米東部<br>時間" : "美东<br>时间")}</span></div>
      <div class="cd" id="pcCd"></div></div>
    <div class="det fadein" style="--d:900ms">${pc.main_et && pc.last_et ? T.pcDetail(esc(tET(main)), esc(tET(last))) : ""}${snap.rcv ? "<br>" + esc(T.rcvShort) : ""}</div></div>`);
  const cd = el.querySelector("#pcCd"); cd.removeAttribute("id");
  const tick = () => {
    const d = last - now(); const since = d <= 0; const p = cdParts(Math.abs(d));
    const g = (v, l) => `<div class="g"><b>${v}</b><span>${esc(l)}</span></div>`;
    cd.innerHTML = (since ? `<div class="g" style="margin-right:20px"><span style="font-size:26px;letter-spacing:.04em;text-align:right">${esc(T.pcSince)}</span></div>` : "") +
      (p.h ? g(p.h, T.hr) + `<div class="c">:</div>` + g(pad(p.m), T.min) : g(p.m, T.min)) + `<div class="c">:</div>` + g(pad(p.s), T.sec);
  };
  tick(); const iv = setInterval(tick, 1000);
  return { el, enter() {}, focus() {}, destroy() { clearInterval(iv); } };
};

/* ---------- national visuals ---------- */
const NE_SMALL = ["VT", "NH", "MA", "RI", "CT", "NJ", "DE", "MD", "DC"];
const LABEL_NUDGE = { FL: [38, 22], LA: [-14, 4], MI: [22, 36], KY: [8, 4], CA: [-14, 10], ID: [0, 30], NY: [10, 0], VA: [16, 6], WV: [-4, 6], NC: [10, 0],
                      MN: [-8, 10], HI: [10, 10], AK: [0, 0], OK: [10, 0], TX: [8, 0], ME: [4, -6], SC: [6, -2], MS: [0, 6], TN: [6, 0] };
function raceMap(nat) { return new Map((nat.races || []).map(r => [r.state, r])); }
function statusFill(r) {
  if (!r) return { f: "#2E3548", ink: "#8992a8", cls: "st-none" };
  if (r.status === "declared" && r.declared) return { f: pt(r.declared.party) === "DEM" ? "var(--dem-700)" : pt(r.declared.party) === "REP" ? "var(--rep-700)" : "var(--ind-700)", ink: "#fff", cls: "st-decl" };
  if (r.status === "polls_closed" || r.status === "counting") return { f: "#E2B227", ink: "#14183a", cls: "st-closed" };
  return { f: "#C9CED8", ink: "#14183a", cls: "st-open" };
}
const statusWord = s => ({ polls_open: T.stOpen, polls_closed: T.stClosed, counting: T.stCounting, declared: T.stDecl }[s] || "");
async function usMap(extent, fillFn, opts) {
  await loadUS(); opts = opts || {};
  const P = d3.geoAlbersUsa().fitExtent(extent, GEO.us); const path = d3.geoPath(P);
  const wrap = div("mapwrap"); const svg = svgEl("svg", { width: 1920, height: 840 }); wrap.appendChild(svg);
  const els = new Map(); const g = svgEl("g", {}, svg); const fg = svgEl("g", {}, svg); const lg = svgEl("g", {}, svg);
  for (const f of GEO.us.features) {
    const id = f.properties.id; const s = fillFn(id); const d = path(f); if (!d) continue;
    els.set(id, svgEl("path", { d, fill: s.f, stroke: "#0E1222", class: "natp", "stroke-linejoin": "round" }, g));
    if (s.featured) svgEl("path", { d, fill: "none", stroke: "#fff", class: "natf", "stroke-linejoin": "round" }, fg);
    if (opts.labels !== false && !NE_SMALL.includes(id)) {
      const c = path.centroid(f); const nd = LABEL_NUDGE[id] || [0, 0];
      const t = svgEl("text", { x: c[0] + nd[0], y: c[1] + nd[1] + 8, "text-anchor": "middle", class: "mlabel", fill: s.ink, stroke: s.ink === "#fff" ? "rgba(0,0,0,.35)" : "rgba(255,255,255,0)" }, lg); t.textContent = id;
    }
  }
  const dim = div("dim"); wrap.appendChild(dim); const fx = svgEl("svg", { width: 1920, height: 840 }); wrap.appendChild(fx);
  return { wrap, svg, fx, P, path, els };
}
function neColumn(x, y, fillFn) {
  return `<div class="necol" style="left:${x}px;top:${y}px">${NE_SMALL.map(id => { const s = fillFn(id); return `<div class="c" style="background:${s.f};color:${s.ink};${s.featured ? "border-color:#fff;border-width:3px" : ""}">${id}</div>`; }).join("")}</div>`;
}
function miniBal(bal) {
  const h = bal.holdover || {}, d = bal.declared || {};
  const D = (h.DEM || 0) + (d.DEM || 0), R = (h.REP || 0) + (d.REP || 0), I = (h.IND || 0) + (d.IND || 0); const U = Math.max(0, 100 - D - R - I);
  return `<div class="mini"><i style="width:${D}%;background:var(--dem-700)"></i><i style="width:${I}%;background:var(--ind-500)"></i><i style="width:${U}%;background:#BBBCBF"></i><i style="width:${R}%;background:var(--rep-700)"></i></div>
    <div class="mini-l"><span style="color:#5aa9ff">${D}<small>${esc(T.dems)}</small></span><span style="color:#ff7b84">${R}<small>${esc(T.reps)}</small></span></div>`;
}
function natFocusCallout(el, m, nat, st, quick) {
  const nec = el.querySelector(".necol"); if (nec) { nec.style.transition = "opacity 250ms linear"; nec.style.opacity = st ? 0 : 1; }
  const box = el.querySelector(".ncall"); const line = el.querySelector(".leader"); box.classList.remove("on"); line.classList.remove("on"); const d0 = el.querySelector(".cdot"); if (d0) d0.classList.remove("on");
  if (!st || !m.els.has(st)) { m.wrap.classList.remove("focused"); m.fx.innerHTML = ""; setZoom(m.wrap, 1, 0, 0, quick ? 0 : 750); return; }
  const f = GEO.usById.get(st); const b = m.path.bounds(f); const z = zoomBox(m.wrap, b, { x: 560, y: 230, w: 420, h: 380 }, 1, 2.4, quick ? 0 : 750);
  m.wrap.classList.add("focused"); m.fx.innerHTML = ""; const d = m.els.get(st).getAttribute("d");
  svgEl("path", { d, fill: "none", stroke: "#000", "stroke-width": 10 / z.k }, m.fx); svgEl("path", { d, fill: m.els.get(st).getAttribute("fill"), stroke: "#fff", "stroke-width": 6 / z.k }, m.fx);
  const r = raceMap(nat).get(st); let x = "";
  if (r) {
    if (r.declared && r.declared.credit) x = esc(r.declared.credit);
    else if (r.leader) x = `<b>${esc(r.leader.short)}</b> (${esc(chip(pt(r.leader.party)))}) ${esc(T.leads)} · <b>${fmtPct(r.leader.pct)}%</b>`;
    else if (r.status === "polls_open") x = esc(T.pollsCloseAt(tET(r.poll_close_last_et)));
    else x = esc(T.noCount);
  }
  box.innerHTML = `<div class="h">${esc(r ? r.state_name : st)}</div><div class="k">${esc(T.usSenate)} · ${esc(r ? statusWord(r.status) : "")}</div><div class="x">${x}</div>`;
  const show = () => { placeCallout(el, box, line, toScreen(z, m.path.centroid(f)), { x0: 100, x1: 1450, y0: 150, y1: 820 }, screenBox(z, b)); box.classList.add("on"); line.classList.add("on"); };
  if (quick || INSTANT) show(); else setTimeout(show, 760);
}
V.nat_map = async (nat) => {
  const el = div("vis v-natmap"); const races = raceMap(nat);
  const fillFn = id => { const r = races.get(id); const s = statusFill(r); s.featured = !!(r && r.featured); return s; };
  const m = await usMap([[100, 160], [1390, 826]], fillFn);
  const clip = div("mapclip"); clip.style.cssText = "position:absolute;left:0;top:0;width:1470px;height:840px;overflow:hidden"; clip.appendChild(m.wrap); el.appendChild(clip);
  const nUp = (nat.races || []).length;
  el.insertAdjacentHTML("beforeend", `<div class="ntitle wipe" style="--d:0ms"><span class="fit" data-sub="1">${esc(T.natTitle)}</span><span class="r">${esc(T.seatsUp(nUp))}</span></div>
    ${neColumn(1418, 300, fillFn)}
    <div class="nside fadein" style="--d:700ms"><div class="bx"><h5>${esc(T.legend)}</h5><div class="legend" style="position:static">
      <div class="li"><span class="sw" style="background:#2E3548"></span><span>${esc(T.lgNoRace)}</span></div>
      <div class="li"><span class="sw" style="background:#C9CED8"></span><span>${esc(T.lgOpen)}</span></div>
      <div class="li"><span class="sw" style="background:#E2B227"></span><span>${esc(T.lgClosed)}</span></div>
      <div class="li"><span class="sw" style="background:linear-gradient(90deg,var(--dem-700) 50%,var(--rep-700) 50%)"></span><span class="fit" data-w="270">${esc(T.lgDecl)}</span></div>
      <div class="li"><span class="sw" style="background:transparent;border:3px solid #fff"></span><span>${esc(T.lgFeat)}</span></div></div></div>
      <div class="bx"><h5>${esc(T.balTitle)}</h5>${miniBal(nat.balance || {})}</div>
      <div class="bx"><h5>${esc(T.lgFeat)}</h5>${(nat.races || []).filter(r => r.featured).map(r => `<div class="fr"><b>${esc(r.state)}</b><span class="fit" data-w="170">${esc(r.state_name)}</span><span class="s ${statusFill(r).cls}">${esc(statusWord(r.status))}</span></div>`).join("")}</div></div>
    <div class="leader"></div><div class="ncall"></div>`);
  return { el, enter() {}, focus(f, q) { natFocusCallout(el, m, nat, f, q); } };
};
V.nat_balance = async (nat) => {
  const el = div("vis v-bal"); const bal = nat.balance || {}; const h = bal.holdover || {}, d = bal.declared || {};
  const D = (h.DEM || 0) + (d.DEM || 0), R = (h.REP || 0) + (d.REP || 0), I = (h.IND || 0) + (d.IND || 0);
  const und = bal.undecided != null ? bal.undecided : Math.max(0, 100 - D - R - I);
  const seats = (n, c) => Array.from({ length: n }, () => `<span class="seat"><i style="background:${c}"></i></span>`).join("");
  const maj = bal.majority || 51;
  el.innerHTML = `<div class="ntitle wipe" style="--d:0ms"><span class="fit" data-sub="1">${esc(T.balTitle)}</span><span class="r">${esc(T.usSenate)}</span></div>
    <div class="bal-tiles">
      <div class="btile p-DEM bi" style="--d:534ms"><div class="bx"><b data-roll="${D}"></b><span>${esc(T.dems)}</span></div><div class="cp">${esc(T.notUpPlus(h.DEM || 0, d.DEM || 0))}</div></div>
      <div class="btile ind p-IND bi" style="--d:594ms"><div class="bx"><b data-roll="${I}"></b><span><span class="fit c" data-w="226">${esc(T.indsLong)}</span></span></div><div class="cp">${esc(T.notUpPlus(h.IND || 0, d.IND || 0))}</div></div>
      <div class="bcenter fadein" style="--d:800ms"><div class="maj">${maj}</div><div class="majl">${esc(T.majority)}</div><div class="und">${esc(T.undecided(und))}</div></div>
      <div class="btile p-REP bi" style="--d:654ms"><div class="bx"><b data-roll="${R}"></b><span>${esc(T.reps)}</span></div><div class="cp">${esc(T.notUpPlus(h.REP || 0, d.REP || 0))}</div></div>
    </div>
    <div class="bbar"><div class="seg l" style="display:flex">${seats(h.DEM || 0, "var(--dem-300)")}${seats(d.DEM || 0, "var(--dem-700)")}${seats(h.IND || 0, "#7d8496")}${seats(d.IND || 0, "var(--ind-700)")}</div>
      <div class="seg u" style="display:flex">${seats(Math.max(0, 100 - D - R - I), "#BBBCBF")}</div>
      <div class="seg r" style="display:flex">${seats(d.REP || 0, "var(--rep-700)")}${seats(h.REP || 0, "var(--rep-300)")}</div></div>
    <div class="btick fadein" style="--d:1200ms"></div><div class="btickl fadein" style="--d:1200ms">${maj} · ${esc(T.majority)}</div>
    <div class="blegend fadein" style="--d:1300ms"><span><i style="background:linear-gradient(90deg,var(--dem-300) 50%,var(--rep-300) 50%)"></i>${esc(T.lgHold)}</span>
      <span><i style="background:linear-gradient(90deg,var(--dem-700) 50%,var(--rep-700) 50%)"></i>${esc(T.lgApDecl)}</span><span><i style="background:#7d8496"></i>${esc(T.indsLong)}</span><span><i style="background:#BBBCBF"></i>${esc(T.lgUnd)}</span></div>
    <div class="nsrc srcline fadein" style="--d:1400ms">${esc(T.balSrc)}</div>`;
  const segs = [...el.querySelectorAll(".bbar .seg")];
  return { el, enter() {
    startRolls(el, 900);
    if (INSTANT) return;
    segs.forEach((s, i) => s.animate([{ transform: "scaleX(0)", opacity: 0 }, { transform: "scaleX(1)", opacity: 1 }], { duration: 600, delay: 700 + i * 120, easing: "cubic-bezier(.16,1,.3,1)", fill: "backwards" }));
  }, focus() {} };
};
V.nat_races = async (nat, sc, desk) => {
  const el = div("vis v-races"); const feat = (nat.races || []).filter(r => r.featured);
  const order = ["TX", "AK", "KS", "ME", "OH", "MI"]; feat.sort((a, b) => order.indexOf(a.state) - order.indexOf(b.state));
  const strip = new Map(((desk && desk.strip) || []).map(s => [s.state, s]));
  const card = (r, i) => {
    let rows = r.rows || (strip.get(r.state) || {}).rows || [];
    const counting = r.status === "counting" || r.status === "declared";
    rows = rows.slice(0, 2).map(x => Object.assign({}, x, { pct: r.rows ? x.pct : (r.leader && x.short === r.leader.short ? r.leader.pct : null) }));
    if (!rows.length && r.leader) rows = [r.leader];
    if (counting) rows.sort((a, b) => (b.pct || 0) - (a.pct || 0));
    const foot = r.declared && r.declared.credit ? esc(r.declared.credit)
      : r.status === "polls_open" ? esc(T.pollsCloseAt(tET(r.poll_close_last_et)))
      : !counting ? esc(T.noCount) : T.seatNow(esc(PARTY_WORD[pt(r.incumbent_party)] || r.incumbent_party || ""));
    const sf = statusFill(r);
    return `<div class="kc bi" style="--d:${534 + i * 40}ms" data-st="${esc(r.state)}"><div class="kh"><span class="sn"><span class="fit" data-w="300">${esc(r.state_name)}</span></span><span class="rl">${esc(T.raceWord)}</span>
      <span class="stc ${sf.cls}">${esc(statusWord(r.status))}</span></div>
      ${rows.map(x => `<div class="kr p-${pt(x.party)}"><div class="ch">${esc(chip(pt(x.party)))}</div><div class="n"><span class="fit">${esc(x.short)}</span></div><div class="p ${x.pct == null || !counting ? "none" : ""}">${x.pct != null && counting ? fmtPct(x.pct) + "%" : ""}</div></div>`).join("")}
      <div class="kf">${foot}</div></div>`;
  };
  el.innerHTML = `<div class="ntitle wipe" style="--d:0ms"><span class="fit" data-sub="1">${esc(T.racesTitle)}</span><span class="r">${esc(T.usSenate)}</span></div>
    <div class="kgrid">${feat.map(card).join("")}</div>
    <div class="nsrc srcline fadein" style="--d:1300ms;top:${156 + 2 * 300 + 22 + 14}px">${esc(T.unofficial)} · ${esc(T.calledBy)}</div>`;
  return { el, enter() {}, focus(f) { const g = el.querySelector(".kgrid"); const ok = f && g.querySelector(`[data-st="${CSS.escape(f)}"]`);
    g.classList.toggle("hasfocus", !!ok); g.querySelectorAll(".kc").forEach(c => c.classList.toggle("focus", !!ok && c.dataset.st === f)); } };
};
V.nat_schedule = async (nat) => {
  const el = div("vis v-sched"); const sched = (nat.schedule || []).slice().sort((a, b) => Date.parse(a.et) - Date.parse(b.et)).slice(0, 10);
  const feat = new Set((nat.races || []).filter(r => r.featured).map(r => r.state));
  const slotOf = new Map(); sched.forEach((s, i) => s.states.forEach(st => slotOf.set(st, i)));
  const nowMs = now(); let nextI = sched.findIndex(s => Date.parse(s.et) > nowMs);
  const fillFn = id => {
    const i = slotOf.get(id); if (i == null) return { f: "#1a1f36", ink: "#59627a", featured: feat.has(id) };
    const t = Date.parse(sched[i].et);
    if (t <= nowMs) return { f: "#6B6F76", ink: "#e6e8ee", featured: feat.has(id) };
    if (i === nextI) return { f: "var(--gold)", ink: "#111", featured: feat.has(id) };
    return { f: "#2c3170", ink: "#dfe3f3", featured: feat.has(id) };
  };
  const m = await usMap([[690, 160], [1720, 820]], fillFn); el.appendChild(m.wrap);
  const tmLabel = iso => tET(iso);
  el.insertAdjacentHTML("beforeend", `<div class="ntitle wipe" style="--d:0ms"><span class="fit" data-sub="1">${esc(T.schedTitle)}</span><span class="r">${esc(T.usSenate)}</span></div>
    <div class="ladder" style="${sched.length > 8 ? "gap:6px" : ""}">${sched.map((s, i) => {
      const past = Date.parse(s.et) <= nowMs, nx = i === nextI;
      return `<div class="slot ${past ? "past" : nx ? "next" : ""} bl" style="--d:${400 + i * 50}ms;${sched.length > 8 ? "height:58px" : ""}"><div class="tm">${esc(tmLabel(s.et))}</div>
        <div class="ss">${s.states.map(st => `<span class="${feat.has(st) ? "ft" : ""}">${esc(st)}</span>`).join("")}</div>${nx ? `<div class="in" data-cd="${Date.parse(s.et)}"></div>` : ""}</div>`; }).join("")}</div>
    ${neColumn(1760, 300, fillFn)}
    <div class="nsrc srcline fadein" style="--d:1300ms">${esc(T.schedSrc)}</div>`);
  const cdn = el.querySelector("[data-cd]");
  const tick = () => { if (!cdn) return; const p = cdParts(+cdn.dataset.cd - now()); cdn.textContent = `${esc(T.schedIn)} ${p.h ? p.h + ":" + pad(p.m) : p.m}:${pad(p.s)}`; };
  tick(); const iv = setInterval(tick, 1000);
  return { el, enter() {}, focus() {}, destroy() { clearInterval(iv); } };
};
const DEFAULT_VIS = { national: "nat_map", state: "st_intro" };
const NAT_VIS = ["nat_map", "nat_balance", "nat_races", "nat_schedule"];
const ST_VIS = ["st_intro", "st_senators", "st_candidates", "st_results", "st_counties", "st_votes_left", "st_history", "st_poll_close"];

/* =====================================================================  persistent chrome  */
let DESK = null, NAT_FALLBACK = null;
function setText(id, s) { const e = $(id); if (e) e.textContent = s; }
function renderStatic() {
  setText("bugLive", T.live); setText("bugA", T.brandA); setText("bugB", T.brandB); setText("discTx", T.disc);
  if (LANG !== "es") { $("crawl").hidden = false; setText("crawlLab", T.crawl); }
  $("testBadge").textContent = T.test;
}
function nationalForChrome() { return (DESK && DESK.national) || NAT_FALLBACK; }
function renderPollClose() {
  const nc = DESK && DESK.next_close; const pc = $("pc");
  let l1, l2, target, since = false;
  const sch0 = ((nationalForChrome() || {}).schedule || []).slice().sort((a, b) => Date.parse(a.et) - Date.parse(b.et));
  let ncx = nc && nc.et && Date.parse(nc.et) > now() ? nc : null;
  if (!ncx) { const nx = sch0.find(x => Date.parse(x.et) > now()); if (nx) ncx = { et: nx.et, states: nx.states }; }
  if (ncx) {
    const nc = ncx; const sts = (nc.states || []); const shown = sts.length > 4 ? sts.slice(0, 3).join(" · ") + ` +${sts.length - 3}` : sts.join(" · ");
    l1 = T.pcL1(LANG === "es" ? shown : shown.replace(/ · /g, "・")); l2 = T.pcL2(tET(nc.et, true)); target = Date.parse(nc.et);
  } else {
    const nat = nationalForChrome(); const sch = (nat && nat.schedule) || []; const lastT = sch.length ? Math.max(...sch.map(s => Date.parse(s.et))) : null;
    l1 = T.allL1; l2 = T.allL2; target = lastT; since = true;
  }
  if (pc._k !== l1 + l2) { pc._k = l1 + l2; setText("pcL1", l1); setText("pcL2", l2); $("pcL1").innerHTML = `<span class="fit">${esc(l1)}</span>`; $("pcL2").innerHTML = `<span class="fit">${esc(l2)}</span>`; fitAll(pc); }
  const cd = $("cd"); if (target == null) { cd.innerHTML = ""; return; }
  const p = cdParts(Math.abs(target - now()));
  const g = (v, l) => `<div class="g"><b>${v}</b><span>${esc(l)}</span></div>`;
  cd.classList.toggle("h", p.h > 0);
  cd.innerHTML = (p.h ? g(p.h, T.hr) + `<div class="c">:</div>` : "") + g(p.h ? pad(p.m) : p.m, T.min) + `<div class="c">:</div>` + g(pad(p.s), T.sec);
}
function renderClock() {
  const n = now(); const et = wall(n, ET_OFF);
  if (LANG === "es") { $("ck1").textContent = `${(et.h % 12) || 12}:${pad(et.m)} ${et.h < 12 ? "AM" : "PM"} ET`; return; }
  const loc = wall(n, LANG === "ja" ? JST_OFF : BJT_OFF);
  $("ck1").textContent = (LANG === "ja" ? "米東部 " : "美东 ") + `${et.h}:${pad(et.m)}`;
  $("ck2").textContent = (LANG === "ja" ? "日本 " : "北京 ") + `${loc.h}:${pad(loc.m)}`;
  const alt = Math.floor(n / 8000) % 2 === 1;
  $("ck1").classList.toggle("hide", alt); $("ck2").classList.toggle("hide", !alt);
}
function renderBalance() {
  const nat = nationalForChrome(); const bal = (nat && nat.balance) || null; const b = $("bal");
  if (!bal) { b.innerHTML = ""; return; }
  const h = bal.holdover || {}, d = bal.declared || {};
  const tile = (cls, p, n, lab, sub) => `<div class="tile ${cls} p-${p}"><div class="n"><b>${n}</b>${lab ? `<span>${esc(lab)}</span>` : ""}</div><div class="sub">${esc(sub)}</div></div>`;
  const sub = p => (d[p] || 0) > 0 ? `+${d[p]} ${T.apShort}` : `${h[p] || 0} ${T.notUp}`;
  const key = JSON.stringify(bal); if (b._k === key) return; b._k = key;
  b.innerHTML = `<div class="bh"><span class="t">${esc(T.balSenate)}</span><span class="m"><small>${esc(T.forMaj)}</small><b>${bal.majority || 51}</b></span></div>
    <div class="tl">${tile("d", "DEM", (h.DEM || 0) + (d.DEM || 0), T.dems, sub("DEM"))}${tile("i", "IND", (h.IND || 0) + (d.IND || 0), "", (d.IND || 0) > 0 ? `+${d.IND}` : String(h.IND || 0))}${tile("r", "REP", (h.REP || 0) + (d.REP || 0), T.reps, sub("REP"))}</div>`;
}
/* race strip flipper (Fox timing: 10 s period, 770 ms changeover) */
const STRIP = { i: -1, list: [], timer: null };
function stripList() {
  if (DESK && Array.isArray(DESK.strip) && DESK.strip.length) return DESK.strip;
  return STRIP.fallback || [];
}
function stripHTML(e) {
  const nat = nationalForChrome(); const r = nat && (nat.races || []).find(x => x.state === e.state);
  const name = e.state_name || (r && r.state_name) || e.label || e.state;
  const counting = (e.status === "counting" || e.status === "declared") && e.results_available !== false;
  const rows = (e.rows || []).slice().sort((a, b) => counting ? (b.pct || 0) - (a.pct || 0) : 0).slice(0, 2);
  let right;
  if (counting && e.counted_vs_2022_pct != null) {
    const lit = clamp(Math.round(e.counted_vs_2022_pct / 10), e.counted_vs_2022_pct > 0 ? 1 : 0, 10);
    right = `<div class="m"><div class="mv">${fmtPct(e.counted_vs_2022_pct)}%<span class="segs">${Array.from({ length: 10 }, (_, i) => `<i class="${i < lit ? "lit" : ""}"></i>`).join("")}</span></div><div class="mc">${esc(T.ofTotal22)}</div></div>`;
  } else {
    const pcl = e.poll_close_last_et || (r && r.poll_close_last_et);
    right = `<div class="stat">${esc((e.status === "polls_open" || e.status === "preview") ? T.stripOpen(pcl ? tET(pcl) : "") : e.status === "declared" ? T.stripDecl : T.stripNoCount)}</div>`;
  }
  const head = `<div class="sh cell c0"><span class="s">${esc(name)}</span><span class="r">${esc(T.raceWord)}</span>${right}</div>`;
  const rw = (x, i) => `<div class="rw cell c${i + 1} p-${pt(x.party)}"><div class="ch">${esc(chip(pt(x.party)))}</div><div class="n"><span class="fit">${esc(x.short)}</span></div>${
    counting && x.votes != null ? `<div class="v">${fmtInt(x.votes)}</div>` : ""}<div class="p ${counting && x.pct != null ? "" : "none"}">${counting && x.pct != null ? fmtPct(x.pct) + "%" : ""}</div></div>`;
  return head + rows.map(rw).join("") + (rows.length < 2 ? `<div class="rw cell c2" style="background:#d9dbe0"></div>`.repeat(2 - rows.length) : "");
}
function stripShow(first) {
  const list = stripList(); const s = $("strip"); if (!list.length) { s.innerHTML = ""; return; }
  STRIP.i = (STRIP.i + 1) % list.length; const e = list[STRIP.i];
  if (first || INSTANT) { s.innerHTML = stripHTML(e); fitAll(s); return; }
  s.classList.remove("in"); s.classList.add("out");
  setTimeout(() => { s.innerHTML = stripHTML(e); fitAll(s); s.querySelectorAll(".cell").forEach(c => c.style.opacity = 0); void s.offsetWidth;
    s.classList.remove("out"); s.classList.add("in"); s.querySelectorAll(".cell").forEach(c => c.style.opacity = ""); }, 400 + 130);
}
/* crawl (ja/zh): composited translateX loop, ~150 px/s */
let CRAWL_KEY = "";
function renderCrawl() {
  if (LANG === "es") return; const items = (DESK && DESK.ticker) || []; const key = JSON.stringify(items); if (key === CRAWL_KEY) return; CRAWL_KEY = key;
  const tr = $("crawlTr"); if (tr._anim) tr._anim.cancel();
  if (!items.length) { tr.innerHTML = ""; return; }
  const once = items.map(esc).join(`<span class="sep">◆</span>`) + `<span class="sep">◆</span>`;
  tr.innerHTML = `<span class="one">${once}</span><span>${once}</span>`;
  const lab = $("crawlLab").offsetWidth;
  tr.style.left = (lab + 24) + "px";
  const w = tr.querySelector(".one").offsetWidth; const repeats = Math.max(2, Math.ceil((1920 - lab) / w) + 1);
  tr.innerHTML = Array.from({ length: repeats }, () => `<span>${once}</span>`).join("");
  tr._anim = tr.animate([{ transform: "translateX(0)" }, { transform: `translateX(${-w}px)` }], { duration: w / 150 * 1000, iterations: Infinity, easing: "linear" });
}
function renderChrome() { renderPollClose(); renderBalance(); renderCrawl(); if (STRIP.i < 0) stripShow(true); }

/* =====================================================================  player  */
const TLOG = []; window.__tlog = TLOG;   /* beat/focus switch times vs the timeline (verification) */
const P = { pkg: null, next: null, playlist: [], idx: 0, sc: null, root: null, vis: {}, cur: null, bi: -1, focus: undefined, playing: false,
            useClock: false, t0: 0, dur: 0, busy: false, failures: 0 };
window.__P = P;
const audio = $("audio");
let SEEK = DEMO ? +(Q.get("seek") || 0) : 0;
const CUT = DEMO ? +(Q.get("cut") || 0) : 0;
function scenesById(m) { return Object.fromEntries((m.scenes || []).map(s => [s.scene_id, s])); }
function playlistOf(m) { const ids = (m.scenes || []).map(s => s.scene_id); const pl = (m.playlist && m.playlist.length) ? m.playlist.filter(id => ids.includes(id)) : ids; return pl.length ? pl : ids; }
function visIdsFor(sc) {
  const allowed = sc.kind === "national" ? NAT_VIS : ST_VIS;
  const ids = (sc.beats || []).map(b => b.visual).filter(v => allowed.includes(v));
  if (!ids.length) ids.push(DEFAULT_VIS[sc.kind === "national" ? "national" : "state"]);
  return [...new Set(ids)];
}
async function buildVisual(sc, id) {
  const snap = sc.snapshot || {};
  const v = await V[id](snap, sc, DESK);
  v.id = id; v.el.dataset.v = id; return v;
}
async function buildScene(sc) {
  const root = div("scn"); const vis = {};
  for (const id of visIdsFor(sc)) {
    try { const v = await buildVisual(sc, id); vis[id] = v; root.appendChild(v.el); } catch (e) { console.warn("visual", id, e); }
  }
  return { root, vis };
}
function layoutScene(root, vis) { fitAll(root); for (const k in vis) if (vis[k].layout) try { vis[k].layout(); } catch (e) { console.warn(e); } }
function sceneTitle(sc) { const s = sc.snapshot || {}; return sc.kind === "national" ? T.natScene : `${s.state_name || sc.key} · ${s.race_label || T.senate}`; }
function enterVis(v) {
  if (!v) return; const e = v.el; e.classList.remove("on", "off"); void e.offsetWidth; e.classList.add("on");
  try { v.enter && v.enter(); } catch (err) { console.warn(err); }
}
function exitVis(v) {
  if (!v) return; const e = v.el; e.classList.add("off");
  setTimeout(() => { if (P.cur === v) return; e.classList.remove("on", "off"); try { v.reset ? v.reset() : (v.focus && v.focus(null, true)); } catch (err) {} }, 240);
}
function showBeat(bi) {
  const b = (P.sc.beats || [])[bi]; let id = b && b.visual;
  if (!P.vis[id]) id = Object.keys(P.vis)[0];
  const v = P.vis[id]; if (v === P.cur) return;
  const old = P.cur; P.cur = v; exitVis(old); enterVis(v);
}
function sceneTime() { return P.useClock ? (performance.now() - P.t0) / 1000 : audio.currentTime; }
function sync() {
  if (!P.playing || !P.sc) return;
  const t = sceneTime(); const beats = P.sc.beats || [];
  let bi = 0; for (let i = 0; i < beats.length; i++) if ((beats[i].start || 0) <= t + 0.001) bi = i;
  if (bi !== P.bi) { P.bi = bi; P.focus = undefined; showBeat(bi); TLOG.push({ k: "beat", sc: P.sc.scene_id, v: beats[bi] && beats[bi].visual, want: beats[bi] ? beats[bi].start : 0, at: +t.toFixed(3) }); }
  const lines = (beats[bi] && beats[bi].lines) || []; let f = null, spk = null, lw = null;
  for (const l of lines) if ((l.start || 0) <= t + 0.001) { f = l.focus == null ? null : String(l.focus); spk = l.speaker || null; lw = l.start; }
  if (f !== P.focus) { P.focus = f; TLOG.push({ k: "focus", sc: P.sc.scene_id, f, want: lw, at: +t.toFixed(3) }); try { P.cur && P.cur.focus && P.cur.focus(f); } catch (e) { console.warn(e); } }
  if (P.useClock && t >= P.dur) sceneEnded();
  else if (CUT && t >= CUT) { audio.pause(); sceneEnded(); }      /* ?cut=<s> (demo): end every scene early to look at transitions */
}
function frame(ts) { tickRolls(ts); sync(); requestAnimationFrame(frame); }

/* T8 stinger: four skewed panels cover the scene area, the scene swaps underneath, audio starts, panels clear */
const STING = { cover: 600, audio: 1300, done: 1940 };   // title slate readable for ~0.6 s (networks hold a branded slate)
function runStinger(title, onCover, onAudio) {
  const s = $("sting"); const panels = [...s.querySelectorAll(".sp")]; const lock = s.querySelector(".lock"); const rule = lock.querySelector(".rule");
  setText("stB1", `${T.brandA} ${T.brandB}`.trim()); setText("stB2", title);
  if (INSTANT) { onCover(); onAudio(); return; }
  s.classList.add("go");
  const sk = " skewX(-25deg)";
  panels.forEach((p, i) => p.animate([{ transform: "translateX(0px)" + sk }, { transform: "translateX(2800px)" + sk, offset: 0.42 }, { transform: "translateX(2800px)" + sk, offset: 0.58 }, { transform: "translateX(5700px)" + sk }],
    { duration: 1000 + 0, delay: i * 60, easing: "linear", fill: "both", composite: "replace" }));
  // per-panel easing via keyframe offsets: enter 420 ms, hold, exit 420 ms (exit order reversed below)
  panels.forEach(p => p.getAnimations().forEach(a => a.cancel()));
  panels.forEach((p, i) => {
    const enterDelay = i * 60, exitDelay = STING.audio - 0 + (panels.length - 1 - i) * 60;
    p.animate([{ transform: "translateX(0px)" + sk }, { transform: "translateX(2800px)" + sk }], { duration: 420, delay: enterDelay, easing: "cubic-bezier(.65,0,.35,1)", fill: "forwards" });
    setTimeout(() => { p.getAnimations().forEach(a => a.cancel()); p.animate([{ transform: "translateX(2800px)" + sk }, { transform: "translateX(5700px)" + sk }], { duration: 440, easing: "cubic-bezier(.65,0,.35,1)", fill: "forwards" }); }, exitDelay);
  });
  lock.animate([{ opacity: 0, transform: "translateY(18px)" }, { opacity: 1, transform: "translateY(0px)", offset: .25 },
                { opacity: 1, transform: "translateY(0px)", offset: .82 }, { opacity: 0, transform: "translateY(-10px)" }],
               { duration: 820, delay: STING.cover - 120, easing: "cubic-bezier(.16,1,.3,1)", fill: "both" });
  rule.animate([{ width: "0px" }, { width: "520px" }], { duration: 380, delay: STING.cover - 20, easing: "cubic-bezier(.16,1,.3,1)", fill: "both" });
  setTimeout(onCover, STING.cover);
  setTimeout(onAudio, STING.audio);
  setTimeout(() => { s.classList.remove("go"); panels.forEach(p => p.getAnimations().forEach(a => a.cancel())); lock.getAnimations().forEach(a => a.cancel()); rule.getAnimations().forEach(a => a.cancel()); }, STING.audio + 3 * 60 + 460);
}
function audioUrl(m, sc) {
  const a = sc.audio || {}; const name = a.path || String(a.key || "").split("/").pop(); if (!name) return null;
  if (DEMO) return [`election/sample/pkg/${name}`, `election/sample/${name}`, `election/sample/${encodeURIComponent(m.package_id)}/${name}`];
  return [`live/${encodeURIComponent(m.package_id)}/${encodeURIComponent(name)}`];
}
async function playIndex(i) {
  if (!P.playlist.length) return;
  P.idx = ((i % P.playlist.length) + P.playlist.length) % P.playlist.length;
  const sc = scenesById(P.pkg)[P.playlist[P.idx]]; if (!sc) { setTimeout(advance, 500); return; }
  P.playing = false; P.busy = true;
  const urls = audioUrl(P.pkg, sc); let urlI = 0;
  if (urls) { audio.src = urls[0]; audio.load(); }
  const built = buildScene(sc);                 // geometry + DOM; awaited under the stinger cover
  heartbeat(sc);
  runStinger(sceneTitle(sc), async () => {
    const { root, vis } = await built;
    if (P.root) { for (const k in P.vis) try { P.vis[k].destroy && P.vis[k].destroy(); } catch (e) {} P.root.remove(); }
    P.root = root; P.vis = vis; P.sc = sc; P.cur = null; P.bi = -1; P.focus = undefined;
    $("scene").appendChild(root); layoutScene(root, vis);
  }, async () => {
    await built;
    const dur = (sc.audio && sc.audio.duration) || Math.max(10, ...(sc.beats || []).map(b => b.end || 0));
    P.dur = dur;
    const seek = SEEK; SEEK = 0;                  /* ?seek=<s> (demo): start the first scene part-way, to look at its end and the next transition */
    const startClock = () => { P.useClock = true; P.t0 = performance.now() - seek * 1000; P.playing = true; P.busy = false; };
    if (!urls) { startClock(); return; }
    audio.onerror = () => {
      if (urls[++urlI]) { audio.src = urls[urlI]; audio.load(); audio.play().catch(() => {}); return; }
      if (DEMO) { startClock(); return; }
      P.failures++; console.warn("audio failed", sc.scene_id); if (!P.playing) startClock();   // keep the visuals honest to the timeline; advance at duration
    };
    P.useClock = false; P.playing = true; P.busy = false;
    if (seek) { try { audio.currentTime = seek; } catch (e) {} }
    const pr = audio.play(); if (pr && pr.catch) pr.catch(err => { if (err && err.name === "NotAllowedError") { $("start").hidden = false; } });
  });
}
function sceneEnded() { if (!P.playing) return; P.playing = false; advance(); }
/* new package: play the scene of the NEW playlist whose key follows the current scene's key (never restart from the top) */
function nextIndexIn(m, curKey, oldPkg, oldPl, oldIdx) {
  const pl = playlistOf(m); const by = scenesById(m); const keys = pl.map(id => (by[id] || {}).key);
  let i = keys.indexOf(curKey); if (i >= 0) return (i + 1) % pl.length;
  const ob = scenesById(oldPkg); const nk = oldPl.length ? (ob[oldPl[(oldIdx + 1) % oldPl.length]] || {}).key : null;
  i = nk ? keys.indexOf(nk) : -1; return i >= 0 ? i : 0;
}
function advance() {
  if (P.next) {
    const nextIdx = P.pkg.standby ? 0 : nextIndexIn(P.next, P.sc && P.sc.key, P.pkg, P.playlist, P.idx);
    P.pkg = P.next; P.next = null; P.playlist = playlistOf(P.pkg); onPackage(P.pkg); playIndex(nextIdx);
  } else playIndex(P.idx + 1);
}
audio.addEventListener("ended", () => { if (!P.useClock) sceneEnded(); });
function heartbeat(sc) {
  if (DEMO || (P.pkg && P.pkg.standby)) return;
  try { fetch("live/playback", { method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true,
    body: JSON.stringify({ package_id: P.pkg.package_id, scene_id: sc.scene_id, playlist_index: P.idx }) }).catch(() => {}); } catch (e) {}
}
function onPackage(m) {
  loadUS().catch(() => {});
  (m.scenes || []).filter(s => s.kind === "state" && s.snapshot && s.snapshot.state).forEach(s => loadState(s.snapshot.state, s.snapshot.units && s.snapshot.units.geo));
  $("testBadge").hidden = !(m.is_test || (DESK && DESK.is_test) || (m.scenes || []).some(s => s.snapshot && s.snapshot.test_data));
  const nat = (m.scenes || []).find(s => s.kind === "national"); if (nat && nat.snapshot) NAT_FALLBACK = nat.snapshot;
  STRIP.fallback = (m.scenes || []).filter(s => s.kind === "state" && s.snapshot).map(s => { const x = s.snapshot; const av = isAvail(x);
    return { state: x.state, state_name: x.state_name, status: x.phase === "preview" ? "polls_open" : av ? "counting" : "polls_closed",
             rows: (x.candidates || []).map(c => ({ short: c.short, party: c.party, pct: c.pct, incumbent: c.incumbent })), counted_vs_2022_pct: x.counted_vs_2022 && x.counted_vs_2022.pct }; });
  warmFonts(m); renderChrome();
}
function warmFonts(m) {
  const bits = [JSON.stringify(T), ...(m.scenes || []).map(s => JSON.stringify(s.snapshot || {}).slice(0, 20000))];
  const fw = $("fontwarm");
  fw.innerHTML = ["var(--f-cond)", "var(--f-num)", "var(--f-sans)"].flatMap(f => [400, 700, 900].map(w => `<div style="font-family:${f};font-weight:${w}">${esc(bits.join(" ").replace(/[{}"\[\]:,]/g, " ").slice(0, 30000))}</div>`)).join("");
}

/* =====================================================================  data: live / demo  */
async function fetchJSON(url) { const r = await fetch(url, { cache: "no-store" }); if (r.status === 204) return null; if (!r.ok) throw new Error(url + " HTTP " + r.status); return r.json(); }
async function demoLoad(kind) {
  const urls = MOCK_ONLY ? [`election/sample/mock_${kind}_${LANG}.json`] : [`election/sample/${kind}_${LANG}.json`, `election/sample/mock_${kind}_${LANG}.json`];
  for (const u of urls) { try { const j = await fetchJSON(u); if (j) return j; } catch (e) {} }
  return null;
}
async function deskPoll() {
  try { const d = DEMO ? await demoLoad("desk") : await fetchJSON("live/desk.json"); if (d) { DESK = d; if (d.is_test) $("testBadge").hidden = false; renderChrome(); } } catch (e) { console.warn("desk", e); }
}
function standbyPkg() {
  const nat = DESK && DESK.national; if (!nat) return null;
  const beats = [{ visual: "nat_map", start: 0, end: 20, lines: [] }, { visual: "nat_schedule", start: 20, end: 40, lines: [] }, { visual: "nat_balance", start: 40, end: 60, lines: [] }];
  return { package_id: "standby", standby: true, playlist: ["standby"], scenes: [{ scene_id: "standby", key: "standby", kind: "national", audio: { path: null, duration: 60 }, beats, snapshot: nat }] };
}
async function manifestPoll() {
  try {
    const m = await fetchJSON("live/current.json");
    if (!m) { if (!P.pkg) { const sb = standbyPkg(); if (sb) { P.pkg = sb; P.playlist = sb.playlist; onPackage(sb); playIndex(0); } } return; }
    if (!m.package_id || !Array.isArray(m.scenes) || !m.scenes.length) throw new Error("bad manifest");
    if (!P.pkg) { P.pkg = m; P.playlist = playlistOf(m); onPackage(m); playIndex(0); }
    else if (P.pkg.standby && !P.next) { P.next = m; if (P.playing) sceneEnded(); }
    else if (m.package_id !== P.pkg.package_id && (!P.next || P.next.package_id !== m.package_id)) P.next = m;
  } catch (e) { console.warn("manifest", e); }
}

/* =====================================================================  still mode (screenshots)  */
async function still() {
  const m = await demoLoad("manifest"); if (!m) { document.body.dataset.thumbError = "no sample manifest"; return; }
  P.pkg = m; onPackage(m);
  const vis = Q.get("visual"); const focus = Q.get("focus");
  const sc = (m.scenes || []).find(s => s.key === STILL || s.scene_id === STILL || (STILL === "national" && s.kind === "national"));
  if (!sc) { document.body.dataset.thumbError = "no scene " + STILL; return; }
  if (Q.get("call") === "1" && sc.snapshot && sc.snapshot.candidates) {
    const c = sc.snapshot.candidates[0];
    sc.snapshot.call = { key: c.key, text: `[TEST] AP declared ${c.name} the winner (test text)`, credit: "Race call: The Associated Press (via apnews.com), 10:42 PM ET" };
  }
  const mid = Q.get("mid"), sting = Q.get("sting");
  INSTANT = !(mid || sting); if (INSTANT) STAGE.classList.add("instant");
  const id = vis || visIdsFor(sc)[0];
  const v = await buildVisual(sc, id); const root = div("scn"); root.appendChild(v.el); $("scene").appendChild(root);
  P.sc = sc; P.vis = { [id]: v }; layoutScene(root, P.vis);
  enterVis(v); P.cur = v;
  if (focus) v.focus(focus, INSTANT);
  if (sting) {
    INSTANT = false; runStinger(sceneTitle(sc), () => {}, () => {});
    await new Promise(r => setTimeout(r, +sting)); document.getAnimations().forEach(a => a.pause());
  } else if (mid) {
    await new Promise(r => setTimeout(r, +mid)); document.getAnimations().forEach(a => a.pause()); ROLLS.forEach(r => { r.t0 = Infinity; });
  }
  await new Promise(r => setTimeout(r, 300));
  document.body.dataset.thumbReady = JSON.stringify({ still: STILL, visual: id, focus });
}

/* =====================================================================  boot  */
function fit() { const s = Math.min(innerWidth / 1920, innerHeight / 1080); STAGE.style.transform = `translate(-50%,-50%) scale(${s})`; }
addEventListener("resize", fit); fit();
(async function boot() {
  renderStatic();
  try { await Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 4000))]); } catch (e) {}
  loadUS().catch(e => console.warn("us geo", e));
  if (DEMO) {
    DESK = await demoLoad("desk");
    const ref = Q.get("now") ? Date.parse(Q.get("now")) : DESK && DESK.as_of ? Date.parse(DESK.as_of) : null;
    if (ref && !isNaN(ref)) CLOCK_OFF = ref - Date.now();
    if (DESK && DESK.is_test) $("testBadge").hidden = false;
  } else await deskPoll();
  renderChrome(); renderClock();
  setInterval(() => { renderPollClose(); renderClock(); }, 1000);
  setInterval(() => stripShow(false), 10000);
  requestAnimationFrame(frame);
  if (STILL) { await still(); return; }
  try { await Promise.race([document.fonts.load("700 40px Oswald"), new Promise(r => setTimeout(r, 2500))]); } catch (e) {}
  if (DEMO) {
    const m = await demoLoad("manifest"); if (!m) { console.warn("no demo manifest"); return; }
    P.pkg = m; P.playlist = playlistOf(m); onPackage(m);
    await loadUS(); await Promise.all((m.scenes || []).filter(s => s.kind === "state").map(s => loadState(s.snapshot.state, s.snapshot.units && s.snapshot.units.geo)));
    const go = () => playIndex(+(Q.get("scene") || 0));
    const needsGesture = (m.scenes || []).some(s => s.audio && s.audio.path) && Q.get("autoplay") !== "1";
    if (needsGesture) { $("start").hidden = false; $("startBtn").onclick = () => { $("start").hidden = true; go(); }; } else go();
    setInterval(deskPoll, 30000);
    return;
  }
  setInterval(deskPoll, 30000);
  if (Q.get("autoplay") !== "1") { $("start").hidden = false; $("startBtn").onclick = () => { $("start").hidden = true; audio.play().catch(() => {}); }; }
  manifestPoll(); setInterval(manifestPoll, 5000);
})();
