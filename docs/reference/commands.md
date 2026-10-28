# Commands

Everything is run through `make` in the project folder. `make help` lists the commands.

## Setup

| Command | What it does |
|---|---|
| `make setup` | Installs everything: Homebrew packages, ffmpeg, Python packages, frontend packages |
| `make setup-brew` | Installs Homebrew packages: `uv`, `node`, `espeak` |
| `make setup-media` | Installs ffmpeg if it is missing |
| `make setup-python` | Creates `.venv` if it is missing and installs the Python packages |
| `make setup-frontend` | Installs the frontend packages (`npm install`) |
| `make lock` | Pins the Python package versions from `.venv` into `requirements.lock` |

## Running

| Command | What it does |
|---|---|
| `make up` | Starts the app: AI proxy, app server and worker. Restarts them if they run |
| `make down` | Stops the app |
| `make logs` | Shows the logs of all three processes in one stream |
| `make update` | Moves the copy to the latest release and starts it. If anything fails, the copy returns to the version it had. See [Updating](../guide/updating.md) |

## Dictionaries

| Command | What it does |
|---|---|
| `make dict-update` | Rebuilds the dictionary cache if the JSON files changed |
| `make dict-rebuild` | Rebuilds the dictionary cache from scratch |

## macOS app

| Command | What it does |
|---|---|
| `make app` | Builds the macOS app and puts it into `~/Applications` |
| `make test-macos` | Runs the macOS app's tests |

## Development

| Command | What it does |
|---|---|
| `make test` | Runs the Python tests |
| `make coverage` | Runs the Python tests with a coverage report |
| `make test-ai` | Runs the AI integration tests against the real AI proxy. Uses your Claude plan |
| `make lint` | Lints the Python code (ruff) |
| `make typecheck` | Type-checks the Python code (mypy) |
| `make up-worktree` | Starts a development worktree on its own ports |
| `make down-worktree` | Stops the worktree |
| `make logs-worktree` | Shows the worktree's logs |

Frontend commands, run in `frontends/web`:

| Command | What it does |
|---|---|
| `npm run build` | Type-checks and builds the frontend. `make up` runs it |
| `npm run lint` | Lints the frontend (ESLint and the design-token check) |
| `npm run test` | Runs the frontend tests (Vitest) |

## Maintenance

| Command | What it does |
|---|---|
| `make migrate-paths` | Points media paths in the database to this copy's media folder, after you move `data/`. A dry run; `APPLY=1` applies it |
| `make card-states-check` | Compares the stored card states with a full recalculation. Read-only |
| `make bench-db`, `make bench-review` | Performance benchmarks on a copy of the database |
