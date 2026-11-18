# AI Knowledge Inbox

Save notes and web links, then ask questions about them in a chat. Answers come **only** from what you saved, and every claim cites the passage it came from.

**Stack:** FastAPI · Python 3.12 · SQLite · NumPy · Google Gemini (embeddings + answers) · React 18 · Vite · Tailwind CSS 4

---

## Contents

1. [Quick start](#1-quick-start)
2. [What it does](#2-what-it-does)
3. [Architecture](#3-architecture)
4. [Ingestion pipeline](#4-ingestion-pipeline)
5. [Question answering (RAG)](#5-question-answering-rag)
6. [API reference](#6-api-reference)
7. [Frontend](#7-frontend)
8. [Debuggability](#8-debuggability)
9. [Testing](#9-testing)
10. [Configuration](#10-configuration)
11. [Project structure](#11-project-structure)
12. [Design decisions and tradeoffs](#12-design-decisions-and-tradeoffs)
13. [What breaks at scale](#13-what-breaks-at-scale)
14. [What I'd change for production](#14-what-id-change-for-production)
15. [Known limitations](#15-known-limitations)

---

## 1. Quick start

### Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.10+ (developed on 3.12) | `python3 --version` |
| Node.js | 18+ | `node --version` |
| Google Gemini API key | free | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → **Create API key** (no card needed) |
| Google Chrome | any recent | only for the end-to-end browser tests |

### 1. Backend (terminal 1)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

echo "GEMINI_API_KEY=your-key-here" > .env   # .env is git-ignored
uvicorn app.main:app --reload
```

The API runs on **http://localhost:8000**. Interactive API docs: **http://localhost:8000/docs**.
The SQLite database is created automatically at `backend/data/inbox.db` on first start.

> Without a key the server refuses to start with: `GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey`

### 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The header should show a green **Connected**.
In development Vite proxies `/api/*` to the backend, so no CORS setup or URLs are needed.

### 3. Try it

1. **Note** tab → paste a few sentences → **Save note**. Watch the steps run in the Library.
2. **Link** tab → `https://en.wikipedia.org/wiki/Retrieval-augmented_generation` → **Save link**.
3. Ask: *"What is retrieval-augmented generation?"* → answer with `[1]` citations; hover a citation to highlight its source.
4. Follow up: *"what are its weaknesses?"* → answered in the same thread, using the conversation for context.
5. Try *"Hey, how are you?"* and *"What is the capital of France?"* → a friendly reply, and an honest "not in your saved items".

### Run the tests

```bash
cd backend  && .venv/bin/python -m pytest      # 93 tests: API, pipeline, RAG, conversations
cd frontend && npm test                        # 37 component tests
cd frontend && npm run test:e2e                # 10 browser tests (starts its own servers, uses local Chrome)
```

No test needs a Gemini key or the internet. See [Testing](#9-testing).

---

## 2. What it does

| Feature | Details |
|---|---|
| **Add notes** | Plain text, up to 20,000 characters |
| **Add links** | The server downloads the page, extracts the readable article text and removes clutter |
| **Live pipeline status** | Each item shows its steps while they run: Received → Loading page → Chunking → Creating vectors → Storing in database, with timings, details and the exact failure reason |
| **Ask questions** | Semantic search over your saved items, answered by Gemini with numbered citations |
| **Cited sources** | Only passages the answer actually cites are shown, with snippet, origin and match score |
| **Chat threads** | Follow-up questions continue the conversation and are understood in context |
| **History** | Conversations are saved; reopen any of them and keep asking |
| **Small talk / off-topic** | Greetings get a friendly reply; questions your library doesn't cover get an honest "not found", never a made-up answer |

---

## 3. Architecture

```
┌──────────────────────────── Browser: React (Vite) ────────────────────────────┐
│  Sidebar: add note/link · Library (live steps) · History   │  Main: chat thread │
└───────────────────────────────┬────────────────────────────────────────────────┘
                                │  HTTP/JSON  (/api/* proxied to :8000 in dev)
┌───────────────────────────────▼──────────────── FastAPI ────────────────────────┐
│  routes (api/) ── validation (schemas/) ── error handlers + request-ID middleware │
│        │                                                                        │
│        ├─ POST /ingest ──► save item (pending) ──► queue ──┐                    │
│        │                                                   ▼                    │
│        │                          background worker (asyncio, 2 consumers)      │
│        │                          [fetch → clean] → chunk → embed → store       │
│        │                                                                        │
│        └─ POST /query ──► [rewrite follow-up] → embed question → cosine top-k   │
│                           → Gemini answer (JSON: kind + text) → keep cited      │
│                           → save turn to conversation                           │
│                                                                                 │
│  services/ (logic) ── repositories/ (all SQL) ── providers/ (Gemini)            │
└───────────────┬─────────────────────────────────────────────┬───────────────────┘
                ▼                                             ▼
     SQLite (WAL): items, chunks (+vectors),          Google Gemini API
     conversations, turns                    embeddings: gemini-embedding-001 (768-d)
                                             answers:    gemini-3.5-flash-lite
```

**Layers (each has one job):**

| Layer | Folder | Responsibility |
|---|---|---|
| Routes | `app/api/` | HTTP only: parse, call a service, shape the response |
| Schemas | `app/schemas/` | Pydantic request/response models and validation rules |
| Services | `app/services/` | Business logic: ingestion, chunking, fetching, retrieval, prompts, citations |
| Repositories | `app/repositories/` | Every SQL statement lives here, nowhere else |
| Providers | `app/providers/` | AI vendor behind an interface (`EmbeddingProvider`, `AnswerGenerator`) |
| Workers | `app/workers/` | The background ingestion queue |
| Core | `app/core/` | Config, database, errors, logging, middleware |

---

## 4. Ingestion pipeline

### Flow

```
POST /ingest ─► validate ─► INSERT item (status=pending, step "received" done) ─► 202 Accepted
                                              │
                                    in-memory queue
                                              ▼
worker:  status=processing
         [links] Loading page   httpx download → trafilatura extract → cleanup
                 Chunking       recursive split, ~800 chars, ~100 overlap
                 Creating vectors  Gemini, batches of 100, RETRIEVAL_DOCUMENT
                 Storing in database   chunks + float32 vectors, one transaction
         status=ready   (or failed: the failed step records the reason, later steps are skipped)
```

### Why asynchronous

Loading a page and creating vectors can take seconds. `POST /ingest` returns **`202 Accepted`** right away with the item in `pending`, plus a `Location` header. The frontend polls `GET /items` every second while anything is processing, and stops when nothing is.

- **Queue:** an `asyncio.Queue` drained by 2 consumer tasks started in FastAPI's lifespan.
- **Durability:** the queue is in memory, but **status lives in the database**. On startup, items still `pending`/`processing` (after a crash or restart) are re-queued and run again from the start. Re-indexing replaces an item's chunks, so this is safe to repeat.
- **Isolation:** each item is its own job. A failure marks only that item `failed`; the worker keeps running.

### Step tracking

Each item stores its pipeline as JSON (`steps`). Every step is written to the database **when it starts and when it finishes**, so `GET /items` reports real progress, not an estimate:

```json
{"name": "fetching", "status": "done", "detail": "Loaded 17,323 characters from en.wikipedia.org",
 "started_at": "…", "finished_at": "…", "duration_ms": 626.7}
```

Statuses: `pending` → `running` → `done` | `failed`. Notes have 4 steps; links have 5 (the extra one is **Loading page**).

### What can fail, and what the user sees

| Step | Cause | Message |
|---|---|---|
| Received | Empty note, bad URL | Rejected by validation (422); nothing is saved |
| Loading page | Page error | "The page returned HTTP 404." |
| | Slow page | "The page didn't respond within 10 seconds." |
| | Site down / doesn't exist | "Couldn't connect to …" / "Couldn't find the website …" |
| | Not a web page (PDF, image, JSON) | "Unsupported content type 'application/pdf'…" |
| | Too large | "The page is larger than the 2 MB limit." |
| | No readable text (JS-only app, login wall) | "Couldn't find readable text on the page. It may need JavaScript or a login." |
| | Local / private address | "Links to private or local network addresses can't be saved." |
| Chunking | Nothing left to index | "There is no text to index." |
| Creating vectors | Gemini key, quota, outage | e.g. "Gemini is rate limiting requests or the free quota is used up…" |
| Storing | Database error | "Unexpected error while indexing. Check the server logs." (full stack trace is logged) |

### URL loading and text extraction

- **Download** (`services/fetcher.py`): async `httpx`, 10 s timeout, 5 redirects max, body streamed with a 2 MB cap, only `text/html`, `application/xhtml+xml` and `text/plain` accepted.
- **SSRF guard:** the hostname is resolved first and loopback, private, link-local and reserved addresses are refused, so the server can't be used to probe its own network.
- **Extraction:** [trafilatura](https://trafilatura.readthedocs.io/) removes navigation, sidebars, footers and comments and keeps the main article text, tables and code. Runs in a thread so it doesn't block the event loop.
- **Cleanup** (`services/text_cleanup.py`): measured on real pages, extraction still left furniture that hurt answers, so a second pass removes:
  - **Reference / bibliography sections** (they turned into chunks of pure citations that competed in search)
  - **Footnote markers** like `[12]` and `[citation needed]` (they look exactly like this app's own `[n]` citations and could confuse the model)
  - `[edit]` links, `¶` heading anchors and table divider lines

  On the Wikipedia *Vector database* page this went from 13,337 characters (63 citation lines) to 3,657 characters of article text.

### Chunking (`services/chunking.py`)

**Approach:** recursive, structure-aware splitting by characters.

1. Normalize whitespace, keeping paragraph breaks.
2. If the text fits in one chunk (≤ 800 chars), keep it whole.
3. Otherwise split on the **largest natural boundary first**: paragraphs → lines → sentences → words. Only pieces still too large fall through to the next level; a single "word" longer than a chunk (e.g. a giant URL) is hard-cut.
4. Pack pieces into chunks of up to **800 characters**. Each new chunk starts with the tail of the previous one (**up to 100 characters, whole pieces only**), so a fact spanning a boundary can be found from either side.

**Why this design:**

| Choice | Reason |
|---|---|
| Recursive, boundary-first | Keeps paragraphs and sentences intact, so a chunk holds a complete thought instead of being cut mid-sentence |
| ~800 characters (~200 tokens) | Small enough for precise matching and short citation snippets; large enough to keep context. Notes are often one chunk |
| ~100-char overlap of whole pieces | Recovers facts that straddle a boundary without cutting words in half; low duplication (~12%) |
| Characters, not tokens | No tokenizer dependency or model coupling; the ratio is stable enough for English text |

Both sizes are settings (`CHUNK_SIZE`, `CHUNK_OVERLAP`).

### Embeddings and vector storage

- **Model:** `gemini-embedding-001` at **768 dimensions** (the model supports up to 3072; 768 keeps storage 4× smaller with little quality loss for short passages).
- **Task types:** passages are embedded as `RETRIEVAL_DOCUMENT` and questions as `RETRIEVAL_QUERY`, which Gemini optimizes for asymmetric search.
- **Batching:** up to 100 texts per request.
- **Storage:** each vector is stored as a `float32` BLOB in the `chunks` table next to its text, **tagged with the model that produced it**. Search only compares vectors from the active model, so switching models can never mix incompatible vectors.

---

## 5. Question answering (RAG)

### Flow (`services/rag.py`)

```
question ─► library empty?  ──yes──► "Save a note or link first" (no AI calls)
           │
           ├─ follow-up? ─► Gemini rewrites it as a standalone question (using last 4 turns)
           │                 e.g. "why disable them?" → "Why do prepared statements need to be
           │                 disabled in PgBouncer transaction pooling mode?"
           │                 (if the rewrite fails, the original wording is searched instead)
           ▼
     embed question (RETRIEVAL_QUERY)
           ▼
     cosine similarity against every chunk (NumPy), top 5 above a 0.3 floor
           ▼
     Gemini answer, JSON output: {"kind": "answer" | "not_found" | "small_talk", "text": "…"}
           ▼
     keep only the passages the answer cites, renumber them [1], [2], …
           ▼
     save the turn to the conversation, return it
```

### Prompt design (`services/prompt.py`)

- Passages are numbered `[1]…[n]` with their source title.
- The model must **use only the passages**, **cite every claim**, and say when the saved items don't cover a question. It is told never to answer from general knowledge.
- Earlier conversation is included as **context for intent only**, never as a source.
- Passages are labelled as **data, not instructions**, as a basic guard against prompt injection from saved web pages.
- Answers are short paragraphs or `-` bullet lists; the UI renders lists, `code` and **bold**.

### Reply kinds

The model labels its own reply **in the same call** that writes it (Gemini JSON mode with a schema), so this costs no extra request:

| Kind | When | UI |
|---|---|---|
| `answer` | Saved passages answer the question | Answer card with `[n]` citations and the cited sources |
| `not_found` | A real question the library doesn't cover (including general knowledge) | Grey card + "Try rephrasing, or add a note or link about this" |
| `small_talk` | Greetings, thanks, "what can you do?" | Plain friendly reply, no sources |

If the model ignores the JSON format, its text is kept as a normal answer instead of failing.

### Citations (`services/citations.py`)

Retrieval sends 5 passages for context, but an answer usually cites fewer. Showing all 5 as "sources" would credit text that played no part in the answer, so:

- citations are collected in order of first use and **renumbered** (`[3][5]` → `[1][2]`);
- `[1, 2]` is expanded to `[1][2]`;
- bracketed numbers that aren't passages (e.g. `[2024]`) are left alone;
- small talk and not-found replies never carry sources.

Sources are stored **as a snapshot** with each answer, so an old answer still shows its sources after the item is deleted.

### Latency (measured)

| Step | Time |
|---|---|
| Embed question | ~0.6 s |
| Answer with `gemini-3.5-flash-lite`, thinking `low` | ~1.6–2.5 s |
| Whole question end to end | ~2–3 s |
| Ingest a 17k-character Wikipedia page (29 chunks) | ~2.5 s |

**Finding:** Gemini 3 models "think" before replying by default. With the default level, the same answer prompt took **34 s and then timed out**; with `thinking_level=low` it took **4.8 s** on `gemini-3.8-flash`. Summarizing given passages doesn't need deep reasoning, so the app sends `low` (setting `GEMINI_THINKING_LEVEL`).

---

## 6. API reference

Full interactive docs at **`/docs`** (generated from the Pydantic schemas).

| Method | Path | Purpose | Success |
|---|---|---|---|
| `POST` | `/ingest` | Save a note or link; indexing runs in the background | **202** + `Location` |
| `GET` | `/items?limit=100` | Saved items, newest first, with pipeline steps | 200 |
| `GET` | `/items/{id}` | One item | 200 |
| `DELETE` | `/items/{id}` | Delete an item and its chunks | 204 |
| `POST` | `/query` | Ask a question or a follow-up | 200 |
| `GET` | `/conversations` | Conversation history, most recent first | 200 |
| `GET` | `/conversations/{id}` | One conversation with every turn | 200 |
| `DELETE` | `/conversations/{id}` | Delete a conversation | 204 |
| `GET` | `/health` | Liveness, models, worker status, queue depth | 200 |

### `POST /ingest`

```bash
curl -X POST localhost:8000/ingest -H 'Content-Type: application/json' \
  -d '{"type": "url", "url": "https://en.wikipedia.org/wiki/Vector_database"}'
```

Request: `{"type": "note", "content": "…"}` **or** `{"type": "url", "url": "https://…"}` (optional `title`).
Rules: `content` required for notes and not allowed for links (and vice versa); URLs must be absolute `http(s)`; unknown fields are rejected.

```json
// 202 Accepted   Location: /items/9f2c…
{"item": {"id": "9f2c…", "source_type": "url", "title": null, "url": "https://en.wikipedia.org/wiki/Vector_database",
  "status": "pending", "error": null, "chunk_count": 0, "content_preview": null,
  "created_at": "2026-11-18T09:49:49Z", "updated_at": "…",
  "steps": [{"name": "received", "status": "done", "detail": "Link received (en.wikipedia.org)", "…": "…"},
            {"name": "fetching", "status": "pending", "…": "…"}, "…"]}}
```

### `POST /query`

```bash
curl -X POST localhost:8000/query -H 'Content-Type: application/json' \
  -d '{"question": "why do we need to disable prepared statements?", "conversation_id": "3f1c…"}'
```

Request: `question` (1–500 chars), optional `conversation_id` (omit to start a new conversation), optional `top_k` (1–20).

```json
{
  "id": "a81e…",
  "conversation_id": "3f1c…",
  "question": "why do we need to disable prepared statements?",
  "search_query": "Why do prepared statements need to be disabled in PgBouncer transaction pooling mode?",
  "kind": "answer",
  "answer": "You need to disable prepared statements because they do not work in transaction pooling mode [1].",
  "sources": [{"item_id": "…", "chunk_index": 0, "source_type": "note", "title": "Postgres connection pooling",
               "url": null, "snippet": "…", "score": 0.73}],
  "created_at": "2026-11-18T06:47:25Z"
}
```

`sources[n-1]` is citation `[n]`. `search_query` shows what was actually searched (it differs from `question` for follow-ups).

### Errors

Every error has the same shape, and the `request_id` matches the `X-Request-ID` response header and the server logs:

```json
{"error": {"code": "VALIDATION_ERROR", "message": "url must be an absolute http(s) link, like https://example.com/page",
           "request_id": "6e2d46c8…", "details": [{"field": "url", "message": "url must be an absolute http(s) link, …"}]}}
```

| Status | Codes | When |
|---|---|---|
| 404 | `NOT_FOUND`, `ITEM_NOT_FOUND`, `CONVERSATION_NOT_FOUND` | Unknown route or id |
| 405 | `METHOD_NOT_ALLOWED` | Wrong method |
| 422 | `VALIDATION_ERROR` | Bad body or query parameter (field-level `details`) |
| 502 | `LLM_ERROR`, `LLM_SERVER_ERROR`, `LLM_UNREACHABLE`, `LLM_MODEL_NOT_FOUND`, `LLM_EMPTY_ANSWER` | Gemini failed |
| 503 | `LLM_AUTH_FAILED`, `LLM_RATE_LIMITED`, `LLM_OVERLOADED`, `WORKER_UNAVAILABLE` | Bad key, quota, Gemini overloaded, worker down |
| 504 | `LLM_TIMEOUT` | Gemini timed out |
| 500 | `INTERNAL_ERROR` | Unexpected bug (details logged, never leaked) |

---

## 7. Frontend

**React 18 with hooks, no state library.** State is small and naturally split by concern, so custom hooks are enough:

| Hook | Owns |
|---|---|
| `useItems` | Library list; polls every 1 s **only while** an item is pending/processing |
| `useConversation` | The current thread: send, open from history, new chat. A new request **cancels** the previous one (AbortController), so a slow reply can't land in the wrong thread |
| `useHistory` | Conversation list; updated locally after each answer (no refetch) |
| `useField` | Blur-first validation: no errors while typing, errors clear on the first fix, untouched fields never complain |
| `useHealth` | Connection indicator |

`App.jsx` holds only cross-pane state: the active sidebar tab, and which citation is highlighted (so hovering `[1]` lights up both the passage and the library item it came from). Components are presentational; all network calls go through one module (`api/client.js`) that parses the error contract into an `ApiError`.

**UX decisions:**

- **Split pane:** sidebar (add + Library / History tabs), main area for the conversation.
- **Note / Link toggle**, each with its own field and draft (switching never loses text).
- **Live pipeline view:** progress bar per item plus an expandable step list with timings and failure reasons.
- **Chat thread:** question bubbles, answer cards, follow-up box pinned to the bottom, "Searched for …" shown under rewritten follow-ups.
- **Ask is disabled** until there's a question; a book-shelf loader shows while answering.
- **Accessibility:** visible labels, keyboard-navigable tabs, focus rings, `aria-live` regions, and reduced-motion support (animations pause).

---

## 8. Debuggability

- **Structured logs** (`structlog`): human-readable in dev, **one JSON object per line** in prod (`APP_ENV=prod`).
- **Request IDs:** every request gets an ID (or reuses an incoming `X-Request-ID`). It's bound to every log line for that request and returned in the error body.
- **Access log:** method, path, status, duration for every request.
- **Pipeline logs:** `step_done` / `step_failed` with step name, detail and duration; worker jobs carry `item_id`.
- **RAG logs:** `query_answered` with kind, retrieved vs cited counts, top score, duration; `query_rewritten` / `query_rewrite_skipped` for follow-ups.
- **Provider errors:** `gemini_error` logs Google's own status and message, while the client gets a safe, clear summary.
- **Persisted state:** each item's steps (with durations and failure reasons) and each answer's duration are stored, so problems can be inspected after the fact.

---

## 9. Testing

| Suite | Command | Count | Covers |
|---|---|---|---|
| Backend | `cd backend && .venv/bin/python -m pytest` | 93 | Every endpoint and error path; full pipeline against a **local web server** (real HTML extraction, 404, wrong content type, no text, unreachable host, size limit); embedding failure on the right step; chunking; retrieval; citations; conversations and follow-ups; reply kinds; rewrite fallback on rate limits; crash recovery; schema migrations |
| Components | `cd frontend && npm test` | 37 | Validation, Note/Link toggle, server-error mapping, citations, answer formatting, pipeline step display, reply kinds |
| End-to-end | `cd frontend && npm run test:e2e` | 10 | Real browser (Chrome) + real Vite + real FastAPI + SQLite: add note/link and watch steps, broken link, ask with citation highlighting, follow-ups, new chat, small talk, history reopen/continue/delete, reload |

**Why tests don't call Gemini:** they replace it with small offline stand-ins (`backend/tests/fakes.py`: keyword-hash embeddings and a quoting answerer) through the same provider interface. Tests stay free, fast (~13 s backend), deterministic and runnable without a key. Real Gemini behavior was verified manually: embeddings, answers, follow-up rewriting, reply kinds and latency.

The end-to-end suite starts its own servers on ports 8100 (API), 8200 (test pages) and 5180 (UI), with a throwaway database.

---

## 10. Configuration

All settings are environment variables (or lines in `backend/.env`), validated at startup. Only the API key is required.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — (required) | Google AI Studio key |
| `GEMINI_CHAT_MODEL` | `gemini-3.5-flash-lite` | Model that writes answers and rewrites follow-ups |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model |
| `GEMINI_EMBEDDING_DIMENSIONS` | `768` | Vector size (128–3072) |
| `GEMINI_THINKING_LEVEL` | `low` | Gemini reasoning depth; empty = model default (much slower) |
| `AI_TIMEOUT_SECONDS` | `30` | Per-request timeout to Gemini (3 attempts on 429/5xx) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `100` | Chunking, in characters |
| `RETRIEVAL_TOP_K` | `5` | Passages sent to the model |
| `MIN_SIMILARITY` | provider default (`0.3`) | Cosine floor for retrieval |
| `FETCH_TIMEOUT_SECONDS` / `FETCH_MAX_BYTES` | `10` / `2000000` | URL loading limits |
| `FETCH_ALLOW_PRIVATE_HOSTS` | `false` | Allow local addresses (tests only; disables the SSRF guard) |
| `INGEST_WORKER_CONCURRENCY` | `2` | Parallel ingestion jobs |
| `DATABASE_PATH` | `data/inbox.db` | SQLite file |
| `APP_ENV` / `LOG_LEVEL` | `dev` / `INFO` | `prod` switches logs to JSON |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed browser origins |

---

## 11. Project structure

```
backend/
  app/
    main.py                 app factory, lifespan (DB init, worker start, crash recovery)
    domain.py               core types: Item, PipelineStep, Passage, AnswerDraft…
    api/                    routes: ingest, items, query (+ conversations), health, deps
    schemas/                Pydantic request/response models
    services/
      ingestion.py          create items; the pipeline (fetch → chunk → embed → store)
      pipeline_steps.py     per-step status tracking, persisted as it runs
      fetcher.py            URL download, SSRF guard, trafilatura extraction
      text_cleanup.py       remove references, footnotes, [edit], anchors
      chunking.py           recursive chunker with overlap
      retrieval.py          cosine top-k (NumPy)
      rag.py                rewrite → retrieve → answer → keep cited
      prompt.py             system prompts and prompt builders
      citations.py          renumber citations, drop uncited passages
    repositories/           items, chunks, conversations: all SQL lives here
    providers/              provider interfaces + Gemini implementation
    workers/ingest_worker.py   asyncio queue + consumers
    core/                   config, db (schema + migrations), errors, logging, middleware
  tests/                    pytest suites, offline Gemini stand-ins, e2e server
frontend/
  src/
    api/client.js           the only place that calls fetch; error parsing
    hooks/                  useItems, useConversation, useHistory, useField, useHealth
    components/             Composer, ItemList/ItemRow, PipelineSteps, ChatPanel, AnswerView, SourceList…
    components/ui/          Button, FieldMessage, ErrorNotice, BookLoader, icons
    lib/                    validators, citation parsing, answer formatting, formatting helpers
  e2e/                      Playwright tests + a local test page
```

---

## 12. Design decisions and tradeoffs

### Why FastAPI
Async I/O suits this workload: most time is spent waiting on web pages and Gemini. Pydantic gives request validation and the OpenAPI docs for free, and FastAPI's lifespan hook is a natural place to run the background worker.

### Why no RAG framework (LangChain / LlamaIndex)
Every stage is about 30–100 lines of readable code: chunker, cosine search, prompt, citation filter. Writing them directly:
- makes each decision visible and explainable (which is what this exercise evaluates);
- made **per-step pipeline tracking** straightforward, since each step is our own code;
- avoids a large, fast-moving dependency.

**Tradeoff:** frameworks give ready-made loaders (PDF, Notion, …), vector-store adapters and advanced retrieval (re-ranking, hybrid search). If the product needed many source types, I would adopt LlamaIndex behind the same provider/repository interfaces.

### Why Gemini
A free tier covers both embeddings and generation with one key, it supports retrieval-specific embedding task types and JSON-schema output, and all vendor code sits behind two small interfaces (`providers/base.py`), so swapping to OpenAI or a local model is one new class. It uses Google's official `google-genai` SDK with retries on 429/5xx and a timeout.

**Model choice:** `gemini-3.5-flash-lite` is the default. In testing it was the fastest (~1.6 s) and has its own free-tier quota; `gemini-3.8-flash` allows only 20 requests/day on the free tier. Embeddings use `gemini-embedding-001`.

### Why SQLite + NumPy as the vector store
- One file, zero setup, and the data survives restarts.
- Vectors live **in the same transaction** as their chunk text and item status, so they can't drift out of sync.
- Brute-force cosine over a NumPy matrix is exact (no approximate-search recall loss) and fast at this scale: thousands of chunks take milliseconds.
- WAL mode lets the worker write while API requests read.

**Tradeoff:** search is O(n) and loads every vector per query. See [What breaks at scale](#13-what-breaks-at-scale).

### Why an in-process queue
`asyncio.Queue` needs no Redis or broker, which matches the "avoid infra theater" guidance. Durability comes from the database: statuses are persisted and unfinished items are re-queued on startup. **Tradeoff:** one process only, and no retries with backoff for ingestion.

### Why characters for chunk size
No tokenizer dependency and no coupling to a specific model's tokenization. **Tradeoff:** chunk token counts vary slightly across languages and code.

### Why only cited sources
Retrieval returns top-k passages for recall, but showing all of them as sources over-credits text the answer never used. Filtering to cited passages keeps sources honest; the cost is that a correct answer that forgets to cite shows no sources.

### Why query rewriting for follow-ups
Embedding "what about the second one?" retrieves nothing useful. Rewriting it into a standalone question using recent turns is the standard fix. **Tradeoff:** one extra model call per follow-up. It's skipped for first questions, and if it fails the original wording is searched instead of failing the turn.

### Why the model labels its reply kind
A separate classifier call would add latency and cost. Asking for `{kind, text}` in the same JSON response gives typed handling (sources only for real answers, friendly small talk, honest not-found) for free.

---

## 13. What breaks at scale

| Component | Breaks when | Why |
|---|---|---|
| **Vector search** | ~100k+ chunks | O(n) brute force; every query loads all vectors from SQLite into memory (100k × 768 × 4 B ≈ 300 MB per query) |
| **SQLite** | Many concurrent writers / multiple servers | Single writer; a local file can't be shared across machines |
| **In-process queue** | Multiple API processes, crashes mid-burst | Jobs live in one process's memory; no distributed workers; recovery happens only at startup |
| **Polling** | Many open browser tabs | Each tab polls `GET /items` every second while something is indexing |
| **Gemini free tier** | Even light use | Per-minute and per-day request quotas (20/day on some models) |
| **URL fetching** | Large or JS-heavy sites | 2 MB cap, no JavaScript rendering, one page per link (no crawling) |
| **Single user** | More than one person | No auth, no per-user data isolation |
| **Conversation context** | Very long threads | Only the last 4 turns are used for follow-ups |

---

## 14. What I'd change for production

1. **Vector store:** Postgres + **pgvector** (HNSW index) so vectors, items and conversations stay in one transactional store; or Qdrant/Weaviate at larger scale. Add **hybrid search** (BM25 + vectors) and a **re-ranker** for precision.
2. **Job queue:** Redis + RQ/Celery or a cloud queue (SQS / Pub/Sub) with separate worker processes, retries with exponential backoff, a dead-letter queue, and a **Retry** button for failed items.
3. **Push instead of poll:** Server-Sent Events or WebSockets for pipeline progress and **streamed answers**.
4. **Auth and multi-tenancy:** user accounts, every item, chunk and conversation scoped by `user_id`, per-user rate limits.
5. **Caching:** cache embeddings by content hash (re-saving the same page costs nothing), and deduplicate saved URLs.
6. **Richer ingestion:** PDFs and documents, JavaScript-rendered pages (headless browser), images via alt text and Gemini vision captions, OCR for screenshots; periodic re-crawl of saved links.
7. **Quality:** an evaluation set of questions with expected sources, tracking retrieval recall@k and citation accuracy on every prompt or model change.
8. **Observability:** OpenTelemetry traces across API → worker → Gemini, metrics (latency, tokens, cost, failure rate per step), alerting.
9. **Security:** stricter SSRF checks (re-validate after each redirect), content-size and rate limits per user, prompt-injection filtering on fetched pages, secrets in a secret manager.
10. **Operations:** a paid Gemini tier, Docker images and a CI pipeline running all three test suites, and database migrations with Alembic instead of hand-written additive migrations.

---

## 15. Known limitations

- **Images are ignored.** Only page text is extracted; diagrams, charts and text inside images aren't indexed. Captions written as normal text are kept. A direct image URL fails with "Unsupported content type".
- **JavaScript-only pages** (single-page apps) and pages behind a login have no extractable text and fail at Loading page.
- **One page per link.** Linked pages aren't followed.
- **Partially related questions** may get "not found" when the saved text is related but doesn't directly answer.
- **Switching embedding models** makes items saved with the old model unsearchable until they're added again (vectors from different models are never compared).
- **Free-tier quotas** can return "rate limiting" errors under heavy testing.
