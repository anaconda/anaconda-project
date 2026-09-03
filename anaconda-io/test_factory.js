// E2E: hunt brand diamonds -> Crown; die; respawn with same clientKey -> Crown/Factory persist;
// then hunt product diamonds -> Factory grows.
const { io } = require('socket.io-client');
const sock = io('http://localhost:3001');
const clientKey = 'test_' + Date.now();
let me = null, diamonds = [], factories = [], log = [];
const say = (m) => { log.push(m); console.log(m); };

sock.on('connect', () => sock.emit('join', { name: 'Founder', color: '#08CA4A', clientKey }));
sock.on('welcome', () => say('joined'));
sock.on('state', (s) => { me = s.snakes.find(x => x.id === sock.id); diamonds = s.diamonds; factories = s.factories; });
sock.on('trifectaWin', (d) => say('CROWN: ' + JSON.stringify(d)));
sock.on('productDiamondCollected', (d) => say('PRODUCT: ' + JSON.stringify(d)));
sock.on('fullStackWin', (d) => say('FULL STACK: ' + JSON.stringify(d)));
sock.on('died', (d) => {
  say('died -> ' + JSON.stringify(d) + ' | crown before respawn=' + (me && me.hasCrown) + ' brands=' + JSON.stringify(me && me.collectedBrands));
  setTimeout(() => sock.emit('respawn', { name: 'Founder', color: '#08CA4A', clientKey }), 300);
});

let killedOnce = false; let lastTarget=null, lastRetarget=0, spawnAt=Date.now();
sock.on('welcome', ()=>{ spawnAt=Date.now(); });
setInterval(() => {
  if (!me || !me.alive) return;
  const head = me.points[0];
  const wantBrands = ['outerbounds', 'kilo', 'enkrypt'].filter(b => !me.collectedBrands.includes(b));
  const wantProds = ['ana-cli', 'main-x', 'anaconda-mcp'].filter(p => !me.unlockedProducts.includes(p));
  let targets = diamonds.filter(d => (d.brand && wantBrands.includes(d.brand)) || (me.hasCrown && d.product && wantProds.includes(d.product)));
  // once crowned and not yet killed, suicide into the border to prove persistence
  if (me.hasCrown && !killedOnce) { killedOnce = true; sock.emit('input', { angle: Math.atan2(head.y, head.x), boosting: true }); return; }
  if (killedOnce && me.alive && me.length < 40) return;
  if (Date.now() - spawnAt < 1500) { sock.emit('input', { angle: 0, boosting: false }); return; }
  if (targets.length === 0) targets = diamonds;
  const now = Date.now();
  if (!lastTarget || !diamonds.find(d => d.id === lastTarget.id) || now - lastRetarget > 800) {
    let best = null, bd = Infinity;
    for (const d of targets) { const dd = (d.x - head.x) ** 2 + (d.y - head.y) ** 2; if (dd < bd) { bd = dd; best = d; } }
    lastTarget = best; lastRetarget = now;
  }
  if (lastTarget) sock.emit('input', { angle: Math.atan2(lastTarget.y - head.y, lastTarget.x - head.x), boosting: false });
}, 60);

setTimeout(() => {
  const mine = factories.find(f => f.name === 'Founder');
  say('FINAL me: crown=' + (me && me.hasCrown) + ' brands=' + JSON.stringify(me && me.collectedBrands) + ' products=' + JSON.stringify(me && me.unlockedProducts) + ' level=' + (me && me.factoryLevel));
  say('FINAL factory record: ' + JSON.stringify(mine));
  process.exit(0);
}, 110000);
