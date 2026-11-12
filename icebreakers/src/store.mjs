import { DatabaseSync } from 'node:sqlite';

import { seedQuestions } from './seed-data.mjs';

const SCHEMA = `
CREATE TABLE IF NOT EXISTS questions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  text       TEXT NOT NULL,
  norm       TEXT NOT NULL UNIQUE,
  category   TEXT NOT NULL DEFAULT 'team',
  created_by TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS answers (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  author      TEXT NOT NULL,
  norm_author TEXT NOT NULL,
  body        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id);
`;

export const LIMITS = {
  question: 200,
  answer: 2000,
  author: 60,
};

/** Error carrying an HTTP status so the transport layer stays dumb. */
export class StoreError extends Error {
  constructor(message, status = 400) {
    super(message);
    this.name = 'StoreError';
    this.status = status;
  }
}

export function nowIso() {
  return new Date().toISOString();
}

/** Loose duplicate-detection key: lowercase alphanumerics only. */
export function normalize(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

export class Store {
  /** @param {string} path SQLite file path, or ':memory:' in tests. */
  constructor(path) {
    this.db = new DatabaseSync(path);
    this.db.exec('PRAGMA journal_mode = WAL;');
    this.db.exec('PRAGMA foreign_keys = ON;');
    this.db.exec(SCHEMA);
    this.#seedIfEmpty();
  }

  #seedIfEmpty() {
    const { count } = this.db.prepare('SELECT COUNT(*) AS count FROM questions').get();
    if (count > 0) return;

    const insert = this.db.prepare(
      `INSERT INTO questions (text, norm, category, created_by, created_at)
       VALUES (?, ?, ?, ?, ?)`,
    );
    const at = nowIso();
    this.db.exec('BEGIN');
    try {
      for (const q of seedQuestions()) {
        insert.run(q.text, normalize(q.text), q.category, q.createdBy, at);
      }
      this.db.exec('COMMIT');
    } catch (err) {
      this.db.exec('ROLLBACK');
      throw err;
    }
  }

  close() {
    this.db.close();
  }

  /**
   * Every question with its answers in chronological order.
   * @returns {Array<{id:number,text:string,category:string,createdBy:string|null,createdAt:string,answers:Array<object>}>}
   */
  listQuestions() {
    const questions = this.db
      .prepare(
        `SELECT id, text, category, created_by, created_at
         FROM questions
         ORDER BY id`,
      )
      .all()
      .map((row) => ({
        id: row.id,
        text: row.text,
        category: row.category,
        createdBy: row.created_by,
        createdAt: row.created_at,
        answers: [],
      }));

    const byId = new Map(questions.map((q) => [q.id, q]));
    const answers = this.db
      .prepare(
        `SELECT id, question_id, author, body, created_at
         FROM answers
         ORDER BY id`,
      )
      .all();

    for (const row of answers) {
      const question = byId.get(row.question_id);
      if (!question) continue;
      question.answers.push({
        id: row.id,
        author: row.author,
        body: row.body,
        createdAt: row.created_at,
      });
    }
    return questions;
  }

  /**
   * @param {{text: string, createdBy: string}} input
   * @returns {number} new question id
   */
  addQuestion({ text, createdBy }) {
    const norm = normalize(text);
    const existing = this.db
      .prepare('SELECT id FROM questions WHERE norm = ?')
      .get(norm);
    if (existing) {
      throw new StoreError('That question is already on the board.', 409);
    }
    const result = this.db
      .prepare(
        `INSERT INTO questions (text, norm, category, created_by, created_at)
         VALUES (?, ?, 'team', ?, ?)`,
      )
      .run(text, norm, createdBy, nowIso());
    return Number(result.lastInsertRowid);
  }

  /**
   * @param {number} questionId
   * @param {{author: string, body: string}} input
   * @returns {number} new answer id
   */
  addAnswer(questionId, { author, body }) {
    const exists = this.db
      .prepare('SELECT 1 AS ok FROM questions WHERE id = ?')
      .get(questionId);
    if (!exists) throw new StoreError('That question no longer exists.', 404);

    const result = this.db
      .prepare(
        `INSERT INTO answers (question_id, author, norm_author, body, created_at)
         VALUES (?, ?, ?, ?, ?)`,
      )
      .run(questionId, author, normalize(author), body, nowIso());
    return Number(result.lastInsertRowid);
  }

  /**
   * Self-service retraction: the supplied author must match the answer's author.
   * @param {number} answerId
   * @param {{author: string}} input
   */
  deleteAnswer(answerId, { author }) {
    const row = this.db
      .prepare('SELECT norm_author FROM answers WHERE id = ?')
      .get(answerId);
    if (!row) throw new StoreError('That answer no longer exists.', 404);
    if (row.norm_author !== normalize(author)) {
      throw new StoreError('You can only retract your own answer.', 403);
    }
    this.db.prepare('DELETE FROM answers WHERE id = ?').run(answerId);
  }

  stats() {
    const questions = this.db.prepare('SELECT COUNT(*) AS c FROM questions').get().c;
    const answers = this.db.prepare('SELECT COUNT(*) AS c FROM answers').get().c;
    const answered = this.db
      .prepare(
        `SELECT COUNT(DISTINCT question_id) AS c FROM answers`,
      )
      .get().c;
    return { questions, answers, answered };
  }
}
