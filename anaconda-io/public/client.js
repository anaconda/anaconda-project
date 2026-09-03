'use strict';
/* Anaconda AI Factory — client (handoff 2: fun + external) */

const ANA = { green: '#08CA4A', deep: '#068F35', mint: '#E6FAED', charcoal: '#2C2C2C', ink: '#0C0C0C', gray: '#C9CDD5', red: '#E0574C' };
const $ = (id) => document.getElementById(id);
const canvas = $('game'), ctx = canvas.getContext('2d'), minimap = $('minimap'), mctx = minimap.getContext('2d'), flashEl = $('flash');
const joinScreen = $('join-screen'), deathScreen = $('death-screen'), hud = $('hud');
const playBtn = $('play-btn'), respawnBtn = $('respawn-btn'), nameInput = $('name-input'), nameBtn = $('name-btn'), shareBtn = $('share-btn'), ctaBtn = $('cta-btn');
const statProjects = $('stat-projects'), statTokens = $('stat-tokens'), statLength = $('stat-length'), statFloor = $('stat-floor');
const fundingDeal = $('funding-deal'), fundingFill = $('funding-fill'), fundingClock = $('funding-clock'), acqChips = $('acq-chips');
const leaderboardList = $('leaderboard-list'), hofList = $('hall-of-fame-list');
const feedEl = $('feed'), toastsEl = $('toasts'), hintEl = $('hint'), billEl = $('bill');
const deathTitle = $('death-title'), deathLine = $('death-line');

let clientKey = localStorage.getItem('anacondae.clientKey');
if (!clientKey) { clientKey = 'ck_' + Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem('anacondae.clientKey', clientKey); }
let savedName = localStorage.getItem('anacondae.name') || '';
const COLORS = ['#08CA4A', '#5EE08A', '#F8F674', '#FF7F00', '#6A9E8B', '#3D7EA6', '#8E6BC7', '#E0574C', '#C9CDD5'];
let color = localStorage.getItem('anacondae.color') || COLORS[Math.floor(Math.random() * COLORS.length)];
localStorage.setItem('anacondae.color', color);
function resize() { canvas.width = innerWidth; canvas.height = innerHeight; } addEventListener('resize', resize); resize();

const ICONS = {};
for (const [k, src] of Object.entries({ anaconda: 'assets/brands/anaconda-mark.png', outerbounds: 'assets/brands/outerbounds-icon-white.svg', kilo: 'assets/brands/kilo-icon-white.svg', enkrypt: 'assets/brands/enkrypt-icon-white.svg' })) { const i = new Image(); i.src = src; ICONS[k] = i; }
const ready = (i) => i && i.complete && i.naturalWidth > 0;
const fmtTokens = (b) => b >= 1000 ? (b / 1000).toFixed(2) + 'T' : Math.round(b) + 'B';
const fmtTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
function hexAlpha(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`; }
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

// ------------------------------- Audio (WebAudio, no assets) ------------------
let AC = null, combo = 0, lastEat = 0, boostOsc = null;
function ac() { if (!AC) { try { AC = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { AC = null; } } if (AC && AC.state === 'suspended') AC.resume(); return AC; }
function tone(freq, dur, type = 'sine', gain = 0.08, slideTo) {
  const a = ac(); if (!a) return; const o = a.createOscillator(), g = a.createGain();
  o.type = type; o.frequency.setValueAtTime(freq, a.currentTime); if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, a.currentTime + dur);
  g.gain.setValueAtTime(gain, a.currentTime); g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + dur);
  o.connect(g).connect(a.destination); o.start(); o.stop(a.currentTime + dur);
}
const sfx = {
  eat() { const now = performance.now(); combo = now - lastEat < 1200 ? combo + 1 : 0; lastEat = now; tone(520 * Math.pow(1.06, Math.min(combo, 12)), 0.09, 'square', 0.04); },
  loop(big) { tone(440, 0.18, 'sine', 0.08); setTimeout(() => tone(big ? 660 : 587, 0.28, 'sine', 0.09), 120); },
  poison() { tone(900, 0.08, 'sawtooth', 0.08, 200); setTimeout(() => tone(1400, 0.06, 'square', 0.05, 300), 40); },
  adopt() { tone(330, 0.5, 'sawtooth', 0.06); tone(415, 0.5, 'sawtooth', 0.06); tone(494, 0.7, 'sawtooth', 0.06); },
  death() { tone(220, 0.7, 'sine', 0.12, 55); },
  build() { tone(523, 0.12, 'triangle', 0.07); setTimeout(() => tone(784, 0.25, 'triangle', 0.07), 100); },
  boost(on) { const a = ac(); if (!a) return; if (on && !boostOsc) { const o = a.createOscillator(), g = a.createGain(); o.type = 'sawtooth'; o.frequency.value = 70; g.gain.value = 0.025; o.connect(g).connect(a.destination); o.start(); boostOsc = { o, g }; } if (!on && boostOsc) { boostOsc.o.stop(); boostOsc = null; } },
};

// ------------------------------- State ----------------------------------------
const socket = io();
let myId = null, myName = '', worldRadius = 2400, state = null, alive = false, boosting = false, everJoined = false;
let PRODUCTS = [], ACQ = [];
const camera = { x: 0, y: 0, zoom: 1 };
let spawnAt = 0, ateOnce = false, hasLeftFloor = false, hasCaptured = false, revealed = false;
const crates = [], pops = [], shards = []; let headSquash = 0, ripple = 0, pulseColor = null, pulseT = 0, slowmoUntil = 0, edgeFlashUntil = 0, lastFloor = 0;
let lastDeath = null;

// Territory canvases
let meta = { cellSize: 50, gridDim: 96 };
const fillCanvas = document.createElement('canvas'), fillCtx = fillCanvas.getContext('2d');
const edgeCanvas = document.createElement('canvas'), edgeCtx = edgeCanvas.getContext('2d');
const EDGE_RES = 6; let cellColors = [];
function initTerritory(m, cells) {
  meta = m; cellColors = new Array(m.gridDim * m.gridDim).fill(null);
  fillCanvas.width = fillCanvas.height = m.gridDim; edgeCanvas.width = edgeCanvas.height = m.gridDim * EDGE_RES;
  fillCtx.clearRect(0, 0, m.gridDim, m.gridDim); edgeCtx.clearRect(0, 0, edgeCanvas.width, edgeCanvas.height); paintCells(cells);
}
function paintCells(cells) {
  const g = meta.gridDim, touched = new Set();
  for (const { idx, color } of cells) {
    cellColors[idx] = color; const c = idx % g, r = (idx / g) | 0;
    if (color) { fillCtx.fillStyle = color; fillCtx.fillRect(c, r, 1, 1); } else fillCtx.clearRect(c, r, 1, 1);
    touched.add(idx); if (c > 0) touched.add(idx - 1); if (c < g - 1) touched.add(idx + 1); if (r > 0) touched.add(idx - g); if (r < g - 1) touched.add(idx + g);
  }
  for (const idx of touched) redrawEdge(idx);
}
function redrawEdge(idx) {
  const g = meta.gridDim, c = idx % g, r = (idx / g) | 0, col = cellColors[idx], x = c * EDGE_RES, y = r * EDGE_RES, w = EDGE_RES;
  edgeCtx.clearRect(x, y, w, w); if (!col) return; edgeCtx.fillStyle = col; const nb = (i) => cellColors[i] === col;
  if (r === 0 || !nb(idx - g)) edgeCtx.fillRect(x, y, w, 1); if (r === g - 1 || !nb(idx + g)) edgeCtx.fillRect(x, y + w - 1, w, 1);
  if (c === 0 || !nb(idx - 1)) edgeCtx.fillRect(x, y, 1, w); if (c === g - 1 || !nb(idx + 1)) edgeCtx.fillRect(x + w - 1, y, 1, w);
}

// ------------------------------- Join / death ---------------------------------
const joinPayload = () => ({ name: savedName || undefined, color, clientKey });
playBtn.onclick = () => { ac(); socket.emit('join', joinPayload()); track('play'); };
respawnBtn.onclick = () => { if (!respawnBtn.disabled) { socket.emit('respawn', joinPayload()); track('play_again'); } };
addEventListener('keydown', (e) => { if (e.key === 'Enter') { if (!joinScreen.classList.contains('hidden')) playBtn.click(); else if (!deathScreen.classList.contains('hidden') && document.activeElement !== nameInput) respawnBtn.click(); } });
nameBtn.onclick = saveName; nameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') saveName(); });
function saveName() { const n = nameInput.value.trim().slice(0, 18); if (!n) return; savedName = n; localStorage.setItem('anacondae.name', n); socket.emit('setName', { name: n }); myName = n; nameBtn.textContent = 'Saved'; setTimeout(() => nameBtn.textContent = 'Save', 1200); renderShareCard(lastDeath); }
ctaBtn.onclick = () => track('cta_click');
shareBtn.onclick = () => { const a = document.createElement('a'); a.download = 'anaconda-ai-factory.png'; a.href = $('share-card').toDataURL('image/png'); a.click(); track('share'); };
function track(event) { socket.emit('analytics', { event }); }

socket.on('welcome', (d) => {
  everJoined = true; myId = d.id; myName = d.you.name; worldRadius = d.worldRadius; alive = true; heading = d.you.angle;
  camera.x = d.you.x; camera.y = d.you.y; spawnAt = Date.now(); ateOnce = false; hasLeftFloor = false; hasCaptured = false; lastFloor = 0;
  PRODUCTS = d.products; ACQ = d.acquisitions; ctaBtn.href = d.cta || ctaBtn.href;
  initTerritory({ cellSize: d.territory.cellSize, gridDim: d.territory.gridDim }, d.territory.cells);
  feedEl.innerHTML = ''; (d.feed || []).slice().reverse().forEach(f => addFeed(f.text));
  joinScreen.classList.add('hidden'); deathScreen.classList.add('hidden'); hud.classList.remove('hidden');
  if (!revealed) setTimeout(revealHud, 60000);
});
function revealHud() { revealed = true; document.querySelectorAll('.reveal').forEach(el => el.classList.add('shown')); }
socket.on('territoryUpdate', ({ cells }) => paintCells(cells));
socket.on('state', (s) => { state = s; worldRadius = s.worldRadius; });
socket.on('connect', () => { if (everJoined) { toast('Reconnected — respawning'); socket.emit('respawn', joinPayload()); } });
socket.on('disconnect', () => { alive = false; });
socket.on('ate', () => { ateOnce = true; sfx.eat(); headSquash = 1; ripple = 1; });
socket.on('setback', (d) => { flash(); shake(); sfx.poison(); toast(`${d.label} in the build · −${d.lost}`, 'bad', d.line); spawnShards(d.lost); });
socket.on('blocked', (d) => toast(d.guard ? `Guardrails absorbed a ${d.label}` : `Package Intelligence blocked a ${d.label}`, 'guard'));
socket.on('capability', (d) => { sfx.adopt(); pulseColor = d.color; pulseT = 1; revealHud(); banner(d.does, `You adopted ${d.capability} · ${d.name} · now part of Anaconda`); track('adopt_' + d.key); });
socket.on('building', (d) => { sfx.build(); toast(`${d.name} — ${d.does}`); });
socket.on('retargeted', () => toast('Retargeted — your land came with you'));
socket.on('banner', ({ text, sub }) => { banner(text, sub); if (/ACQUIRES/.test(text)) revealHud(); });
socket.on('feed', (f) => addFeed(f.text));
socket.on('shipment', (d) => crates.push({ x: d.from.x, y: d.from.y, color: d.color, t0: performance.now(), n: d.projects, ang: Math.atan2(d.from.y, d.from.x) }));
socket.on('tokenBill', ({ rows }) => { billEl.innerHTML = `<div class="panel-title">Token bill</div><table><tr><th>Player</th><th>Shipped</th><th>Burned</th><th>Routed/100</th></tr>` + rows.map(r => `<tr><td>${esc(r.name)}</td><td>${r.shipped}</td><td>${r.burned}</td><td>${(r.eff * 100).toFixed(0)}</td></tr>`).join('') + '</table>'; billEl.classList.remove('hidden'); setTimeout(() => billEl.classList.add('hidden'), 9000); });
socket.on('died', (d) => {
  alive = false; sfx.death(); sfx.boost(false); slowmoUntil = performance.now() + 600; lastDeath = d;
  const me = state && state.snakes.find(s => s.id === myId); if (me) spawnShards(Math.min(30, me.length), true);
  setTimeout(() => {
    deathTitle.textContent = d.copy ? d.copy.title : 'Shed';
    deathLine.textContent = (d.copy ? `“${d.copy.line}”` : '') + (d.killer ? ` — ${d.killer}` : '');
    const S = d.summary || {};
    $('d-projects').textContent = S.projects || 0; $('d-tokens').textContent = fmtTokens(S.tokens || 0);
    $('d-caps').textContent = S.caps && S.caps.length ? 'adopted ' + S.caps.join(' + ') : 'adopted nothing yet'; $('d-time').textContent = fmtTime(S.seconds || 0);
    $('d-pitch').textContent = `“${S.pitch || ''}”`;
    $('name-row').style.display = S.guest ? 'flex' : 'none'; nameInput.value = savedName;
    renderShareCard(d);
    deathScreen.classList.remove('hidden'); hud.classList.add('hidden');
    respawnBtn.disabled = true; let left = Math.ceil((d.respawnMs || 2600) / 1000); respawnBtn.textContent = `PLAY AGAIN (${left}s)`;
    const iv = setInterval(() => { left--; if (left <= 0) { clearInterval(iv); respawnBtn.disabled = false; respawnBtn.textContent = 'PLAY AGAIN'; } else respawnBtn.textContent = `PLAY AGAIN (${left}s)`; }, 1000);
  }, 650);
});

function renderShareCard(d) {
  const c = $('share-card'), g = c.getContext('2d'), S = (d && d.summary) || {};
  g.fillStyle = ANA.ink; g.fillRect(0, 0, 600, 315);
  const grad = g.createRadialGradient(120, 60, 0, 120, 60, 420); grad.addColorStop(0, hexAlpha(ANA.green, 0.25)); grad.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = grad; g.fillRect(0, 0, 600, 315);
  if (ready(ICONS.anaconda)) g.drawImage(ICONS.anaconda, 24, 22, 34, 34);
  g.fillStyle = '#fff'; g.font = '800 15px Inter'; g.fillText('ANACONDA AI FACTORY', 68, 45);
  g.fillStyle = ANA.gray; g.font = '600 14px Inter'; g.fillText(myName || 'builder', 24, 90);
  g.fillStyle = ANA.green; g.font = '900 64px Inter'; g.fillText(String(S.projects || 0), 24, 160);
  g.fillStyle = '#fff'; g.font = '700 20px Inter'; g.fillText('AI projects in production', 24, 190);
  g.fillStyle = ANA.gray; g.font = '600 13px Inter'; g.fillText(`Routed ${fmtTokens(S.tokens || 0)} tokens · ${fmtTime(S.seconds || 0)}`, 24, 216);
  const caps = S.caps || []; g.fillText(caps.length ? 'Adopted: ' + caps.join(' · ') : '88% of AI projects never reach production.', 24, 238);
  // mini factory snapshot
  let y = 290; (S.products || []).forEach((k, i) => { const p = PRODUCTS.find(pp => pp.key === k) || { color: ANA.green }; const w = 120 - i * 10; g.fillStyle = p.color; g.fillRect(470 - w / 2, y - 14, w, 14); y -= 16; });
  g.beginPath(); g.arc(470, 296, 10, 0, Math.PI * 2); g.fillStyle = '#fff'; g.fill(); if (ready(ICONS.anaconda)) g.drawImage(ICONS.anaconda, 463, 289, 14, 14);
  g.fillStyle = ANA.gray; g.font = '600 11px Inter'; g.textAlign = 'right'; g.fillText('anaconda.com/platform', 576, 300); g.textAlign = 'left';
}

// ------------------------------- Feel helpers ---------------------------------
function flash() { flashEl.className = 'on'; setTimeout(() => flashEl.className = 'off', 60); }
function shake() { canvas.classList.remove('shake'); void canvas.offsetWidth; canvas.classList.add('shake'); }
function spawnShards(n, death) { const me = state && state.snakes.find(s => s.id === myId); if (!me) return; for (let i = 0; i < Math.min(n, 40); i++) { const p = me.points[Math.min(me.points.length - 1, i * 2)] || me.points[0]; shards.push({ x: p.x, y: p.y, vx: (Math.random() - 0.5) * 6, vy: (Math.random() - 0.5) * 6, life: 1, color: death ? me.color : ANA.red }); } }
function toast(text, kind, sub) { const el = document.createElement('div'); el.className = 'toast' + (kind ? ' ' + kind : ''); if (!kind) el.style.background = ANA.mint; el.textContent = text + (sub ? ` — “${sub}”` : ''); toastsEl.appendChild(el); setTimeout(() => el.remove(), 3900); }
function banner(text, sub) { const el = document.createElement('div'); el.className = 'win-banner'; el.innerHTML = esc(text) + (sub ? `<small>${esc(sub)}</small>` : ''); document.body.appendChild(el); setTimeout(() => el.remove(), 7100); }
function addFeed(text) { const el = document.createElement('div'); el.textContent = text; feedEl.prepend(el); while (feedEl.children.length > 5) feedEl.lastChild.remove(); }

// ------------------------------- Input ----------------------------------------
const TURN_STEP = 0.12; let heading = 0; const keys = new Set();
addEventListener('keydown', (e) => {
  if (document.activeElement === nameInput || !alive) return;
  if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Space'].includes(e.code)) e.preventDefault();
  if (e.code === 'ArrowLeft') { heading -= TURN_STEP; keys.add('l'); } if (e.code === 'ArrowRight') { heading += TURN_STEP; keys.add('r'); }
  if (e.code === 'ArrowUp' || e.code === 'Space') { boosting = true; sfx.boost(true); } if (e.code === 'KeyR') socket.emit('retarget');
}, { passive: false });
addEventListener('keyup', (e) => { if (e.code === 'ArrowLeft') keys.delete('l'); if (e.code === 'ArrowRight') keys.delete('r'); if (e.code === 'ArrowUp' || e.code === 'Space') { boosting = false; sfx.boost(false); } });
addEventListener('touchstart', (e) => { const t = e.touches[0]; if (!t) return; heading += (t.clientX < innerWidth / 2 ? -1 : 1) * TURN_STEP * 3; boosting = true; }, { passive: true });
addEventListener('touchend', () => { boosting = false; });
setInterval(() => { if (!alive) return; if (keys.has('l')) heading -= TURN_STEP * 0.5; if (keys.has('r')) heading += TURN_STEP * 0.5; socket.emit('input', { angle: heading, boosting }); }, 50);

// ------------------------------- Drawing --------------------------------------
const W = (x) => (x - camera.x) * camera.zoom + canvas.width / 2, H = (y) => (y - camera.y) * camera.zoom + canvas.height / 2;
const onScreen = (x, y) => Math.abs(x - camera.x) < 1700 && Math.abs(y - camera.y) < 1700;
let t = 0, prevComps = new Map();

function drawBackground() { const g = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, 0, canvas.width / 2, canvas.height / 2, Math.max(canvas.width, canvas.height) * 0.75); g.addColorStop(0, '#141614'); g.addColorStop(1, ANA.ink); ctx.fillStyle = g; ctx.fillRect(0, 0, canvas.width, canvas.height); }
function drawFloor(me) {
  const size = meta.gridDim * meta.cellSize * camera.zoom, x = W(-worldRadius), y = H(-worldRadius);
  ctx.save(); ctx.imageSmoothingEnabled = false; ctx.globalAlpha = 0.5; ctx.drawImage(fillCanvas, x, y, size, size);
  ctx.globalAlpha = performance.now() < edgeFlashUntil ? 1 : 0.9; ctx.imageSmoothingEnabled = true; ctx.drawImage(edgeCanvas, x, y, size, size);
  if (performance.now() < edgeFlashUntil) { ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.5; ctx.drawImage(edgeCanvas, x, y, size, size); }
  ctx.restore();
}
function drawBoundary() { ctx.beginPath(); ctx.arc(W(0), H(0), worldRadius * camera.zoom, 0, Math.PI * 2); ctx.lineWidth = 14; ctx.strokeStyle = hexAlpha(ANA.red, 0.18); ctx.stroke(); ctx.lineWidth = 3; ctx.strokeStyle = ANA.red; ctx.stroke(); }
function compColor(c, caps) { if (c.p && caps && caps.includes('enkrypt')) return ANA.red; if (c.k) return ANA.mint; return c.t === 'model' ? '#5EE08A' : c.t === 'dataset' ? '#C9CDD5' : c.t === 'mcp' ? '#F8F674' : ANA.green; }
function drawShape(type, s) {
  if (type === 'package') { ctx.rotate(Math.PI / 4); ctx.fillRect(-s, -s, s * 2, s * 2); ctx.strokeRect(-s, -s, s * 2, s * 2); }
  else if (type === 'dataset') { ctx.fillRect(-s, -s * 0.8, s * 2, s * 1.6); ctx.strokeRect(-s, -s * 0.8, s * 2, s * 1.6); ctx.strokeStyle = 'rgba(0,0,0,0.4)'; for (let i = -1; i <= 1; i++) { ctx.beginPath(); ctx.moveTo(-s * 0.7, i * s * 0.45); ctx.lineTo(s * 0.7, i * s * 0.45); ctx.stroke(); } }
  else if (type === 'model') { ctx.beginPath(); for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3; ctx.lineTo(Math.cos(a) * s * 1.25, Math.sin(a) * s * 1.25); } ctx.closePath(); ctx.fill(); ctx.stroke(); }
  else { const col = ctx.fillStyle; ctx.beginPath(); ctx.arc(0, 0, s, 0, Math.PI * 2); ctx.lineWidth = 2.5; ctx.strokeStyle = col; ctx.stroke(); ctx.beginPath(); ctx.arc(0, 0, s * 0.35, 0, Math.PI * 2); ctx.fill(); }
}
function drawComponent(c, caps) {
  if (!onScreen(c.x, c.y)) return;
  const z = camera.zoom, s = 7 * z, col = compColor(c, caps);
  ctx.save(); ctx.translate(W(c.x), H(c.y)); ctx.fillStyle = col; ctx.strokeStyle = 'rgba(255,255,255,0.6)'; ctx.lineWidth = 1; if (c.k) { ctx.shadowColor = ANA.mint; ctx.shadowBlur = 12; }
  drawShape(c.t, s);
  if (c.p && caps && caps.includes('enkrypt')) { ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = '#fff'; ctx.font = `900 ${Math.max(9, 9 * z)}px Inter`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('!', W(c.x), H(c.y) + 1); }
  ctx.restore();
}
function drawPops() { const now = performance.now(); for (let i = pops.length - 1; i >= 0; i--) { const p = pops[i], k = (now - p.t0) / 120; if (k >= 1) { pops.splice(i, 1); continue; } const sc = k < 0.5 ? 1 + k * 1.2 : 1.6 * (1 - (k - 0.5) * 2); ctx.save(); ctx.translate(W(p.x), H(p.y)); ctx.globalAlpha = 1 - k; ctx.fillStyle = p.color; ctx.strokeStyle = 'rgba(255,255,255,0.6)'; drawShape(p.t, 7 * camera.zoom * sc); ctx.restore(); } }
function drawShards() { for (let i = shards.length - 1; i >= 0; i--) { const s = shards[i]; s.x += s.vx; s.y += s.vy; s.vx *= 0.96; s.vy *= 0.96; s.life -= 0.02; if (s.life <= 0) { shards.splice(i, 1); continue; } ctx.save(); ctx.globalAlpha = s.life; ctx.fillStyle = s.color; ctx.beginPath(); ctx.arc(W(s.x), H(s.y), 5 * camera.zoom, 0, Math.PI * 2); ctx.fill(); ctx.restore(); } }
function tracePath(pts) { ctx.beginPath(); ctx.moveTo(W(pts[0].x), H(pts[0].y)); for (let i = 1; i < pts.length - 1; i++) { const mx = (pts[i].x + pts[i + 1].x) / 2, my = (pts[i].y + pts[i + 1].y) / 2; ctx.quadraticCurveTo(W(pts[i].x), H(pts[i].y), W(mx), H(my)); } const l = pts[pts.length - 1]; ctx.lineTo(W(l.x), H(l.y)); }
function drawSnake(s, isMe) {
  const pts = s.points; if (!pts || !pts.length) return;
  const r = s.headRadius * camera.zoom;
  if (s.trail && s.trail.length) {
    ctx.save(); ctx.beginPath(); ctx.moveTo(W(s.trail[0].x), H(s.trail[0].y)); for (let i = 1; i < s.trail.length; i++) ctx.lineTo(W(s.trail[i].x), H(s.trail[i].y)); ctx.lineTo(W(pts[0].x), H(pts[0].y));
    ctx.lineWidth = Math.max(3, 8 * camera.zoom); ctx.strokeStyle = hexAlpha(s.color, 0.35); ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.stroke();
    ctx.setLineDash([6 * camera.zoom, 8 * camera.zoom]); ctx.lineWidth = Math.max(1.5, 2 * camera.zoom); ctx.strokeStyle = hexAlpha(s.color, 0.95); ctx.stroke(); ctx.restore();
  }
  if (pts.length > 1) {
    ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    if (isMe && boosting) { ctx.globalAlpha = 0.25; tracePath(pts); ctx.lineWidth = r * 3; ctx.strokeStyle = s.color; ctx.stroke(); ctx.globalAlpha = 1; }
    tracePath(pts); ctx.lineWidth = r * 2 + 3; ctx.strokeStyle = 'rgba(0,0,0,0.55)'; ctx.stroke();
    ctx.lineWidth = r * 2; ctx.strokeStyle = isMe && pulseT > 0 ? pulseColor : s.color; ctx.stroke();
    if (isMe && pulseT > 0) { ctx.globalAlpha = pulseT * 0.6; ctx.lineWidth = r * 2.6; ctx.strokeStyle = pulseColor; ctx.stroke(); ctx.globalAlpha = 1; }
    ctx.globalAlpha = 0.22; ctx.lineWidth = Math.max(1, r * 0.16); ctx.strokeStyle = '#fff';
    const step = Math.max(2, Math.floor((r * 1.4) / (8 * camera.zoom)));
    for (let i = step; i < pts.length - 1; i += step) { const a = pts[i], b = pts[i - 1], ang = Math.atan2(a.y - b.y, a.x - b.x), cx = W(a.x), cy = H(a.y); for (const d of [-1, 1]) { const q = ang + d * Math.PI / 3.2; ctx.beginPath(); ctx.moveTo(cx - Math.cos(q) * r * 0.9, cy - Math.sin(q) * r * 0.9); ctx.lineTo(cx + Math.cos(q) * r * 0.9, cy + Math.sin(q) * r * 0.9); ctx.stroke(); } }
    if (isMe && ripple > 0) { const i = Math.min(pts.length - 1, Math.floor((1 - ripple) * pts.length)); ctx.globalAlpha = ripple * 0.7; ctx.beginPath(); ctx.arc(W(pts[i].x), H(pts[i].y), r * 1.3, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); }
    ctx.globalAlpha = 0.16; ctx.lineWidth = r * 0.5; ctx.strokeStyle = '#fff'; tracePath(pts); ctx.stroke(); ctx.restore();
  }
  const hx = W(pts[0].x), hy = H(pts[0].y), ang = pts.length > 1 ? Math.atan2(pts[0].y - pts[1].y, pts[0].x - pts[1].x) : 0;
  if (s.shield) { ctx.save(); ctx.beginPath(); ctx.arc(hx, hy, r * 2.2, 0, Math.PI * 2); ctx.setLineDash([6, 6]); ctx.lineWidth = 2; ctx.strokeStyle = hexAlpha(ANA.mint, 0.8); ctx.stroke(); ctx.restore(); }
  const sq = isMe ? 1 - headSquash * 0.08 : 1;
  ctx.save(); ctx.translate(hx, hy); ctx.rotate(ang); ctx.scale(sq, 2 - sq); ctx.beginPath(); ctx.arc(0, 0, r * 1.08, 0, Math.PI * 2); ctx.fillStyle = s.color; ctx.fill();
  ctx.lineWidth = Math.max(1.5, r * 0.14); ctx.strokeStyle = isMe ? '#fff' : s.inTerritory ? 'rgba(0,0,0,0.5)' : hexAlpha(ANA.red, 0.8); ctx.stroke(); ctx.restore();
  for (const side of [-1, 1]) { const p = ang + Math.PI / 2 * side, ex = hx + Math.cos(ang) * r * 0.35 + Math.cos(p) * r * 0.5, ey = hy + Math.sin(ang) * r * 0.35 + Math.sin(p) * r * 0.5; ctx.beginPath(); ctx.arc(ex, ey, r * 0.24, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.beginPath(); ctx.arc(ex + Math.cos(ang) * r * 0.08, ey + Math.sin(ang) * r * 0.08, r * 0.12, 0, Math.PI * 2); ctx.fillStyle = ANA.ink; ctx.fill(); }
  for (const o of s.orbs || []) { ctx.save(); ctx.beginPath(); ctx.arc(W(o.x), H(o.y), 5 * camera.zoom, 0, Math.PI * 2); ctx.fillStyle = '#F8F674'; ctx.shadowColor = '#F8F674'; ctx.shadowBlur = 8; ctx.fill(); ctx.restore(); }
  ctx.save(); ctx.font = '700 13px Inter'; ctx.textAlign = 'center'; ctx.fillStyle = '#fff'; ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 5; ctx.fillText((s.crown ? '👑 ' : '') + s.name, hx, hy - r - 12);
  const caps = (s.caps || []).map(k => (ACQ.find(a => a.key === k) || {}).color).filter(Boolean); caps.forEach((c, i) => { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(hx - (caps.length - 1) * 5 + i * 10, hy - r - 26, 4, 0, Math.PI * 2); ctx.fill(); }); ctx.restore();
}
function drawLandmarks() {
  for (const a of state.acquisitions) {
    if (!a.funded || !onScreen(a.site.x, a.site.y)) continue;
    const x = W(a.site.x), y = H(a.site.y), z = camera.zoom, held = !!a.holder, pulse = held ? 0 : (Math.sin(t * 3) + 1) / 2;
    ctx.save(); ctx.beginPath(); ctx.arc(x, y, (60 + pulse * 14) * z, 0, Math.PI * 2); ctx.strokeStyle = hexAlpha(a.color, held ? 0.9 : 0.5 + pulse * 0.4); ctx.lineWidth = 3; ctx.setLineDash(held ? [] : [10, 8]); ctx.stroke(); ctx.setLineDash([]);
    const w = 70 * z, h = 56 * z; ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(x - w / 2 + 4 * z, y - h + 4 * z, w, h); ctx.fillStyle = ANA.charcoal; ctx.fillRect(x - w / 2, y - h, w, h); ctx.fillStyle = a.color; ctx.fillRect(x - w / 2, y - h - 8 * z, w, 8 * z);
    const icon = ICONS[a.key]; if (ready(icon)) { const sc = (30 * z) / Math.max(icon.naturalWidth, icon.naturalHeight); ctx.drawImage(icon, x - icon.naturalWidth * sc / 2, y - h / 2 - icon.naturalHeight * sc / 2, icon.naturalWidth * sc, icon.naturalHeight * sc); }
    ctx.font = `800 ${Math.max(11, 12 * z)}px Inter`; ctx.textAlign = 'center'; ctx.fillStyle = '#fff'; ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 4;
    ctx.fillText(`${a.name} · now part of Anaconda`, x, y + 16 * z);
    ctx.font = `600 ${Math.max(10, 11 * z)}px Inter`; ctx.fillStyle = held ? a.holderColor : ANA.gray; ctx.fillText(held ? `${a.capability} · adopted by ${a.holder}` : `enclose to adopt ${a.capability}`, x, y + 30 * z); ctx.restore();
  }
}
function drawFactory(s) {
  if (!s.alive || !s.home || !onScreen(s.home.x, s.home.y)) return;
  const x = W(s.home.x), y = H(s.home.y), z = camera.zoom;
  ctx.save(); ctx.beginPath(); ctx.arc(x, y, 14 * z, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = s.color; ctx.stroke(); if (ready(ICONS.anaconda)) ctx.drawImage(ICONS.anaconda, x - 10 * z, y - 10 * z, 20 * z, 20 * z); ctx.restore();
  if (!s.products || !s.products.length) return;
  const bw = 56 * z, bh = 18 * z; let top = y - 22 * z;
  s.products.forEach((k, i) => { const p = PRODUCTS.find(pp => pp.key === k) || { color: ANA.green, name: k }; const w = bw - i * 4 * z; ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(x - w / 2 + 3 * z, top - bh + 3 * z, w, bh); ctx.fillStyle = p.color; ctx.fillRect(x - w / 2, top - bh, w, bh); ctx.fillStyle = 'rgba(0,0,0,0.25)'; ctx.fillRect(x - w / 2, top - bh, w, 3 * z); ctx.save(); ctx.font = `800 ${Math.max(9, 9 * z)}px Inter`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = ANA.ink; ctx.fillText(p.name, x, top - bh / 2); ctx.restore(); top -= bh + 2 * z; });
  ctx.save(); ctx.font = `700 ${Math.max(10, 11 * z)}px Inter`; ctx.textAlign = 'center'; ctx.fillStyle = '#fff'; ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 4; ctx.fillText(`${s.name} · ${s.products.length}/${PRODUCTS.length} shipping`, x, top - 6 * z); ctx.restore();
}
function drawCrates() { const now = performance.now(); for (let i = crates.length - 1; i >= 0; i--) { const c = crates[i], k = (now - c.t0) / 1800; if (k >= 1) { crates.splice(i, 1); continue; } const tx = Math.cos(c.ang) * worldRadius, ty = Math.sin(c.ang) * worldRadius, x = W(c.x + (tx - c.x) * k), y = H(c.y + (ty - c.y) * k) - Math.sin(k * Math.PI) * 40 * camera.zoom; if (x < -20 || x > canvas.width + 20 || y < -20 || y > canvas.height + 20) continue; const s = 6 * camera.zoom; ctx.save(); ctx.globalAlpha = 1 - k * 0.6; ctx.fillStyle = c.color; ctx.fillRect(x - s, y - s, s * 2, s * 2); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1; ctx.strokeRect(x - s, y - s, s * 2, s * 2); if (k < 0.2) { ctx.font = '700 11px Inter'; ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.fillText(`+${c.n} in production`, x, y - 12); } ctx.restore(); } }

// ------------------------------- HUD ------------------------------------------
let lastChipSig = '';
function updateHud(me) {
  if (me) {
    statProjects.textContent = me.projects; statLength.textContent = me.length; statTokens.textContent = fmtTokens(me.tokens); statFloor.textContent = me.floor;
    if (me.floor > lastFloor + 4 && lastFloor > 0) { sfx.loop(me.floor - lastFloor > 40); edgeFlashUntil = performance.now() + 400; hasCaptured = true; }
    lastFloor = me.floor;
    if (!me.inTerritory) hasLeftFloor = true;
    hintEl.textContent = hasCaptured ? '' : !ateOnce ? 'eat to grow' : hasLeftFloor ? 'get home to close the loop' : 'leave your floor and come back to claim it';
  }
  const f = state.funding;
  fundingDeal.textContent = f.capability ? `${f.capability} (${f.dealName})` : 'all capabilities landed';
  fundingFill.style.width = f.capability ? Math.min(100, (f.units / f.target) * 100).toFixed(1) + '%' : '100%';
  fundingClock.style.width = f.capability ? (f.clockPct * 100).toFixed(1) + '%' : '0%';
  const sig = state.acquisitions.map(a => `${a.key}:${a.funded ? 1 : 0}:${me && me.caps.includes(a.key) ? 1 : 0}`).join('|');
  if (sig !== lastChipSig) { lastChipSig = sig; acqChips.innerHTML = state.acquisitions.map(a => `<span class="acq ${a.funded ? 'funded' : ''} ${me && me.caps.includes(a.key) ? 'held' : ''}" style="background:${a.color}" title="${esc(a.name)}">${esc(a.capability)}</span>`).join(''); }
  leaderboardList.innerHTML = state.leaderboard.map(r => `<li class="${r.name === myName ? 'me' : ''}">${r.crown ? '◆◆◆ ' : ''}${esc(r.name)} — ${r.projects} <small>· ${fmtTokens(r.tokens)}</small></li>`).join('');
  hofList.innerHTML = state.hallOfFame.length ? state.hallOfFame.map(h => `<li>${esc(h.name)}</li>`).join('') : '<li>No one yet — route 1T tokens</li>';
}
function drawMinimap() {
  if (!minimap.clientWidth || !minimap.classList.contains('shown')) return;
  const w = minimap.width = minimap.clientWidth * devicePixelRatio, h = minimap.height = minimap.clientHeight * devicePixelRatio;
  mctx.clearRect(0, 0, w, h); mctx.save(); mctx.translate(w / 2, h / 2); const sc = (Math.min(w, h) / 2 - 4) / worldRadius;
  mctx.save(); mctx.beginPath(); mctx.arc(0, 0, worldRadius * sc, 0, Math.PI * 2); mctx.clip(); mctx.globalAlpha = 0.6; mctx.imageSmoothingEnabled = false; mctx.drawImage(fillCanvas, -worldRadius * sc, -worldRadius * sc, worldRadius * 2 * sc, worldRadius * 2 * sc); mctx.restore();
  for (const a of state.acquisitions) { if (!a.funded) continue; const pulse = a.holder ? 0 : (Math.sin(t * 3) + 1) / 2; mctx.beginPath(); mctx.arc(a.site.x * sc, a.site.y * sc, 4 + pulse * 3, 0, Math.PI * 2); mctx.fillStyle = a.color; mctx.fill(); mctx.lineWidth = 1.5; mctx.strokeStyle = '#fff'; mctx.stroke(); }
  for (const s of state.snakes) { if (!s.alive) continue; const me = s.id === myId; mctx.beginPath(); mctx.moveTo(s.points[0].x * sc, s.points[0].y * sc); for (let i = 1; i < s.points.length; i++) mctx.lineTo(s.points[i].x * sc, s.points[i].y * sc); mctx.strokeStyle = me ? '#fff' : s.color; mctx.lineWidth = (me ? 2.6 : 1.6) * devicePixelRatio; mctx.lineCap = 'round'; mctx.stroke(); }
  mctx.restore();
}

// ------------------------------- Loop -----------------------------------------
let lastFrame = performance.now();
function render(now) {
  const dt = Math.min(0.05, (now - lastFrame) / 1000) * (now < slowmoUntil ? 0.4 : 1); lastFrame = now; t += dt * 3;
  headSquash = Math.max(0, headSquash - dt * 8); ripple = Math.max(0, ripple - dt * 5); pulseT = Math.max(0, pulseT - dt * 0.85);
  drawBackground();
  if (state) {
    const me = state.snakes.find(s => s.id === myId);
    if (me && me.alive) { camera.x = me.points[0].x; camera.y = me.points[0].y; const targetZoom = Math.max(0.55, 1.05 - Math.sqrt(me.length) * 0.02) * (boosting ? 0.95 : 1); camera.zoom += (targetZoom - camera.zoom) * 0.06; }
    // pop animation for components that vanished near me
    const cur = new Map(); for (const c of state.components) cur.set(c.id, c);
    for (const [id, c] of prevComps) if (!cur.has(id) && onScreen(c.x, c.y) && me && Math.hypot(c.x - me.points[0].x, c.y - me.points[0].y) < 80) pops.push({ x: c.x, y: c.y, t: c.t, color: compColor(c, me.caps), t0: now });
    prevComps = cur;
    drawFloor(me); drawBoundary(); drawLandmarks(); for (const s of state.snakes) drawFactory(s);
    for (const c of state.components) drawComponent(c, me ? me.caps : []); drawPops();
    for (const s of state.snakes) if (s.alive) drawSnake(s, s.id === myId);
    drawShards(); drawCrates(); updateHud(me); drawMinimap();
  }
  requestAnimationFrame(render);
}
requestAnimationFrame(render);
