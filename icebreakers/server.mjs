import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

import { createApp } from './src/http.mjs';
import { Store } from './src/store.mjs';

const PORT = Number(process.env.PORT ?? 3000);
const HOST = process.env.HOST ?? '0.0.0.0';
const DB_PATH = process.env.ICEBREAKER_DB ?? resolve(import.meta.dirname, 'data/icebreakers.db');

if (DB_PATH !== ':memory:') {
  mkdirSync(dirname(DB_PATH), { recursive: true });
}

const store = new Store(DB_PATH);
const server = createApp(store);

server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`Port ${PORT} is already in use. Start with PORT=<free port> npm start`);
  } else {
    console.error(err);
  }
  store.close();
  process.exit(1);
});

server.listen(PORT, HOST, () => {
  const { port } = server.address();
  console.log(`Ice Breakers running at http://localhost:${port}`);
  console.log(`Database: ${DB_PATH}`);
});

let shuttingDown = false;
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    if (shuttingDown) return;
    shuttingDown = true;
    server.close(() => {
      store.close();
      process.exit(0);
    });
    setTimeout(() => process.exit(0), 3000).unref();
  });
}
