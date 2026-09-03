'use strict';
/**
 * ANACONDA AI FACTORY (Anacondae) — authoritative game server
 *
 * Loop: eat components to grow → loop home to claim floor → fund + integrate the
 * three acquisitions → your floor builds and ships the September products →
 * route a trillion tokens.
 */
const express = require('express');
const http = require('http');
const path = require('path');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' }, perMessageDeflate: { threshold: 512 } });
app.use(express.static(path.join(__dirname, 'public')));
const analytics = { sessions: 0, deaths: 0, runSeconds: [] };
app.get('/__analytics', (req, res) => {
  const runs = analytics.runSeconds.slice().sort((a, b) => a - b);
  res.json({ ...analytics, runSeconds: undefined, runs: runs.length, medianRunSeconds: runs.length ? runs[Math.floor(runs.length / 2)] : 0 });
});

// ------------------------------- Numbers (§10) --------------------------------
const WORLD_RADIUS = 2400;
const CELL_SIZE = 50;
const TICK_RATE = 20;
const TICK_MS = 1000 / TICK_RATE;
const BASE_SPEED = 190 / TICK_RATE;   // units per tick
const BOOST_SPEED = 330 / TICK_RATE;
const BASE_LENGTH = 26;               // segments
const MAX_LENGTH = 420;
const SEGMENT_SPACING = 8;            // world units per segment
const BOOST_DRAIN = 0.09;             // segments per tick while boosting outside land
const TURN_RATE = 0.12;
const COMPONENT_TARGET = 420;
const POISON_RATE = 0.12;
const SETBACK_FRACTION = 0.25;
const SETBACK_MIN = 5;
const SPAWN_GRACE_TICKS = TICK_RATE * 3;
const SPAWN_POISON_CLEAR = 260;
const SPAWN_SAFE_DIST = 260;
const RESPAWN_MS = 2600;
const HOME_PLOT = 5;                  // 5x5 cells
const FUNDING_TARGET = 90;
const FUNDING_BOOST_RATE = 0.2;       // units per token burned
const CURATED_SPAWN_TICKS = TICK_RATE * 3;
const SHIP_TICKS = TICK_RATE * 5;
const TOKEN_BILL_TICKS = TICK_RATE * 120;
const TRILLION = 1000;                // tokens routed are tracked in billions; 1T = 1000B
const BOT_TARGET_COUNT = 6;
const PROJECT_COMPONENTS = 10;   // components processed per shipped project (before building speedups)
const PROJECT_TOKENS = 25;       // B tokens routed per project

const GRID_DIM = Math.round((WORLD_RADIUS * 2) / CELL_SIZE);
const CELL_COUNT = GRID_DIM * GRID_DIM;

const COLORS = ['#08CA4A', '#9CF215', '#C1FF60', '#068C35', '#6D5BF6', '#8A7CF8', '#F0EFFE']; // B10 skins; yellow is reserved as the accent

// ------------------------------- Content --------------------------------------
const COMPONENT_TYPES = {
  package: { grow: 1, weight: 0.55 },
  dataset: { grow: 1, weight: 0.17 },
  model:   { grow: 2, weight: 0.10 },
  mcp:     { grow: 1, weight: 0.18 },
};
const THREATS = {
  package: [
    ['Typosquat', 'typosquatted package · requets, not requests'],
    ['Known CVE', 'known CVE in urllib3 1.26.4 · CVSS 9.1'],
    ['Malicious install script', 'malicious setup.py · ran on install'],
    ['Dependency confusion', 'dependency confusion · public package shadowed your internal one'],
    ['Leaked secret', 'hard-coded credential shipped in the package'],
    ['Hijacked maintainer', 'maintainer account hijacked · new release is malware'],
  ],
  model: [
    ['Unsafe serialization', 'pickle payload in model weights · executed on load'],
    ['Backdoored weights', 'trojaned model · hidden trigger phrase'],
    ['Wrong provenance', 'no provenance · weights don’t match the model card'],
    ['Licence trap', 'restricted licence · not cleared for commercial use'],
  ],
  dataset: [
    ['Prompt injection', 'prompt injection in training rows'],
    ['Data poisoning', 'poisoned labels · 3% flipped'],
    ['PII leak', 'unredacted PII in the dataset'],
    ['Schema drift', 'schema drift · pipeline silently broke'],
  ],
  mcp: [
    ['Rogue server', 'rogue MCP server · exfiltrating context'],
    ['Tool poisoning', 'tool description carries hidden instructions'],
    ['Over-permissioned', 'MCP granted write access it never needed'],
    ['Unsafe tool call', 'agent called a destructive tool · guardrail absent'],
  ],
};
const pickThreat = (type) => { const l = THREATS[type]; return l[Math.floor(Math.random() * l.length)]; };

// Acquisitions in funding order.
const ACQUISITIONS = [
  { key: 'outerbounds', name: 'Outerbounds', color: '#08CA4A', capability: 'AI Orchestration',         does: 'You adopted AI Orchestration — run your factory wherever you need it, and take your governance with you. R retargets once per life; loops now close on any of your land.' },
  { key: 'kilo',        name: 'Kilo',        color: '#FFBA06', capability: 'AI Workspaces',            does: 'You adopted AI Workspaces — components arrive pre-configured, boost costs half, your agents collect for you.' },
  { key: 'enkrypt',     name: 'Enkrypt AI',  color: '#6D5BF6', capability: 'AI Security & Guardrails', does: 'You adopted AI Security & Guardrails — the whole ecosystem is red-teamed for you now.' },
];
const CAPABILITY_CLOCK_MS = 110000; // clock fallback: a deal lands at min(bar full, 100s since last)
const EMBARGO = process.env.EMBARGO === '1'; // pre-launch builds show only Anaconda CLI
const GUEST = () => 'builder-' + Math.floor(1000 + Math.random() * 9000);
const BOT_NAMES = ['priya_ml', 'data_team_3', 'ops-nightly', 'copilot-fork', 'sre-batch', 'jules.dev', 'mlops_sam', 'quant-anna', 'infra_kai', 'platform-eng'];
// Landmark sites: 120° apart at 55% radius.
const SITE_ANGLES = [-Math.PI / 2, Math.PI / 6, (5 * Math.PI) / 6];
ACQUISITIONS.forEach((a, i) => {
  a.site = { x: Math.cos(SITE_ANGLES[i]) * WORLD_RADIUS * 0.55, y: Math.sin(SITE_ANGLES[i]) * WORLD_RADIUS * 0.55 };
  a.funded = false;
  a.firstIntegrator = null;
});

// September products, built automatically on floor (§5).
const ALL_PRODUCTS = [
  { key: 'cli',      name: 'Anaconda CLI',               footprint: 40,  color: '#08CA4A', does: 'you move and close loops faster now' },
  { key: 'pkgintel', name: 'Package Intelligence APIs',  footprint: 70,  color: '#5EE08A', does: 'poisoned components entering your floor are neutralized' },
  { key: 'mcp',      name: 'Anaconda MCP',               footprint: 110, color: '#068F35', does: 'boost costs less and your reach is wider' },
  { key: 'desktop',  name: 'Kilo Desktop',               footprint: 170, color: '#F8F674', does: 'four agents now, and what they collect counts double' },
  { key: 'platform', name: 'Anaconda Platform',          footprint: 240, color: '#E6FAED', does: 'your whole floor is the Platform — shipping rate ×2' },
];
const PRODUCTS = EMBARGO ? ALL_PRODUCTS.slice(0, 1) : ALL_PRODUCTS;

const DEATH_COPY = {
  tail:   { title: 'Innovation bottleneck', line: 'Our LLM stack is held together with duct tape.' },
  border: { title: 'Out of bounds',          line: 'We need cloud, on-prem and sovereign flexibility.' },
  snake:  { title: 'Collision',              line: 'Every team is assembling its own AI stack.' },
  cut:    { title: 'Collision',              line: 'Every team is assembling its own AI stack.' },
};
const SETBACK_COPY = {
  package: 'We’ve had open-source packages slip in that weren’t vetted.',
  dataset: 'We’re worried about prompt injection if agents act on their own.',
  model:   'We don’t have a formal process for red-teaming models before they go live.',
  mcp:     'We don’t actually know what MCP servers our developers are connecting to.',
};

// ------------------------------- Helpers --------------------------------------
const rand = (a, b) => Math.random() * (b - a) + a;
const dist2 = (x1, y1, x2, y2) => (x1 - x2) ** 2 + (y1 - y2) ** 2;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
function angleLerp(from, to, maxDelta) {
  let d = to - from;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return from + clamp(d, -maxDelta, maxDelta);
}
const cellIndex = (col, row) => row * GRID_DIM + col;
function worldToCell(x, y) {
  return {
    col: clamp(Math.floor((x + WORLD_RADIUS) / CELL_SIZE), 0, GRID_DIM - 1),
    row: clamp(Math.floor((y + WORLD_RADIUS) / CELL_SIZE), 0, GRID_DIM - 1),
  };
}
function cellCenter(idx) {
  const col = idx % GRID_DIM, row = (idx / GRID_DIM) | 0;
  return { x: col * CELL_SIZE - WORLD_RADIUS + CELL_SIZE / 2, y: row * CELL_SIZE - WORLD_RADIUS + CELL_SIZE / 2 };
}
function randomPointInWorld(margin = 0.95) {
  const r = Math.sqrt(Math.random()) * WORLD_RADIUS * margin, a = Math.random() * Math.PI * 2;
  return { x: Math.cos(a) * r, y: Math.sin(a) * r };
}
const headRadius = (len) => clamp(7 + Math.sqrt(len) * 0.7, 7, 22);
const fmtTokens = (b) => b >= 1000 ? (b / 1000).toFixed(2) + 'T' : Math.round(b) + 'B';

// ------------------------------- State ----------------------------------------
const snakes = new Map();      // socketId -> Snake
const components = new Map();  // id -> component
const players = new Map();     // clientKey -> PlayerRecord (persistent across deaths)
const gridOwnerCode = new Int32Array(CELL_COUNT);
const codeToColor = new Map();
let nextOwnerCode = 1;
let compSeq = 0;
const compAdded = new Map(), compRemoved = new Set();
const compWire = (c) => ({ id: c.id, x: Math.round(c.x), y: Math.round(c.y), t: c.type, p: c.poisoned, k: c.curated, th: c.threat });
let tick = 0;
const hallOfFame = [];         // { name, at }
const feed = [];               // last event lines
const funding = { dealIndex: 0, units: 0, contributions: new Map(), lastLandAt: Date.now() };

function pushFeed(text) { feed.unshift({ text, at: Date.now() }); if (feed.length > 5) feed.length = 5; io.emit('feed', feed[0]); }
function banner(text, sub) { io.emit('banner', { text, sub: sub || '' }); pushFeed(text); }

function getOrCreatePlayer(clientKey, name, color, isBot) {
  if (clientKey && players.has(clientKey)) { const p = players.get(clientKey); if (name) p.name = name; if (color) p.color = color; codeToColor.set(p.code, p.color); return p; }
  const p = {
    clientKey: clientKey || ('anon_' + Math.random().toString(36).slice(2)), name, color, isBot: !!isBot,
    code: nextOwnerCode++, capabilities: new Set(), tokensRouted: 0, tokensBurned: 0, shipped: 0, trillion: false, projects: 0, firstSeen: Date.now(), home: null, padCells: [], buildings: [],
  };
  codeToColor.set(p.code, p.color);
  players.set(p.clientKey, p);
  return p;
}
const hasCap = (p, key) => p.capabilities.has(key);
const trustedFoundation = (p) => ACQUISITIONS.every(a => p.capabilities.has(a.key));

// ------------------------------- Components -----------------------------------
function pickType() {
  let r = Math.random(), acc = 0;
  for (const [k, v] of Object.entries(COMPONENT_TYPES)) { acc += v.weight; if (r <= acc) return k; }
  return 'package';
}
function spawnComponent(at, opts = {}) {
  const id = 'c' + (compSeq++);
  const p = at || randomPointInWorld();
  const type = opts.type || pickType();
  const poisoned = opts.curated || opts.clean ? false : Math.random() < POISON_RATE;
  const threat = poisoned ? pickThreat(type) : null;
  const comp = { id, x: p.x, y: p.y, type, poisoned, curated: !!opts.curated, threat: threat ? threat[0] : null, threatLine: threat ? threat[1] : null };
  components.set(id, comp); compAdded.set(id, comp);
  return id;
}
function ensureComponents() { if (components.size < COMPONENT_TARGET) spawnComponent(); }
function clearPoisonNear(x, y, r) {
  const r2 = r * r;
  for (const c of components.values()) if (c.poisoned && dist2(x, y, c.x, c.y) < r2) { c.poisoned = false; compAdded.set(c.id, c); }
}

// ------------------------------- Territory ------------------------------------
function ownedCount(code) { let n = 0; for (let i = 0; i < CELL_COUNT; i++) if (gridOwnerCode[i] === code) n++; return n; }
function emitCells(changed, color) { if (changed.length) io.emit('territoryUpdate', { cells: changed.map(idx => ({ idx, color })) }); }
const padLock = new Int32Array(CELL_COUNT); // pad cells are permanent and unclaimable
function clearLand(code, keepPad) {
  const changed = [];
  for (let i = 0; i < CELL_COUNT; i++) if (gridOwnerCode[i] === code && !(keepPad && padLock[i] === code)) { gridOwnerCode[i] = 0; changed.push(i); }
  emitCells(changed, null);
}
function padCellsAround(x, y) {
  const { col: c0, row: r0 } = worldToCell(x, y), h = (HOME_PLOT - 1) / 2, out = [];
  for (let dr = -h; dr <= h; dr++) for (let dc = -h; dc <= h; dc++) { const col = c0 + dc, row = r0 + dr; if (col >= 0 && col < GRID_DIM && row >= 0 && row < GRID_DIM) out.push(cellIndex(col, row)); }
  return out;
}
function seedHomePlot(snake) {
  const changed = [];
  for (const idx of snake.player.padCells) if (gridOwnerCode[idx] !== snake.code) { gridOwnerCode[idx] = snake.code; changed.push(idx); }
  emitCells(changed, snake.color);
}
function floodClaim(snake) {
  const blocked = new Uint8Array(CELL_COUNT);
  for (let i = 0; i < CELL_COUNT; i++) if (gridOwnerCode[i] === snake.code) blocked[i] = 1;
  for (const idx of snake.trailCells) blocked[idx] = 1;
  const outside = new Uint8Array(CELL_COUNT), queue = [];
  const tryPush = (idx) => { if (!blocked[idx] && !outside[idx]) { outside[idx] = 1; queue.push(idx); } };
  for (let c = 0; c < GRID_DIM; c++) { tryPush(cellIndex(c, 0)); tryPush(cellIndex(c, GRID_DIM - 1)); }
  for (let r = 0; r < GRID_DIM; r++) { tryPush(cellIndex(0, r)); tryPush(cellIndex(GRID_DIM - 1, r)); }
  while (queue.length) {
    const idx = queue.pop(), row = (idx / GRID_DIM) | 0, col = idx % GRID_DIM;
    if (col > 0) tryPush(idx - 1); if (col < GRID_DIM - 1) tryPush(idx + 1);
    if (row > 0) tryPush(idx - GRID_DIM); if (row < GRID_DIM - 1) tryPush(idx + GRID_DIM);
  }
  const changed = [];
  for (let i = 0; i < CELL_COUNT; i++) {
    if (padLock[i] !== 0 && padLock[i] !== snake.code) continue; // someone's Factory pad: untouchable
    if ((blocked[i] || !outside[i]) && gridOwnerCode[i] !== snake.code) { gridOwnerCode[i] = snake.code; changed.push(i); }
  }
  snake.trailCells.length = 0; snake.trailPts.length = 0;
  emitCells(changed, snake.color);
  if (changed.length) { snake.captures += 1; snake.floor = ownedCount(snake.code); checkIntegrations(snake); }
}

// ------------------------------- Acquisitions ---------------------------------
function currentDeal() { return ACQUISITIONS[funding.dealIndex] || null; }
function addFunding(player, units) {
  const deal = currentDeal(); if (!deal) return;
  const alive = [...snakes.values()].filter(s => s.alive).length;
  const u = units / Math.max(4, alive);
  funding.units += u;
  funding.contributions.set(player.clientKey, (funding.contributions.get(player.clientKey) || 0) + u);
  if (funding.units >= FUNDING_TARGET) landDeal(deal);
}
function landDeal(deal) {
  { deal.funded = true; funding.lastLandAt = Date.now();
    let top = null, topU = -1;
    for (const [k, v] of funding.contributions) if (v > topU) { topU = v; top = players.get(k); }
    banner(`ANACONDA ACQUIRES ${deal.name.toUpperCase()}`, top ? `Top contributor: ${top.name} · enclose the landmark to adopt ${deal.capability}` : `Enclose the landmark to adopt ${deal.capability}`);
    io.emit('landmark', { key: deal.key, site: deal.site });
    funding.dealIndex += 1; funding.units = 0; funding.contributions.clear();
  }
}
function fundingClock() {
  const deal = currentDeal(); if (!deal) return;
  const humans = [...snakes.values()].some(s => !s.isBot && s.alive);
  if (humans && Date.now() - funding.lastLandAt >= CAPABILITY_CLOCK_MS) landDeal(deal);
}
function padIndex(a) { const { col, row } = worldToCell(a.site.x, a.site.y); return cellIndex(col, row); }
function checkIntegrations(snake) {
  for (const a of ACQUISITIONS) {
    if (!a.funded || snake.player.capabilities.has(a.key)) continue;
    if (gridOwnerCode[padIndex(a)] !== snake.code) continue;
    snake.player.capabilities.add(a.key);
    const msg = `${snake.name} adopted ${a.capability}`;
    if (!a.firstIntegrator) { a.firstIntegrator = snake.name; banner(`${snake.name} adopted ${a.capability}`, `first on the server · ${a.name} · now part of Anaconda`); }
    else pushFeed(msg);
    io.to(snake.id).emit('capability', { key: a.key, name: a.name, capability: a.capability, does: a.does, color: a.color });
    if (trustedFoundation(snake.player)) banner(`${snake.name} completed the Trusted AI Foundation`);
  }
}
function padHolder(a) { const code = gridOwnerCode[padIndex(a)]; if (!code) return null; for (const s of snakes.values()) if (s.alive && s.code === code) return s; return null; }
function curatedSpawns() {
  for (const a of ACQUISITIONS) {
    if (!a.funded) continue;
    const holder = padHolder(a); if (!holder) continue;
    const idx = padIndex(a), c0 = idx % GRID_DIM, r0 = (idx / GRID_DIM) | 0, cands = [];
    for (let dr = -6; dr <= 6; dr++) for (let dc = -6; dc <= 6; dc++) {
      const col = c0 + dc, row = r0 + dr; if (col < 0 || col >= GRID_DIM || row < 0 || row >= GRID_DIM) continue;
      const i = cellIndex(col, row); if (gridOwnerCode[i] === holder.code) cands.push(i);
    }
    if (cands.length) { const c = cellCenter(cands[Math.floor(Math.random() * cands.length)]); spawnComponent({ x: c.x + rand(-15, 15), y: c.y + rand(-15, 15) }, { curated: true }); }
  }
}

// ------------------------------- Products / shipping --------------------------
const has = (list, k) => list.includes(k);

// ------------------------------- Snake ----------------------------------------
class Snake {
  constructor(id, name, color, isBot, clientKey) {
    this.id = id; this.name = (name || GUEST()).slice(0, 18);
    this.color = color || COLORS[Math.floor(Math.random() * COLORS.length)];
    this.isBot = !!isBot; this.alive = true; this.boosting = false;
    const prior = clientKey && players.get(clientKey);
    let spawn = prior && prior.home ? { x: prior.home.x, y: prior.home.y } : findSafeSpawn();
    if (this.isBot) { const h = nearestFreshHuman(); if (h) { for (let i = 0; i < 12; i++) { const a = rand(0, Math.PI * 2), r = rand(500, 900), c = { x: h.x + Math.cos(a) * r, y: h.y + Math.sin(a) * r }; if (c.x * c.x + c.y * c.y < (WORLD_RADIUS * 0.85) ** 2) { spawn = c; break; } } this.followTarget = h.id; this.followUntil = Date.now() + 60000; } }
    this.x = spawn.x; this.y = spawn.y;
    this.player = getOrCreatePlayer(clientKey, this.name, this.color, this.isBot);
    this.code = this.player.code;
    this.angle = rand(0, Math.PI * 2); this.targetAngle = this.angle;
    this.length = BASE_LENGTH; this.points = [{ x: this.x, y: this.y }];
    this.grace = SPAWN_GRACE_TICKS; this.shield = SPAWN_GRACE_TICKS;
    this.datasets = 0; this.captures = 0; this.floor = 0; this.pipeline = 0; this.prevProducts = [];
    this.spawnedAt = Date.now(); this.followTarget = null; this.followUntil = 0; this.hesitate = 0;
    this.enkryptFreeHit = true; this.retargetUsed = false;
    this.inTerritory = true; this.trailCells = []; this.trailPts = []; this.orbs = [];
    this.botTimer = 0; this.loopTicks = 0; this.loopDir = 1;
    this.deathReason = null;
    if (!this.player.home) {
      this.player.home = { x: this.x, y: this.y };
      this.player.padCells = padCellsAround(this.x, this.y);
      for (const idx of this.player.padCells) if (padLock[idx] === 0) padLock[idx] = this.code;
    }
    this.home = this.player.home;
    clearPoisonNear(this.x, this.y, SPAWN_POISON_CLEAR);
    if (!this.isBot) spawnKit(this);
    seedHomePlot(this);
    this.floor = ownedCount(this.code);
  }
  get headRadius() { return headRadius(this.length); }
  get products() { return this.player.buildings; }
  desiredPoints() { return Math.max(4, Math.floor(this.length)); }
  isProtected() { return this.inTerritory || (hasCap(this.player, 'enkrypt') && this.trailCells.length > 0); }

  step() {
    if (!this.alive) return;
    if (this.grace > 0) this.grace--; if (this.shield > 0) this.shield--;
    this.angle = angleLerp(this.angle, this.targetAngle, TURN_RATE);
    let speed = BASE_SPEED * (has(this.products, 'cli') ? 1.12 : 1);
    if (this.boosting) {
      speed = BOOST_SPEED * (has(this.products, 'cli') ? 1.12 : 1);
      if (!this.inTerritory && this.length > BASE_LENGTH * 0.6) {
        let drain = BOOST_DRAIN;
        if (hasCap(this.player, 'kilo')) drain *= 0.5;
        if (has(this.products, 'mcp')) drain *= 0.7;
        this.length -= drain; this.player.tokensBurned += drain;
        addFunding(this.player, drain * FUNDING_BOOST_RATE);
      }
    }
    this.x += Math.cos(this.angle) * speed; this.y += Math.sin(this.angle) * speed;
    this.points.unshift({ x: this.x, y: this.y });
    const desired = this.desiredPoints(); if (this.points.length > desired) this.points.length = desired;
    if (this.x * this.x + this.y * this.y > WORLD_RADIUS * WORLD_RADIUS) { this.die('border'); return; }
    this.updateTerritory();
    this.updateOrbs();
  }
  updateTerritory() {
    const { col, row } = worldToCell(this.x, this.y), idx = cellIndex(col, row);
    if (gridOwnerCode[idx] === this.code) {
      this.outTicks = 0;
      const canClose = hasCap(this.player, 'outerbounds') || padLock[idx] === this.code;
      if (this.trailCells.length > 0 && canClose) floodClaim(this);
      else if (this.trailCells.length > 0) { const last = this.trailCells[this.trailCells.length - 1]; if (last !== idx) this.trailCells.push(idx); }
      this.inTerritory = true;
    } else {
      this.inTerritory = false;
      if (this.trailCells[this.trailCells.length - 1] !== idx && this.trailCells.length < 4000) this.trailCells.push(idx);
      const lp = this.trailPts[this.trailPts.length - 1];
      if (!lp || dist2(lp.x, lp.y, this.x, this.y) > 24 * 24) { if (this.trailPts.length < 1200) this.trailPts.push({ x: Math.round(this.x), y: Math.round(this.y) }); }
      this.outTicks = (this.outTicks || 0) + 1;
    }
  }
  updateOrbs() {
    const n = hasCap(this.player, 'kilo') ? (has(this.products, 'desktop') ? 4 : 2) : 0;
    this.orbs.length = n;
    for (let i = 0; i < n; i++) {
      const a = tick * 0.09 + (i / n) * Math.PI * 2;
      this.orbs[i] = { x: Math.round(this.x + Math.cos(a) * 58), y: Math.round(this.y + Math.sin(a) * 58) };
    }
  }
  grow(amount) { this.length = Math.min(MAX_LENGTH, this.length + amount); }
  setback(type, c) {
    const lose = Math.max(SETBACK_MIN, Math.floor(this.length * SETBACK_FRACTION));
    const actual = Math.min(lose, Math.max(0, this.length - SETBACK_MIN));
    this.length -= actual;
    for (let i = 0; i < actual; i++) {
      const p = this.points[Math.min(this.points.length - 1, this.points.length - 1 - i)] || { x: this.x, y: this.y };
      spawnComponent({ x: p.x + rand(-40, 40), y: p.y + rand(-40, 40) }, { clean: true, type: 'package' });
    }
    io.to(this.id).emit('setback', { type, threat: c.threat, label: c.threatLine, lost: actual, line: SETBACK_COPY[type] });
  }
  die(reason, killer) {
    if (!this.alive) return;
    this.alive = false; this.deathReason = reason;
    if (!this.isBot) { analytics.deaths += 1; analytics.runSeconds.push(Math.round((Date.now() - this.spawnedAt) / 1000)); if (this.player.capabilities.size) analytics.adoptedAny = (analytics.adoptedAny || 0) + 1; }
    for (let i = 0; i < this.points.length; i += 3) { const p = this.points[i]; spawnComponent({ x: p.x + rand(-8, 8), y: p.y + rand(-8, 8) }, { clean: true }); }
    clearLand(this.code, true); // land is lost; the pad, its buildings, acquisitions and tokens stay
    const p = this.player, caps = [...p.capabilities];
    const lines = {
      kilo: 'With Kilo your boosts cost half. Imagine that on your real token bill.',
      enkrypt: 'You could see the poison. Most teams can’t.',
      outerbounds: 'You moved your whole factory and lost nothing. That’s orchestration.',
    };
    const pitch = caps.length ? lines[caps[caps.length - 1]] : 'You built fast. 88% of AI projects still never reach production.';
    io.to(this.id).emit('died', {
      reason, killer: killer || null, copy: DEATH_COPY[reason], respawnMs: RESPAWN_MS,
      summary: { projects: p.projects, tokens: Math.round(p.tokensRouted), caps: caps.map(k => (ACQUISITIONS.find(a => a.key === k) || {}).capability), products: this.player.buildings.slice(), seconds: Math.round((Date.now() - this.spawnedAt) / 1000), pitch, guest: /^builder-\d+$/.test(this.name) },
    });
  }
  retarget() {
    if (!hasCap(this.player, 'outerbounds') || this.retargetUsed || !this.alive) return false;
    this.retargetUsed = true;
    const p = findSafeSpawn();
    this.x = p.x; this.y = p.y; this.points = [{ x: p.x, y: p.y }]; this.trailCells.length = 0; this.trailPts.length = 0;
    this.shield = TICK_RATE; this.floor = ownedCount(this.code);
    io.to(this.id).emit('retargeted', {});
    return true;
  }
  botAI() {
    if (this.hesitate > 0) { this.hesitate--; return; } // human-ish pause before committing to a turn
    if (this.followTarget && Date.now() < this.followUntil && Math.random() < 0.6) {
      const h = snakes.get(this.followTarget);
      if (h && h.alive && dist2(this.x, this.y, h.x, h.y) > 320 * 320) { if (--this.botTimer <= 0) { this.botTimer = 12; this.hesitate = 3; this.targetAngle = Math.atan2(h.y - this.y, h.x - this.x) + rand(-0.4, 0.4); } return; }
    }
    if (this.loopTicks > 0 && Math.hypot(this.x, this.y) < WORLD_RADIUS * 0.85) {
      this.loopTicks--; this.targetAngle += this.loopDir * 0.05;
      if (this.loopTicks === 0) { this.targetAngle = Math.atan2(this.home.y - this.y, this.home.x - this.x); this.botTimer = 60; }
      return;
    }
    if (!this.inTerritory && (this.outTicks || 0) > TICK_RATE * 25) { this.targetAngle = Math.atan2(this.home.y - this.y, this.home.x - this.x) + rand(-0.15, 0.15); this.boosting = false; return; }
    if (--this.botTimer > 0) return;
    this.botTimer = 15 + Math.floor(Math.random() * 20);
    if (this.inTerritory && Math.random() < 0.15) { this.loopTicks = 60 + Math.floor(Math.random() * 60); this.loopDir = Math.random() < 0.5 ? -1 : 1; this.targetAngle = rand(0, Math.PI * 2); return; }
    if (Math.hypot(this.x, this.y) > WORLD_RADIUS * 0.85) { this.targetAngle = Math.atan2(-this.y, -this.x) + rand(-0.3, 0.3); return; }
    let best = null, bd = Infinity;
    for (const c of components.values()) { if (c.poisoned) continue; const d = dist2(this.x, this.y, c.x, c.y); if (d < bd) { bd = d; best = c; } }
    this.hesitate = Math.random() < 0.3 ? 4 : 0;
    this.targetAngle = best && Math.random() > 0.08 ? Math.atan2(best.y - this.y, best.x - this.x) : this.targetAngle + rand(-0.9, 0.9); // occasional bad decision
    this.boosting = Math.random() < 0.02;
  }
}

function findSafeSpawn() {
  for (let i = 0; i < 40; i++) {
    const c = randomPointInWorld(0.7);
    let ok = true;
    const d2 = SPAWN_SAFE_DIST ** 2;
    for (const s of snakes.values()) { if (!s.alive) continue; for (let k = 0; k < s.points.length && ok; k += 2) if (dist2(c.x, c.y, s.points[k].x, s.points[k].y) < d2) ok = false; if (!ok) break; }
    if (!ok) continue;
    const { col, row } = worldToCell(c.x, c.y), h = (HOME_PLOT - 1) / 2 + 1;
    for (let dr = -h; dr <= h && ok; dr++) for (let dc = -h; dc <= h; dc++) {
      const cc = col + dc, rr = row + dr; if (cc < 0 || cc >= GRID_DIM || rr < 0 || rr >= GRID_DIM) continue;
      if (gridOwnerCode[cellIndex(cc, rr)] !== 0) { ok = false; break; }
    }
    if (ok) return c;
  }
  return randomPointInWorld(0.7);
}
// First eat within 2s: 5-8 clean components on screen, one directly ahead.
function spawnKit(s) {
  spawnComponent({ x: s.x + Math.cos(s.angle) * 120, y: s.y + Math.sin(s.angle) * 120 }, { clean: true, type: 'package' });
  const n = 4 + Math.floor(Math.random() * 4);
  for (let i = 0; i < n; i++) { const a = rand(0, Math.PI * 2), r = rand(120, 420); spawnComponent({ x: s.x + Math.cos(a) * r, y: s.y + Math.sin(a) * r }, { clean: true }); }
}
// Never a screen with fewer than 6 pickups around a human.
function densityAroundHumans() {
  for (const s of snakes.values()) {
    if (s.isBot || !s.alive) continue;
    let n = 0; for (const c of components.values()) if (dist2(s.x, s.y, c.x, c.y) < 700 * 700) { n++; if (n >= 6) break; }
    if (n < 6) { const a = rand(0, Math.PI * 2), r = rand(250, 650); const p = { x: s.x + Math.cos(a) * r, y: s.y + Math.sin(a) * r }; if (p.x * p.x + p.y * p.y < (WORLD_RADIUS * 0.95) ** 2) spawnComponent(p, { clean: true }); }
  }
}
function nearestFreshHuman() {
  const now = Date.now(); let best = null;
  for (const s of snakes.values()) if (!s.isBot && s.alive && now - s.spawnedAt < 60000) { if (!best || s.spawnedAt > best.spawnedAt) best = s; }
  return best;
}
function createSnake(id, name, color, isBot, clientKey) { const s = new Snake(id, name, color, isBot, clientKey); snakes.set(id, s); return s; }
function removeSnake(id) { const s = snakes.get(id); if (!s) return; if (s.alive) clearLand(s.code, !s.isBot); if (s.isBot) { clearLand(s.code, false); for (const i of s.player.padCells) if (padLock[i] === s.code) padLock[i] = 0; players.delete(s.player.clientKey); } snakes.delete(id); }

let botSeq = 0;
function maintainBots() {
  const bots = [...snakes.values()].filter(s => s.isBot);
  for (const b of bots) if (!b.alive) removeSnake(b.id);
  const names = ['Kaa', 'Boa', 'Viper', 'Cobra', 'Python', 'Mamba', 'Sidewinder', 'Adder'];
  while ([...snakes.values()].filter(s => s.isBot).length < BOT_TARGET_COUNT) createSnake('bot_' + (botSeq++), BOT_NAMES[Math.floor(Math.random() * BOT_NAMES.length)], undefined, true, null);
}

// ------------------------------- Pickups --------------------------------------
function collect(s, c, viaOrb) {
  components.delete(c.id); compRemoved.add(c.id); compAdded.delete(c.id);
  let poisoned = c.poisoned;
  if (poisoned && s.inTerritory) { poisoned = false; io.to(s.id).emit('vetted', { threat: c.threat }); } // your floor is main: secure by default
  if (poisoned) {
    if (s.grace > 0 || s.length < BASE_LENGTH + 3) return;
    if (hasCap(s.player, 'enkrypt') && s.enkryptFreeHit) { s.enkryptFreeHit = false; io.to(s.id).emit('blocked', { threat: c.threat, label: c.threatLine }); return; }
    s.setback(c.type, c); return;
  }
  s.player.tokensRouted += 1;
  let grow = COMPONENT_TYPES[c.type].grow;
  if (hasCap(s.player, 'kilo')) grow *= 2;
  if (viaOrb && has(s.products, 'desktop')) grow *= 2;
  s.grow(grow);
  if (c.type === 'dataset') s.datasets = Math.min(8, s.datasets + 1);
  addFunding(s.player, 1);
  io.to(s.id).emit('ate', { t: c.type, grow });
}
function pickups() {
  for (const s of snakes.values()) {
    if (!s.alive) continue;
    const r = (s.headRadius + 16) * (has(s.products, 'mcp') ? 1.6 : 1), r2 = r * r;
    for (const c of components.values()) {
      if (dist2(s.x, s.y, c.x, c.y) <= r2) { collect(s, c, false); continue; }
      for (const o of s.orbs) if (dist2(o.x, o.y, c.x, c.y) <= 14 * 14) { if (!c.poisoned) collect(s, c, true); break; }
    }
  }
}

// ------------------------------- Collisions -----------------------------------
function collisions() {
  const alive = [...snakes.values()].filter(s => s.alive);
  const kills = new Map();
  for (const a of alive) {
    if (a.shield > 0) continue;
    const ar = a.headRadius, rr = (ar * 1.9) ** 2;
    const skip = Math.max(6, Math.ceil(ar * 3.2 / SEGMENT_SPACING));
    for (let i = skip; i < a.points.length; i += 2) if (dist2(a.x, a.y, a.points[i].x, a.points[i].y) <= rr) { kills.set(a.id, { reason: 'tail' }); break; }
  }
  // Cut a rival's trail while they're outside their land: they die, you get their segments.
  for (const a of alive) {
    const { col, row } = worldToCell(a.x, a.y), headIdx = cellIndex(col, row);
    for (const b of alive) {
      if (a === b || b.shield > 0 || kills.has(b.id) || b.isProtected() || b.trailCells.length < 4) continue;
      const n = b.trailCells.length - 3;
      for (let i = 0; i < n; i++) if (b.trailCells[i] === headIdx) { kills.set(b.id, { reason: 'cut', killer: a.name }); break; }
    }
  }
  for (const a of alive) {
    if (kills.has(a.id) || a.shield > 0) continue;
    for (const b of alive) {
      if (a === b || b.shield > 0 || kills.has(b.id)) continue;
      const hh = (a.headRadius + b.headRadius) ** 2;
      if (dist2(a.x, a.y, b.x, b.y) <= hh) {
        const ap = a.isProtected(), bp = b.isProtected();
        if (ap && !bp) kills.set(b.id, { reason: 'snake', killer: a.name });
        else if (bp && !ap) kills.set(a.id, { reason: 'snake', killer: b.name });
        else { kills.set(a.id, { reason: 'snake', killer: b.name }); kills.set(b.id, { reason: 'snake', killer: a.name }); }
        continue;
      }
      const rr = (a.headRadius + b.headRadius * 0.9) ** 2;
      for (let i = 4; i < b.points.length; i += 2) {
        if (dist2(a.x, a.y, b.points[i].x, b.points[i].y) <= rr) {
          if (b.isProtected()) kills.set(a.id, { reason: 'snake', killer: b.name });
          else kills.set(b.id, { reason: 'snake', killer: a.name });
          break;
        }
      }
      if (kills.has(a.id)) break;
    }
  }
  // Fresh humans (first 15s) can't be killed by bots — nobody dies before they've learned to steer.
  for (const [id, k] of [...kills]) { const v = snakes.get(id); if (!v || v.isBot || !k.killer) continue; const killer = alive.find(o => o.name === k.killer); if (killer && killer.isBot && Date.now() - v.spawnedAt < 15000) kills.delete(id); }
  for (const [id, k] of kills) { const s = snakes.get(id); if (s) { s.die(k.reason, k.killer); if (k.killer) for (const o of alive) if (o.name === k.killer && !o.isBot) io.to(o.id).emit('gotcha', { victim: s.name }); } }
}

// ------------------------------- Shipping / score -----------------------------
// Score = AI projects in production. Eating components feeds the pipeline; standing
// buildings ship on their own every 5s. Each project routes tokens.
function shipProject(s, order, prodKey) {
  const p = PRODUCTS.find(pp => pp.key === prodKey);
  const floorScale = Math.min(1, s.floor / (p ? p.footprint : 40)); // shipping rate scales with current floor
  const mult = (1 + 0.25 * s.datasets) * (has(s.products, 'platform') ? 2 : 1);
  const tokens = 10 * order * mult * floorScale;
  s.player.projects += 1; s.player.tokensRouted += tokens; s.player.shipped += 1;
  io.emit('shipment', { id: s.id, from: s.home, tokens, order, key: prodKey, color: p ? p.color : s.color });
  if (!s.player.trillion && s.player.tokensRouted >= TRILLION) {
    s.player.trillion = true;
    hallOfFame.unshift({ name: s.name, at: Date.now() }); if (hallOfFame.length > 20) hallOfFame.length = 20;
    banner(`${s.name} reached Trillion-Token Scale`);
  }
}
function shipping() {
  for (const s of snakes.values()) if (s.alive) s.products.forEach((k, i) => shipProject(s, i + 1, k));
}
// B to build: needs Trusted Foundation and floor >= next footprint (checked at build time only).
function tryBuild(s) {
  if (!s.alive) return;
  if (!trustedFoundation(s.player)) { io.to(s.id).emit('buildFail', { why: 'Adopt all three capabilities first.' }); return; }
  const next = PRODUCTS[s.player.buildings.length];
  if (!next) { io.to(s.id).emit('buildFail', { why: 'Your Factory is complete.' }); return; }
  if (s.floor < next.footprint) { io.to(s.id).emit('buildFail', { why: `${next.name} needs ${next.footprint} floor — you have ${s.floor}.` }); return; }
  s.player.buildings.push(next.key);
  io.to(s.id).emit('building', { key: next.key, name: next.name, does: next.does, color: next.color });
  pushFeed(`${s.name} built ${next.name}`);
}

function tokenBill() {
  const rows = [...players.values()].filter(p => !p.isBot && p.tokensRouted > 0)
    .map(p => ({ name: p.name, shipped: p.shipped, burned: Math.round(p.tokensBurned), routed: Math.round(p.tokensRouted), eff: p.tokensRouted / Math.max(1, p.tokensBurned) }))
    .sort((a, b) => b.eff - a.eff).slice(0, 6);
  if (rows.length) io.emit('tokenBill', { rows });
}

// ------------------------------- Tick -----------------------------------------
function gameTick() {
  tick++;
  for (const s of snakes.values()) { if (s.isBot && s.alive) s.botAI(); s.step(); }
  pickups();
  collisions();
  for (const s of snakes.values()) if (s.alive) s.floor = ownedCount(s.code);
  fundingClock();
  if (tick % 10 === 0) densityAroundHumans();
  ensureComponents();
  if (tick % CURATED_SPAWN_TICKS === 0) curatedSpawns();
  if (tick % SHIP_TICKS === 0) shipping();
  if (tick % TOKEN_BILL_TICKS === 0) tokenBill();
  maintainBots();
  broadcast();
}

function flat(pts) { const a = new Array(pts.length * 2); for (let i = 0; i < pts.length; i++) { a[i * 2] = Math.round(pts[i].x); a[i * 2 + 1] = Math.round(pts[i].y); } return a; }
// Body stream: first 6 points at full resolution, then every 2nd (client re-inserts midpoints).
function flatTrail(pts) { const a = []; const n = pts.length; const start = Math.max(0, n - 60); const older = []; for (let i = 0; i < start; i += 3) older.push(pts[i]); const keep = older.slice(-240).concat(pts.slice(start)); for (const p of keep) a.push(p.x, p.y); return a; }
function flatBody(pts) { const a = []; for (let i = 0; i < pts.length; i += i < 6 ? 1 : 2) a.push(Math.round(pts[i].x), Math.round(pts[i].y)); return a; }
function broadcast() {
  const dyn = [...snakes.values()].map(s => ({
    id: s.id, alive: s.alive, length: Math.round(s.length), headRadius: +s.headRadius.toFixed(1),
    pts: flatBody(s.points), shield: s.shield > 0, inTerritory: s.inTerritory, trail: flatTrail(s.trailPts), orbs: s.orbs, floor: s.floor,
  }));
  const added = [...compAdded.values()].filter(c => components.has(c.id)).map(compWire), removed = [...compRemoved]; compAdded.clear(); compRemoved.clear();
  io.emit('state', { t: Date.now(), snakes: dyn, compAdd: added, compRemove: removed });
  if (tick % 10 === 0) broadcastMeta();
}
function broadcastMeta() {
  const metaSnakes = [...snakes.values()].map(s => ({
    id: s.id, name: s.name, color: s.color, home: s.home, products: s.products, datasets: s.datasets,
    nextFootprint: (PRODUCTS[s.player.buildings.length] || {}).footprint || null, nextProduct: (PRODUCTS[s.player.buildings.length] || {}).name || null,
    caps: [...s.player.capabilities], crown: trustedFoundation(s.player), tokens: Math.round(s.player.tokensRouted), burned: Math.round(s.player.tokensBurned),
    retargetUsed: s.retargetUsed, projects: s.player.projects, age: Date.now() - s.spawnedAt,
  }));
  const leaderboard = [...snakes.values()].filter(s => s.alive)
    .sort((a, b) => (b.player.projects - a.player.projects) || ((b.player.tokensRouted / Math.max(1, b.player.tokensBurned)) - (a.player.tokensRouted / Math.max(1, a.player.tokensBurned))) || (b.length - a.length))
    .slice(0, 8).map(s => ({ name: s.name, projects: s.player.projects, tokens: Math.round(s.player.tokensRouted), crown: trustedFoundation(s.player), color: s.color }));
  const deal = currentDeal();
  io.emit('meta', {
    worldRadius: WORLD_RADIUS, snakes: metaSnakes, leaderboard, hallOfFame: hallOfFame.slice(0, 5),
    funding: { deal: deal ? deal.key : null, dealName: deal ? deal.name : null, capability: deal ? deal.capability : null, units: funding.units, target: FUNDING_TARGET, clockPct: deal ? Math.min(1, (Date.now() - funding.lastLandAt) / CAPABILITY_CLOCK_MS) : 1 },
    acquisitions: ACQUISITIONS.map(a => { const h = a.funded ? padHolder(a) : null; return { key: a.key, name: a.name, color: a.color, capability: a.capability, funded: a.funded, site: a.site, holder: h ? h.name : null, holderColor: h ? h.color : null, firstIntegrator: a.firstIntegrator }; }),
    playerCount: [...snakes.values()].filter(s => !s.isBot).length,
  });
}

function territorySnapshot() {
  const cells = [];
  for (let i = 0; i < CELL_COUNT; i++) { const c = gridOwnerCode[i]; if (c) cells.push({ idx: i, color: codeToColor.get(c) || '#08CA4A' }); }
  return cells;
}
function welcome(socket, s) {
  return {
    id: socket.id, worldRadius: WORLD_RADIUS, you: { x: s.x, y: s.y, angle: s.angle, color: s.color, name: s.name },
    territory: { cellSize: CELL_SIZE, gridDim: GRID_DIM, cells: territorySnapshot() },
    products: PRODUCTS.map(p => ({ key: p.key, name: p.name, footprint: p.footprint, color: p.color })),
    colors: COLORS,
    acquisitions: ACQUISITIONS.map(a => ({ key: a.key, name: a.name, color: a.color, capability: a.capability, does: a.does, site: a.site })),
    embargo: EMBARGO, cta: process.env.CTA_URL || 'https://www.anaconda.com/platform',
    feed,
    components: [...components.values()].map(compWire),
  };
}

for (let i = 0; i < COMPONENT_TARGET; i++) spawnComponent();
setInterval(gameTick, TICK_MS);

// ------------------------------- Networking -----------------------------------
io.on('connection', (socket) => {
  socket.on('join', ({ name, color, clientKey } = {}) => {
    if (snakes.has(socket.id)) removeSnake(socket.id);
    analytics.sessions += 1;
    const s = createSnake(socket.id, name, color, false, clientKey);
    socket.emit('welcome', welcome(socket, s)); broadcastMeta();
  });
  socket.on('respawn', ({ name, color, clientKey } = {}) => {
    const prev = snakes.get(socket.id);
    removeSnake(socket.id);
    const s = createSnake(socket.id, name || (prev && prev.name), color || (prev && prev.color), false, clientKey);
    socket.emit('welcome', welcome(socket, s)); broadcastMeta();
  });
  socket.on('input', ({ angle, boosting } = {}) => {
    const s = snakes.get(socket.id); if (!s || !s.alive) return;
    if (typeof angle === 'number' && isFinite(angle)) s.targetAngle = angle;
    s.boosting = !!boosting;
  });
  socket.on('retarget', () => { const s = snakes.get(socket.id); if (s) s.retarget(); });
  socket.on('build', () => { const s = snakes.get(socket.id); if (s) tryBuild(s); });
  socket.on('setSkin', ({ color: c } = {}) => { const s = snakes.get(socket.id); if (s && COLORS.includes(c)) { s.color = c; s.player.color = c; codeToColor.set(s.code, c); } });
  socket.on('setName', ({ name } = {}) => { const s = snakes.get(socket.id); const n = String(name || '').trim().slice(0, 18); if (!n) return; if (s) { s.name = n; s.player.name = n; } });
  socket.on('analytics', ({ event } = {}) => { if (typeof event === 'string' && event.length < 40) analytics[event] = (analytics[event] || 0) + 1; });
  socket.on('disconnect', () => removeSnake(socket.id));
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => console.log(`ANACONDA AI FACTORY server listening on http://localhost:${PORT}`));
