import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';

import { createApp } from '../src/http.mjs';
import { Store } from '../src/store.mjs';

let store;
let server;
let base;

before(async () => {
  store = new Store(':memory:');
  server = createApp(store, { logger: { error() {} } });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = 'http://127.0.0.1:' + server.address().port;
});

after(async () => {
  await new Promise((resolve) => server.close(resolve));
  store.close();
});

async function call(path, { method = 'GET', body, raw } = {}) {
  const res = await fetch(base + path, {
    method,
    headers: body === undefined && raw === undefined ? {} : { 'Content-Type': 'application/json' },
    body: raw ?? (body === undefined ? undefined : JSON.stringify(body)),
  });
  const text = await res.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    json = undefined;
  }
  return { res, json, text };
}

test('seeds the question set from the source article', async () => {
  const { res, json } = await call('/api/questions');
  assert.equal(res.status, 200);
  assert.equal(json.questions.length, 36);
  assert.equal(json.stats.answers, 0);
  assert.equal(json.stats.answered, 0);
  assert.match(json.questions[0].text, /most famous person/);
  assert.equal(json.questions[0].createdBy, 'Todd Caponi');
  assert.equal(json.questions[0].category, 'classic');
  assert.equal(json.questions[35].category, 'crowdsourced');
  assert.deepEqual(json.questions[0].answers, []);
});

test('adds a question and returns it in the list', async () => {
  const created = await call('/api/questions', {
    method: 'POST',
    body: { text: 'What is the best meal you have ever cooked?', createdBy: 'Sam' },
  });
  assert.equal(created.res.status, 201);
  assert.equal(created.json.ok, true);
  assert.match(created.res.headers.get('location'), /^\/api\/questions\/\d+$/);

  const { json } = await call('/api/questions');
  const added = json.questions.find((q) => q.id === created.json.id);
  assert.ok(added);
  assert.equal(added.createdBy, 'Sam');
  assert.equal(added.category, 'team');
});

test('rejects a duplicate question', async () => {
  const first = await call('/api/questions', {
    method: 'POST',
    body: { text: 'Is a hot dog a sandwich?', createdBy: 'Sam' },
  });
  assert.equal(first.res.status, 201);

  const second = await call('/api/questions', {
    method: 'POST',
    body: { text: '  is a hot dog a SANDWICH?!  ', createdBy: 'Alex' },
  });
  assert.equal(second.res.status, 409);
  assert.match(second.json.error, /already on the board/);
});

test('defaults a question author to Anonymous', async () => {
  const { res, json } = await call('/api/questions', {
    method: 'POST',
    body: { text: 'What is your go-to karaoke song?' },
  });
  assert.equal(res.status, 201);

  const list = await call('/api/questions');
  const added = list.json.questions.find((q) => q.id === json.id);
  assert.equal(added.createdBy, 'Anonymous');
});

test('validates question input', async () => {
  const empty = await call('/api/questions', { method: 'POST', body: { text: '   ' } });
  assert.equal(empty.res.status, 400);
  assert.match(empty.json.error, /Question is required/);

  const tooLong = await call('/api/questions', {
    method: 'POST',
    body: { text: 'x'.repeat(201) },
  });
  assert.equal(tooLong.res.status, 400);
  assert.match(tooLong.json.error, /200 characters or fewer/);

  const notJson = await call('/api/questions', { method: 'POST', raw: 'not json' });
  assert.equal(notJson.res.status, 400);
});

test('accepts answers and groups them under their question', async () => {
  const { json: created } = await call('/api/questions', {
    method: 'POST',
    body: { text: 'What was your first screen name in this app test?', createdBy: 'Sam' },
  });

  const answer = await call('/api/questions/' + created.id + '/answers', {
    method: 'POST',
    body: { author: 'Sam', body: 'sk8erboi99' },
  });
  assert.equal(answer.res.status, 201);

  const list = await call('/api/questions');
  const question = list.json.questions.find((q) => q.id === created.id);
  assert.equal(question.answers.length, 1);
  assert.equal(question.answers[0].author, 'Sam');
  assert.equal(question.answers[0].body, 'sk8erboi99');
  assert.ok(list.json.stats.answered >= 1);
});

test('rejects answers for unknown questions and empty bodies', async () => {
  const missing = await call('/api/questions/999999/answers', {
    method: 'POST',
    body: { author: 'Sam', body: 'hello' },
  });
  assert.equal(missing.res.status, 404);

  const { json: created } = await call('/api/questions', {
    method: 'POST',
    body: { text: 'What is the app test question about empty answers?' },
  });
  const empty = await call('/api/questions/' + created.id + '/answers', {
    method: 'POST',
    body: { author: 'Sam', body: '   ' },
  });
  assert.equal(empty.res.status, 400);
  assert.match(empty.json.error, /Answer is required/);

  const noAuthor = await call('/api/questions/' + created.id + '/answers', {
    method: 'POST',
    body: { body: 'missing author' },
  });
  assert.equal(noAuthor.res.status, 400);
  assert.match(noAuthor.json.error, /Your name is required/);
});

test('lets an author retract their own answer only', async () => {
  const { json: created } = await call('/api/questions', {
    method: 'POST',
    body: { text: 'Retraction behaviour check question?' },
  });
  const { json: answer } = await call('/api/questions/' + created.id + '/answers', {
    method: 'POST',
    body: { author: 'Sam', body: 'temporary' },
  });

  const wrongAuthor = await call('/api/answers/' + answer.id, {
    method: 'DELETE',
    body: { author: 'Alex' },
  });
  assert.equal(wrongAuthor.res.status, 403);

  const own = await call('/api/answers/' + answer.id, {
    method: 'DELETE',
    body: { author: 'sam' },
  });
  assert.equal(own.res.status, 200);

  const list = await call('/api/questions');
  const question = list.json.questions.find((q) => q.id === created.id);
  assert.equal(question.answers.length, 0);

  const missing = await call('/api/answers/' + answer.id, {
    method: 'DELETE',
    body: { author: 'Sam' },
  });
  assert.equal(missing.res.status, 404);
});

test('serves the app shell and static assets', async () => {
  const page = await call('/');
  assert.equal(page.res.status, 200);
  assert.match(page.res.headers.get('content-type'), /text\/html/);
  assert.match(page.text, /Ice Breakers/);
  assert.match(page.res.headers.get('content-security-policy'), /default-src 'self'/);

  const js = await call('/app.js');
  assert.equal(js.res.status, 200);
  assert.match(js.res.headers.get('content-type'), /javascript/);

  const css = await call('/styles.css');
  assert.equal(css.res.status, 200);
});

test('returns 404 and 405 for unsupported requests', async () => {
  const missing = await call('/nope');
  assert.equal(missing.res.status, 404);

  const wrongMethod = await call('/api/questions', { method: 'PUT', body: {} });
  assert.equal(wrongMethod.res.status, 405);
  assert.equal(wrongMethod.res.headers.get('allow'), 'GET, POST');
});
