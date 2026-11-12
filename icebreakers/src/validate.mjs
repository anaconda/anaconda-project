import { LIMITS, StoreError } from './store.mjs';

/**
 * Validate and trim a required user-supplied string.
 * @param {unknown} value
 * @param {string} label Human label used in error messages.
 * @param {number} max
 * @returns {string}
 */
export function requiredText(value, label, max) {
  if (typeof value !== 'string') {
    throw new StoreError(`${label} is required.`, 400);
  }
  const text = value.trim();
  if (!text) {
    throw new StoreError(`${label} is required.`, 400);
  }
  if (text.length > max) {
    throw new StoreError(`${label} must be ${max} characters or fewer.`, 400);
  }
  return text;
}

/**
 * @param {Record<string, unknown>} payload
 * @returns {{text: string, createdBy: string}}
 */
export function questionInput(payload) {
  return {
    text: requiredText(payload.text, 'Question', LIMITS.question),
    createdBy:
      payload.createdBy === undefined || payload.createdBy === null || payload.createdBy === ''
        ? 'Anonymous'
        : requiredText(payload.createdBy, 'Your name', LIMITS.author),
  };
}

/**
 * @param {Record<string, unknown>} payload
 * @returns {{author: string, body: string}}
 */
export function answerInput(payload) {
  return {
    author: requiredText(payload.author, 'Your name', LIMITS.author),
    body: requiredText(payload.body, 'Answer', LIMITS.answer),
  };
}

/**
 * @param {Record<string, unknown>} payload
 * @returns {{author: string}}
 */
export function authorInput(payload) {
  return { author: requiredText(payload.author, 'Your name', LIMITS.author) };
}
