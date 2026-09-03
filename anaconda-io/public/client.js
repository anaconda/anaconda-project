'use strict';
/* Anaconda AI Factory — client, handoff 3 (Part B visual system, Part C screens) */

const C = { lilac900: '#2E2667', lilac500: '#6D5BF6', lilac400: '#8A7CF8', lilac50: '#F0EFFE', green500: '#08CA4A', green300: '#9CF215', green200: '#C1FF60', green950: '#023E18', yellow: '#FFBA06', red: '#D00100', groundHi: '#3A3080', groundLo: '#241C55', outside: '#1B1540' };
const FONT = { head: "'Space Grotesk', sans-serif", eyebrow: "'Space Mono', monospace", body: "'Inter', sans-serif", num: "'Roboto Mono', monospace" };
const EASE = 'cubic-bezier(.2,.8,.2,1)';
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = (id) => document.getElementById(id);
const canvas = $('game'), ctx = canvas.getContext('2d'); window.__ctx = ctx; const minimap = $('minimap'), mctx = minimap.getContext('2d');
const el = { flash: $('flash'), join: $('join-screen'), death: $('death-screen'), hud: $('hud'), play: $('play-btn'), respawn: $('respawn-btn'), name: $('name-input'), skins: $('skins'), share: $('share-btn'), cta: $('cta-btn'), mute: $('mute'),
  projects: $('stat-projects'), length: $('stat-length'), floor: $('stat-floor'), floorWrap: $('stat-floor-wrap'), fundLabel: $('funding-label'), fundPct: $('funding-pct'), fundFill: $('funding-fill'), chips: $('acq-chips'), funding: $('funding'),
  lb: $('leaderboard'), lbList: $('leaderboard-list'), hof: $('hall-of-fame'), hofList: $('hall-of-fame-list'), feed: $('feed'), toasts: $('toasts'), hint: $('hint'), buildHint: $('build-hint'), hero: $('hero') };

let clientKey = localStorage.getItem('anacondae.clientKey'); if (!clientKey) { clientKey = 'ck_' + Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem('anacondae.clientKey', clientKey); }
let savedName = localStorage.getItem('anacondae.name') || '';
let SKINS = ['#08CA4A', '#9CF215', '#C1FF60', '#068C35', '#6D5BF6', '#8A7CF8', '#F0EFFE'];
let skin = localStorage.getItem('anacondae.color') || SKINS[Math.floor(Math.random() * SKINS.length)];
function resize() { canvas.width = innerWidth; canvas.height = innerHeight; } addEventListener('resize', resize); resize();

const ICONS = {}; for (const [k, src] of Object.entries({ anaconda: 'assets/brands/anaconda-mark.png', outerbounds: 'assets/brands/outerbounds-icon-white.svg', kilo: 'assets/brands/kilo-icon-white.svg', enkrypt: 'assets/brands/enkrypt-icon-white.svg' })) { const i = new Image(); i.src = src; ICONS[k] = i; }
const ready = (i) => i && i.complete && i.naturalWidth > 0;
const fmtT = (b) => b >= 1000 ? (b / 1000).toFixed(2) + 'T' : Math.round(b) + 'B';
const fmtTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function rgba(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`; }
function shade(hex, f) { const n = parseInt(hex.slice(1), 16); let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255; if (f < 0) { r *= 1 + f; g *= 1 + f; b *= 1 + f; } else { r += (255 - r) * f; g += (255 - g) * f; b += (255 - b) * f; } return `rgb(${r | 0},${g | 0},${b | 0})`; }

// ------------------------------- Sound (E5, synthesized) -----------------------
let AC = null, muted = localStorage.getItem('anacondae.mute') === '1', combo = 0, lastEat = 0, boostNode = null, ambient = null;
el.mute.textContent = muted ? 'SOUND OFF' : 'SOUND ON';
el.mute.onclick = () => { muted = !muted; localStorage.setItem('anacondae.mute', muted ? '1' : '0'); el.mute.textContent = muted ? 'SOUND OFF' : 'SOUND ON'; music.setMuted(muted); if (muted) sfx.boost(false); };
function ac() { if (!AC) { try { AC = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return null; } } if (AC.state === 'suspended') AC.resume(); return AC; }
function tone(f, dur, type = 'triangle', gain = 0.06, to) { if (muted) return; const a = ac(); if (!a) return; const o = a.createOscillator(), g = a.createGain(); o.type = type; o.frequency.setValueAtTime(f, a.currentTime); if (to) o.frequency.exponentialRampToValueAtTime(to, a.currentTime + dur); g.gain.setValueAtTime(gain, a.currentTime); g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + dur); o.connect(g).connect(a.destination); o.start(); o.stop(a.currentTime + dur); }
function noise(dur, gain = 0.06, hp = 800) { if (muted) return; const a = ac(); if (!a) return; const buf = a.createBuffer(1, a.sampleRate * dur, a.sampleRate), d = buf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; const src = a.createBufferSource(); src.buffer = buf; const f = a.createBiquadFilter(); f.type = 'highpass'; f.frequency.value = hp; const g = a.createGain(); g.gain.setValueAtTime(gain, a.currentTime); g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + dur); src.connect(f).connect(g).connect(a.destination); src.start(); }
const NOTE = { C4: 261.6, E4: 329.6, G4: 392, C5: 523.3, D5: 587.3, E5: 659.3, G5: 784, A5: 880, C6: 1046.5 };
// ------------------------------- Music (generative pad + arpeggio) -------------
const music = (() => {
  let started = false, master = null, timer = null, step = 0;
  const CHORDS = [[261.6, 329.6, 392, 493.9], [220, 261.6, 329.6, 392], [174.6, 220, 261.6, 329.6], [196, 246.9, 293.7, 349.2]]; // Cmaj7 Am7 Fmaj7 G
  function pad(freqs, dur) { const a = ac(); if (!a) return; for (const f of freqs) for (const det of [-3, 3]) { const o = a.createOscillator(), g = a.createGain(); o.type = 'triangle'; o.frequency.value = f / 2; o.detune.value = det; g.gain.setValueAtTime(0.0001, a.currentTime); g.gain.exponentialRampToValueAtTime(0.028, a.currentTime + 1.2); g.gain.setValueAtTime(0.028, a.currentTime + dur - 1.4); g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + dur); o.connect(g).connect(master); o.start(); o.stop(a.currentTime + dur + 0.05); } }
  function pluck(f, when) { const a = ac(); if (!a) return; const o = a.createOscillator(), g = a.createGain(), lp = a.createBiquadFilter(); o.type = 'sine'; o.frequency.value = f; lp.type = 'lowpass'; lp.frequency.value = 2200; g.gain.setValueAtTime(0.0001, when); g.gain.exponentialRampToValueAtTime(0.05, when + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, when + 0.7); o.connect(lp).connect(g).connect(master); o.start(when); o.stop(when + 0.75); }
  function bar() { const a = ac(); if (!a) return; const chord = CHORDS[step % CHORDS.length]; pad(chord, 6.2); const beat = 6 / 11; for (let i = 0; i < 11; i++) { if (Math.random() < 0.55) pluck(chord[(i * 2 + step) % chord.length] * (Math.random() < 0.3 ? 2 : 1), a.currentTime + i * beat + 0.05); } step++; }
  return {
    start() { const a = ac(); if (!a || started) return; started = true; master = a.createGain(); master.gain.value = muted ? 0 : 0.6; master.connect(a.destination); bar(); timer = setInterval(bar, 6000); },
    duck(ms) { if (!master) return; const a = ac(); master.gain.cancelScheduledValues(a.currentTime); master.gain.setValueAtTime(muted ? 0 : 0.15, a.currentTime); master.gain.linearRampToValueAtTime(muted ? 0 : 0.6, a.currentTime + ms / 1000); },
    setMuted(m) { if (master) master.gain.value = m ? 0 : 0.6; },
  };
})();

const sfx = {
  eat() { const n = performance.now(); combo = n - lastEat < 1200 ? Math.min(combo + 1, 12) : 0; lastEat = n; tone(880 * Math.pow(2, combo / 12), 0.06, 'triangle', 0.05); },
  claim(big) { tone(big ? NOTE.C4 : NOTE.C5, 0.18, 'sine', 0.07); setTimeout(() => tone(big ? NOTE.G4 : NOTE.G5, 0.25, 'sine', 0.08), 110); },
  vetted() { tone(1200, 0.04, 'square', 0.03); setTimeout(() => tone(1500, 0.05, 'sine', 0.03, 1900), 40); },
  setback() { noise(0.12, 0.09, 1200); setTimeout(() => tone(700, 0.05, 'square', 0.05, 300), 90); setTimeout(() => tone(400, 0.06, 'square', 0.05, 150), 170); },
  block() { noise(0.3, 0.03, 2000); setTimeout(() => tone(1760, 0.15, 'sine', 0.06), 280); },
  adopt(key) { const root = { outerbounds: NOTE.C4, kilo: NOTE.E4, enkrypt: NOTE.G4 }[key] || NOTE.C4; tone(root, 0.9, 'sawtooth', 0.05); tone(root * 2, 0.9, 'sawtooth', 0.03); },
  landmark() { tone(60, 0.7, 'sine', 0.1, 40); tone(220, 0.7, 'sine', 0.03, 660); },
  build() { tone(NOTE.C4 / 2, 0.7, 'sawtooth', 0.06); tone(NOTE.C4, 0.7, 'sawtooth', 0.03); },
  ship(order) { tone([NOTE.C5, NOTE.D5, NOTE.E5, NOTE.G5, NOTE.A5][(order || 1) - 1] || NOTE.C5, 0.08, 'sine', 0.03); },
  death() { tone(120, 1, 'sine', 0.12, 50); },
  gotcha() { tone(NOTE.C5, 0.1, 'triangle', 0.06); setTimeout(() => tone(NOTE.G5, 0.12, 'triangle', 0.06), 90); },
  bong() { tone(110, 0.3, 'sine', 0.03); },
  trillion() { [NOTE.C4, NOTE.E4, NOTE.G4, NOTE.C6].forEach(f => tone(f, 1.5, 'sawtooth', 0.04)); },
  boost(on) { const a = ac(); if (!a || muted) return; if (on && !boostNode) { const buf = a.createBuffer(1, a.sampleRate, a.sampleRate), d = buf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; const src = a.createBufferSource(); src.buffer = buf; src.loop = true; const f = a.createBiquadFilter(); f.type = 'highpass'; f.frequency.setValueAtTime(200, a.currentTime); f.frequency.linearRampToValueAtTime(600, a.currentTime + 0.4); const g = a.createGain(); g.gain.value = 0.02; src.connect(f).connect(g).connect(a.destination); src.start(); boostNode = { src }; } if (!on && boostNode) { boostNode.src.stop(); boostNode = null; } },
  ambient() { const a = ac(); if (!a || ambient) return; const buf = a.createBuffer(1, a.sampleRate * 2, a.sampleRate), d = buf.getChannelData(0); let b0 = 0; for (let i = 0; i < d.length; i++) { const w = Math.random() * 2 - 1; b0 = 0.98 * b0 + w * 0.02; d[i] = b0 * 3; } const src = a.createBufferSource(); src.buffer = buf; src.loop = true; const g = a.createGain(); g.gain.value = muted ? 0 : 0.012; src.connect(g).connect(a.destination); src.start(); ambient = { src, g }; },
};

// ------------------------------- State ----------------------------------------
const socket = io();
let myId = null, myName = '', worldRadius = 2400, state = null, alive = false, boosting = false, everJoined = false, PRODUCTS = [], ACQ = [];
const camera = { x: 0, y: 0, zoom: 1.05 };
let spawnAt = 0, ateOnce = false, leftFloor = false, captured = false, lastFloor = 0, edgeFlashUntil = 0, claimSweep = null;
let headSquash = 0, ripple = 0, slowmoUntil = 0, foundationAt = 0, lastDeath = null;
const pops = [], shards = [], crates = [], dust = [], vetFlashes = [], landmarkAppear = {}, buildAppear = {};
let prevComps = new Map(), reveal = { floor: false, funding: false, lb: false };

// Territory canvases (1px/cell fill + 1px/cell edge)
let meta = { cellSize: 50, gridDim: 96 }; let cellColors = [];
const fillC = document.createElement('canvas'), fillX = fillC.getContext('2d'), edgeC = document.createElement('canvas'), edgeX = edgeC.getContext('2d');
function initTerritory(m, cells) { meta = m; cellColors = new Array(m.gridDim * m.gridDim).fill(null); fillC.width = fillC.height = edgeC.width = edgeC.height = m.gridDim; fillX.clearRect(0, 0, m.gridDim, m.gridDim); edgeX.clearRect(0, 0, m.gridDim, m.gridDim); paintCells(cells); }
function paintCells(cells) {
  const g = meta.gridDim, touched = new Set();
  for (const { idx, color } of cells) { cellColors[idx] = color; const c = idx % g, r = (idx / g) | 0; if (color) { fillX.fillStyle = color; fillX.fillRect(c, r, 1, 1); } else fillX.clearRect(c, r, 1, 1); touched.add(idx); if (c > 0) touched.add(idx - 1); if (c < g - 1) touched.add(idx + 1); if (r > 0) touched.add(idx - g); if (r < g - 1) touched.add(idx + g); }
  for (const idx of touched) { const g2 = meta.gridDim, c = idx % g2, r = (idx / g2) | 0, col = cellColors[idx]; edgeX.clearRect(c, r, 1, 1); if (!col) continue; const nb = (i) => cellColors[i] === col; if (r === 0 || r === g2 - 1 || c === 0 || c === g2 - 1 || !nb(idx - g2) || !nb(idx + g2) || !nb(idx - 1) || !nb(idx + 1)) { edgeX.fillStyle = col; edgeX.fillRect(c, r, 1, 1); } }
}

// ------------------------------- Screens --------------------------------------
const joinPayload = () => ({ name: savedName || undefined, color: skin, clientKey });
const startName = $('start-name'); startName.value = savedName;
function takeStartName() { const n = startName.value.trim().slice(0, 18); if (n) { savedName = n; localStorage.setItem('anacondae.name', n); } }
el.play.onclick = () => { ac(); takeStartName(); music.start(); socket.emit('join', joinPayload()); track('play'); };
el.respawn.onclick = () => { if (!el.respawn.disabled) { commitName(); socket.emit('respawn', joinPayload()); track('play_again'); } };
addEventListener('keydown', (e) => { if (e.key !== 'Enter') return; if (!el.join.classList.contains('hidden')) el.play.click(); else if (!el.death.classList.contains('hidden')) el.respawn.click(); });
addEventListener('keydown', (e) => { if (document.activeElement === startName && !['Enter', 'Tab'].includes(e.key)) e.stopPropagation(); }, true);
function commitName() { const n = el.name.value.trim().slice(0, 18); if (n && n !== savedName) { savedName = n; localStorage.setItem('anacondae.name', n); socket.emit('setName', { name: n }); myName = n; } }
el.cta.onclick = () => track('cta_click');
el.share.onclick = () => { renderShareCard(lastDeath); const a = document.createElement('a'); a.download = 'anaconda-ai-factory.png'; a.href = $('share-card').toDataURL('image/png'); a.click(); track('share'); };
function track(event) { socket.emit('analytics', { event }); }
function renderSkins() { el.skins.innerHTML = ''; for (const c of SKINS) { const d = document.createElement('div'); d.className = 'skin' + (c === skin ? ' sel' : ''); d.style.background = c; d.onclick = () => { skin = c; localStorage.setItem('anacondae.color', c); socket.emit('setSkin', { color: c }); renderSkins(); }; el.skins.appendChild(d); } }

socket.on('welcome', (d) => {
  everJoined = true; myId = d.id; myName = d.you.name; worldRadius = d.worldRadius; alive = true; heading = d.you.angle; camera.x = d.you.x; camera.y = d.you.y;
  spawnAt = Date.now(); ateOnce = false; leftFloor = false; captured = false; lastFloor = 0; PRODUCTS = d.products; ACQ = d.acquisitions; if (d.colors) SKINS = d.colors; if (d.cta) el.cta.href = d.cta;
  initTerritory({ cellSize: d.territory.cellSize, gridDim: d.territory.gridDim }, d.territory.cells);
  comps.clear(); for (const c of d.components || []) comps.set(c.id, c);
  el.feed.innerHTML = ''; el.join.classList.add('hidden'); el.death.classList.add('hidden'); el.hud.classList.remove('hidden');
  setTimeout(() => show('lb'), 30000);
});
function show(k) { if (reveal[k]) return; reveal[k] = true; ({ floor: el.floorWrap, funding: el.funding, lb: el.lb }[k]).classList.add('shown'); if (k === 'lb') minimap.classList.add('shown'); }
socket.on('territoryUpdate', ({ cells }) => paintCells(cells));
const comps = new Map();
function unflat(a) { const out = new Array(a.length / 2); for (let i = 0; i < out.length; i++) out[i] = { x: a[i * 2], y: a[i * 2 + 1] }; return out; }
let metaState = null; const snakeMeta = new Map();
socket.on('meta', (m) => { metaState = m; worldRadius = m.worldRadius; snakeMeta.clear(); for (const sn of m.snakes) snakeMeta.set(sn.id, sn); if (state) mergeState(state); });
function mergeState(s) {
  for (const sn of s.snakes) { const m = snakeMeta.get(sn.id); if (m) Object.assign(sn, m); else Object.assign(sn, { name: '', color: C.lilac400, home: null, products: [], caps: [], crown: false, tokens: 0, projects: 0, datasets: 0 }); }
  if (metaState) { s.leaderboard = metaState.leaderboard; s.hallOfFame = metaState.hallOfFame; s.funding = metaState.funding; s.acquisitions = metaState.acquisitions; s.playerCount = metaState.playerCount; }
  else { s.leaderboard = []; s.hallOfFame = []; s.funding = { units: 0, target: 90, clockPct: 0 }; s.acquisitions = []; }
}
socket.on('state', (s) => {
  for (const id of s.compRemove || []) { const c = comps.get(id); if (c) { removedComps.push(c); comps.delete(id); } }
  for (const c of s.compAdd || []) comps.set(c.id, c);
  for (const sn of s.snakes) {
    const raw = unflat(sn.pts), out = [];
    for (let i = 0; i < raw.length; i++) { out.push(raw[i]); if (i >= 5 && i < raw.length - 1) out.push({ x: (raw[i].x + raw[i + 1].x) / 2, y: (raw[i].y + raw[i + 1].y) / 2 }); }
    sn.points = out; sn.trail = unflat(sn.trail || []);
  }
  mergeState(s); s.components = comps; state = s;
});
const removedComps = [];
socket.on('connect', () => { if (everJoined) socket.emit('respawn', joinPayload()); });
socket.on('disconnect', () => { alive = false; });
socket.on('ate', () => { ateOnce = true; sfx.eat(); headSquash = 1; ripple = 1; });
socket.on('vetted', () => { sfx.vetted(); const me = mine(); if (me) vetFlashes.push({ x: me.points[0].x, y: me.points[0].y, t0: performance.now() }); });
socket.on('setback', (d) => { flash(); shake(); sfx.setback(); toast(`<span class="th">${esc(d.label)}</span><span class="n">−${d.lost}</span><span class="q">“${esc(d.line)}”</span>`, 'setback'); spawnShards(d.lost, C.green300); });
socket.on('blocked', (d) => { sfx.block(); toast(`<span class="th">blocked: ${esc(d.threat || d.label)}</span><span class="q">Red-teamed before it reached the build.</span>`, 'block'); });
socket.on('capability', (d) => { sfx.adopt(d.key); show('funding'); hero(d.capability, d.does.split(' — ')[0].replace('You adopted ', 'You adopted ').toUpperCase(), d.does.split(' — ')[1] || '', d.color, `${d.name} · now part of Anaconda`); track('adopt_' + d.key); });
socket.on('building', (d) => { sfx.build(); buildAppear[d.key] = performance.now(); const me = mine(); if (me) for (let i = 0; i < 8; i++) dust.push({ x: me.home.x + (Math.random() - .5) * 60, y: me.home.y + (Math.random() - .5) * 60, vx: (Math.random() - .5) * 2, vy: -1 - Math.random(), t0: performance.now(), color: me.color }); toast(`${esc(d.name)} — ${esc(d.does)}`); });
socket.on('buildFail', (d) => toast(esc(d.why), 'warn'));
socket.on('retargeted', () => toast('Retargeted — your land came with you'));
socket.on('gotcha', () => sfx.gotcha());
socket.on('banner', ({ text, sub }) => { if (/ACQUIRES/.test(text)) { show('funding'); sfx.landmark(); const key = ACQ.find(a => text.includes(a.name.toUpperCase())); hero('Acquisition', text, sub, key ? key.color : C.green500, key ? `${key.capability}` : ''); } else if (/Trusted AI Foundation/.test(text)) { hero('Trusted AI Foundation', text, sub || 'All three capabilities adopted', C.green500, ''); if (text.startsWith(myName)) foundationAt = performance.now(); } else if (/Trillion-Token/.test(text)) { sfx.trillion(); hero('Trillion-Token Scale', text, 'Hall of Fame', C.green300, ''); } else hero('', text, sub, C.green500, ''); });
socket.on('feed', (f) => addFeed(f.text));
socket.on('landmark', ({ key }) => { landmarkAppear[key] = performance.now(); });
socket.on('shipment', (d) => { crates.push({ x: d.from.x, y: d.from.y, color: d.color, t0: performance.now(), tokens: d.tokens, ang: Math.atan2(d.from.y, d.from.x) }); if (d.id === myId) sfx.ship(d.order); });
socket.on('tokenBill', () => sfx.bong());
socket.on('died', (d) => {
  alive = false; sfx.death(); sfx.boost(false); music.duck(2500); slowmoUntil = performance.now() + 600; lastDeath = d; const me = mine(); if (me) spawnShards(Math.min(40, me.length), me.color);
  setTimeout(() => {
    const S = d.summary || {};
    $('death-title').textContent = d.copy ? d.copy.title : 'Shed'; $('death-line').textContent = (d.copy ? `“${d.copy.line}”` : '') + (d.killer ? ` — ${d.killer}` : '');
    $('d-projects').textContent = S.projects || 0; $('d-tokens').textContent = fmtT(S.tokens || 0); $('d-time').textContent = fmtTime(S.seconds || 0);
    $('d-caps').textContent = S.caps && S.caps.length ? 'adopted ' + S.caps.map(c => c.replace('AI ', '').replace(' & Guardrails', '')).join(' + ') : 'adopted nothing yet';
    const rank = state && state.leaderboard.findIndex(r => r.name === myName); $('d-rank').textContent = rank >= 0 ? `#${rank + 1} on the board · ` : '';
    const built = S.products || []; $('d-built').classList.toggle('hidden', !built.length); if (built.length) $('d-built').textContent = 'Built: ' + built.map(k => (PRODUCTS.find(p => p.key === k) || { name: k }).name).join(' · ');
    $('d-pitch').textContent = `“${S.pitch || ''}”`; el.name.value = savedName; el.name.placeholder = myName; renderSkins();
    el.death.classList.remove('hidden'); el.hud.classList.add('hidden'); el.hero.innerHTML = '';
    el.respawn.disabled = true; let left = Math.ceil((d.respawnMs || 2600) / 1000); el.respawn.textContent = `Play again (${left})`;
    const iv = setInterval(() => { left--; if (left <= 0) { clearInterval(iv); el.respawn.disabled = false; el.respawn.textContent = 'Play again'; } else el.respawn.textContent = `Play again (${left})`; }, 1000);
  }, 650);
});
function hero(kicker, h2, sub, color, blurb) { el.hero.innerHTML = ''; const d = document.createElement('div'); d.className = 'hero'; d.style.setProperty('--c', color); d.innerHTML = `<div class="k">${esc(kicker)}</div><h2>${esc(h2)}</h2><div class="s">${esc(sub || '')}</div>${blurb ? `<div class="b">${esc(blurb)}</div>` : ''}`; el.hero.appendChild(d); setTimeout(() => d.remove(), 7300); }
function toast(html, kind) { const t = document.createElement('div'); t.className = 'toast' + (kind ? ' ' + kind : ''); t.innerHTML = html; el.toasts.appendChild(t); while (el.toasts.children.length > 3) el.toasts.firstChild.remove(); setTimeout(() => t.remove(), 6100); }
function addFeed(text) { const d = document.createElement('div'); d.textContent = text; el.feed.prepend(d); while (el.feed.children.length > 5) el.feed.lastChild.remove(); setTimeout(() => d.remove(), 5300); }
function flash() { if (REDUCED) return; el.flash.className = 'on'; setTimeout(() => el.flash.className = 'off', 60); }
function shake() { if (REDUCED) return; canvas.classList.remove('shake'); void canvas.offsetWidth; canvas.classList.add('shake'); }
function spawnShards(n, color) { const me = mine(); if (!me) return; for (let i = 0; i < Math.min(n, 40); i++) { const p = me.points[Math.min(me.points.length - 1, i * 2)] || me.points[0]; const a = Math.random() * Math.PI * 2, v = 2 + Math.random() * 3; shards.push({ x: p.x, y: p.y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, t0: performance.now(), color }); } }
const mine = () => state && state.snakes.find(s => s.id === myId);

function renderShareCard(d) {
  const c = $('share-card'), g = c.getContext('2d'), S = (d && d.summary) || {};
  g.fillStyle = C.lilac900; g.fillRect(0, 0, 1200, 630); const gr = g.createRadialGradient(300, 150, 0, 300, 150, 800); gr.addColorStop(0, rgba(C.lilac500, .35)); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.fillRect(0, 0, 1200, 630);
  if (ready(ICONS.anaconda)) g.drawImage(ICONS.anaconda, 60, 56, 56, 56);
  g.fillStyle = '#fff'; g.font = `700 26px ${FONT.head}`; g.fillText('ANACONDA AI FACTORY', 132, 94);
  g.fillStyle = C.lilac400; g.font = `500 22px ${FONT.body}`; g.fillText(myName || 'builder', 60, 190);
  g.fillStyle = C.green300; g.font = `500 150px ${FONT.num}`; g.fillText(String(S.projects || 0), 56, 340);
  g.fillStyle = '#fff'; g.font = `600 40px ${FONT.head}`; g.fillText('AI projects in production', 60, 400);
  g.fillStyle = C.lilac400; g.font = `400 22px ${FONT.num}`; g.fillText(`Routed ${fmtT(S.tokens || 0)} tokens · ${fmtTime(S.seconds || 0)}`, 60, 450);
  g.fillStyle = rgba(C.lilac50, .8); g.font = `400 22px ${FONT.body}`; g.fillText((S.caps && S.caps.length) ? 'Adopted: ' + S.caps.join(' · ') : '88% of AI projects never reach production.', 60, 490);
  g.fillStyle = C.lilac400; g.font = `400 18px ${FONT.eyebrow}`; g.fillText('ANACONDA.COM/PLATFORM', 60, 570);
}

// ------------------------------- Input ----------------------------------------
const TURN = 0.12; let heading = 0; const keys = new Set();
addEventListener('keydown', (e) => { if (document.activeElement === el.name || document.activeElement === startName || !alive) return; if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Space'].includes(e.code)) e.preventDefault(); if (e.code === 'ArrowLeft') { heading -= TURN; keys.add('l'); } if (e.code === 'ArrowRight') { heading += TURN; keys.add('r'); } if (e.code === 'ArrowUp' || e.code === 'Space') { boosting = true; sfx.boost(true); } if (e.code === 'KeyR') socket.emit('retarget'); if (e.code === 'KeyB') socket.emit('build'); }, { passive: false });
addEventListener('keyup', (e) => { if (e.code === 'ArrowLeft') keys.delete('l'); if (e.code === 'ArrowRight') keys.delete('r'); if (e.code === 'ArrowUp' || e.code === 'Space') { boosting = false; sfx.boost(false); } });
addEventListener('touchstart', (e) => { const t = e.touches[0]; if (!t) return; heading += (t.clientX < innerWidth / 2 ? -1 : 1) * TURN * 3; boosting = true; }, { passive: true });
addEventListener('touchend', () => { boosting = false; });
setInterval(() => { if (!alive) return; if (keys.has('l')) heading -= TURN * .5; if (keys.has('r')) heading += TURN * .5; socket.emit('input', { angle: heading, boosting }); }, 50);

// ------------------------------- Drawing --------------------------------------
const W = (x) => (x - camera.x) * camera.zoom + canvas.width / 2, H = (y) => (y - camera.y) * camera.zoom + canvas.height / 2;
const onScreen = (x, y) => { const sx = W(x), sy = H(y); return sx > -80 && sx < canvas.width + 80 && sy > -80 && sy < canvas.height + 80; };
let t = 0; const gridPatterns = new Map();

function drawArena() {
  ctx.fillStyle = C.outside; ctx.fillRect(0, 0, canvas.width, canvas.height);
  const cx = W(0), cy = H(0), R = worldRadius * camera.zoom;
  const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R); g.addColorStop(0, C.groundHi); g.addColorStop(1, C.groundLo);
  ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
  // dot grid (world-space, 50px)
  ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.clip();
  const step = Math.max(8, Math.round(50 * camera.zoom)); let pat = gridPatterns.get(step);
  if (!pat) { const pc = document.createElement('canvas'); pc.width = pc.height = step; const g = pc.getContext('2d'); g.fillStyle = 'rgba(240,239,254,.09)'; g.fillRect(0, 0, 2, 2); pat = ctx.createPattern(pc, 'repeat'); gridPatterns.set(step, pat); }
  ctx.translate(W(0) % step, H(0) % step); ctx.fillStyle = pat; ctx.fillRect(-step, -step, canvas.width + step * 2, canvas.height + step * 2);
  ctx.restore();
}
function drawFloor(me) {
  const size = meta.gridDim * meta.cellSize * camera.zoom, x = W(-worldRadius), y = H(-worldRadius);
  ctx.save(); ctx.imageSmoothingEnabled = false;
  ctx.globalAlpha = .42; ctx.drawImage(fillC, x, y, size, size);
  if (me) { // own floor brighter: redraw own cells via composite (cheap approximation: tint by drawing edge canvas of own colour) — use a second pass at +8% only for own colour
    ctx.globalAlpha = .08; ctx.drawImage(fillC, x, y, size, size);
  }
  ctx.globalAlpha = performance.now() < edgeFlashUntil ? 1 : .95; ctx.drawImage(edgeC, x, y, size, size);
  if (performance.now() < edgeFlashUntil && !REDUCED) { ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = .7; ctx.drawImage(edgeC, x, y, size, size); }
  ctx.restore();
}
function drawBorderAndVignette() {
  const cx = W(0), cy = H(0), R = worldRadius * camera.zoom;
  ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.lineWidth = 26; ctx.strokeStyle = 'rgba(208,1,0,.14)'; ctx.stroke(); ctx.lineWidth = 6; ctx.strokeStyle = 'rgba(208,1,0,.55)'; ctx.stroke();
  const vr = Math.max(canvas.width, canvas.height), v = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, vr * .42, canvas.width / 2, canvas.height / 2, vr * .78); v.addColorStop(0, 'rgba(27,21,64,0)'); v.addColorStop(1, 'rgba(27,21,64,.72)'); ctx.fillStyle = v; ctx.fillRect(0, 0, canvas.width, canvas.height);
}
function drawPad(s) {
  if (!s.home || !onScreen(s.home.x, s.home.y)) return;
  const z = camera.zoom, size = 5 * meta.cellSize * z, x = W(s.home.x) - size / 2, y = H(s.home.y) - size / 2; // approx: pad centred on home
  ctx.save(); ctx.fillStyle = rgba(s.color, .65); ctx.fillRect(x, y, size, size); ctx.fillStyle = rgba(s.color, .3); ctx.fillRect(x + size * .2, y + size * .2, size * .6, size * .6);
  const glow = s.crown || s.products.includes('platform'); if (glow) { ctx.shadowColor = C.green500; ctx.shadowBlur = 22; ctx.strokeStyle = rgba(C.green500, .6 + .3 * Math.sin(t * 2)); ctx.lineWidth = 2; ctx.strokeRect(x, y, size, size); }
  ctx.restore();
  const cx = W(s.home.x), cy = H(s.home.y), platform = s.products.includes('platform');
  // The workshop: the Factory exists from second one. Dark body (Lilac 900), lit windows and sawtooth roof in the owner's colour.
  const ww = 64 * z, wh = 34 * z, wy = cy + 30 * z;
  ctx.save(); ctx.fillStyle = rgba(C.lilac900, .92); ctx.fillRect(cx - ww / 2, wy - wh, ww, wh);
  ctx.shadowColor = s.color; ctx.shadowBlur = 14; ctx.fillStyle = s.color;
  for (let k = 0; k < 3; k++) { const x0 = cx - ww / 2 + k * ww / 3; ctx.beginPath(); ctx.moveTo(x0, wy - wh); ctx.lineTo(x0 + ww / 3 * .7, wy - wh - 12 * z); ctx.lineTo(x0 + ww / 3, wy - wh); ctx.closePath(); ctx.fill(); }
  for (let i = 0; i < 3; i++) ctx.fillRect(cx - ww / 2 + (8 + i * 18) * z, wy - wh + 10 * z, 10 * z, 8 * z);
  ctx.fillRect(cx - 6 * z, wy - 12 * z, 12 * z, 12 * z);
  ctx.restore();
  if (ready(ICONS.anaconda)) { const r = (platform ? 40 : 24) * z; ctx.save(); ctx.translate(cx + ww / 2 + 16 * z, wy - wh - 2 * z); if (platform) ctx.rotate(t * .07); ctx.beginPath(); ctx.arc(0, 0, r * .62, 0, Math.PI * 2); ctx.fillStyle = C.lilac900; ctx.fill(); ctx.drawImage(ICONS.anaconda, -r / 2, -r / 2, r, r); ctx.restore(); }
  ctx.save(); ctx.textAlign = 'center'; ctx.font = `600 ${Math.max(10, 11 * z)}px ${FONT.head}`; ctx.fillStyle = 'rgba(240,239,254,.75)'; ctx.fillText(`${s.name} · AI FACTORY`, cx, wy + 16 * z); ctx.restore();
  drawBuildings(s, cx, cy - 10 * z, z);
}
let ctx2 = null;
function cutout(x, y, w, h) { const g = ctx2 || ctx; g.fillStyle = rgba(C.lilac900, .85); g.fillRect(x, y, w, h); }
function drawBuildings(s, cx, cy, z) {
  const list = s.products || []; if (!list.length) return;
  const slots = [[-72, 30], [72, 30], [-72, -30], [72, -30]]; // flanking the workshop; Platform is the pad itself
  list.forEach((k, i) => {
    if (k === 'platform') return; const p = PRODUCTS.find(pp => pp.key === k) || { color: C.green300, name: k };
    const rise = buildAppear[k] ? Math.min(1, (performance.now() - buildAppear[k]) / 600) : 1, ease = 1 - Math.pow(1 - rise, 3);
    const [ox, oy] = slots[i] || [0, 0], bx = cx + ox * z, by = cy + oy * z;
    ctx.save(); ctx.shadowColor = p.color; ctx.shadowBlur = 14; ctx.fillStyle = p.color;
    if (k === 'cli') { const w = 16 * z, h = 36 * z * ease; ctx.fillRect(bx - w / 2, by - h, w, h); if (Math.floor(t * 2) % 2) cutout(bx - 4 * z, by - h + 8 * z, 8 * z, 3 * z); chip(bx, by - h - 10 * z, 'GA', z); }
    else if (k === 'pkgintel') { const w = 44 * z, h = 18 * z * ease; ctx.fillRect(bx - w / 2, by - h, w, h); for (let i = 0; i < 3; i++) cutout(bx - w / 2 + 6 * z, by - h + (4 + i * 5) * z, w - 12 * z, 1.5 * z); chip(bx, by - h - 10 * z, 'OPEN BETA', z); }
    else if (k === 'mcp') { const w = 12 * z, h = 44 * z * ease; ctx.fillRect(bx - w / 2, by - h, w, h); ctx.beginPath(); ctx.arc(bx, by - h, 8 * z, 0, Math.PI * 2); ctx.lineWidth = 2.5 * z; ctx.strokeStyle = p.color; ctx.stroke(); chip(bx, by - h - 18 * z, 'GA', z); }
    else if (k === 'desktop') { const w = 52 * z, h = 34 * z * ease; ctx.fillRect(bx - w / 2, by - h, w, h); cutout(bx - w / 2 + 6 * z, by - h + 5 * z, w - 12 * z, h - 12 * z); ctx.fillStyle = C.green300; ctx.beginPath(); ctx.arc(bx - 8 * z, by - h / 2, 2.5 * z, 0, Math.PI * 2); ctx.arc(bx - 2 * z, by - h / 2 + 2 * z, 2.5 * z, 0, Math.PI * 2); ctx.arc(bx + 4 * z, by - h / 2, 2.5 * z, 0, Math.PI * 2); ctx.fill(); chip(bx, by - h - 10 * z, 'BETA', z); }
    ctx.restore();
  });
}
function chip(x, y, text, z) { ctx.save(); ctx.shadowBlur = 0; ctx.font = `400 ${9 * z}px ${FONT.num}`; const w = ctx.measureText(text).width + 12 * z; ctx.fillStyle = 'rgba(12,12,12,.4)'; ctx.fillRect(x - w / 2, y - 7 * z, w, 14 * z); ctx.strokeStyle = 'rgba(240,239,254,.14)'; ctx.lineWidth = 1; ctx.strokeRect(x - w / 2, y - 7 * z, w, 14 * z); ctx.fillStyle = C.lilac50; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, x, y); ctx.restore(); }

const GLYPH = ['cloud', 'sparkle', 'cylinder', 'bracket', 'chip'];
function glyph(kind, x, y, s) { const ctx = ctx2 || window.__ctx; ctx.save(); ctx.translate(x, y); ctx.globalAlpha = .55; ctx.strokeStyle = C.lilac900; ctx.fillStyle = C.lilac900; ctx.lineWidth = 1.2; if (kind === 'cloud') { ctx.beginPath(); ctx.arc(-s * .3, 0, s * .35, 0, Math.PI * 2); ctx.arc(s * .2, -s * .15, s * .4, 0, Math.PI * 2); ctx.arc(s * .35, s * .2, s * .3, 0, Math.PI * 2); ctx.fill(); } else if (kind === 'sparkle') { ctx.beginPath(); ctx.moveTo(0, -s); ctx.lineTo(s * .25, -s * .25); ctx.lineTo(s, 0); ctx.lineTo(s * .25, s * .25); ctx.lineTo(0, s); ctx.lineTo(-s * .25, s * .25); ctx.lineTo(-s, 0); ctx.lineTo(-s * .25, -s * .25); ctx.fill(); } else if (kind === 'cylinder') { ctx.fillRect(-s * .6, -s * .5, s * 1.2, s); ctx.beginPath(); ctx.ellipse(0, -s * .5, s * .6, s * .25, 0, 0, Math.PI * 2); ctx.fill(); } else if (kind === 'bracket') { ctx.beginPath(); ctx.moveTo(-s * .2, -s); ctx.lineTo(-s * .7, -s); ctx.lineTo(-s * .7, s); ctx.lineTo(-s * .2, s); ctx.moveTo(s * .2, -s); ctx.lineTo(s * .7, -s); ctx.lineTo(s * .7, s); ctx.lineTo(s * .2, s); ctx.stroke(); } else { ctx.fillRect(-s * .6, -s * .6, s * 1.2, s * 1.2); for (let i = -1; i <= 1; i++) { ctx.fillRect(-s - .5, i * s * .45 - .6, s * .4, 1.2); ctx.fillRect(s * .6, i * s * .45 - .6, s * .4, 1.2); } } ctx.restore(); }
function compStyle(c) { return c.t === 'package' ? { col: C.green300, s: 20 } : c.t === 'dataset' ? { col: C.green200, s: 22 } : c.t === 'model' ? { col: C.lilac400, s: 28 } : { col: C.lilac50, s: 23 }; }
function drawCompShape(c, s) {
  const g = ctx2 || ctx;
  if (c.t === 'package') { g.save(); g.rotate(Math.PI / 4); g.fillRect(-s / 2, -s / 2, s, s); g.restore(); }
  else if (c.t === 'dataset') { const w = s * .76, h = s; g.fillRect(-w / 2, -h / 2, w, h); for (let i = -1; i <= 1; i++) cutout(-w / 2 + w * .15, i * h * .25 - .75, w * .7, 1.5); }
  else if (c.t === 'model') { g.beginPath(); for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3 + Math.PI / 6; g.lineTo(Math.cos(a) * s / 2, Math.sin(a) * s / 2); } g.closePath(); g.fill(); }
  else { const R = Math.max(0.1, s / 2), r = Math.max(0, R - 4.6 * .55); g.beginPath(); g.arc(0, 0, R, 0, Math.PI * 2); g.arc(0, 0, r, 0, Math.PI * 2, true); g.fill('evenodd'); g.beginPath(); g.arc(0, 0, Math.min(2.3, R), 0, Math.PI * 2); g.fill(); }
}
function poisonVisible(c, me) { if (!c.p || !me) return false; if (me.caps.includes('enkrypt')) return true; const g = meta.gridDim, col = Math.floor((c.x + worldRadius) / meta.cellSize), row = Math.floor((c.y + worldRadius) / meta.cellSize); return cellColors[row * g + col] === me.color; }
const spriteCache = new Map();
function compSprite(c, poison, zb) {
  const seed = parseInt(c.id.slice(1), 10) || 0, key = `${c.t}|${poison ? 1 : 0}|${c.k ? 1 : 0}|${seed % 5}|${zb}`;
  let sp = spriteCache.get(key); if (sp) return sp;
  const z = zb / 10, st = compStyle(c), s = st.s * z, pad = 24, size = Math.ceil(s + pad * 2);
  const oc = document.createElement('canvas'); oc.width = oc.height = size; const o = oc.getContext('2d'); o.translate(size / 2, size / 2);
  const saved = ctx; // reuse shape helpers by temporarily pointing them at the offscreen ctx
  ctxRef.c = o;
  if (poison) { o.strokeStyle = C.red; o.lineWidth = 2.2; o.shadowColor = C.red; o.shadowBlur = 18; if (c.t === 'package') { o.rotate(Math.PI / 4); o.strokeRect(-s / 2, -s / 2, s, s); } else if (c.t === 'dataset') o.strokeRect(-s * .38, -s / 2, s * .76, s); else if (c.t === 'model') { o.beginPath(); for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3 + Math.PI / 6; o.lineTo(Math.cos(a) * s / 2, Math.sin(a) * s / 2); } o.closePath(); o.stroke(); } else { o.beginPath(); o.arc(0, 0, s / 2, 0, Math.PI * 2); o.stroke(); } }
  else { o.fillStyle = st.col; o.shadowColor = c.k ? C.green500 : st.col; o.shadowBlur = 12; drawCompShapeOn(o, c, s); o.shadowBlur = 0; glyphOn(o, GLYPH[seed % 5], s * .32, -s * .32, 3 * z); }
  ctxRef.c = saved;
  sp = { canvas: oc, half: size / 2 }; spriteCache.set(key, sp); return sp;
}
const ctxRef = { c: null };
function drawCompShapeOn(o, c, s) { const keep = ctx2; ctx2 = o; drawCompShape(c, s); ctx2 = keep; }
function glyphOn(o, kind, x, y, s) { const keep = ctx2; ctx2 = o; glyph(kind, x, y, s); ctx2 = keep; }
function drawComponent(c, me) {
  if (!onScreen(c.x, c.y)) return;
  const zb = Math.max(5, Math.min(11, Math.round(camera.zoom * 10))), z = zb / 10;
  const seed = parseInt(c.id.slice(1), 10) || 0, bob = REDUCED ? 0 : Math.sin(t * 4.4 + seed) * 2 * z;
  const sp = compSprite(c, poisonVisible(c, me), zb);
  ctx.drawImage(sp.canvas, W(c.x) - sp.half, H(c.y) + bob - sp.half);
}
function drawComponentLegacy(c, me) {
  if (!onScreen(c.x, c.y)) return; const z = camera.zoom, st = compStyle(c), s = st.s * z;
  const seed = parseInt(c.id.slice(1), 10) || 0, bob = REDUCED ? 0 : Math.sin(t * 2.2 * 2 + seed) * 2 * z;
  ctx.save(); ctx.translate(W(c.x), H(c.y) + bob);
  if (poisonVisible(c, me)) { ctx.strokeStyle = C.red; ctx.lineWidth = 2.2; ctx.shadowColor = C.red; ctx.shadowBlur = 18 * (.7 + .3 * Math.sin(t * 4.2 + seed)); ctx.fillStyle = 'rgba(0,0,0,0)'; if (c.t === 'package') { ctx.rotate(Math.PI / 4); ctx.strokeRect(-s / 2, -s / 2, s, s); } else if (c.t === 'dataset') ctx.strokeRect(-s * .38, -s / 2, s * .76, s); else if (c.t === 'model') { ctx.beginPath(); for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3 + Math.PI / 6; ctx.lineTo(Math.cos(a) * s / 2, Math.sin(a) * s / 2); } ctx.closePath(); ctx.stroke(); } else { ctx.beginPath(); ctx.arc(0, 0, s / 2, 0, Math.PI * 2); ctx.stroke(); } ctx.restore(); return; }
  ctx.fillStyle = st.col; ctx.shadowColor = c.k ? C.green500 : st.col; ctx.shadowBlur = 12; drawCompShape(c, s); ctx.shadowBlur = 0;
  glyph(GLYPH[seed % 5], s * .32, -s * .32, 3 * z); ctx.restore();
}
function drawSnake(s, isMe) {
  const pts = s.points; if (!pts || !pts.length) return; const z = camera.zoom;
  const width = (15 + (30 - 15) * Math.min(1, s.length / 420)) * z, r = width / 2, dark = shade(s.color, -.28), light = shade(s.color, .18);
  if (s.trail && s.trail.length) { ctx.save(); ctx.beginPath(); ctx.moveTo(W(s.trail[0].x), H(s.trail[0].y)); for (let i = 1; i < s.trail.length; i++) ctx.lineTo(W(s.trail[i].x), H(s.trail[i].y)); ctx.lineTo(W(pts[0].x), H(pts[0].y)); ctx.lineWidth = width * 2.6; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = rgba(s.color, .22); ctx.stroke(); ctx.restore(); }
  const boost = isMe ? boosting : false;
  ctx.save(); if (boost) { ctx.shadowColor = s.color; ctx.shadowBlur = 22; }
  const stride = boost ? 1 : 1;
  for (let i = pts.length - 1; i >= 1; i -= stride) { const p = pts[i], x = W(p.x), y = H(p.y); ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fillStyle = i % 2 ? dark : s.color; ctx.fill(); if (i % 4 === 0) { ctx.beginPath(); ctx.arc(x - r * .25, y - r * .3, r * .3, 0, Math.PI * 2); ctx.fillStyle = light; ctx.fill(); } }
  if (s.crown) { ctx.beginPath(); ctx.moveTo(W(pts[0].x), H(pts[0].y)); for (let i = 1; i < pts.length; i++) ctx.lineTo(W(pts[i].x), H(pts[i].y)); ctx.lineWidth = width + 5; ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.globalCompositeOperation = 'destination-over'; ctx.stroke(); ctx.globalCompositeOperation = 'source-over'; }
  ctx.restore();
  if (isMe && ripple > 0 && !REDUCED) { const i = Math.min(pts.length - 1, Math.floor((1 - ripple) * pts.length)); ctx.save(); ctx.globalAlpha = ripple * .6; ctx.beginPath(); ctx.arc(W(pts[i].x), H(pts[i].y), r * 1.25, 0, Math.PI * 2); ctx.fillStyle = light; ctx.fill(); ctx.restore(); }
  // head
  const hx = W(pts[0].x), hy = H(pts[0].y), ang = pts.length > 1 ? Math.atan2(pts[0].y - pts[1].y, pts[0].x - pts[1].x) : 0, hr = r * 1.45;
  ctx.save(); if (boost) { ctx.shadowColor = s.color; ctx.shadowBlur = 22; }
  ctx.translate(hx, hy); ctx.rotate(ang); const sq = isMe ? 1 - headSquash * .08 : 1; ctx.scale(sq, 2 - sq);
  ctx.beginPath(); ctx.arc(0, 0, hr, 0, Math.PI * 2); ctx.fillStyle = light; ctx.fill();
  ctx.beginPath(); ctx.arc(hr * .35, 0, hr * .7, 0, Math.PI * 2); ctx.fillStyle = s.color; ctx.fill();
  for (const side of [-1, 1]) { ctx.beginPath(); ctx.arc(hr * .35, side * hr * .5, hr * .28, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.beginPath(); ctx.arc(hr * .45, side * hr * .5, hr * .14, 0, Math.PI * 2); ctx.fillStyle = C.lilac900; ctx.fill(); }
  ctx.restore();
  if (boost) { ctx.save(); ctx.strokeStyle = rgba(s.color, .5); ctx.lineWidth = 2; for (const side of [-1, 1]) { const px = hx - Math.cos(ang) * hr * 2 + Math.cos(ang + Math.PI / 2) * side * hr * .9, py = hy - Math.sin(ang) * hr * 2 + Math.sin(ang + Math.PI / 2) * side * hr * .9; ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px - Math.cos(ang) * 26 * z, py - Math.sin(ang) * 26 * z); ctx.stroke(); } ctx.restore(); }
  if (s.shield) { ctx.save(); ctx.beginPath(); ctx.arc(hx, hy, hr * 1.9, 0, Math.PI * 2); ctx.setLineDash([6, 6]); ctx.lineWidth = 2; ctx.strokeStyle = rgba(C.lilac50, .6); ctx.stroke(); ctx.restore(); }
  for (const o of s.orbs || []) { ctx.save(); ctx.shadowColor = C.yellow; ctx.shadowBlur = 12; ctx.fillStyle = C.yellow; ctx.beginPath(); ctx.arc(W(o.x), H(o.y), 6 * z, 0, Math.PI * 2); ctx.fill(); ctx.restore(); }
  // name + pips
  ctx.save(); ctx.textAlign = 'center'; ctx.font = isMe ? `600 13px ${FONT.body}` : `500 12px ${FONT.body}`; ctx.fillStyle = isMe ? '#fff' : 'rgba(240,239,254,.7)'; ctx.fillText(s.name, hx, hy + hr + 18);
  const caps = (s.caps || []).map(k => (ACQ.find(a => a.key === k) || {}).color).filter(Boolean); caps.forEach((c, i) => { ctx.save(); ctx.translate(hx - (caps.length - 1) * 6 + i * 12, hy - hr - 14); ctx.rotate(Math.PI / 4); ctx.fillStyle = c; ctx.fillRect(-3.5, -3.5, 7, 7); ctx.restore(); }); ctx.restore();
}
function drawLandmarks() {
  for (const a of state.acquisitions) {
    if (!a.funded || !onScreen(a.site.x, a.site.y)) continue;
    const x = W(a.site.x), y = H(a.site.y), z = camera.zoom, held = !!a.holder;
    const ap = landmarkAppear[a.key] ? Math.min(1, (performance.now() - landmarkAppear[a.key]) / 700) : 1, rise = 1 - Math.pow(1 - ap, 3);
    ctx.save(); ctx.globalAlpha = rise;
    const hr = 70 * z + (held || REDUCED ? 0 : Math.sin(t * 2 * 2) * 6 * z); ctx.beginPath(); ctx.arc(x, y, hr, 0, Math.PI * 2); ctx.lineWidth = held ? 1 : 3; ctx.strokeStyle = held ? a.holderColor : rgba(a.color, .22); ctx.stroke();
    ctx.shadowColor = a.color; ctx.shadowBlur = 22; ctx.fillStyle = a.color;
    const blocks = [[60, 30], [40, 20], [18, 16]]; let top = y + 20 * z;
    blocks.forEach(([w, h], i) => { const bw = w * z, bh = h * z * rise; ctx.fillRect(x - bw / 2, top - bh, bw, bh); if (i < 2) for (let k = -1; k <= 1; k += 2) cutout(x + k * bw * .25 - 4 * z, top - bh / 2 - 4 * z, 8 * z, 8 * z); top -= bh; });
    const icon = ICONS[a.key]; if (ready(icon)) { ctx.shadowBlur = 0; const sc = (16 * z) / Math.max(icon.naturalWidth, icon.naturalHeight); ctx.drawImage(icon, x - icon.naturalWidth * sc / 2, top + 8 * z * rise - icon.naturalHeight * sc / 2 - 8 * z * rise + 8 * z, icon.naturalWidth * sc, icon.naturalHeight * sc); }
    ctx.shadowBlur = 0; ctx.textAlign = 'center'; ctx.font = `600 15px ${FONT.head}`; ctx.fillStyle = a.color; ctx.fillText(a.name.toUpperCase(), x, top - 12 * z);
    ctx.font = `500 11px ${FONT.body}`; ctx.fillStyle = held ? a.holderColor : 'rgba(240,239,254,.7)'; ctx.fillText(held ? `held by ${a.holder}` : 'now part of Anaconda · run your trail through it', x, y + 40 * z);
    ctx.restore();
  }
}
function drawFx() {
  const now = performance.now();
  for (let i = pops.length - 1; i >= 0; i--) { const p = pops[i], k = (now - p.t0) / 120; if (k >= 1) { pops.splice(i, 1); continue; } const sc = k < .5 ? 1 + k * 1.2 : 1.6 * (1 - (k - .5) * 2); ctx.save(); ctx.translate(W(p.x), H(p.y)); ctx.globalAlpha = 1 - k; ctx.fillStyle = p.col; drawCompShape(p, p.s * camera.zoom * sc); ctx.restore(); }
  for (let i = vetFlashes.length - 1; i >= 0; i--) { const v = vetFlashes[i], k = (now - v.t0) / 200; if (k >= 1) { vetFlashes.splice(i, 1); continue; } ctx.save(); ctx.globalAlpha = 1 - k; ctx.beginPath(); ctx.arc(W(v.x), H(v.y), (14 + k * 16) * camera.zoom, 0, Math.PI * 2); ctx.lineWidth = 2; ctx.strokeStyle = C.green500; ctx.stroke(); ctx.font = `400 9px ${FONT.eyebrow}`; ctx.fillStyle = C.green300; ctx.textAlign = 'center'; ctx.fillText('vetted', W(v.x), H(v.y) - (20 + k * 10) * camera.zoom); ctx.restore(); }
  for (let i = shards.length - 1; i >= 0; i--) { const s = shards[i], k = (now - s.t0) / 300; if (k >= 1) { shards.splice(i, 1); continue; } const e = 1 - Math.pow(1 - k, 3); s.x += s.vx * (1 - e); s.y += s.vy * (1 - e); ctx.save(); ctx.globalAlpha = 1 - k; ctx.translate(W(s.x), H(s.y)); ctx.rotate(Math.PI / 4); ctx.fillStyle = s.color; ctx.fillRect(-5 * camera.zoom, -5 * camera.zoom, 10 * camera.zoom, 10 * camera.zoom); ctx.restore(); }
  for (let i = dust.length - 1; i >= 0; i--) { const d = dust[i], k = (now - d.t0) / 400; if (k >= 1) { dust.splice(i, 1); continue; } d.x += d.vx; d.y += d.vy; ctx.save(); ctx.globalAlpha = (1 - k) * .7; ctx.fillStyle = d.color; ctx.beginPath(); ctx.arc(W(d.x), H(d.y), 3 * camera.zoom, 0, Math.PI * 2); ctx.fill(); ctx.restore(); }
  for (let i = crates.length - 1; i >= 0; i--) { const c = crates[i], k = (now - c.t0) / 1500; if (k >= 1) { crates.splice(i, 1); continue; } const dist = 300 * k, x = W(c.x + Math.cos(c.ang) * dist), y = H(c.y + Math.sin(c.ang) * dist); ctx.save(); ctx.globalAlpha = 1 - k; ctx.fillStyle = c.color; ctx.fillRect(x - 5 * camera.zoom, y - 4 * camera.zoom, 10 * camera.zoom, 8 * camera.zoom); for (let d = 1; d <= 3; d++) { ctx.globalAlpha = (1 - k) * (.6 - d * .15); ctx.beginPath(); ctx.arc(x - Math.cos(c.ang) * d * 8 * camera.zoom, y - Math.sin(c.ang) * d * 8 * camera.zoom, 1.5, 0, Math.PI * 2); ctx.fill(); } if (k < .5) { ctx.globalAlpha = 1 - k * 2; ctx.font = `400 11px ${FONT.num}`; ctx.fillStyle = C.green300; ctx.textAlign = 'center'; ctx.fillText(`+${Math.round(c.tokens)}B`, x, y - (14 + k * 30)); } ctx.restore(); }
}

// ------------------------------- HUD ------------------------------------------
let chipSig = '', bumpFloor = 0, lastHudDom = 0;
function updateHud(me) {
  const doDom = performance.now() - lastHudDom > 250; if (doDom) lastHudDom = performance.now();
  if (me) {
    el.projects.textContent = me.projects; el.length.textContent = me.length;
    if (me.floor !== +el.floor.textContent) { el.floor.textContent = me.floor; el.floor.classList.remove('bump'); void el.floor.offsetWidth; el.floor.classList.add('bump'); }
    if (me.floor > lastFloor + 4 && lastFloor > 0) { sfx.claim(me.floor - lastFloor > 60); edgeFlashUntil = performance.now() + 150; captured = true; show('floor'); show('funding'); }
    lastFloor = me.floor; if (!me.inTerritory) leftFloor = true;
    const age = Date.now() - spawnAt;
    el.hint.textContent = captured || age > 14000 ? '' : !ateOnce ? 'eat to grow' : leftFloor ? 'get home to close the loop' : 'leave your floor and come back to claim it';
    const canBuild = me.crown && me.nextFootprint && me.floor >= me.nextFootprint; el.buildHint.classList.toggle('hidden', !canBuild); if (canBuild) el.buildHint.textContent = `B · build ${me.nextProduct}`;
  }
  const f = state.funding; el.fundLabel.textContent = f.dealName ? `NEXT · ${f.dealName.toUpperCase()}` : 'ALL CAPABILITIES LANDED'; el.fundPct.textContent = f.dealName ? Math.round(Math.max(f.units / f.target, f.clockPct) * 100) + '%' : '';
  const next = ACQ.find(a => a.key === f.deal); el.fundFill.style.background = next ? next.color : C.green500; el.fundFill.style.width = f.dealName ? Math.min(100, Math.max(f.units / f.target, f.clockPct) * 100) + '%' : '100%';
  const sig = state.acquisitions.map(a => `${a.key}:${me && me.caps.includes(a.key) ? 1 : 0}`).join('|');
  if (sig !== chipSig) { chipSig = sig; el.chips.innerHTML = state.acquisitions.map(a => `<div class="acq ${me && me.caps.includes(a.key) ? 'held' : ''}" style="--c:${a.color}"><span class="n"><i></i>${esc(a.capability)}</span><span class="b">${esc(a.name)}</span></div>`).join(''); }
  if (!doDom) return;
  el.lbList.innerHTML = state.leaderboard.map(r => `<li class="${r.name === myName ? 'me' : ''}"><i style="background:${state.snakes.find(s => s.name === r.name)?.color || C.lilac400}"></i>${esc(r.name)}${r.crown ? ' <span class="pips">◆◆◆</span>' : ''}<span class="v">${r.projects}</span></li>`).join('');
  el.hof.classList.toggle('hidden', !state.hallOfFame.length); el.hofList.innerHTML = state.hallOfFame.map(h => `<li>${esc(h.name)}</li>`).join('');
}
let lastMini = 0;
function drawMinimap() {
  if (!minimap.clientWidth || !minimap.classList.contains('shown')) return; if (performance.now() - lastMini < 100) return; lastMini = performance.now();
  const w = minimap.width = minimap.clientWidth * devicePixelRatio, h = minimap.height = minimap.clientHeight * devicePixelRatio; mctx.clearRect(0, 0, w, h); mctx.save(); mctx.translate(w / 2, h / 2); const sc = (Math.min(w, h) / 2 - 4) / worldRadius;
  mctx.save(); mctx.beginPath(); mctx.arc(0, 0, worldRadius * sc, 0, Math.PI * 2); mctx.clip(); mctx.globalAlpha = .5; mctx.imageSmoothingEnabled = false; mctx.drawImage(fillC, -worldRadius * sc, -worldRadius * sc, worldRadius * 2 * sc, worldRadius * 2 * sc); mctx.restore();
  mctx.beginPath(); mctx.arc(0, 0, worldRadius * sc, 0, Math.PI * 2); mctx.lineWidth = 3; mctx.strokeStyle = rgba(C.red, .45); mctx.stroke();
  for (const a of state.acquisitions) { if (!a.funded) continue; const p = a.holder || REDUCED ? 0 : (Math.sin(t * 4) + 1) / 2; mctx.fillStyle = a.color; const s = 8 + p * 3; mctx.fillRect(a.site.x * sc - s / 2, a.site.y * sc - s / 2, s, s); }
  for (const s of state.snakes) { if (!s.alive) continue; const me = s.id === myId; mctx.beginPath(); mctx.arc(s.points[0].x * sc, s.points[0].y * sc, (me ? 3.4 : 2.2) * devicePixelRatio, 0, Math.PI * 2); mctx.fillStyle = me ? '#fff' : s.color; mctx.fill(); }
  mctx.restore();
}

// ------------------------------- Loop -----------------------------------------
let lastFrame = performance.now();
function render(now) {
  try { renderFrame(now); } catch (e) { if (!render.logged) { render.logged = true; console.error('frame error', e); socket.emit('analytics', { event: 'client_error' }); } }
  requestAnimationFrame(render);
}
function renderFrame(now) {
  const dt = Math.min(.05, (now - lastFrame) / 1000) * (now < slowmoUntil ? .4 : 1); lastFrame = now; t += dt;
  headSquash = Math.max(0, headSquash - dt * 8); ripple = Math.max(0, ripple - dt * 5);
  if (state) {
    const me = mine();
    if (me && me.alive) { camera.x += (me.points[0].x - camera.x) * .16; camera.y += (me.points[0].y - camera.y) * .16; const tz = (1.05 - (1.05 - .62) * Math.min(1, me.length / 420)) * (boosting ? .95 : 1); camera.zoom += (tz - camera.zoom) * .04; }
    for (const c of removedComps) if (me && Math.hypot(c.x - me.points[0].x, c.y - me.points[0].y) < 90) { const st = compStyle(c); pops.push({ x: c.x, y: c.y, t: c.t, col: st.col, s: st.s, t0: now }); }
    removedComps.length = 0;
    drawArena(); drawFloor(me); for (const s of state.snakes) if (s.alive) drawPad(s); drawLandmarks();
    for (const c of comps.values()) drawComponent(c, me);
    for (const s of state.snakes) if (s.alive) drawSnake(s, s.id === myId);
    drawFx(); drawBorderAndVignette(); updateHud(me); drawMinimap();
  } else drawArena();
}
requestAnimationFrame(render);
