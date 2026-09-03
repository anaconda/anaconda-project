'use strict';
/**
 * ANACONDAE — multiplayer slither-style snake game
 * Authoritative Node.js game server (Express + Socket.io)
 *
 * World: a CIRCLE (not a rectangle) of radius WORLD_RADIUS. Snakes that
 * cross the boundary die. Multiple snakes compete for diamonds; touching
 * another snake's body with your head kills you (and drops your body as
 * diamonds), so from the other snake's point of view "if they bite you,
 * they die" holds symmetrically — the head that makes contact always loses.
 */

const express = require('express');
const http = require('http');
const path = require('path');
const { Server } = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: '*' },
});

app.use(express.static(path.join(__dirname, 'public')));

// ----------------------------- Tunables ------------------------------------
const WORLD_RADIUS = 3200;
const TICK_RATE = 30; // server ticks per second
const TICK_MS = 1000 / TICK_RATE;
const BASE_SPEED = 3.4; // units per tick
const BOOST_MULT = 1.9;
const BOOST_DRAIN_PER_TICK = 0.12; // length units drained per tick while boosting
const MAX_TURN_RATE_BASE = 0.11; // radians per tick, scaled down as snake grows
const START_LENGTH = 60; // starting body "length units"
const SEGMENT_SPACING = 5.5; // distance between stored trail points
const MIN_HEAD_RADIUS = 9;
const MAX_HEAD_RADIUS = 34;
const RADIUS_GROWTH_K = 0.011; // how quickly thickness grows with length
const DIAMOND_MIN_VALUE = 6;
const DIAMOND_MAX_VALUE = 14;
const DIAMOND_TARGET_DENSITY = 1 / 26000; // diamonds per square unit of world area
const WORLD_AREA = Math.PI * WORLD_RADIUS * WORLD_RADIUS;
const DIAMOND_TARGET_COUNT = Math.floor(WORLD_AREA * DIAMOND_TARGET_DENSITY);
const DEATH_DIAMOND_STRIDE = 3; // drop a diamond every N body points on death
const BOT_TARGET_COUNT = 5; // keep the world lively even with few humans

const COLORS = [
  '#3EB049', '#F2B705', '#2FA4A9', '#E0574C', '#8E6BC7',
  '#4E9F3D', '#D98E04', '#3D7EA6', '#C43E3E', '#5CB85C',
];

// Anaconda's acquisitions get a rare, extra-valuable "brand diamond" cameo,
// rendered client-side with each company's real mark + real brand color.
const BRAND_DIAMONDS = [
  { brand: 'outerbounds', label: 'Outerbounds', color: '#6A9E8B', valueMult: 3.2 },
  { brand: 'kilo', label: 'Kilo', color: '#F8F674', valueMult: 3.2 }, // Kilo's actual brand yellow (CTA button color on kilo.ai)
  { brand: 'enkrypt', label: 'Enkrypt', color: '#FF7F00', valueMult: 3.2 },
];
const BRAND_DIAMOND_CHANCE = 0.09; // chance a new diamond spawn is a brand cameo
const MAX_BRAND_DIAMONDS_ALIVE = 9; // bumped up so they're actually easy to run into
const ALL_BRAND_KEYS = BRAND_DIAMONDS.map(b => b.brand);
const TRIFECTA_LENGTH_BONUS = 200; // reward for completing the Acquisition Trifecta

// Post-Crown tier: this September's product launches. Only meaningful (grow
// your AI Factory) once you hold the Crown; otherwise just a regular pickup.
const PRODUCT_DIAMONDS = [
  { product: 'ana-cli', label: 'Ana CLI GA', short: 'ana', color: '#08CA4A', valueMult: 4 },
  { product: 'main-x', label: 'Main-X GA', short: 'MX', color: '#068F35', valueMult: 4 },
  { product: 'anaconda-mcp', label: 'Anaconda MCP GA', short: 'MCP', color: '#E6FAED', valueMult: 4 },
];
const ALL_PRODUCT_KEYS = PRODUCT_DIAMONDS.map(p => p.product);
const PRODUCT_DIAMOND_CHANCE = 0.06;
const MAX_PRODUCT_DIAMONDS_ALIVE = 6;
const PRODUCT_LENGTH_BONUS = 120;

// Session-lifetime "Hall of Fame" (in-memory, resets on server restart).
const hallOfFame = [];

// ----------------------------- Persistent players ----------------------------
// Progress (acquisitions, Crown, product launches, AI Factory location) lives
// on a PlayerRecord keyed by a client-generated key, NOT on the per-life Snake,
// so dying never takes it away.
const players = new Map();
function getOrCreatePlayer(clientKey, name, color, spawn, isBot) {
  if (clientKey && players.has(clientKey)) {
    const p = players.get(clientKey);
    if (name) p.name = name;
    if (color) p.color = color;
    return p;
  }
  const p = {
    clientKey: clientKey || ('anon_' + Math.random().toString(36).slice(2)),
    name, color,
    collectedBrands: new Set(),
    crown: false,
    unlockedProducts: new Set(),
    home: { x: spawn.x, y: spawn.y },
    created: Date.now(),
    code: nextOwnerCode++,
  };
  codeToColor.set(p.code, p.color);
  players.set(p.clientKey, p);
  if (!isBot) lockFortress(p);
  return p;
}
function factoryLevel(p) { return 1 + p.collectedBrands.size + p.unlockedProducts.size; } // 1..7
function anyoneCrowned() { for (const p of players.values()) if (p.crown) return true; return false; }

// ----------------------------- Territory (paper.io-style) -------------------
const CELL_SIZE = 16; // world units per grid cell (small = ground hugs the actual path, not blocky squares)
const GRID_DIM = Math.round((WORLD_RADIUS * 2) / CELL_SIZE); // 160 for our world
const CELL_COUNT = GRID_DIM * GRID_DIM;
const HOME_TERRITORY_RADIUS = 90; // seeded disk of owned ground at spawn
const TRAIL_CAP = 6000; // safety valve so a very long excursion can't grow unbounded

const gridOwnerCode = new Int32Array(CELL_COUNT); // 0 = unclaimed
const codeToColor = new Map(); // ownerCode -> hex color (persists after death, like real paper.io)
let nextOwnerCode = 1;
const FORTRESS_RADIUS = 110; // ground around a Factory that can never be taken
const cellLock = new Int32Array(CELL_COUNT); // 0 = free; else owner code that permanently holds it

function cellIndex(col, row) { return row * GRID_DIM + col; }
function cellCenter(idx) {
  const col = idx % GRID_DIM, row = (idx / GRID_DIM) | 0;
  return { x: col * CELL_SIZE - WORLD_RADIUS + CELL_SIZE / 2, y: row * CELL_SIZE - WORLD_RADIUS + CELL_SIZE / 2 };
}
function worldToCell(x, y) {
  const col = clamp(Math.floor((x + WORLD_RADIUS) / CELL_SIZE), 0, GRID_DIM - 1);
  const row = clamp(Math.floor((y + WORLD_RADIUS) / CELL_SIZE), 0, GRID_DIM - 1);
  return { col, row };
}

function lockFortress(player) {
  const { col: cCol, row: cRow } = worldToCell(player.home.x, player.home.y);
  const cr = Math.ceil(FORTRESS_RADIUS / CELL_SIZE);
  const changed = [];
  for (let dr = -cr; dr <= cr; dr++) for (let dc = -cr; dc <= cr; dc++) {
    const col = cCol + dc, row = cRow + dr;
    if (col < 0 || col >= GRID_DIM || row < 0 || row >= GRID_DIM || dc * dc + dr * dr > cr * cr) continue;
    const idx = cellIndex(col, row);
    if (cellLock[idx] !== 0) continue; // first fortress wins overlapping ground
    cellLock[idx] = player.code; gridOwnerCode[idx] = player.code; changed.push(idx);
  }
  if (changed.length) io.emit('territoryUpdate', { cells: changed.map(idx => ({ idx, color: player.color })) });
}

function seedHomeTerritory(snake) {
  const changed = [];
  const { col: cCol, row: cRow } = worldToCell(snake.x, snake.y);
  const cellRadius = Math.ceil(HOME_TERRITORY_RADIUS / CELL_SIZE);
  for (let dr = -cellRadius; dr <= cellRadius; dr++) {
    for (let dc = -cellRadius; dc <= cellRadius; dc++) {
      const col = cCol + dc, row = cRow + dr;
      if (col < 0 || col >= GRID_DIM || row < 0 || row >= GRID_DIM) continue;
      if (dc * dc + dr * dr > cellRadius * cellRadius) continue;
      const idx = cellIndex(col, row);
      if (cellLock[idx] !== 0 && cellLock[idx] !== snake.code) continue;
      if (gridOwnerCode[idx] === snake.code) continue;
      gridOwnerCode[idx] = snake.code;
      changed.push(idx);
    }
  }
  return changed;
}

// Flood-fill claim: BFS "outside" from the grid border; anything not reached
// and not part of the snake's own territory/trail was enclosed by the loop
// the snake just drew, so it gets claimed (stealing it from anyone else who
// owned it). This is the standard paper.io capture algorithm.
function floodClaim(snake) {
  const blocked = new Uint8Array(CELL_COUNT);
  for (let i = 0; i < CELL_COUNT; i++) if (gridOwnerCode[i] === snake.code) blocked[i] = 1;
  for (const idx of snake.trailCells) blocked[idx] = 1;

  const outside = new Uint8Array(CELL_COUNT);
  const queue = [];
  function tryPush(idx) { if (!blocked[idx] && !outside[idx]) { outside[idx] = 1; queue.push(idx); } }
  for (let col = 0; col < GRID_DIM; col++) { tryPush(cellIndex(col, 0)); tryPush(cellIndex(col, GRID_DIM - 1)); }
  for (let row = 0; row < GRID_DIM; row++) { tryPush(cellIndex(0, row)); tryPush(cellIndex(GRID_DIM - 1, row)); }

  while (queue.length) {
    const idx = queue.pop();
    const row = (idx / GRID_DIM) | 0, col = idx % GRID_DIM;
    if (col > 0) tryPush(idx - 1);
    if (col < GRID_DIM - 1) tryPush(idx + 1);
    if (row > 0) tryPush(idx - GRID_DIM);
    if (row < GRID_DIM - 1) tryPush(idx + GRID_DIM);
  }

  const changed = [];
  for (let i = 0; i < CELL_COUNT; i++) {
    if (cellLock[i] !== 0 && cellLock[i] !== snake.code) continue; // someone's fortress: untouchable
    if (blocked[i]) {
      if (gridOwnerCode[i] !== snake.code) { gridOwnerCode[i] = snake.code; changed.push(i); }
    } else if (!outside[i]) {
      if (gridOwnerCode[i] !== snake.code) { gridOwnerCode[i] = snake.code; changed.push(i); }
    }
  }
  snake.trailCells.length = 0;
  return changed;
}

function emitTerritoryChange(snake, changedIndices) {
  if (!changedIndices || changedIndices.length === 0) return;
  io.emit('territoryUpdate', { cells: changedIndices.map(idx => ({ idx, color: snake.color })) });
}

function rand(min, max) { return Math.random() * (max - min) + min; }
function dist2(x1, y1, x2, y2) { const dx = x1 - x2, dy = y1 - y2; return dx * dx + dy * dy; }
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function angleLerp(from, to, maxDelta) {
  let diff = to - from;
  while (diff > Math.PI) diff -= Math.PI * 2;
  while (diff < -Math.PI) diff += Math.PI * 2;
  diff = clamp(diff, -maxDelta, maxDelta);
  return from + diff;
}

function headRadiusForLength(length) {
  return clamp(MIN_HEAD_RADIUS + Math.sqrt(length) * RADIUS_GROWTH_K * 10, MIN_HEAD_RADIUS, MAX_HEAD_RADIUS);
}

// ----------------------------- Game State -----------------------------------
/** @type {Map<string, Snake>} */
const snakes = new Map();
/** @type {Map<string, Diamond>} */
const diamonds = new Map();
let diamondSeq = 0;

function randomPointInWorld(marginFactor = 0.98) {
  const r = Math.sqrt(Math.random()) * WORLD_RADIUS * marginFactor;
  const a = Math.random() * Math.PI * 2;
  return { x: Math.cos(a) * r, y: Math.sin(a) * r };
}

const SPAWN_SAFE_DIST = 260;
const SPAWN_SHIELD_TICKS = TICK_RATE * 2; // 2s of invulnerability after spawning
function isSpawnSafe(x, y) {
  const d2 = SPAWN_SAFE_DIST * SPAWN_SAFE_DIST;
  for (const s of snakes.values()) {
    if (!s.alive) continue;
    for (let i = 0; i < s.points.length; i += 2) if (dist2(x, y, s.points[i].x, s.points[i].y) < d2) return false;
    for (let i = 0; i < s.trailCells.length; i += 3) { const c = cellCenter(s.trailCells[i]); if (dist2(x, y, c.x, c.y) < d2) return false; }
  }
  return true;
}
function findSafeSpawn(preferred, jitter) {
  for (let attempt = 0; attempt < 40; attempt++) {
    const spread = jitter * (1 + attempt * 0.35);
    const c = preferred
      ? { x: preferred.x + rand(-spread, spread), y: preferred.y + rand(-spread, spread) }
      : randomPointInWorld(0.55);
    if (c.x * c.x + c.y * c.y > (WORLD_RADIUS * 0.9) ** 2) continue;
    if (isSpawnSafe(c.x, c.y)) return c;
  }
  return preferred || randomPointInWorld(0.55);
}

function spawnDiamond(at, forceBrand) {
  const id = 'd' + (diamondSeq++);
  const p = at || randomPointInWorld();
  const brandsAlive = [...diamonds.values()].filter(d => d.brand).length;

  let brandDef = forceBrand;
  if (!brandDef && brandsAlive < MAX_BRAND_DIAMONDS_ALIVE && Math.random() < BRAND_DIAMOND_CHANCE) {
    brandDef = BRAND_DIAMONDS[Math.floor(Math.random() * BRAND_DIAMONDS.length)];
  }

  if (brandDef) {
    const value = rand(DIAMOND_MAX_VALUE, DIAMOND_MAX_VALUE * 1.4) * brandDef.valueMult;
    diamonds.set(id, {
      id, x: p.x, y: p.y, value,
      brand: brandDef.brand, label: brandDef.label, color: brandDef.color, big: true,
    });
    io.emit('brandDiamondSpawned', { label: brandDef.label, brand: brandDef.brand, x: p.x, y: p.y });
    return id;
  }

  // Product-launch diamonds only start appearing once someone in the arena holds a Crown.
  if (!at && anyoneCrowned()) {
    const productsAlive = [...diamonds.values()].filter(d => d.product).length;
    if (productsAlive < MAX_PRODUCT_DIAMONDS_ALIVE && Math.random() < PRODUCT_DIAMOND_CHANCE) {
      const def = PRODUCT_DIAMONDS[Math.floor(Math.random() * PRODUCT_DIAMONDS.length)];
      const value = rand(DIAMOND_MAX_VALUE, DIAMOND_MAX_VALUE * 1.4) * def.valueMult;
      diamonds.set(id, { id, x: p.x, y: p.y, value, product: def.product, label: def.label, short: def.short, color: def.color, big: true });
      io.emit('productDiamondSpawned', { label: def.label, product: def.product });
      return id;
    }
  }

  const big = Math.random() < 0.08;
  const value = big ? rand(DIAMOND_MAX_VALUE * 1.6, DIAMOND_MAX_VALUE * 2.4) : rand(DIAMOND_MIN_VALUE, DIAMOND_MAX_VALUE);
  diamonds.set(id, { id, x: p.x, y: p.y, value, big });
  return id;
}

function ensureDiamondCount() {
  while (diamonds.size < DIAMOND_TARGET_COUNT) spawnDiamond();
}

class Snake {
  constructor(id, name, color, isBot, clientKey) {
    this.id = id;
    this.name = (name || 'Anaconda').slice(0, 16);
    this.color = color || COLORS[Math.floor(Math.random() * COLORS.length)];
    this.isBot = !!isBot;
    this.alive = true;
    this.boosting = false;
    // Returning players respawn near their AI Factory; new players get a fresh home.
    const existing = clientKey && players.get(clientKey);
    const spawn = findSafeSpawn(existing ? existing.home : null, 120);
    this.shield = SPAWN_SHIELD_TICKS;
    this.x = spawn.x;
    this.y = spawn.y;
    this.player = getOrCreatePlayer(clientKey, this.name, this.color, spawn, this.isBot);
    this.angle = rand(0, Math.PI * 2);
    this.targetAngle = this.angle;
    this.length = START_LENGTH;
    this.points = [{ x: this.x, y: this.y }];
    this.deaths = 0;
    this.kills = 0;
    this.joinedAt = Date.now();
    this.botTimer = 0;
    this.loopTicks = 0;
    this.loopDir = 1;
    // Territory (paper.io-style): each snake gets a persistent numeric owner
    // code (territory outlives death, like real paper.io ground), a home
    // patch seeded at spawn, and a live trail while outside owned ground.
    this.code = this.player.code;
    codeToColor.set(this.code, this.color);
    this.inTerritory = true;
    this.trailCells = [];
    emitTerritoryChange(this, seedHomeTerritory(this));
  }

  get headRadius() { return headRadiusForLength(this.length); }

  desiredPointCount() {
    return Math.max(6, Math.floor(this.length / SEGMENT_SPACING));
  }

  turnRate() {
    // bigger snakes turn a bit slower
    return MAX_TURN_RATE_BASE * clamp(1.15 - this.length / 4000, 0.45, 1.15);
  }

  step() {
    if (!this.alive) return;
    if (this.shield > 0) this.shield -= 1;
    this.angle = angleLerp(this.angle, this.targetAngle, this.turnRate());

    let speed = BASE_SPEED;
    if (this.boosting && this.length > START_LENGTH * 0.6) {
      speed *= BOOST_MULT;
      // Pure dash: only drains length, no side-effect diamonds. (A diamond
      // used to be dropped here as a "boost trail" cost, but since it spawned
      // right under the snake's own head it got vacuumed up by the very same
      // tick's diamond-consumption pass, causing net GROWTH from boosting —
      // effectively free length. Removed; boosting should never be a way to
      // grow without eating diamonds.)
      this.length = Math.max(START_LENGTH * 0.5, this.length - BOOST_DRAIN_PER_TICK);
    } else {
      this.boosting = false;
    }

    this.x += Math.cos(this.angle) * speed;
    this.y += Math.sin(this.angle) * speed;

    this.points.unshift({ x: this.x, y: this.y });
    const desired = this.desiredPointCount();
    if (this.points.length > desired) this.points.length = desired;

    // world boundary — die if outside the circle
    if (this.x * this.x + this.y * this.y > WORLD_RADIUS * WORLD_RADIUS) {
      this.alive = false;
      this.deathReason = 'boundary';
      return;
    }

    this.updateTerritory();
  }

  // paper.io-style: leave a trail while outside your own ground; re-entering
  // your territory flood-fills and claims whatever the trail enclosed.
  updateTerritory() {
    const { col, row } = worldToCell(this.x, this.y);
    const idx = cellIndex(col, row);
    if (gridOwnerCode[idx] === this.code) {
      if (this.trailCells.length > 0) {
        emitTerritoryChange(this, floodClaim(this));
      }
      this.inTerritory = true;
    } else {
      this.inTerritory = false;
      const last = this.trailCells[this.trailCells.length - 1];
      if (last !== idx && this.trailCells.length < TRAIL_CAP) {
        this.trailCells.push(idx);
      }
    }
  }

  bodySamples(skipNearHead = 4) {
    // sample every other point after a safety gap near the head to reduce cost
    const out = [];
    for (let i = skipNearHead; i < this.points.length; i += 2) out.push(this.points[i]);
    return out;
  }

  // Points far enough from the head that a normal turn can't produce a false
  // self-collision, used for the classic "don't bite your own tail" rule.
  selfBodySamples() {
    const safeGapUnits = this.headRadius * 3.2;
    const skip = Math.max(6, Math.ceil(safeGapUnits / SEGMENT_SPACING));
    return this.bodySamples(skip);
  }

  simpleBotAI() {
    const distFromCenter0 = Math.hypot(this.x, this.y);

    // Land-grab mode: bots periodically carve a wide loop and return home, so
    // territory actually gets claimed/contested even in a bot-heavy arena.
    if (this.loopTicks > 0 && distFromCenter0 < WORLD_RADIUS * 0.85) {
      this.loopTicks -= 1;
      this.targetAngle += this.loopDir * 0.045;
      if (this.loopTicks === 0) {
        // head home to close the loop
        this.targetAngle = Math.atan2(this.player.home.y - this.y, this.player.home.x - this.x);
        this.botTimer = 90;
      }
      return;
    }

    this.botTimer -= 1;
    if (this.botTimer > 0) return;
    this.botTimer = 20 + Math.floor(Math.random() * 30);

    if (this.inTerritory && Math.random() < 0.12) {
      this.loopTicks = 90 + Math.floor(Math.random() * 90);
      this.loopDir = Math.random() < 0.5 ? -1 : 1;
      this.targetAngle = rand(0, Math.PI * 2);
      return;
    }

    // steer toward the nearest diamond, but stay inside the world and avoid edges
    let best = null, bestD = Infinity;
    for (const d of diamonds.values()) {
      const dd = dist2(this.x, this.y, d.x, d.y);
      if (dd < bestD) { bestD = dd; best = d; }
    }
    const distFromCenter = Math.hypot(this.x, this.y);
    if (distFromCenter > WORLD_RADIUS * 0.85) {
      this.targetAngle = Math.atan2(-this.y, -this.x) + rand(-0.3, 0.3);
    } else if (best) {
      this.targetAngle = Math.atan2(best.y - this.y, best.x - this.x) + rand(-0.15, 0.15);
    } else {
      this.targetAngle += rand(-0.5, 0.5);
    }
    this.boosting = Math.random() < 0.03;
  }

  toDeathDiamonds() {
    for (let i = 0; i < this.points.length; i += DEATH_DIAMOND_STRIDE) {
      const p = this.points[i];
      spawnDiamond({ x: p.x + rand(-6, 6), y: p.y + rand(-6, 6) });
    }
  }
}

function createSnake(id, name, color, isBot, clientKey) {
  const s = new Snake(id, name, color, isBot, clientKey);
  snakes.set(id, s);
  return s;
}

function removeSnake(id) {
  const s = snakes.get(id);
  // Bots get throwaway player records; drop them unless they built something worth keeping.
  if (s && s.isBot && s.player && s.player.collectedBrands.size === 0) players.delete(s.player.clientKey);
  snakes.delete(id);
}

// ------------------------------- Bots ----------------------------------------
let botSeq = 0;
function maintainBots() {
  const humanCount = [...snakes.values()].filter(s => !s.isBot).length;
  const botCount = [...snakes.values()].filter(s => s.isBot).length;
  const wanted = Math.max(0, Math.min(BOT_TARGET_COUNT, BOT_TARGET_COUNT - Math.floor(humanCount / 2) + botCount));
  if (botCount < BOT_TARGET_COUNT) {
    const id = 'bot_' + (botSeq++);
    const names = ['Kaa', 'Slytherin', 'Boa', 'Viper', 'Cobra', 'Python', 'Mamba', 'Sidewinder'];
    createSnake(id, names[Math.floor(Math.random() * names.length)], undefined, true);
  }
}

// ---------------------------- Collision / Tick --------------------------------
function tick() {
  for (const s of snakes.values()) {
    if (s.isBot && s.alive) s.simpleBotAI();
    const wasAlive = s.alive;
    s.step();
    if (wasAlive && !s.alive && s.deathReason === 'boundary') {
      s.deaths += 1;
      s.toDeathDiamonds();
      const sock = io.sockets.sockets.get(s.id);
      if (sock) sock.emit('died', { killer: null });
    }
  }

  // Diamond consumption
  for (const s of snakes.values()) {
    if (!s.alive) continue;
    const hr = s.headRadius;
    for (const d of diamonds.values()) {
      const rr = hr + ((d.brand || d.product) ? 16 : 7);
      if (dist2(s.x, s.y, d.x, d.y) <= rr * rr) {
        s.length += d.value;
        diamonds.delete(d.id);
        const p = s.player;

        if (d.brand) {
          const isNew = !p.collectedBrands.has(d.brand);
          p.collectedBrands.add(d.brand);
          io.emit('brandDiamondCollected', { name: s.name, label: d.label, brand: d.brand, newBuilding: isNew });
          // The Acquisition Trifecta (cumulative across lives) -> permanent Crown.
          if (!p.crown && ALL_BRAND_KEYS.every(b => p.collectedBrands.has(b))) {
            p.crown = true;
            s.length += TRIFECTA_LENGTH_BONUS;
            hallOfFame.unshift({ name: s.name, type: 'trifecta', at: Date.now() });
            if (hallOfFame.length > 20) hallOfFame.length = 20;
            io.emit('trifectaWin', { name: s.name });
          }
        } else if (d.product) {
          if (p.crown) {
            const isNew = !p.unlockedProducts.has(d.product);
            p.unlockedProducts.add(d.product);
            if (isNew) s.length += PRODUCT_LENGTH_BONUS;
            io.emit('productDiamondCollected', { name: s.name, label: d.label, product: d.product, newBuilding: isNew });
            if (isNew && ALL_PRODUCT_KEYS.every(k => p.unlockedProducts.has(k))) {
              hallOfFame.unshift({ name: s.name, type: 'fullstack', at: Date.now() });
              if (hallOfFame.length > 20) hallOfFame.length = 20;
              io.emit('fullStackWin', { name: s.name });
            }
          } else {
            const sock = io.sockets.sockets.get(s.id);
            if (sock) sock.emit('productLocked', { label: d.label });
          }
        }
      }
    }
  }
  ensureDiamondCount();

  // Snake-vs-snake collisions (head touches another body => head owner dies)
  const alive = [...snakes.values()].filter(s => s.alive);
  const toKill = new Map(); // id -> killerName|reason

  // Classic rule: biting your own tail kills you too.
  for (const a of alive) {
    if (a.shield > 0) continue;
    const ar = a.headRadius;
    const rr = ar + ar * 0.9;
    for (const p of a.selfBodySamples()) {
      if (dist2(a.x, a.y, p.x, p.y) <= rr * rr) {
        toKill.set(a.id, a.name);
        break;
      }
    }
  }

  // Territory-aware biting (head of a touches body of b):
  //  - b outside its own land  -> b is exposed: b dies, a gets the kill.
  //  - b inside its own land   -> b is protected: the biter (a) dies.
  //  - head-to-head            -> whoever is on home ground survives; both die if neither/both.
  for (const a of alive) {
    if (toKill.has(a.id) || a.shield > 0) continue;
    const ar = a.headRadius;
    for (const b of alive) {
      if (a === b || b.shield > 0 || toKill.has(b.id)) continue;
      const br = b.headRadius;
      const hh = ar + br;
      if (dist2(a.x, a.y, b.x, b.y) <= hh * hh) {
        if (a.inTerritory && !b.inTerritory) { toKill.set(b.id, a.name); a.kills += 1; }
        else if (b.inTerritory && !a.inTerritory) { toKill.set(a.id, b.name); b.kills += 1; }
        else { toKill.set(a.id, b.name); toKill.set(b.id, a.name); }
        continue;
      }
      const rr = ar + br * 0.9;
      for (const p of b.bodySamples()) {
        if (dist2(a.x, a.y, p.x, p.y) <= rr * rr) {
          if (b.inTerritory) { toKill.set(a.id, 'fortress:' + b.name); b.kills += 1; }
          else { toKill.set(b.id, a.name); a.kills += 1; }
          break;
        }
      }
      if (toKill.has(a.id)) break;
    }
  }

  for (const [id, killer] of toKill.entries()) {
    const s = snakes.get(id);
    if (!s || !s.alive) continue;
    s.alive = false;
    s.deathReason = killer;
    s.deaths += 1;
    s.toDeathDiamonds();
    const sock = io.sockets.sockets.get(id);
    if (sock) sock.emit('died', { killer });
  }

  // remove dead bots (respawn fresh), keep dead humans until they choose respawn
  for (const s of [...snakes.values()]) {
    if (!s.alive && s.isBot) removeSnake(s.id);
  }
  maintainBots();

  broadcast();
}

function broadcast() {
  const snakePayload = [...snakes.values()].map(s => ({
    id: s.id,
    name: s.name,
    color: s.color,
    alive: s.alive,
    length: Math.round(s.length),
    headRadius: s.headRadius,
    points: s.points, // [{x,y}], head-first
    hasCrown: s.player.crown,
    shield: s.shield > 0,
    collectedBrands: [...s.player.collectedBrands],
    unlockedProducts: [...s.player.unlockedProducts],
    factoryLevel: factoryLevel(s.player),
    home: s.player.home,
    trail: s.trailCells.length ? s.trailCells.map(cellCenter) : [],
  }));
  const diamondPayload = [...diamonds.values()].map(d => ({
    id: d.id, x: d.x, y: d.y, value: Math.round(d.value), big: d.big,
    brand: d.brand, product: d.product, short: d.short, label: d.label, color: d.color,
  }));

  const leaderboard = [...snakes.values()]
    .filter(s => s.alive)
    .sort((a, b) => b.length - a.length)
    .slice(0, 10)
    .map(s => ({ name: s.name, length: Math.round(s.length), isBot: s.isBot, hasCrown: s.player.crown, factoryLevel: factoryLevel(s.player) }));

  io.emit('state', {
    t: Date.now(),
    worldRadius: WORLD_RADIUS,
    snakes: snakePayload,
    diamonds: diamondPayload,
    hallOfFame: hallOfFame.slice(0, 5),
    factories: [...players.values()].filter(p => !p.clientKey.startsWith('anon_') || p.collectedBrands.size > 0).map(p => ({
      name: p.name, color: p.color, home: p.home, hasCrown: p.crown,
      collectedBrands: [...p.collectedBrands], unlockedProducts: [...p.unlockedProducts], factoryLevel: factoryLevel(p),
    })),
    leaderboard,
    playerCount: [...snakes.values()].filter(s => !s.isBot).length,
  });
}

ensureDiamondCount();
setInterval(tick, TICK_MS);

function territorySnapshot() {
  const cells = [];
  for (let i = 0; i < CELL_COUNT; i++) {
    const code = gridOwnerCode[i];
    if (code !== 0) cells.push({ idx: i, color: codeToColor.get(code) || '#3EB049' });
  }
  return cells;
}

function buildWelcomePayload(socket, s) {
  return {
    id: socket.id,
    worldRadius: WORLD_RADIUS,
    you: { x: s.x, y: s.y, angle: s.angle, color: s.color, name: s.name },
    territory: { cellSize: CELL_SIZE, gridDim: GRID_DIM, cells: territorySnapshot() },
  };
}

// ------------------------------ Networking -----------------------------------
io.on('connection', (socket) => {
  socket.on('join', ({ name, color, clientKey }) => {
    if (snakes.has(socket.id)) removeSnake(socket.id);
    const s = createSnake(socket.id, name, color, false, clientKey);
    socket.emit('welcome', buildWelcomePayload(socket, s));
  });

  socket.on('input', ({ angle, boosting }) => {
    const s = snakes.get(socket.id);
    if (!s || !s.alive) return;
    if (typeof angle === 'number' && isFinite(angle)) s.targetAngle = angle;
    s.boosting = !!boosting;
  });

  socket.on('respawn', ({ name, color, clientKey }) => {
    const existing = snakes.get(socket.id);
    const prevName = existing ? existing.name : name;
    const prevColor = existing ? existing.color : color;
    removeSnake(socket.id);
    const s = createSnake(socket.id, name || prevName, color || prevColor, false, clientKey);
    socket.emit('welcome', buildWelcomePayload(socket, s));
  });

  socket.on('disconnect', () => {
    removeSnake(socket.id);
  });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`ANACONDAE server listening on http://localhost:${PORT}`);
});
