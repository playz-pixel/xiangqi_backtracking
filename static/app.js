
const state = {
  board: [],
  turn: "red",
  selected: null,
  moves: [],
  lastMove: null,
  gameOver: false,
  mode: "human_vs_bt",
  redAlgorithm: "human",
  blackAlgorithm: "backtracking",
};

const CHARS = {
  K:"帥", A:"仕", E:"相", H:"傌", R:"俥", C:"炮", P:"兵",
  k:"將", a:"士", e:"象", h:"馬", r:"車", c:"砲", p:"卒"
};

const ALGO_LABEL = { human: "Người chơi", backtracking: "Backtracking (Minimax + Alpha-Beta)", bfs: "BFS (Tìm kiếm theo chiều rộng)" };

const wrap = document.getElementById("boardWrap");
const statusEl = document.getElementById("status");
const turnEl = document.getElementById("turn");
const historyEl = document.getElementById("history");
const checkEl = document.getElementById("check");
const depthEl = document.getElementById("depth");
const lastNodesEl = document.getElementById("lastNodes");
const lastTimeEl = document.getElementById("lastTime");
const lastDepthEl = document.getElementById("lastDepth");
const lastMateInEl = document.getElementById("lastMateIn");
const lastMemoryEl = document.getElementById("lastMemory");
const modeInfoEl = document.getElementById("modeInfo");
const toggleModeBtn = document.getElementById("toggleMode");
const aiMoveBtn = document.getElementById("aiMove");
const aiVsAiStepBtn = document.getElementById("aiVsAiStep");
const aiVsAiRunBtn = document.getElementById("aiVsAiRun");
const viewCompareBtn = document.getElementById("viewCompare");
const guideList = document.getElementById("guideList");

let searchChart = null;
let compareNodesChart = null;
let compareTimeChart = null;
let compareScoreChart = null;
let compareMemoryChart = null;

function sideOf(p) {
  if (!p) return null;
  return p === p.toUpperCase() ? "red" : "black";
}

async function getJSON(url, options={}) {
  const res = await fetch(url, options);
  return await res.json();
}

async function refresh() {
  const s = await getJSON("/api/state");
  applyState(s);
}

function applyState(s) {
  state.board = s.board;
  state.turn = s.turn;
  state.lastMove = s.lastMove;
  state.gameOver = s.gameOver;
  state.mode = s.mode || state.mode;
  state.redAlgorithm = s.redAlgorithm || state.redAlgorithm;
  state.blackAlgorithm = s.blackAlgorithm || state.blackAlgorithm;
  state.selected = null;
  state.moves = [];
  render(s);
  updateModeUI();
}

function updateStatsPanel(info) {
  if (!info) return;
  if (info.nodes !== undefined) lastNodesEl.textContent = (info.nodes || 0).toLocaleString();
  if (info.timeMs !== undefined) lastTimeEl.textContent = info.timeMs !== null ? `${info.timeMs} ms` : "—";
  if (info.depth !== undefined) lastDepthEl.textContent = info.depth ?? "—";
  lastMateInEl.textContent = (info.mateIn === null || info.mateIn === undefined) ? "Chưa tìm thấy" : `${info.mateIn} ply`;
  if (info.peakMemoryKb !== undefined) {
    lastMemoryEl.textContent = (info.peakMemoryKb === null) ? "—" : `${info.peakMemoryKb} KB`;
  }
}

function updateModeUI() {
  const isCompareMode = state.mode === "bt_vs_other";
  toggleModeBtn.textContent = isCompareMode
    ? "Chế độ: Backtracking vs BFS"
    : "Chế độ: Người vs Backtracking";
  aiMoveBtn.hidden = isCompareMode;
  aiVsAiStepBtn.hidden = !isCompareMode;
  aiVsAiRunBtn.hidden = !isCompareMode;
  viewCompareBtn.hidden = !isCompareMode;

  if (isCompareMode) {
    modeInfoEl.innerHTML = `Đỏ = <b>${ALGO_LABEL.bfs}</b> &nbsp;|&nbsp; Đen = <b>${ALGO_LABEL.backtracking}</b>. Hai thuật toán tự động đấu với nhau để so sánh hiệu quả.`;
    guideList.innerHTML = `
      <li>Đỏ dùng thuật toán BFS: duyệt cây bằng hàng đợi theo từng lớp, không cắt tỉa.</li>
      <li>Đen dùng Backtracking (Minimax + Alpha-Beta), nhìn trước nhiều nước.</li>
      <li>Nhấn <b>Chạy 1 nước</b> để xem từng bước, hoặc <b>Tự động 10 nước</b> để chạy nhanh.</li>
      <li>Nhấn <b>Biểu đồ so sánh</b> để xem số nút duyệt, thời gian và điểm số của 2 thuật toán.</li>
      <li>Quân Đen vừa đi sẽ sáng lên để dễ theo dõi.</li>`;
  } else {
    modeInfoEl.innerHTML = `Đỏ = <b>Người chơi</b> &nbsp;|&nbsp; Đen = <b>${ALGO_LABEL.backtracking}</b>.`;
    guideList.innerHTML = `
      <li>Đỏ là người chơi, Đen là AI.</li>
      <li>Click vào quân cờ để xem các ô đi hợp lệ.</li>
      <li>Các chấm tròn là nước có thể đi.</li>
      <li>Click ô đích để thực hiện nước đi.</li>
      <li>Sau khi Đỏ đi, AI tự động tìm nước bằng Backtracking. Quân Đen vừa đi sẽ <b>sáng lên</b> để dễ nhận biết.</li>`;
  }
}

function render(s) {
  statusEl.textContent = s.message;
  turnEl.textContent = s.turn === "red"
    ? (state.mode === "bt_vs_other" ? "ĐỎ (BFS)" : "ĐỎ (bạn)")
    : "ĐEN (Backtracking)";
  historyEl.textContent = s.historyLength;
  checkEl.textContent = s.gameOver ? "Kết thúc" : (s.check ? "Đang bị chiếu" : "Bình thường");
  wrap.innerHTML = "";
  wrap.appendChild(drawBoard());
}

function esc(s) {
  return s.replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
}

function drawBoard() {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 900 980");
  svg.classList.add("board-svg");

  // Outer wooden frame
  addRect(svg, 8, 8, 884, 964, 34, "#b85a08", "#7d3a08", 6);
  addRect(svg, 42, 42, 816, 888, 10, "#f6b33f", "#6b461e", 3);

  const left=65, top=60, cell=96, right=833, bottom=924;
  // Grid: 10 rows x 9 files. The river is exactly one cell high.
  for (let r=0; r<10; r++) {
    const y = top + r*cell;
    addLine(svg, left, y, right, y);
  }
  for (let c=0; c<9; c++) {
    const x = left + c*cell;
    addLine(svg, x, top, x, top + 4*cell);
    addLine(svg, x, top + 5*cell, x, bottom);
  }
  // River boundary lines
  addLine(svg, left, top+4*cell, right, top+4*cell);
  addLine(svg, left, top+5*cell, right, top+5*cell);

  // Palace diagonals
  addLine(svg, left+3*cell, top, left+5*cell, top+2*cell);
  addLine(svg, left+5*cell, top, left+3*cell, top+2*cell);
  addLine(svg, left+3*cell, top+7*cell, left+5*cell, top+9*cell);
  addLine(svg, left+5*cell, top+7*cell, left+3*cell, top+9*cell);

  // River text
  addText(svg, 315, top+4*cell+48, "楚", 36, "#7d5423");
  addText(svg, 565, top+4*cell+48, "漢", 36, "#7d5423");

  // Star points
  [[2,1],[2,7],[7,1],[7,7]].forEach(([r,c]) => drawStar(svg, left+c*cell, top+r*cell));
  [[3,0],[3,2],[3,4],[3,6],[3,8],[6,0],[6,2],[6,4],[6,6],[6,8]].forEach(([r,c]) => drawStar(svg, left+c*cell, top+r*cell));

  // Last move highlight
  if (state.lastMove) {
    [state.lastMove.from, state.lastMove.to].forEach(([r,c]) => {
      const y = boardY(r);
      addCircle(svg, left+c*cell, y, 31, "none", "#2b6cb0", 5, .35);
    });
  }

  // Hints
  state.moves.forEach(m => {
    const [r,c] = m.to;
    const g = document.createElementNS(NS,"g");
    g.classList.add("hit");
    g.addEventListener("click", () => doMove(state.selected, [r,c]));
    const circle = addCircle(g, left+c*cell, boardY(r), 13, "#fff1a8", "#6c4f16", 2, .95);
    svg.appendChild(g);
  });

  // Pieces
  for (let r=0;r<10;r++) {
    for (let c=0;c<9;c++) {
      const p = state.board[r]?.[c];
      if (!p) continue;
      drawPiece(svg, p, r, c);
    }
  }
  return svg;
}

function boardY(r) {
  return 60 + r*96;
}

function addRect(parent,x,y,w,h,rx,fill,stroke,sw) {
  const NS="http://www.w3.org/2000/svg";
  const el=document.createElementNS(NS,"rect");
  [["x",x],["y",y],["width",w],["height",h],["rx",rx],["fill",fill],["stroke",stroke],["stroke-width",sw]].forEach(([a,v])=>el.setAttribute(a,v));
  parent.appendChild(el); return el;
}
function addLine(parent,x1,y1,x2,y2,stroke="#5b3e20",sw=3) {
  const NS="http://www.w3.org/2000/svg"; const el=document.createElementNS(NS,"line");
  [["x1",x1],["y1",y1],["x2",x2],["y2",y2],["stroke",stroke],["stroke-width",sw]].forEach(([a,v])=>el.setAttribute(a,v));
  parent.appendChild(el); return el;
}
function addCircle(parent,cx,cy,r,fill,stroke,sw=1,op=1) {
  const NS="http://www.w3.org/2000/svg"; const el=document.createElementNS(NS,"circle");
  [["cx",cx],["cy",cy],["r",r],["fill",fill],["stroke",stroke],["stroke-width",sw],["opacity",op]].forEach(([a,v])=>el.setAttribute(a,v));
  parent.appendChild(el); return el;
}
function addText(parent,x,y,text,size,fill) {
  const NS="http://www.w3.org/2000/svg"; const el=document.createElementNS(NS,"text");
  el.setAttribute("x",x); el.setAttribute("y",y); el.setAttribute("text-anchor","middle");
  el.setAttribute("dominant-baseline","middle"); el.setAttribute("font-size",size);
  el.setAttribute("font-family","Noto Serif CJK SC, SimSun, serif"); el.setAttribute("fill",fill);
  el.textContent=text; parent.appendChild(el); return el;
}
function drawStar(svg,x,y) {
  const NS="http://www.w3.org/2000/svg";
  const g=document.createElementNS(NS,"g");
  const s=9;
  [[-18,0,-4,0],[4,0,18,0],[0,-18,0,-4],[0,4,0,18]].forEach(a=>addLine(g,x+a[0],y+a[1],x+a[2],y+a[3],"#5b3e20",2));
  svg.appendChild(g);
}
function drawPiece(svg,p,r,c) {
  const NS="http://www.w3.org/2000/svg";
  const g=document.createElementNS(NS,"g");
  g.classList.add("piece");
  const isBlack = sideOf(p) === "black";
  // Quân Đen luôn là quân của AI. Nếu đây chính là ô mà nước đi GẦN NHẤT vừa đến,
  // và quân đứng đó là quân Đen -> cho quân này "sáng" lên để người xem biết AI vừa đi đâu.
  const justMovedByAI = isBlack && state.lastMove &&
    state.lastMove.to[0] === r && state.lastMove.to[1] === c;
  if (justMovedByAI) g.classList.add("ai-moved");
  const x=65+c*96, y=boardY(r), color=isBlack ? "#201b18" : "#b32121";
  g.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (state.gameOver || state.mode !== "human_vs_bt") return;

    // Nếu ô này đang là đích ăn quân của quân đã chọn,
    // cho phép click trực tiếp vào quân đối phương để thực hiện bắt quân.
    const canCapture = state.selected &&
      state.moves.some(m => m.to[0] === r && m.to[1] === c);
    if (canCapture && sideOf(p) !== state.turn) {
      await doMove(state.selected, [r, c]);
      return;
    }

    // Quân đối phương không được chọn làm quân đang di chuyển.
    if (state.turn !== sideOf(p)) return;

    const data=await getJSON(`/api/moves/${r}/${c}`);
    state.selected=[r,c];
    state.moves=data.moves || [];
    wrap.innerHTML="";
    wrap.appendChild(drawBoard());
  });
  if (justMovedByAI) {
    // Vòng hào quang phía sau quân cờ, cùng với animation "ai-moved" trong CSS.
    addCircle(g, x, y, 40, "none", "#7fd7ff", 4, .9);
  }
  addCircle(g,x+2,y+3,35,"#000", "none", 0, .15);
  addCircle(g,x,y,34,"#f7e8bf","#5e4328",3,1);
  addCircle(g,x,y,29,"none",color,2,1);
  const t=addText(g,x,y+1,CHARS[p] || p,36,color);
  t.setAttribute("font-weight","700");
  svg.appendChild(g);
}

async function doMove(from,to) {
  if (!from) return;
  const result=await getJSON("/api/move", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify({from,to,depth:parseInt(depthEl.value,10)})
  });
  if (!result.ok) { alert(result.message); return; }

  applyState(result.state);

  // /api/move đã thực hiện luôn AI trên server. Không gọi /api/ai lần nữa.
  if (result.ai && result.ai.move) {
    const m = result.ai.move;
    const captured = result.ai.capturedPiece ? `, ăn ${result.ai.capturedPiece}` : "";
    const mateTxt = result.ai.mateIn !== null && result.ai.mateIn !== undefined ? ` | Tìm thấy chiếu bí trong ${result.ai.mateIn} ply!` : "";
    statusEl.textContent = `AI đã đi: (${m.from[0]},${m.from[1]}) → (${m.to[0]},${m.to[1]})${captured} | Backtracking: độ sâu ${result.ai.depth}, duyệt ${(result.ai.nodes || 0).toLocaleString()} nút, ${result.ai.timeMs} ms.${mateTxt}`;
    updateStatsPanel({ nodes: result.ai.nodes, timeMs: result.ai.timeMs, depth: result.ai.depth, mateIn: result.ai.mateIn, peakMemoryKb: result.ai.peakMemoryKb });
  }
}

async function runAI() {
  if (state.turn !== "black" || state.gameOver) {
    statusEl.textContent = state.gameOver ? "Ván đã kết thúc." : "Chưa đến lượt Đen (AI). Sau khi Đỏ đi, AI sẽ tự động đi.";
    return;
  }
  statusEl.textContent = "AI đang suy nghĩ bằng Backtracking...";
  aiMoveBtn.disabled = true;
  const depth = parseInt(depthEl.value, 10);
  try {
    const result = await getJSON("/api/ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ depth })
    });

    if (result.state) {
      applyState(result.state);
    }

    if (result.ok && result.state?.lastMove) {
      const m = result.state.lastMove;
      const captured = result.capturedPiece ? `, ăn ${result.capturedPiece}` : "";
      const mateTxt = result.mateIn !== null && result.mateIn !== undefined ? ` | Tìm thấy chiếu bí trong ${result.mateIn} ply!` : "";
      statusEl.textContent = `AI đã đi: (${m.from[0]},${m.from[1]}) → (${m.to[0]},${m.to[1]})${captured} | Đã duyệt ${(result.nodes || 0).toLocaleString()} nút, ${result.timeMs} ms.${mateTxt}`;
      updateStatsPanel({ nodes: result.nodes, timeMs: result.timeMs, depth: result.depth, mateIn: result.mateIn, peakMemoryKb: result.peakMemoryKb });
    } else if (!result.ok) {
      statusEl.textContent = result.message || "AI không thực hiện được nước đi.";
    }
  } catch (err) {
    console.error(err);
    statusEl.textContent = "Không gọi được AI. Hãy kiểm tra Terminal Flask.";
  } finally {
    aiMoveBtn.disabled = false;
  }
}

async function toggleMode() {
  const nextMode = state.mode === "bt_vs_other" ? "human_vs_bt" : "bt_vs_other";
  const result = await getJSON("/api/mode", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: nextMode })
  });
  if (result.ok) {
    applyState(result.state);
    document.getElementById("searchPanel").hidden = true;
    document.getElementById("comparePanel").hidden = true;
  }
}

async function aiVsAiStep() {
  const depth = parseInt(depthEl.value, 10);
  aiVsAiStepBtn.disabled = true;
  try {
    const result = await getJSON("/api/ai-vs-ai/step", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ depth })
    });
    if (result.state) applyState(result.state);
    if (result.entry) {
      const e = result.entry;
      const captured = e.capturedPiece ? `, ăn ${e.capturedPiece}` : "";
      statusEl.textContent = `${e.side === "black" ? "Đen (Backtracking)" : "Đỏ (BFS)"} đi (${e.move.from[0]},${e.move.from[1]})→(${e.move.to[0]},${e.move.to[1]})${captured} | ${e.nodes} nút, ${e.timeMs} ms.`;
      updateStatsPanel({ nodes: e.nodes, timeMs: e.timeMs, depth: e.depth, mateIn: e.mateIn, peakMemoryKb: e.peakMemoryKb });
    } else if (!result.ok) {
      statusEl.textContent = result.message || "Không thực hiện được nước đi.";
    }
  } finally {
    aiVsAiStepBtn.disabled = false;
  }
}

async function aiVsAiRun() {
  const depth = parseInt(depthEl.value, 10);
  aiVsAiRunBtn.disabled = true;
  statusEl.textContent = "Đang tự động chạy Backtracking vs BFS...";
  try {
    const result = await getJSON("/api/ai-vs-ai/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ depth, maxMoves: 10 })
    });
    if (result.state) applyState(result.state);
    statusEl.textContent = `Đã tự động chạy ${result.entries.length} nước. Nhấn "Biểu đồ so sánh" để xem chi tiết.`;
  } finally {
    aiVsAiRunBtn.disabled = false;
  }
}

async function showSearchLog() {
  const panel = document.getElementById("searchPanel");
  const summary = document.getElementById("searchSummary");
  const log = document.getElementById("searchLog");
  try {
    const data = await getJSON("/api/ai/search-log");
    log.innerHTML = "";
    const stats = data.stats || {};
    const modeTxt = stats.super_hard ? " (chế độ Siêu khó — Iterative Deepening)" : "";
    summary.textContent = data.moves.length
      ? `Độ sâu ${data.depth}${modeTxt} • ${data.moves.length.toLocaleString()} nước Đen được duyệt • ${data.nodes.toLocaleString()} nút Backtracking • ${stats.time_ms ?? "—"} ms.`
      : "Chưa có dữ liệu. Hãy để AI đi ít nhất một nước trước.";

    data.moves.forEach((item, index) => {
      const li = document.createElement("li");
      const m = item.move;
      const captured = item.captured ? ` • ăn ${item.captured}` : "";
      const score = Number.isFinite(item.score) ? ` • điểm ${item.score}` : "";
      li.textContent = `#${index + 1} | tầng ${item.ply}: (${m.from[0]},${m.from[1]}) → (${m.to[0]},${m.to[1]})${captured}${score}`;
      log.appendChild(li);
    });

    drawSearchChart(data.moves);
    panel.hidden = false;
  } catch (err) {
    console.error(err);
    if (typeof Chart === "undefined") {
      alert("Không tìm thấy thư viện vẽ biểu đồ (Chart.js). Hãy chắc chắn thư mục static/vendor/chart.umd.js tồn tại và đã chạy lại server Flask.");
    } else {
      alert("Không đọc được danh sách Backtracking.");
    }
  }
}

function drawSearchChart(moves) {
  const ctx = document.getElementById("searchChart");
  const top = moves.slice(0, 20); // giới hạn để biểu đồ dễ đọc
  const labels = top.map((m, i) => `(${m.move.from[0]},${m.move.from[1]})→(${m.move.to[0]},${m.move.to[1]})`);
  const data = top.map(m => m.score ?? 0);
  if (searchChart) searchChart.destroy();
  searchChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Điểm đánh giá sau khi thử nước (Backtracking, tầng 1)",
        data,
        backgroundColor: data.map(v => v >= 0 ? "#2b6cb0" : "#b32121"),
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: true } },
      scales: { x: { ticks: { autoSkip: false, maxRotation: 70, minRotation: 40 } } }
    }
  });
}

async function showCompareChart() {
  const panel = document.getElementById("comparePanel");
  const summary = document.getElementById("compareSummary");
  try {
    const data = await getJSON("/api/comparison");
    const log = data.comparisonLog || [];
    if (!log.length) {
      summary.textContent = "Chưa có dữ liệu. Hãy chạy vài nước ở chế độ Backtracking vs BFS trước.";
      panel.hidden = false;
      return;
    }
    const btEntries = log.filter(e => e.algorithm === "backtracking");
    const bfsEntries = log.filter(e => e.algorithm === "bfs");
    const avg = (arr, key) => arr.length ? Math.round(arr.reduce((s, e) => s + (e[key] || 0), 0) / arr.length) : 0;
    const avgF = (arr, key) => arr.length ? (arr.reduce((s, e) => s + (e[key] || 0), 0) / arr.length).toFixed(1) : 0;
    summary.innerHTML = `
      Backtracking: ${btEntries.length} nước • trung bình ${avg(btEntries, "nodes").toLocaleString()} nút/nước • trung bình ${avg(btEntries, "timeMs")} ms/nước • bộ nhớ ~${avgF(btEntries, "peakMemoryKb")} KB/nước.<br>
      BFS: ${bfsEntries.length} nước • trung bình ${avg(bfsEntries, "nodes").toLocaleString()} nút/nước • trung bình ${avg(bfsEntries, "timeMs")} ms/nước • bộ nhớ ~${avgF(bfsEntries, "peakMemoryKb")} KB/nước.<br>
      → BFS duyệt TOÀN BỘ cây trong giới hạn độ sâu (không cắt tỉa) nên số nút thường nhiều hơn Backtracking rõ rệt ở cùng độ sâu; Backtracking dùng Alpha-Beta để bỏ qua sớm các nhánh chắc chắn không tốt hơn, nhờ đó có thể tìm sâu hơn trong cùng thời gian.<br>
      → Về <b>bộ nhớ</b>: Backtracking (DFS + quay lui) chỉ cần lưu 1 đường đi tại 1 thời điểm — độ phức tạp không gian O(b×m); BFS phải lưu TOÀN BỘ cây đã duyệt trong hàng đợi — độ phức tạp không gian O(b^d), nên tốn bộ nhớ hơn hẳn dù cùng độ sâu (xem biểu đồ bộ nhớ bên dưới).`;

    drawCompareCharts(log);
    panel.hidden = false;
  } catch (err) {
    console.error(err);
    if (typeof Chart === "undefined") {
      alert("Không tìm thấy thư viện vẽ biểu đồ (Chart.js). Hãy chắc chắn thư mục static/vendor/chart.umd.js tồn tại và đã chạy lại server Flask.");
    } else {
      alert("Không đọc được dữ liệu so sánh.");
    }
  }
}

function drawCompareCharts(log) {
  const labels = log.map(e => `#${e.moveNumber}`);
  const nodesBT = log.map(e => e.algorithm === "backtracking" ? e.nodes : null);
  const nodesGR = log.map(e => e.algorithm === "bfs" ? e.nodes : null);
  const timeBT = log.map(e => e.algorithm === "backtracking" ? e.timeMs : null);
  const timeGR = log.map(e => e.algorithm === "bfs" ? e.timeMs : null);
  const scoreLine = log.map(e => e.score);
  const memBT = log.map(e => e.algorithm === "backtracking" ? e.peakMemoryKb : null);
  const memGR = log.map(e => e.algorithm === "bfs" ? e.peakMemoryKb : null);

  if (compareNodesChart) compareNodesChart.destroy();
  compareNodesChart = new Chart(document.getElementById("compareNodesChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Backtracking — số nút duyệt", data: nodesBT, backgroundColor: "#201b18" },
        { label: "BFS — số nút duyệt", data: nodesGR, backgroundColor: "#b32121" },
      ]
    },
    options: { responsive: true, plugins: { title: { display: true, text: "Số nút duyệt mỗi nước" } } }
  });

  if (compareTimeChart) compareTimeChart.destroy();
  compareTimeChart = new Chart(document.getElementById("compareTimeChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Backtracking — thời gian (ms)", data: timeBT, backgroundColor: "#2b6cb0" },
        { label: "BFS — thời gian (ms)", data: timeGR, backgroundColor: "#e2a13a" },
      ]
    },
    options: { responsive: true, plugins: { title: { display: true, text: "Thời gian tìm nước mỗi nước (ms)" } } }
  });

  if (compareScoreChart) compareScoreChart.destroy();
  compareScoreChart = new Chart(document.getElementById("compareScoreChart"), {
    type: "line",
    data: {
      labels,
      datasets: [{ label: "Điểm đánh giá bàn cờ theo thời gian (dương = lợi thế Đỏ)", data: scoreLine, borderColor: "#6b461e", fill: false, tension: .2 }]
    },
    options: { responsive: true, plugins: { title: { display: true, text: "Diễn biến điểm đánh giá ván đấu" } } }
  });

  if (compareMemoryChart) compareMemoryChart.destroy();
  compareMemoryChart = new Chart(document.getElementById("compareMemoryChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Backtracking — bộ nhớ ước tính (KB) — O(b×m)", data: memBT, backgroundColor: "#2f7a4f" },
        { label: "BFS — bộ nhớ ước tính (KB) — O(b^d)", data: memGR, backgroundColor: "#a1522f" },
      ]
    },
    options: {
      responsive: true,
      plugins: { title: { display: true, text: "Độ phức tạp không gian (bộ nhớ ước tính) mỗi nước" } },
      scales: { y: { title: { display: true, text: "KB" } } }
    }
  });
}

document.getElementById("newGame").addEventListener("click", async ()=>{
  await getJSON("/api/reset",{method:"POST"});
  await refresh();
});
toggleModeBtn.addEventListener("click", toggleMode);
aiMoveBtn.addEventListener("click", runAI);
aiVsAiStepBtn.addEventListener("click", aiVsAiStep);
aiVsAiRunBtn.addEventListener("click", aiVsAiRun);
document.getElementById("viewSearch").addEventListener("click", showSearchLog);
viewCompareBtn.addEventListener("click", showCompareChart);
document.getElementById("closeSearch").addEventListener("click", () => {
  document.getElementById("searchPanel").hidden = true;
});
document.getElementById("closeCompare").addEventListener("click", () => {
  document.getElementById("comparePanel").hidden = true;
});
refresh();
