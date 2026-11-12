const NAME_KEY = 'icebreakers:name';

const state = {
  questions: [],
  stats: { questions: 0, answers: 0, answered: 0 },
  filter: 'all',
  query: '',
  drafts: new Map(),
  loading: true,
  loadError: null,
};

const dom = {
  me: document.getElementById('me'),
  search: document.getElementById('search'),
  stats: document.getElementById('stats'),
  list: document.getElementById('list'),
  random: document.getElementById('random'),
  form: document.getElementById('new-question'),
  questionText: document.getElementById('new-question-text'),
  formError: document.getElementById('new-question-error'),
  toast: document.getElementById('toast'),
};

/* ---------------------------------------------------------------- helpers */

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key.includes('-')) node.setAttribute(key, value);
    else node[key] = value;
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function readName() {
  return dom.me.value.trim();
}

function storedName() {
  try {
    return localStorage.getItem(NAME_KEY) ?? '';
  } catch {
    return '';
  }
}

function storeName(value) {
  try {
    localStorage.setItem(NAME_KEY, value);
  } catch {
    /* storage may be unavailable (private mode, blocked cookies) */
  }
}

function plural(n, one, many = one + 's') {
  return n + ' ' + (n === 1 ? one : many);
}

function timeAgo(iso) {
  const then = Date.parse(iso);
  if (!Number.isFinite(then)) return '';
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 45) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return minutes + 'm ago';
  const hours = Math.round(minutes / 60);
  if (hours < 24) return hours + 'h ago';
  const days = Math.round(hours / 24);
  if (days < 7) return days + 'd ago';
  return new Date(then).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

let toastTimer;
function toast(message, kind = 'info') {
  dom.toast.textContent = message;
  dom.toast.classList.toggle('is-error', kind === 'error');
  dom.toast.classList.add('is-visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => dom.toast.classList.remove('is-visible'), 3200);
}

async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || 'Request failed (' + res.status + ')');
  return data;
}

/* ------------------------------------------------------------------- data */

async function load() {
  state.loading = true;
  state.loadError = null;
  render();
  try {
    const data = await api('/api/questions');
    state.questions = data.questions;
    state.stats = data.stats;
  } catch (err) {
    state.loadError = err.message;
  } finally {
    state.loading = false;
    render();
  }
}

async function postQuestion(text) {
  const createdBy = readName();
  if (!createdBy) {
    dom.me.focus();
    throw new Error('Add your name first so the team knows who asked.');
  }
  return api('/api/questions', { method: 'POST', body: { text, createdBy } });
}

async function postAnswer(questionId, body) {
  const author = readName();
  if (!author) {
    dom.me.focus();
    throw new Error('Add your name first so the team knows who answered.');
  }
  return api('/api/questions/' + questionId + '/answers', {
    method: 'POST',
    body: { author, body },
  });
}

async function retractAnswer(answerId) {
  return api('/api/answers/' + answerId, {
    method: 'DELETE',
    body: { author: readName() },
  });
}

/* ----------------------------------------------------------------- render */

function matchesFilters(question) {
  if (state.filter === 'unanswered' && question.answers.length > 0) return false;
  if (state.filter === 'mine') {
    const me = readName().toLowerCase();
    if (!me) return false;
    if (!question.answers.some((a) => a.author.toLowerCase() === me)) return false;
  }
  if (state.query && !question.text.toLowerCase().includes(state.query.toLowerCase())) {
    return false;
  }
  return true;
}

function answerItem(question, answer) {
  const isMine = answer.author.toLowerCase() === readName().toLowerCase();
  const item = el(
    'li',
    { class: 'answer' },
    el(
      'div',
      { class: 'answer-head' },
      el('span', { class: 'answer-author', text: answer.author }),
      el('span', { class: 'answer-time', text: timeAgo(answer.createdAt) }),
      isMine &&
        readName() &&
        el('button', {
          class: 'link-button',
          type: 'button',
          text: 'retract',
          onclick: async (event) => {
            const button = event.currentTarget;
            if (!window.confirm('Retract your answer?')) return;
            button.disabled = true;
            try {
              await retractAnswer(answer.id);
              await load();
              toast('Answer retracted.');
            } catch (err) {
              button.disabled = false;
              toast(err.message, 'error');
            }
          },
        }),
    ),
    el('p', { class: 'answer-body', text: answer.body }),
  );
  return item;
}

function answerForm(question) {
  const textarea = el('textarea', {
    rows: 2,
    maxLength: 2000,
    placeholder: 'Add your answer…',
    'aria-label': 'Your answer to: ' + question.text,
  });
  textarea.value = state.drafts.get(question.id) ?? '';
  textarea.addEventListener('input', () => {
    const value = textarea.value;
    if (value) state.drafts.set(question.id, value);
    else state.drafts.delete(question.id);
  });

  const submit = el('button', { class: 'btn btn-primary', type: 'submit' }, 'Post answer');
  const form = el('form', { class: 'answer-form' }, textarea, el('div', { class: 'answer-actions' }, submit));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const body = textarea.value.trim();
    if (!body) {
      toast('Write something first.', 'error');
      textarea.focus();
      return;
    }
    submit.disabled = true;
    try {
      await postAnswer(question.id, body);
      state.drafts.delete(question.id);
      await load();
      toast('Answer posted.');
    } catch (err) {
      submit.disabled = false;
      toast(err.message, 'error');
    }
  });

  textarea.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      form.requestSubmit();
    }
  });

  return form;
}

function questionCard(question) {
  const count = question.answers.length;
  const card = el('article', { class: 'question card', id: 'q-' + question.id });

  card.append(
    el(
      'div',
      { class: 'question-head' },
      el('h2', { class: 'question-text', text: question.text }),
      el('span', {
        class: 'badge',
        text: question.category === 'classic' ? 'From the list' : 'Team question',
      }),
    ),
    el('p', {
      class: 'question-meta',
      text:
        (count === 0 ? 'No answers yet' : plural(count, 'answer')) +
        (question.createdBy ? ' · added by ' + question.createdBy : ''),
    }),
  );

  if (count === 0) {
    card.append(el('p', { class: 'empty', text: 'Be the first to answer.' }));
  } else {
    const list = el('ul', { class: 'answers' });
    for (const answer of question.answers) list.append(answerItem(question, answer));
    card.append(list);
  }

  card.append(answerForm(question));
  return card;
}

function render() {
  const { questions, answered } = state.stats;
  dom.stats.textContent = state.loading
    ? 'Loading questions…'
    : answered + ' of ' + plural(questions, 'question') + ' answered · ' +
      plural(state.stats.answers, 'answer') + ' total';

  dom.list.replaceChildren();

  if (state.loading) {
    dom.list.append(el('p', { class: 'list-empty', text: 'Loading…' }));
    return;
  }

  if (state.loadError) {
    dom.list.append(
      el(
        'div',
        { class: 'list-empty' },
        el('p', { text: 'Could not load questions: ' + state.loadError }),
        el('button', { class: 'btn', type: 'button', text: 'Try again', onclick: () => load() }),
      ),
    );
    return;
  }

  const visible = state.questions.filter(matchesFilters);
  if (!visible.length) {
    const reason =
      state.filter === 'mine'
        ? 'No answers from you yet.'
        : state.filter === 'unanswered'
          ? 'Every question has at least one answer.'
          : 'No questions match “' + state.query + '”.';
    dom.list.append(el('p', { class: 'list-empty', text: reason }));
    return;
  }

  for (const question of visible) dom.list.append(questionCard(question));
}

function scheduleRerender() {
  // Deferred so typing a name does not rebuild the list on every keystroke.
  clearTimeout(scheduleRerender.timer);
  scheduleRerender.timer = setTimeout(render, 250);
}

/* --------------------------------------------------------------- listeners */

dom.me.value = storedName();
dom.me.addEventListener('input', () => {
  storeName(readName());
  scheduleRerender();
});

dom.search.addEventListener('input', () => {
  state.query = dom.search.value.trim();
  render();
});

for (const chip of document.querySelectorAll('[data-filter]')) {
  chip.addEventListener('click', () => {
    state.filter = chip.dataset.filter;
    for (const other of document.querySelectorAll('[data-filter]')) {
      const active = other === chip;
      other.classList.toggle('is-active', active);
      other.setAttribute('aria-pressed', String(active));
    }
    render();
  });
}

dom.form.addEventListener('submit', async (event) => {
  event.preventDefault();
  dom.formError.hidden = true;
  const text = dom.questionText.value.trim();
  if (!text) {
    dom.formError.textContent = 'Write a question first.';
    dom.formError.hidden = false;
    dom.questionText.focus();
    return;
  }
  const button = dom.form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await postQuestion(text);
    dom.questionText.value = '';
    state.filter = 'all';
    state.query = '';
    dom.search.value = '';
    for (const other of document.querySelectorAll('[data-filter]')) {
      const active = other.dataset.filter === 'all';
      other.classList.toggle('is-active', active);
      other.setAttribute('aria-pressed', String(active));
    }
    await load();
    toast('Question added.');
  } catch (err) {
    dom.formError.textContent = err.message;
    dom.formError.hidden = false;
  } finally {
    button.disabled = false;
  }
});

dom.random.addEventListener('click', () => {
  if (state.loading || !state.questions.length) return;
  if (!state.questions.some(matchesFilters)) {
    state.filter = 'all';
    state.query = '';
    dom.search.value = '';
    for (const chip of document.querySelectorAll('[data-filter]')) {
      const active = chip.dataset.filter === 'all';
      chip.classList.toggle('is-active', active);
      chip.setAttribute('aria-pressed', String(active));
    }
    render();
  }
  const pool = state.questions.filter(matchesFilters);
  const pick = pool[Math.floor(Math.random() * pool.length)];
  const card = document.getElementById('q-' + pick.id);
  if (!card) return;
  card.scrollIntoView({ behavior: 'smooth', block: 'center' });
  card.classList.remove('flash');
  requestAnimationFrame(() => card.classList.add('flash'));
  card.querySelector('textarea')?.focus({ preventScroll: true });
});

load();
