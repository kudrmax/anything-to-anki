# Architecture

AnythingToAnki is a Python backend with a replaceable frontend. The backend holds all of the product's logic; the web page and the macOS app only show it.

## Processes

```
 Browser / macOS app
        │  HTTP (port 17832)
        ▼
 ┌──────────────┐   SQLite (data/app.db)   ┌──────────────┐
 │  App server  │◄────────────────────────►│    Worker    │
 │  (FastAPI)   │        jobs table        │  (job queue) │
 └──────┬───────┘                          └──────┬───────┘
        │                                         │
        │ AnkiConnect (8765)          HTTP (8766) │
        ▼                                         ▼
      Anki                               ┌──────────────┐
                                         │   AI proxy   │──► claude CLI ──► Claude
                                         └──────────────┘
```

| Process | Code | Role |
|---|---|---|
| App server | `backend.infrastructure.api.app` (uvicorn) | The HTTP API and the built web frontend. Adding, processing, review, export |
| Worker | `backend.infrastructure.queue` | Runs background jobs from the `jobs` table: meanings, polish, media, pronunciation, TTS, video downloads, topic words |
| AI proxy | `ai_proxy.py` | A small FastAPI server that calls Claude through [claude-agent-sdk](https://pypi.org/project/claude-agent-sdk/) and the user's `claude` login. It runs on the host because the login lives in the macOS Keychain |

`make up` starts all three. They share the SQLite database in `data/`. One worker runs per data folder.

TTS runs in a separate child process of the worker, which loads Kokoro and PyTorch once and exits when no speech jobs are left.

## Layers

The backend in `backend/src/backend` follows Clean Architecture:

```
domain ◄── application ◄── infrastructure
                ▲
            frontends
```

| Layer | Contents |
|---|---|
| `domain/` | Entities and value objects (frozen dataclasses), ports (abstract interfaces), and pure domain services: CEFR voting, card sections and sorting, phrase selection, decision rules |
| `application/` | Use cases (one per user action: `add_source`, `process_source`, `decide_phrase`, `run_generation`, `sync_to_anki`, …), DTOs (pydantic), source intake |
| `infrastructure/` | Adapters for the ports: SQLAlchemy persistence, spaCy, wordfreq, the dictionary cache, ffmpeg, yt-dlp, Kokoro, AnkiConnect, the AI service, image search. Also the FastAPI routes, the worker, and `container.py`, which wires everything together |
| `frontends/web` | React + TypeScript + Vite. Rendering, local UI state and API calls only |
| `frontends/macos` | A Swift WKWebView shell around the web frontend, with file drop, a file picker and Quick Add |

Rules:

- `domain` imports nothing from the other layers; `application` imports only `domain`.
- Use cases get their dependencies from `container.py`; they never create infrastructure objects.
- **All business logic is in the backend.** A frontend renders what the API returns: the backend decides card states, which buttons are enabled, and what a press does. A new frontend (a mobile app, a bot) must not need to repeat any rule.
- The backend never knows which frontend calls it.

## Pipeline

```
Source ─► Text extraction ─► Phrase segmentation ─► Target selection ─► Card generation ─► Review ─► Anki
```

1. **Intake** (`application/source_intake`, `infrastructure/readers`). A format detector picks a reader by file extension or by the pasted text: plain, Markdown, HTML, EPUB, SRT, video file or YouTube. The text is normalised: tags and timecodes are removed, slang is spelled out.
2. **Processing** (`process_source`, `analyze_text`). spaCy parses the text. The app collects the lemmas, phrasal verbs and collocations. It filters out words you know, words below your CEFR level, and very frequent words. Then it chooses, for every target, the phrase where everything else is most familiar. Processing runs as one long operation and is saved in one transaction.
3. **Generation** (`run_generation`, the worker). Jobs per card: polish and meaning (AI, in batches of 15), media (ffmpeg), pronunciation (dictionary audio), TTS (Kokoro).
4. **Review** (`open_review`, `decide_phrase`). The backend orders the cards, splits them into sections and applies decisions. Card states are kept in a stored projection.
5. **Export** (`sync_to_anki`). Notes are added through AnkiConnect, with their media.

## Data

- SQLite in WAL mode, through SQLAlchemy. Every write goes through one unit of work.
- The schema changes only through [Alembic](https://alembic.sqlalchemy.org/) migrations in `backend/src/backend/alembic/versions`. The app migrates on start and backs the database up first.
- Long operations (processing, a level change) hold a global lock. Other writes get HTTP 423, and the frontend shows a blocking overlay.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | The Python backend and its tests |
| `frontends/web/` | The web frontend |
| `frontends/macos/` | The macOS app |
| `ai_proxy.py` | The AI proxy |
| `config/prompts.yaml` | AI prompts |
| `anki-templates/` | Anki card templates and CSS |
| `scripts/` | Maintenance, analysis and benchmark scripts |
| `docs/` | This documentation |
| `internal/` | Working notes: specs, plans, task lists, design mockups. Not user documentation |
