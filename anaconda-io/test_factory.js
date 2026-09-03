// E2E: funding -> landmarks -> integration -> Trusted Foundation -> products -> shipping.
const { io } = require('socket.io-client');
const URL = 'http://localhost:3001';
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

function eater(name) {
  const s = io(URL); let me = null, comps = [];
  s.on('connect', () => s.emit('join', { name, color: '#3D7EA6', clientKey: name + Date.now() }));
  s.on('state', (st) => { me = st.snakes.find(x => x.id === s.id); comps = st.components; });
  s.on('died', () => setTimeout(() => s.emit('respawn', { name, color: '#3D7EA6', clientKey: name + Date.now() }), 2700));
  let target = null, lastPick = 0;
  setInterval(() => {
    if (!me || !me.alive) return; const h = me.points[0];
    if (!target || !comps.find(c => c.id === target.id) || Date.now() - lastPick > 700) {
      let bd = Infinity; target = null;
      for (const c of comps) { if (c.p) continue; const d = (c.x - h.x) ** 2 + (c.y - h.y) ** 2; if (d < bd) { bd = d; target = c; } }
      lastPick = Date.now();
    }
    if (target) s.emit('input', { angle: Math.atan2(target.y - h.y, target.x - h.x), boosting: Math.hypot(h.x, h.y) < 1800 && me.inTerritory === false && me.length > 40 });
  }, 60);
  return s;
}

const F = io(URL); const fkey = 'founder_' + Date.now();
let me = null, st = null, phase = 'wait', phaseT = 0, targetAcq = null;
F.on('connect', () => F.emit('join', { name: 'Founder', color: '#08CA4A', clientKey: fkey }));
F.on('state', (s) => { st = s; me = s.snakes.find(x => x.id === F.id); });
F.on('banner', (b) => log('BANNER:', b.text, b.sub || ''));
F.on('capability', (c) => log('CAPABILITY:', c.capability));
F.on('died', (d) => { log('Founder died:', d.reason, d.killer || ''); phase = 'wait'; setTimeout(() => F.emit('respawn', { name: 'Founder', color: '#08CA4A', clientKey: fkey }), 2700); });
F.on('shipment', (d) => { if (d.id === F.id) log('SHIPMENT', d.tokens.toFixed(1) + 'B'); });
F.on('building', (d) => log('BUILT:', d.name));
F.on('buildFail', (d) => log('build fail:', d.why));
setInterval(() => { if (me && me.alive && me.crown) F.emit('build'); }, 5000);

for (let i = 0; i < 6; i++) eater('Eater' + i);

// Founder strategy: go to a funded, un-integrated landmark; circle it at ~140 radius (trail), then head to own floor to close.
setInterval(() => {
  if (!me || !me.alive || !st) return;
  const h = me.points[0];
  const now = Date.now();
  if (phase === 'wait') {
    // grow a bit at home first, and wait for a landmark I don't hold
    targetAcq = st.acquisitions.find(a => a.funded && !me.caps.includes(a.key));
    if (targetAcq) { phase = 'approach'; phaseT = now; }
    else { // gentle circle on home to eat nearby without leaving much
      F.emit('input', { angle: Math.atan2(me.home.y - h.y, me.home.x - h.x) + Math.PI / 2 + (120 - Math.hypot(h.x - me.home.x, h.y - me.home.y)) * 0.01, boosting: false });
    }
    return;
  }
  const site = targetAcq.site, d = Math.hypot(h.x - site.x, h.y - site.y);
  if (phase === 'approach') {
    F.emit('input', { angle: Math.atan2(site.y - h.y, site.x - h.x), boosting: d > 500 });
    if (d < 150) { phase = 'circle'; phaseT = now; }
  } else if (phase === 'circle') {
    const ang = Math.atan2(h.y - site.y, h.x - site.x);
    F.emit('input', { angle: ang + Math.PI / 2 + (140 - d) * 0.01, boosting: false });
    if (now - phaseT > 7000) { phase = 'home'; phaseT = now; }
  } else if (phase === 'home') {
    F.emit('input', { angle: Math.atan2(me.home.y - h.y, me.home.x - h.x), boosting: true });
    if ((me.inTerritory && me.floor > 25) || now - phaseT > 40000) { phase = 'wait'; }
  }
}, 60);

setInterval(() => {
  if (!me || !st) return;
  log(`funding ${st.funding.dealName || 'done'} ${st.funding.units.toFixed(1)}/${st.funding.target} | founder caps=${JSON.stringify(me.caps)} floor=${me.floor} len=${me.length} products=${JSON.stringify(me.products)} tokens=${me.tokens} crown=${me.crown}`);
}, 20000);

setTimeout(() => { log('END'); process.exit(0); }, 235000);
