'use strict';
/* ANACONDAE client — canvas renderer + input + socket handling */

const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const minimap = document.getElementById('minimap');
const mctx = minimap.getContext('2d');

const joinScreen = document.getElementById('join-screen');
const deathScreen = document.getElementById('death-screen');
const hud = document.getElementById('hud');
const nameInput = document.getElementById('name-input');
const playBtn = document.getElementById('play-btn');
const respawnBtn = document.getElementById('respawn-btn');
const colorSwatchesEl = document.getElementById('color-swatches');
const leaderboardList = document.getElementById('leaderboard-list');
const statLength = document.getElementById('stat-length');
const statPlayers = document.getElementById('stat-players');
const finalLengthEl = document.getElementById('final-length');
const deathReasonEl = document.getElementById('death-reason');

let toastStack = document.getElementById('toast-stack');
if (!toastStack) {
  toastStack = document.createElement('div');
  toastStack.id = 'toast-stack';
  document.body.appendChild(toastStack);
}

const COLORS = [
  '#3EB049', '#F2B705', '#2FA4A9', '#E0574C', '#8E6BC7',
  '#4E9F3D', '#D98E04', '#3D7EA6', '#C43E3E', '#5CB85C',
];
let selectedColor = COLORS[0];
COLORS.forEach((c, i) => {
  const el = document.createElement('div');
  el.className = 'swatch' + (i === 0 ? ' selected' : '');
  el.style.background = c;
  el.addEventListener('click', () => {
    selectedColor = c;
    document.querySelectorAll('.swatch').forEach(s => s.classList.remove('selected'));
    el.classList.add('selected');
  });
  colorSwatchesEl.appendChild(el);
});
nameInput.value = 'Kaa' + Math.floor(Math.random() * 90 + 10);

function resize() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

const socket = io();

let myId = null;
let myName = '';
let worldRadius = 3200;
let latestState = null;
let alive = false;
let camera = { x: 0, y: 0, zoom: 1 };
let boosting = false;

function showJoin() {
  joinScreen.classList.remove('hidden');
  deathScreen.classList.add('hidden');
  hud.classList.add('hidden');
}
function showDeath(reason, length) {
  if (!reason) {
    deathReasonEl.textContent = 'You slithered into the border.';
  } else if (reason === myName) {
    deathReasonEl.textContent = 'You bit your own tail!';
  } else {
    deathReasonEl.textContent = `Bitten by ${reason}`;
  }
  finalLengthEl.textContent = length;
  deathScreen.classList.remove('hidden');
  joinScreen.classList.add('hidden');
  hud.classList.add('hidden');
}
function showGame() {
  joinScreen.classList.add('hidden');
  deathScreen.classList.add('hidden');
  hud.classList.remove('hidden');
}

playBtn.addEventListener('click', () => {
  const name = nameInput.value.trim() || 'Anaconda';
  socket.emit('join', { name, color: selectedColor });
});
respawnBtn.addEventListener('click', () => {
  const name = nameInput.value.trim() || 'Anaconda';
  socket.emit('respawn', { name, color: selectedColor });
});

socket.on('welcome', (data) => {
  myId = data.id;
  myName = data.you.name;
  worldRadius = data.worldRadius;
  alive = true;
  heading = data.you.angle;
  camera.x = data.you.x;
  camera.y = data.you.y;
  showGame();
});

socket.on('died', (data) => {
  alive = false;
  const me = latestState && latestState.snakes.find(s => s.id === myId);
  showDeath(data.killer, me ? me.length : 0);
});

socket.on('state', (state) => {
  latestState = state;
  worldRadius = state.worldRadius;
});

// Real acquisition brand marks (Anaconda owns these trademarks), preloaded once.
const BRAND_ICON_SRC = {
  outerbounds: 'assets/brands/outerbounds-icon-white.svg',
  kilo: 'assets/brands/kilo-icon-white.svg',
  enkrypt: 'assets/brands/enkrypt-icon-white.svg',
};
const BRAND_ICONS = {};
for (const [brand, src] of Object.entries(BRAND_ICON_SRC)) {
  const img = new Image();
  img.src = src;
  BRAND_ICONS[brand] = img;
}

socket.on('brandDiamondSpawned', ({ label }) => {
  spawnToast(`💎 A ${label} diamond appeared in the arena!`, '#F2B705');
});
socket.on('brandDiamondCollected', ({ name, label }) => {
  spawnToast(`${name} scooped up the ${label} diamond!`, '#3EB049');
});

function spawnToast(text, color) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.style.background = color;
  el.textContent = text;
  toastStack.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ------------------------------- Input (keyboard-only steering) ---------------
// Left/Right arrows turn the snake; each key repeat (or held key) keeps
// steering that way, just like tapping a direction in classic Snake — no
// mouse involved. Up arrow / Space boosts.
const TURN_STEP = 0.11; // radians nudged per key event, mirrors server turn rate
let heading = 0;
const keysDown = new Set();

function isTypingInField() {
  const tag = document.activeElement && document.activeElement.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA';
}
window.addEventListener('keydown', (e) => {
  if (isTypingInField() || !alive) return;
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
// Touch fallback for mobile: tap left/right half of the screen to turn.
window.addEventListener('touchstart', (e) => {
  const t = e.touches[0];
  if (!t) return;
  if (t.clientX < window.innerWidth / 2) heading -= TURN_STEP * 3;
  else heading += TURN_STEP * 3;
  boosting = true;
}, { passive: true });
window.addEventListener('touchend', () => { boosting = false; });

function sendInput() {
  if (!alive) return;
  // continuous turning while a key is held down
  if (keysDown.has('left')) heading -= TURN_STEP * 0.5;
  if (keysDown.has('right')) heading += TURN_STEP * 0.5;
  socket.emit('input', { angle: heading, boosting });
}
setInterval(sendInput, 1000 / 25);

// ------------------------------- Rendering ------------------------------------
function zoomForLength(length) {
  // zoom out gently as the snake grows, like slither.io
  return Math.max(0.55, 1.05 - Math.sqrt(length) * 0.012);
}

function drawWorldBackground() {
  // A plain, calm jungle-dark backdrop with a soft vignette toward the edges.
  // (A decorative diamond grid used to live here — removed since it was
  // screen-space only and didn't correspond to anything in the world.)
  const grad = ctx.createRadialGradient(
    canvas.width / 2, canvas.height / 2, 0,
    canvas.width / 2, canvas.height / 2, Math.max(canvas.width, canvas.height) * 0.7
  );
  grad.addColorStop(0, '#161d13');
  grad.addColorStop(1, '#0c0f0a');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawSnake(s, isMe) {
  const pts = s.points;
  if (!pts || pts.length < 1) return;
  const r = s.headRadius;

  // body: diamond-scale pattern using alternating light/dark circles along the spine
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i];
    const t = i / pts.length; // 0 at head, 1 at tail
    const segR = r * (1 - t * 0.35);
    const sx = (p.x - camera.x) * camera.zoom + canvas.width / 2;
    const sy = (p.y - camera.y) * camera.zoom + canvas.height / 2;
    const sr = segR * camera.zoom;
    if (sx < -sr || sx > canvas.width + sr || sy < -sr || sy > canvas.height + sr) continue;

    ctx.beginPath();
    ctx.arc(sx, sy, sr, 0, Math.PI * 2);
    ctx.fillStyle = s.color;
    ctx.fill();

    if (i % 2 === 0) {
      ctx.beginPath();
      ctx.arc(sx, sy, sr * 0.55, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,255,255,0.16)';
      ctx.fill();
    }
  }

  // head + eyes + name
  const head = pts[0];
  const hx = (head.x - camera.x) * camera.zoom + canvas.width / 2;
  const hy = (head.y - camera.y) * camera.zoom + canvas.height / 2;
  const hr = r * camera.zoom;
  const ang = pts.length > 1 ? Math.atan2(head.y - pts[1].y, head.x - pts[1].x) : 0;

  ctx.beginPath();
  ctx.arc(hx, hy, hr, 0, Math.PI * 2);
  ctx.fillStyle = s.color;
  ctx.fill();
  ctx.lineWidth = Math.max(1, hr * 0.12);
  ctx.strokeStyle = isMe ? '#F2B705' : 'rgba(0,0,0,0.25)';
  ctx.stroke();

  const eyeOff = hr * 0.5;
  const eyeFwd = hr * 0.35;
  for (const side of [-1, 1]) {
    const perp = ang + (Math.PI / 2) * side;
    const ex = hx + Math.cos(ang) * eyeFwd + Math.cos(perp) * eyeOff;
    const ey = hy + Math.sin(ang) * eyeFwd + Math.sin(perp) * eyeOff;
    ctx.beginPath(); ctx.arc(ex, ey, hr * 0.22, 0, Math.PI * 2);
    ctx.fillStyle = '#fff'; ctx.fill();
    ctx.beginPath(); ctx.arc(ex + Math.cos(ang) * hr * 0.08, ey + Math.sin(ang) * hr * 0.08, hr * 0.1, 0, Math.PI * 2);
    ctx.fillStyle = '#111'; ctx.fill();
  }

  ctx.font = '600 13px Rubik, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.shadowColor = 'rgba(0,0,0,0.8)';
  ctx.shadowBlur = 4;
  ctx.fillText(s.name, hx, hy - hr - 12);
  ctx.shadowBlur = 0;
}

function drawDiamond(d, tPulse) {
  const sx = (d.x - camera.x) * camera.zoom + canvas.width / 2;
  const sy = (d.y - camera.y) * camera.zoom + canvas.height / 2;
  const baseSize = (d.brand ? 15 : (d.big ? 11 : 7)) * camera.zoom;
  if (sx < -40 || sx > canvas.width + 40 || sy < -40 || sy > canvas.height + 40) return;
  const size = baseSize * (1 + Math.sin(tPulse) * 0.08);

  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(Math.PI / 4);

  if (d.brand) {
    ctx.shadowColor = d.color;
    ctx.shadowBlur = 22;
  }
  const grad = ctx.createLinearGradient(-size, -size, size, size);
  const color = d.color || '#3EB049';
  grad.addColorStop(0, '#ffffff');
  grad.addColorStop(0.35, color);
  grad.addColorStop(1, color);
  ctx.fillStyle = grad;
  ctx.fillRect(-size, -size, size * 2, size * 2);
  ctx.strokeStyle = 'rgba(255,255,255,0.6)';
  ctx.lineWidth = 1.2;
  ctx.strokeRect(-size, -size, size * 2, size * 2);
  ctx.restore();

  if (d.brand) {
    const icon = BRAND_ICONS[d.brand];
    if (icon && icon.complete && icon.naturalWidth > 0) {
      const iw = icon.naturalWidth, ih = icon.naturalHeight;
      const scale = (size * 1.15) / Math.max(iw, ih);
      const dw = iw * scale, dh = ih * scale;
      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,0.6)';
      ctx.shadowBlur = 3;
      ctx.drawImage(icon, sx - dw / 2, sy - dh / 2, dw, dh);
      ctx.restore();
    } else {
      // fallback while the icon is still loading
      ctx.save();
      ctx.font = `800 ${Math.max(10, size * 0.62)}px Rubik, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#10130F';
      ctx.fillText(d.label[0], sx, sy + 1);
      ctx.restore();
    }

    ctx.save();
    ctx.font = '700 11px Rubik, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = d.color;
    ctx.shadowColor = 'rgba(0,0,0,0.9)';
    ctx.shadowBlur = 4;
    ctx.fillText(d.label, sx, sy - size - 8);
    ctx.restore();
  }
}

function drawBoundary() {
  const sx = (0 - camera.x) * camera.zoom + canvas.width / 2;
  const sy = (0 - camera.y) * camera.zoom + canvas.height / 2;
  const sr = worldRadius * camera.zoom;
  ctx.beginPath();
  ctx.arc(sx, sy, sr, 0, Math.PI * 2);
  ctx.lineWidth = 14;
  ctx.strokeStyle = 'rgba(242,183,5,0.55)';
  ctx.stroke();
  ctx.lineWidth = 3;
  ctx.strokeStyle = 'rgba(224,87,76,0.85)';
  ctx.stroke();
}

function updateLeaderboard(state) {
  leaderboardList.innerHTML = '';
  state.leaderboard.forEach((row, i) => {
    const li = document.createElement('li');
    const isMe = latestState && latestState.snakes.find(s => s.id === myId && s.name === row.name);
    if (isMe) li.className = 'me';
    li.innerHTML = `<b>${i + 1}.</b> ${escapeHtml(row.name)} — ${row.length}`;
    leaderboardList.appendChild(li);
  });
  statPlayers.textContent = state.playerCount;
}
function escapeHtml(s) { return s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

function drawMinimap(state) {
  const w = minimap.width = minimap.clientWidth * devicePixelRatio;
  const h = minimap.height = minimap.clientHeight * devicePixelRatio;
  mctx.clearRect(0, 0, w, h);
  mctx.save();
  mctx.translate(w / 2, h / 2);
  const scale = (Math.min(w, h) / 2 - 4) / worldRadius;
  for (const s of state.snakes) {
    if (!s.alive) continue;
    const p = s.points[0];
    mctx.beginPath();
    mctx.arc(p.x * scale, p.y * scale, s.id === myId ? 4 : 2.5, 0, Math.PI * 2);
    mctx.fillStyle = s.id === myId ? '#F2B705' : s.color;
    mctx.fill();
  }
  mctx.restore();
}

let t = 0;
function render() {
  t += 0.05;
  ctx.fillStyle = '#10130F';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (latestState) {
    const me = latestState.snakes.find(s => s.id === myId);
    if (me && me.alive) {
      camera.x = me.points[0].x;
      camera.y = me.points[0].y;
      camera.zoom += (zoomForLength(me.length) - camera.zoom) * 0.06;
      statLength.textContent = me.length;
    }

    drawWorldBackground();
    drawBoundary();

    for (const d of latestState.diamonds) drawDiamond(d, t + (d.id.length || 0));
    for (const s of latestState.snakes) {
      if (!s.alive) continue;
      drawSnake(s, s.id === myId);
    }

    updateLeaderboard(latestState);
    drawMinimap(latestState);
  }

  requestAnimationFrame(render);
}
render();
