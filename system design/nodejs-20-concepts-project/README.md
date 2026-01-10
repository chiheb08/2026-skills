# Node.js essentials — mini runnable project

This project is a **simple, hands-on** companion to the notes:
- `system design/02-nodejs-20-concepts-2026-junior-friendly.md`

Instead of reading only theory, you can **run tiny scripts** that show what each concept means.

## What you need
- Node.js **18+** (recommended)
- npm

## Setup

From this folder:

```bash
npm install
```

Optional (for env demo):

```bash
echo "PORT=3000" > .env
```

---

## 1) Event loop (why Node feels fast)

Run:

```bash
npm run demo:eventloop
```

What to notice:
- `setTimeout(..., 0)` does **not** run immediately.
- The log order shows how the event loop schedules tasks.

---

## 2) Async patterns (callbacks vs promises vs async/await)

Run:

```bash
npm run demo:async
```

What to notice:
- same goal (read file), 3 different styles.

---

## 3) Environment variables

Run:

```bash
npm run demo:env
```

What to notice:
- how `process.env` works
- why we avoid hardcoding secrets

---

## 4) Simple HTTP server (no frameworks)

Run:

```bash
npm run start:http
```

Then open:
- `http://localhost:3000/health`
- `http://localhost:3000/slow?ms=1500`

What to notice:
- request/response basics
- a “slow endpoint” that simulates waiting

---

## 5) Express server + middleware

Run:

```bash
npm run start:express
```

Then open:
- `http://localhost:3000/health`
- `http://localhost:3000/hello?name=Chiheb`

What to notice:
- middleware logs every request
- validation example
- error handling middleware

---

## 6) Streams + Buffers

Run:

```bash
npm run demo:streams
npm run demo:buffer
```

What to notice:
- streaming reads big files chunk-by-chunk
- buffers are raw bytes (not strings)

---

## 7) CPU work: worker threads

Run:

```bash
npm run demo:worker
```

What to notice:
- doing CPU work in the main thread blocks everything
- worker thread keeps main thread responsive

---

## 8) Tiny performance demo

Run:

```bash
npm run demo:bench
```

What to notice:
- how to measure elapsed time
- why “blocking” hurts throughput

---

## Where are the examples?

- `src/` — event loop, async/await, env, error handling
- `http/` — Node built-in HTTP server
- `express/` — Express + middleware + errors
- `streams/` — stream + buffer demos
- `workers/` — worker thread demo

