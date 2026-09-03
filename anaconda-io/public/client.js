'use strict';
/* ANACONDAE client — Anaconda-brand renderer, keyboard input, socket handling */

// ------------------------------- Palette --------------------------------------
const ANA = { green: '#08CA4A', deep: '#068F35', mint: '#E6FAED', charcoal: '#2C2C2C', ink: '#0C0C0C', gray: '#C9CDD5' };

// ------------------------------- DOM ------------------------------------------
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const minimap = document.getElementById('minimap');
const mctx = minimap.getContext('2d');
const $ = (id) => document.getElementById(id);
const joinScreen = $('join-screen'), deathScreen = $('death-screen'), hud = $('hud');
const nameInput = $('name-input'), playBtn = $('play-btn'), respawnBtn = $('respawn-btn');
const colorSwatchesEl = $('color-swatches'), leaderboardList = $('leaderboard-list'), hallOfFameList = $('hall-of-fame-list');
const statLength = $('stat-length'), statLand = $('stat-land'), statPlayers = $('stat-players');
const finalLengthEl = $('final-length'), deathReasonEl = $('death-reason');
const factorySlots = $('factory-slots'), factoryHint = $('factory-hint');

let toastStack = document.createElement('div');
toastStack.id = 'toast-stack';
document.body.appendChild(toastStack);

// Persistent identity: your Crown / acquisitions / Factory survive death and reloads.
let clientKey = localStorage.getItem('anacondae.clientKey');
if (!clientKey) {
  clientKey = 'ck_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
  localStorage.setItem('anacondae.clientKey', clientKey);
}

// Snake skins: Anaconda greens first, then complementary tones.
const COLORS = ['#08CA4A', '#068F35', '#5EE08A', '#F8F674', '#FF7F00', '#6A9E8B', '#3D7EA6', '#8E6BC7', '#E0574C', '#C9CDD5'];
let selectedColor = localStorage.getItem('anacondae.color') || COLORS[0];
COLORS.forEach((c) => {
  const el = document.createElement('div');
  el.className = 'swatch' + (c === selectedColor ? ' selected' : '');
  el.style.background = c;
  el.addEventListener('click', () => {
    selectedColor = c; localStorage.setItem('anacondae.color', c);
    document.querySelectorAll('.swatch').forEach(s => s.classList.remove('selected'));
    el.classList.add('selected');
  });
  colorSwatchesEl.appendChild(el);
});
nameInput.value = localStorage.getItem('anacondae.name') || ('Kaa' + Math.floor(Math.random() * 90 + 10));

function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
window.addEventListener('resize', resize); resize();

// ------------------------------- Assets ---------------------------------------
const ICON_SRC = {
  anaconda: 'assets/brands/anaconda-mark.png',
  outerbounds: 'assets/brands/outerbounds-icon-white.svg',
  kilo: 'assets/brands/kilo-icon-white.svg',
  enkrypt: 'assets/brands/enkrypt-icon-white.svg',
};
const ICONS = {};
for (const [k, src] of Object.entries(ICON_SRC)) { const img = new Image(); img.src = src; ICONS[k] = img; }
const ready = (img) => img && img.complete && img.naturalWidth > 0;

const BRAND_META = {
  outerbounds: { label: 'Outerbounds', color: '#6A9E8B' },
  kilo: { label: 'Kilo', color: '#F8F674' },
  enkrypt: { label: 'Enkrypt', color: '#FF7F00' },
};
const PRODUCT_META = {
  'ana-cli': { label: 'Ana CLI', short: 'ana', color: '#08CA4A' },
  'main-x': { label: 'Main-X', short: 'MX', color: '#068F35' },
  'anaconda-mcp': { label: 'MCP', short: 'MCP', color: '#E6FAED' },
};
const BRAND_ORDER = ['outerbounds', 'kilo', 'enkrypt'];
const PRODUCT_ORDER = ['ana-cli', 'main-x', 'anaconda-mcp'];

// ------------------------------- State ----------------------------------------
const socket = io();
let myId = null, myName = '', worldRadius = 3200, latestState = null, alive = false, boosting = false;
const camera = { x: 0, y: 0, zoom: 1 };

// Territory ground (paper.io-style), kept on an offscreen canvas at 1px/cell.
let territoryMeta = { cellSize: 16, gridDim: 400 };
const territoryCanvas = document.createElement('canvas');
const territoryCtx = territoryCanvas.getContext('2d');
const ownedCountByColor = new Map();
let cellColors = [];

function initTerritory(meta, cells) {
  territoryMeta = meta;
  territoryCanvas.width = meta.gridDim; territoryCanvas.height = meta.gridDim;
  territoryCtx.clearRect(0, 0, meta.gridDim, meta.gridDim);
  cellColors = new Array(meta.gridDim * meta.gridDim).fill(null);
  ownedCountByColor.clear();
  paintTerritoryCells(cells);
}
function paintTerritoryCells(cells) {
  for (const { idx, color } of cells) {
    const prev = cellColors[idx];
    if (prev) ownedCountByColor.set(prev, (ownedCountByColor.get(prev) || 1) - 1);
    cellColors[idx] = color;
    ownedCountByColor.set(color, (ownedCountByColor.get(color) || 0) + 1);
    territoryCtx.fillStyle = color;
    territoryCtx.fillRect(idx % territoryMeta.gridDim, (idx / territoryMeta.gridDim) | 0, 1, 1);
  }
}

// ------------------------------- Screens --------------------------------------
function showDeath(reason, length) {
  deathReasonEl.textContent = !reason ? 'You slithered into the border.' : reason === myName ? 'You bit your own tail!' : `Bitten by ${reason}`;
  finalLengthEl.textContent = length;
  deathScreen.classList.remove('hidden'); joinScreen.classList.add('hidden'); hud.classList.add('hidden');
}
function showGame() { joinScreen.classList.add('hidden'); deathScreen.classList.add('hidden'); hud.classList.remove('hidden'); }

function joinPayload() {
  const name = nameInput.value.trim() || 'Anaconda';
  localStorage.setItem('anacondae.name', name);
  return { name, color: selectedColor, clientKey };
}
playBtn.addEventListener('click', () => socket.emit('join', joinPayload()));
respawnBtn.addEventListener('click', () => socket.emit('respawn', joinPayload()));

// ------------------------------- Socket ---------------------------------------
socket.on('welcome', (d) => {
  myId = d.id; myName = d.you.name; worldRadius = d.worldRadius; alive = true;
  heading = d.you.angle; camera.x = d.you.x; camera.y = d.you.y;
  if (d.territory) initTerritory({ cellSize: d.territory.cellSize, gridDim: d.territory.gridDim }, d.territory.cells);
  showGame();
});
socket.on('territoryUpdate', ({ cells }) => paintTerritoryCells(cells));
socket.on('state', (s) => { latestState = s; worldRadius = s.worldRadius; });
socket.on('died', (d) => {
  alive = false;
  const me = latestState && latestState.snakes.find(s => s.id === myId);
  showDeath(d.killer, me ? me.length : 0);
});
socket.on('brandDiamondSpawned', ({ label }) => toast(`◆ ${label} acquisition diamond is in the arena`, ANA.mint));
socket.on('brandDiamondCollected', ({ name, label, newBuilding }) => {
  toast(newBuilding ? `${name} acquired ${label} — new building!` : `${name} grabbed a ${label} diamond`, BRAND_META[label.toLowerCase()] ? BRAND_META[label.toLowerCase()].color : ANA.green);
});
socket.on('productDiamondSpawned', ({ label }) => toast(`🚀 ${label} launch diamond is live`, ANA.green));
socket.on('productDiamondCollected', ({ name, label, newBuilding }) => {
  toast(newBuilding ? `${name} shipped ${label} — Factory upgraded!` : `${name} grabbed ${label}`, ANA.green);
});
socket.on('productLocked', ({ label }) => toast(`${label} needs the Crown first — finish the Trifecta`, ANA.gray));
socket.on('trifectaWin', ({ name }) => banner(`👑 ${name} completed the Acquisition Trifecta — Crowned!`));
socket.on('fullStackWin', ({ name }) => banner(`🏭 ${name} shipped the full stack — AI Factory complete!`));

function toast(text, color) {
  const el = document.createElement('div'); el.className = 'toast'; el.style.background = color; el.textContent = text;
  toastStack.appendChild(el); setTimeout(() => el.remove(), 3300);
}
function banner(text) {
  const el = document.createElement('div'); el.className = 'win-banner'; el.textContent = text;
  document.body.appendChild(el); setTimeout(() => el.remove(), 5200);
}

// ------------------------------- Input (keyboard) -----------------------------
const TURN_STEP = 0.11;
let heading = 0;
const keysDown = new Set();
const typing = () => ['INPUT', 'TEXTAREA'].includes(document.activeElement && document.activeElement.tagName);
window.addEventListener('keydown', (e) => {
  if (typing() || !alive) return;
  if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Space'].includes(e.code)) e.preventDefault();
  if (e.code === 'ArrowLeft') { heading -= TURN_STEP; keysDown.add('left'); }
  if (e.code === 'ArrowRight') { heading += TURN_STEP; keysDown.add('right'); }
  if (e.code === 'ArrowUp' || e.code === 'Space') boosting = true;
}, { passive: false });
window.addEventListener('keyup', (e) => {
  if (e.code === 'ArrowLeft') keysDown.delete('left');
  if (e.code === 'ArrowRight') keysDown.delete('right');
  if (e.code === 'ArrowUp' || e.code === 'Space') boosting = false;
});
window.addEventListener('touchstart', (e) => {
  const t = e.touches[0]; if (!t) return;
  heading += (t.clientX < window.innerWidth / 2 ? -1 : 1) * TURN_STEP * 3; boosting = true;
}, { passive: true });
window.addEventListener('touchend', () => { boosting = false; });
setInterval(() => {
  if (!alive) return;
  if (keysDown.has('left')) heading -= TURN_STEP * 0.5;
  if (keysDown.has('right')) heading += TURN_STEP * 0.5;
  socket.emit('input', { angle: heading, boosting });
}, 1000 / 25);

// ------------------------------- Helpers --------------------------------------
const W = (x) => (x - camera.x) * camera.zoom + canvas.width / 2;
const H = (y) => (y - camera.y) * camera.zoom + canvas.height / 2;
const zoomForLength = (len) => Math.max(0.5, 1.05 - Math.sqrt(len) * 0.012);
function hexAlpha(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

// ------------------------------- Draw: world ----------------------------------
function drawBackground() {
  const g = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, 0, canvas.width / 2, canvas.height / 2, Math.max(canvas.width, canvas.height) * 0.75);
  g.addColorStop(0, '#141614'); g.addColorStop(1, ANA.ink);
  ctx.fillStyle = g; ctx.fillRect(0, 0, canvas.width, canvas.height);
}
function drawTerritory() {
  const size = territoryMeta.gridDim * territoryMeta.cellSize * camera.zoom;
  ctx.save();
  ctx.imageSmoothingEnabled = true;
  ctx.globalAlpha = 0.42;
  ctx.drawImage(territoryCanvas, W(-worldRadius), H(-worldRadius), size, size);
  ctx.restore();
}
function drawBoundary() {
  ctx.beginPath(); ctx.arc(W(0), H(0), worldRadius * camera.zoom, 0, Math.PI * 2);
  ctx.lineWidth = 16; ctx.strokeStyle = hexAlpha(ANA.green, 0.18); ctx.stroke();
  ctx.lineWidth = 3; ctx.strokeStyle = ANA.green; ctx.stroke();
}

// ------------------------------- Draw: snake ----------------------------------
// Body is a continuous smooth stroke (round joins) with a lattice overlay —
// the same crossing-lines motif as the Anaconda ring mark.
function drawSnake(s, isMe) {
  const pts = s.points; if (!pts || pts.length < 1) return;
  const r = s.headRadius * camera.zoom;

  // live claim trail (dotted) while outside own territory
  if (s.trail && s.trail.length > 1) {
    ctx.save();
    ctx.beginPath(); ctx.moveTo(W(s.trail[0].x), H(s.trail[0].y));
    for (let i = 1; i < s.trail.length; i++) ctx.lineTo(W(s.trail[i].x), H(s.trail[i].y));
    ctx.lineTo(W(pts[0].x), H(pts[0].y));
    ctx.setLineDash([6 * camera.zoom, 8 * camera.zoom]); ctx.lineWidth = Math.max(2, 3 * camera.zoom);
    ctx.strokeStyle = hexAlpha(s.color, 0.85); ctx.lineCap = 'round'; ctx.stroke();
    ctx.restore();
  }

  if (pts.length > 1) {
    // shadow/outline
    ctx.save();
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    tracePath(pts);
    ctx.lineWidth = r * 2 + Math.max(2, 3 * camera.zoom); ctx.strokeStyle = 'rgba(0,0,0,0.55)'; ctx.stroke();
    // body fill
    ctx.lineWidth = r * 2; ctx.strokeStyle = s.color; ctx.stroke();
    // lattice overlay, clipped to body
    ctx.save();
    ctx.lineWidth = r * 2; ctx.strokeStyle = '#000'; ctx.globalCompositeOperation = 'source-over';
    ctx.clip(strokeToClipPath(pts, r * 2));
    ctx.globalAlpha = 0.22; ctx.strokeStyle = '#fff'; ctx.lineWidth = Math.max(1, r * 0.16);
    drawLattice(pts, r);
    ctx.restore();
    // highlight spine
    ctx.globalAlpha = 0.18; ctx.lineWidth = r * 0.55; ctx.strokeStyle = '#fff'; tracePath(pts); ctx.stroke();
    ctx.restore();
  }

  // head
  const head = pts[0], hx = W(head.x), hy = H(head.y);
  const ang = pts.length > 1 ? Math.atan2(head.y - pts[1].y, head.x - pts[1].x) : 0;
  ctx.beginPath(); ctx.arc(hx, hy, r * 1.08, 0, Math.PI * 2); ctx.fillStyle = s.color; ctx.fill();
  ctx.lineWidth = Math.max(1.5, r * 0.14); ctx.strokeStyle = isMe ? '#fff' : 'rgba(0,0,0,0.5)'; ctx.stroke();
  for (const side of [-1, 1]) {
    const perp = ang + (Math.PI / 2) * side;
    const ex = hx + Math.cos(ang) * r * 0.35 + Math.cos(perp) * r * 0.5;
    const ey = hy + Math.sin(ang) * r * 0.35 + Math.sin(perp) * r * 0.5;
    ctx.beginPath(); ctx.arc(ex, ey, r * 0.24, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill();
    ctx.beginPath(); ctx.arc(ex + Math.cos(ang) * r * 0.08, ey + Math.sin(ang) * r * 0.08, r * 0.12, 0, Math.PI * 2); ctx.fillStyle = ANA.ink; ctx.fill();
  }

  // name + crown
  ctx.save();
  ctx.font = '700 13px Inter, sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = '#fff';
  ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 5;
  ctx.fillText(s.name, hx, hy - r - 12);
  if (s.hasCrown) { ctx.font = `${Math.max(16, r * 1.1)}px sans-serif`; ctx.fillText('👑', hx, hy - r - 28); }
  ctx.restore();
}
function tracePath(pts) {
  ctx.beginPath(); ctx.moveTo(W(pts[0].x), H(pts[0].y));
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i].x + pts[i + 1].x) / 2, my = (pts[i].y + pts[i + 1].y) / 2;
    ctx.quadraticCurveTo(W(pts[i].x), H(pts[i].y), W(mx), H(my));
  }
  const l = pts[pts.length - 1]; ctx.lineTo(W(l.x), H(l.y));
}
function strokeToClipPath(pts, width) {
  // Approximate the stroked body as a union of circles for clipping.
  const p = new Path2D();
  const step = Math.max(1, Math.floor(pts.length / 220));
  for (let i = 0; i < pts.length; i += step) { p.moveTo(W(pts[i].x) + width / 2, H(pts[i].y)); p.arc(W(pts[i].x), H(pts[i].y), width / 2, 0, Math.PI * 2); }
  return p;
}
function drawLattice(pts, r) {
  // Diagonal crossing scales along the spine, echoing the Anaconda mark's lattice.
  const step = Math.max(2, Math.floor((r * 1.3) / (5.5 * camera.zoom)));
  for (let i = step; i < pts.length - 1; i += step) {
    const a = pts[i], b = pts[i - 1];
    const ang = Math.atan2(a.y - b.y, a.x - b.x);
    const cx = W(a.x), cy = H(a.y);
    for (const d of [-1, 1]) {
      const t = ang + d * Math.PI / 3.2;
      ctx.beginPath();
      ctx.moveTo(cx - Math.cos(t) * r, cy - Math.sin(t) * r);
      ctx.lineTo(cx + Math.cos(t) * r, cy + Math.sin(t) * r);
      ctx.stroke();
    }
  }
}

// ------------------------------- Draw: diamonds -------------------------------
function drawDiamond(d, t) {
  const sx = W(d.x), sy = H(d.y);
  if (sx < -60 || sx > canvas.width + 60 || sy < -60 || sy > canvas.height + 60) return;
  const special = d.brand || d.product;
  const base = (special ? 16 : d.big ? 10 : 6.5) * camera.zoom;
  const size = base * (1 + Math.sin(t) * 0.07);
  const color = d.color || ANA.green;

  ctx.save();
  ctx.translate(sx, sy); ctx.rotate(Math.PI / 4);
  if (special) { ctx.shadowColor = color; ctx.shadowBlur = 26; }
  const g = ctx.createLinearGradient(-size, -size, size, size);
  g.addColorStop(0, '#fff'); g.addColorStop(0.4, color); g.addColorStop(1, special ? color : ANA.deep);
  ctx.fillStyle = g; ctx.fillRect(-size, -size, size * 2, size * 2);
  ctx.lineWidth = 1.2; ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.strokeRect(-size, -size, size * 2, size * 2);
  ctx.restore();

  if (d.brand) {
    const icon = ICONS[d.brand];
    if (ready(icon)) {
      const sc = (size * 1.15) / Math.max(icon.naturalWidth, icon.naturalHeight);
      ctx.drawImage(icon, sx - icon.naturalWidth * sc / 2, sy - icon.naturalHeight * sc / 2, icon.naturalWidth * sc, icon.naturalHeight * sc);
    }
  } else if (d.product) {
    ctx.save();
    ctx.font = `900 ${Math.max(9, size * 0.6)}px Inter, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = ANA.ink; ctx.fillText(d.short || 'GA', sx, sy + 1);
    ctx.restore();
  }
  if (special) {
    ctx.save();
    ctx.font = '700 11px Inter, sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = color;
    ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 4;
    ctx.fillText(d.label, sx, sy - size - 9);
    ctx.restore();
  }
}

// ------------------------------- Draw: AI Factory -----------------------------
// Level 1: Anaconda workshop. +1 building per acquisition (with its mark),
// +1 per shipped product launch. Sits at the player's permanent home.
function drawFactory(s) {
  if (!s.home) return;
  const cx = W(s.home.x), cy = H(s.home.y);
  const z = camera.zoom;
  if (cx < -300 || cx > canvas.width + 300 || cy < -300 || cy > canvas.height + 300) return;

  const buildings = [{ kind: 'core' }];
  for (const b of BRAND_ORDER) if (s.collectedBrands && s.collectedBrands.includes(b)) buildings.push({ kind: 'brand', key: b });
  for (const p of PRODUCT_ORDER) if (s.unlockedProducts && s.unlockedProducts.includes(p)) buildings.push({ kind: 'product', key: p });

  // ground pad
  const padR = (46 + buildings.length * 12) * z;
  ctx.save();
  ctx.beginPath(); ctx.ellipse(cx, cy + 10 * z, padR, padR * 0.55, 0, 0, Math.PI * 2);
  ctx.fillStyle = hexAlpha(s.color, 0.28); ctx.fill();
  ctx.lineWidth = 2; ctx.strokeStyle = hexAlpha(s.color, 0.8); ctx.stroke();
  ctx.restore();

  // layout: core center, others on a ring
  buildings.forEach((b, i) => {
    let bx = cx, by = cy, w, h;
    if (i === 0) { w = 44 * z; h = (34 + 6 * (buildings.length - 1)) * z; }
    else {
      const ang = -Math.PI / 2 + ((i - 1) / Math.max(1, buildings.length - 1)) * Math.PI * 2;
      const rr = (34 + buildings.length * 6) * z;
      bx = cx + Math.cos(ang) * rr; by = cy + Math.sin(ang) * rr * 0.55;
      w = 26 * z; h = (b.kind === 'product' ? 30 : 24) * z;
    }
    drawBuilding(bx, by, w, h, b, s.color, z);
  });

  // label
  ctx.save();
  ctx.font = `800 ${Math.max(10, 11 * z)}px Inter, sans-serif`; ctx.textAlign = 'center';
  ctx.fillStyle = '#fff'; ctx.shadowColor = 'rgba(0,0,0,0.9)'; ctx.shadowBlur = 4;
  ctx.fillText(`${s.name}'s AI Factory · L${s.factoryLevel || 1}`, cx, cy + padR * 0.55 + 18 * z);
  ctx.restore();
}
function drawBuilding(x, y, w, h, b, ownerColor, z) {
  const wall = b.kind === 'core' ? ANA.charcoal : b.kind === 'brand' ? '#1E2A22' : '#0F3A1F';
  const accent = b.kind === 'core' ? ANA.green : b.kind === 'brand' ? BRAND_META[b.key].color : PRODUCT_META[b.key].color;
  // body
  ctx.fillStyle = 'rgba(0,0,0,0.45)'; ctx.fillRect(x - w / 2 + 3 * z, y - h + 3 * z, w, h);
  ctx.fillStyle = wall; ctx.fillRect(x - w / 2, y - h, w, h);
  // roof
  ctx.fillStyle = accent;
  if (b.kind === 'core') {
    ctx.beginPath(); ctx.moveTo(x - w / 2 - 3 * z, y - h); ctx.lineTo(x, y - h - 14 * z); ctx.lineTo(x + w / 2 + 3 * z, y - h); ctx.closePath(); ctx.fill();
  } else { ctx.fillRect(x - w / 2, y - h - 5 * z, w, 5 * z); }
  // windows
  ctx.fillStyle = hexAlpha(ANA.mint, 0.85);
  const rows = Math.max(1, Math.floor(h / (10 * z)));
  for (let r = 0; r < rows; r++) for (let c = 0; c < 2; c++) ctx.fillRect(x - w / 2 + (5 + c * (w / z / 2 - 2)) * z, y - h + (5 + r * 10) * z, 4 * z, 4 * z);
  // sign / mark
  const icon = b.kind === 'core' ? ICONS.anaconda : b.kind === 'brand' ? ICONS[b.key] : null;
  const isz = Math.min(w * 0.6, 20 * z);
  if (icon && ready(icon)) {
    ctx.save(); ctx.beginPath(); ctx.arc(x, y - h / 2, isz * 0.62, 0, Math.PI * 2);
    ctx.fillStyle = b.kind === 'core' ? '#fff' : accent; ctx.fill(); ctx.restore();
    const sc = (isz * 0.85) / Math.max(icon.naturalWidth, icon.naturalHeight);
    ctx.drawImage(icon, x - icon.naturalWidth * sc / 2, y - h / 2 - icon.naturalHeight * sc / 2, icon.naturalWidth * sc, icon.naturalHeight * sc);
  } else if (b.kind === 'product') {
    ctx.save(); ctx.font = `900 ${Math.max(8, 8 * z)}px Inter, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = accent; ctx.fillText(PRODUCT_META[b.key].short, x, y - h / 2); ctx.restore();
  }
  // owner flag on core
  if (b.kind === 'core') {
    ctx.fillStyle = ownerColor; ctx.fillRect(x - 1 * z, y - h - 26 * z, 2 * z, 14 * z);
    ctx.fillRect(x + 1 * z, y - h - 26 * z, 9 * z, 6 * z);
  }
}

// ------------------------------- HUD ------------------------------------------
function updateHud(state) {
  leaderboardList.innerHTML = '';
  state.leaderboard.forEach((row, i) => {
    const li = document.createElement('li');
    if (row.name === myName) li.className = 'me';
    li.textContent = `${row.name} — ${row.length}${row.hasCrown ? ' 👑' : ''}${row.factoryLevel > 1 ? ` · L${row.factoryLevel}` : ''}`;
    leaderboardList.appendChild(li);
  });
  statPlayers.textContent = state.playerCount;

  hallOfFameList.innerHTML = '';
  if (!state.hallOfFame || state.hallOfFame.length === 0) {
    const li = document.createElement('li'); li.textContent = 'No one yet — be first'; hallOfFameList.appendChild(li);
  } else for (const row of state.hallOfFame) {
    const li = document.createElement('li');
    li.textContent = `${row.type === 'fullstack' ? '🏭' : '👑'} ${row.name}`;
    hallOfFameList.appendChild(li);
  }

  const me = state.snakes.find(s => s.id === myId);
  if (me) {
    statLength.textContent = me.length;
    const cells = ownedCountByColor.get(me.color) || 0;
    const km2 = (cells * territoryMeta.cellSize * territoryMeta.cellSize) / 1e4;
    statLand.textContent = km2.toFixed(1);
    renderFactorySlots(me);
  }
}
function renderFactorySlots(me) {
  const items = [
    { key: 'core', label: 'ANA', color: ANA.green, built: true, icon: ICON_SRC.anaconda },
    ...BRAND_ORDER.map(b => ({ key: b, label: BRAND_META[b].label.slice(0, 3).toUpperCase(), color: BRAND_META[b].color, built: me.collectedBrands.includes(b), icon: ICON_SRC[b] })),
    ...PRODUCT_ORDER.map(p => ({ key: p, label: PRODUCT_META[p].short, color: PRODUCT_META[p].color, built: me.unlockedProducts.includes(p), locked: !me.hasCrown })),
  ];
  const sig = items.map(i => (i.built ? 1 : 0)).join('') + (me.hasCrown ? 'c' : '');
  if (factorySlots.dataset.sig === sig) return;
  factorySlots.dataset.sig = sig;
  factorySlots.innerHTML = '';
  for (const it of items) {
    const el = document.createElement('div');
    el.className = 'slot' + (it.built ? ' built' : '');
    el.title = it.label;
    if (it.built) { el.style.background = it.color; el.style.borderColor = it.color; }
    if (it.built && it.icon) { const img = document.createElement('img'); img.src = it.icon; el.appendChild(img); }
    else el.textContent = it.locked && !it.built ? '🔒' : it.label;
    factorySlots.appendChild(el);
  }
  const brandsLeft = BRAND_ORDER.filter(b => !me.collectedBrands.includes(b)).length;
  const prodsLeft = PRODUCT_ORDER.filter(p => !me.unlockedProducts.includes(p)).length;
  factoryHint.textContent = !me.hasCrown
    ? `${brandsLeft} acquisition${brandsLeft === 1 ? '' : 's'} to go for the Crown.`
    : prodsLeft > 0 ? `Crowned. Ship ${prodsLeft} more launch${prodsLeft === 1 ? '' : 'es'} (Ana CLI, Main-X, MCP) to complete your Factory.` : 'Full-stack AI Factory complete.';
}

// ------------------------------- Minimap --------------------------------------
function drawMinimap(state) {
  if (!minimap.clientWidth) return; // HUD hidden
  const w = minimap.width = minimap.clientWidth * devicePixelRatio, h = minimap.height = minimap.clientHeight * devicePixelRatio;
  mctx.clearRect(0, 0, w, h);
  mctx.save(); mctx.translate(w / 2, h / 2);
  const sc = (Math.min(w, h) / 2 - 4) / worldRadius;
  // territory thumbnail
  mctx.save(); mctx.globalAlpha = 0.55; mctx.imageSmoothingEnabled = true;
  mctx.beginPath(); mctx.arc(0, 0, worldRadius * sc, 0, Math.PI * 2); mctx.clip();
  mctx.drawImage(territoryCanvas, -worldRadius * sc, -worldRadius * sc, worldRadius * 2 * sc, worldRadius * 2 * sc);
  mctx.restore();
  for (const s of state.snakes) {
    if (!s.alive || !s.points || !s.points.length) continue;
    const me = s.id === myId;
    mctx.beginPath(); mctx.moveTo(s.points[0].x * sc, s.points[0].y * sc);
    for (let i = 1; i < s.points.length; i++) mctx.lineTo(s.points[i].x * sc, s.points[i].y * sc);
    mctx.strokeStyle = me ? '#fff' : s.color; mctx.lineWidth = (me ? 2.6 : 1.8) * devicePixelRatio; mctx.lineCap = 'round'; mctx.stroke();
    mctx.beginPath(); mctx.arc(s.points[0].x * sc, s.points[0].y * sc, me ? 4 : 2.5, 0, Math.PI * 2); mctx.fillStyle = me ? '#fff' : s.color; mctx.fill();
    if (s.home) { mctx.fillStyle = s.color; mctx.fillRect(s.home.x * sc - 2, s.home.y * sc - 2, 4, 4); }
  }
  mctx.restore();
}

// ------------------------------- Render loop ----------------------------------
let t = 0;
function render() {
  t += 0.05;
  drawBackground();
  if (latestState) {
    const me = latestState.snakes.find(s => s.id === myId);
    if (me && me.alive) {
      camera.x = me.points[0].x; camera.y = me.points[0].y;
      camera.zoom += (zoomForLength(me.length) - camera.zoom) * 0.06;
    }
    drawTerritory();
    drawBoundary();
    for (const f of (latestState.factories || [])) drawFactory(f);
    for (const d of latestState.diamonds) drawDiamond(d, t + d.id.length);
    for (const s of latestState.snakes) if (s.alive) drawSnake(s, s.id === myId);
    updateHud(latestState);
    drawMinimap(latestState);
  }
  requestAnimationFrame(render);
}
render();
