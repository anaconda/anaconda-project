# Ice Breakers

A small shared board for team ice breaker questions. Everyone can answer any question,
and anyone can add a question they want the team to answer. Answers are visible to
everyone using the same server.

Ships preloaded with the 30 questions (plus crowdsourced additions) from Todd Caponi's
[Sales Meetings: The Purpose, and My Top 30 Ice-Breaker Questions](https://toddcaponi.com/sales-meetings-the-purpose-and-my-top-30-ice-breaker-questions/).

## Requirements

- Node.js 22.5 or newer (uses the built-in `node:sqlite` module)
- No dependencies, no build step, no accounts

## Run

```bash
cd icebreakers
npm start            # http://localhost:3000
```

The database is created on first run at `icebreakers/data/icebreakers.db` and seeded
with the question set.

| Variable        | Default                     | Purpose                          |
| --------------- | --------------------------- | -------------------------------- |
| `PORT`          | `3000`                      | HTTP port                        |
| `HOST`          | `0.0.0.0`                   | Bind address                     |
| `ICEBREAKER_DB` | `./data/icebreakers.db`     | SQLite file path (`:memory:` for a throwaway instance) |

Is this deployed anywhere the disk resets? Point `ICEBREAKER_DB` at a mounted volume,
otherwise answers are lost on redeploy.

```bash
npm run dev          # restarts on file changes
npm test             # API tests (node:test)
```

## Features

- Answer any question; answers are listed chronologically under each question.
- Add a question for the team. Near-duplicates (case/punctuation-insensitive) are
  rejected with a clear message.
- Search across questions, and filter to `Unanswered` or `My answers`.
- "Surprise me" picks a question and scrolls to it — handy for opening a meeting.
- Your name is remembered in `localStorage`; you can retract your own answers.
- Light and dark themes, keyboard accessible, no inline scripts (strict CSP).

## API

All requests and responses are JSON.

| Method | Path                                 | Body                        | Notes                        |
| ------ | ------------------------------------ | --------------------------- | ---------------------------- |
| GET    | `/api/questions`                     | –                           | `{ questions, stats }`       |
| POST   | `/api/questions`                     | `{ text, createdBy? }`      | `201`; `409` if duplicate    |
| POST   | `/api/questions/:id/answers`         | `{ author, body }`          | `201`; `404` if no question  |
| DELETE | `/api/answers/:id`                   | `{ author }`                | `403` unless author matches  |
| GET    | `/api/health`                        | –                           | `{ ok: true }`               |

Limits: question 200 characters, answer 2000, name 60. Errors come back as
`{ "error": "message" }`.

```bash
curl -X POST http://localhost:3000/api/questions/1/answers \
  -H 'Content-Type: application/json' \
  -d '{"author":"Sam","body":"A local news anchor, at a county fair."}'
```

## Layout

```
server.mjs          entry point: config, listen, graceful shutdown
src/seed-data.mjs   the source questions
src/store.mjs       SQLite schema, seeding, queries, validation of ownership
src/validate.mjs    request field validation and trimming
src/http.mjs        routing, JSON body limits, static files, security headers
public/             index.html, styles.css, app.js, favicon.svg
test/api.test.mjs   API tests against an in-memory database
```

## Notes and limits

- Identity is self-declared (a remembered name), so "retract" is honor-system only.
  Put real auth in front of it, or behind a team passphrase, if that matters.
- No rate limiting or moderation. Fine for a small trusted group; add a reverse proxy
  with rate limits before exposing it publicly.
- The schema is two tables (`questions`, `answers`). Natural next steps: reactions on
  answers, a single-question "presenter" view for meetings, CSV export.

## Attribution

The question set comes from Todd Caponi's article above and is credited in the app
footer. Keep that credit if you reuse the content.
