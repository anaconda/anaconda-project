import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { fileURLToPath } from 'node:url';

import { StoreError } from './store.mjs';
import { answerInput, authorInput, questionInput } from './validate.mjs';

const PUBLIC_DIR = fileURLToPath(new URL('../public/', import.meta.url));

/** Only these paths are served from disk; anything else is rejected. */
const STATIC_FILES = new Map([
  ['/', 'index.html'],
  ['/index.html', 'index.html'],
  ['/styles.css', 'styles.css'],
  ['/app.js', 'app.js'],
  ['/favicon.svg', 'favicon.svg'],
]);

const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
};

const MAX_BODY_BYTES = 64 * 1024;

const SECURITY_HEADERS = {
  'Content-Security-Policy':
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; " +
    "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
};

const ANSWER_PATH = /^\/api\/questions\/(\d+)\/answers$/;
const DELETE_ANSWER_PATH = /^\/api\/answers\/(\d+)$/;

const staticCache = new Map();

async function staticBody(name) {
  if (!staticCache.has(name)) {
    staticCache.set(name, await readFile(PUBLIC_DIR + name, 'utf8'));
  }
  return staticCache.get(name);
}

function sendJson(res, status, payload, headers = {}) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    ...SECURITY_HEADERS,
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
    ...headers,
  });
  res.end(body);
}

/** Read and parse a JSON request body. @returns {Promise<Record<string, unknown>>} */
async function readJsonBody(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) {
      throw new StoreError('That request is too large.', 413);
    }
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  const raw = Buffer.concat(chunks).toString('utf8');
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new StoreError('Request body must be valid JSON.', 400);
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new StoreError('Request body must be a JSON object.', 400);
  }
  return parsed;
}

/**
 * @param {import('./store.mjs').Store} store
 * @param {{logger?: Pick<Console, 'error'>}} [options]
 */
export function createApp(store, options = {}) {
  const logger = options.logger ?? console;

  /** @param {import('node:http').IncomingMessage} req @param {import('node:http').ServerResponse} res */
  return createServer(async (req, res) => {
    const { pathname } = new URL(req.url ?? '/', 'http://localhost');
    const method = req.method ?? 'GET';

    try {
      if (pathname.startsWith('/api/')) {
        await handleApi(store, req, res, pathname, method);
        return;
      }

      const file = STATIC_FILES.get(pathname);
      if (!file) {
        sendJson(res, 404, { error: 'Not found' });
        return;
      }
      if (method !== 'GET' && method !== 'HEAD') {
        sendJson(res, 405, { error: 'Method not allowed' }, { Allow: 'GET, HEAD' });
        return;
      }
      const body = await staticBody(file);
      const ext = file.slice(file.lastIndexOf('.'));
      res.writeHead(200, {
        ...SECURITY_HEADERS,
        'Content-Type': CONTENT_TYPES[ext] ?? 'application/octet-stream',
        'Content-Length': Buffer.byteLength(body),
        'Cache-Control': 'no-cache',
      });
      res.end(method === 'HEAD' ? undefined : body);
    } catch (err) {
      if (err instanceof StoreError) {
        sendJson(res, err.status, { error: err.message });
        return;
      }
      logger.error('Unhandled request error:', err);
      sendJson(res, 500, { error: 'Something went wrong on the server.' });
    }
  });
}

async function handleApi(store, req, res, pathname, method) {
  if (pathname === '/api/health') {
    if (method !== 'GET') return sendJson(res, 405, { error: 'Method not allowed' }, { Allow: 'GET' });
    return sendJson(res, 200, { ok: true });
  }

  if (pathname === '/api/questions') {
    if (method === 'GET') {
      return sendJson(res, 200, {
        questions: store.listQuestions(),
        stats: store.stats(),
      });
    }
    if (method === 'POST') {
      const payload = await readJsonBody(req);
      const input = questionInput(payload);
      const id = store.addQuestion(input);
      return sendJson(res, 201, { ok: true, id }, { Location: `/api/questions/${id}` });
    }
    return sendJson(res, 405, { error: 'Method not allowed' }, { Allow: 'GET, POST' });
  }

  const answerMatch = ANSWER_PATH.exec(pathname);
  if (answerMatch) {
    if (method !== 'POST') {
      return sendJson(res, 405, { error: 'Method not allowed' }, { Allow: 'POST' });
    }
    const questionId = Number(answerMatch[1]);
    const payload = await readJsonBody(req);
    const id = store.addAnswer(questionId, answerInput(payload));
    return sendJson(res, 201, { ok: true, id });
  }

  const deleteMatch = DELETE_ANSWER_PATH.exec(pathname);
  if (deleteMatch) {
    if (method !== 'DELETE') {
      return sendJson(res, 405, { error: 'Method not allowed' }, { Allow: 'DELETE' });
    }
    const payload = await readJsonBody(req);
    store.deleteAnswer(Number(deleteMatch[1]), authorInput(payload));
    return sendJson(res, 200, { ok: true });
  }

  return sendJson(res, 404, { error: 'Not found' });
}
