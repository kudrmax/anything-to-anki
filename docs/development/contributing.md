# Contributing

## Setup

Follow [Installation](../getting-started/installation.md). `make setup` installs the development tools too.

Run every process through `make`: `make up`, `make down`, `make logs`. If a `make` command doesn't do what you need, fix the `Makefile` rather than starting processes by hand.

## Checks

Before you commit, run the checks for what you changed. All of them must pass.

Python:

```bash
make lint
make typecheck
make test
```

Web frontend (in `frontends/web`):

```bash
npm run lint
npm run build
npm run test
```

`npm run build` is what `make up` runs, so check with it rather than `tsc --noEmit`.

macOS app:

```bash
make test-macos
```

A failing test is never skipped or disabled; fix the test or the code.

`make test-ai` runs the AI integration tests against the real Claude. It uses your Claude plan, so it is not part of `make test`.

## Code standards

- **Types.** `mypy --strict`. Every parameter and return value is annotated. `Any` needs a comment that explains why.
- **Data.** Frozen `dataclass` for domain entities and value objects; `pydantic` for DTOs and configuration. Never a plain `dict` for structured data.
- **Composition over inheritance.** Inheritance only to implement ports.
- **Constants.** Named `UPPER_SNAKE_CASE` constants instead of magic numbers and strings.
- **Lint.** `ruff`, configured in `pyproject.toml`. Relative imports are not allowed.
- **Frontend styles.** Colours and sizes come from `src/styles/tokens.css`; `npm run lint` rejects hard-coded values.
- **Architecture.** See [Architecture](architecture.md). Business logic belongs to the backend. Use cases get their dependencies from `container.py`.

## Database migrations

Change the schema only with an Alembic migration in `backend/src/backend/alembic/versions`, never with `CREATE TABLE` or `ALTER TABLE` in code. Migrations are numbered `NNNN_slug.py`. Before picking a number, check that no other branch uses it.

## Bugs

Find the cause before you fix a bug: read the logs (`make logs`), reproduce it, and fix the place where things go wrong. Don't hide a symptom, for example with a background task that resets stuck jobs.

## Git

- Work in a branch, never in `master`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`. The subject is in the imperative mood and at most 72 characters, e.g. `feat: sync translation and synonyms to Anki`.
- Feature branches are merged with `git merge --no-ff`, never fast-forward, so the history keeps the branch's boundary.

## Documentation

The documentation in `docs/` is part of the product. **A change that adds, removes or changes a feature updates its page in the same branch:**

| You changed | Update |
|---|---|
| What users can add, or source management | [guide/sources.md](../guide/sources.md) |
| The Review screen, cards, generation | [guide/review.md](../guide/review.md) |
| Export, note types, fields, templates | [guide/anki-export.md](../guide/anki-export.md) |
| Level, known words, calibration | [guide/vocabulary.md](../guide/vocabulary.md) |
| Queue or Usage | [guide/queue-and-usage.md](../guide/queue-and-usage.md) |
| A setting | [guide/settings.md](../guide/settings.md) |
| The macOS app | [guide/macos-app.md](../guide/macos-app.md) |
| Updates, releases, `make update` | [guide/updating.md](../guide/updating.md) |
| Installation, `make` targets, `.env`, environment variables | [getting-started/installation.md](../getting-started/installation.md), [reference/commands.md](../reference/commands.md), [reference/configuration.md](../reference/configuration.md) |
| Dictionary format | [reference/dictionaries.md](../reference/dictionaries.md) |
| An error message | [reference/troubleshooting.md](../reference/troubleshooting.md) |
| Processes, layers, pipeline | [development/architecture.md](architecture.md) |

Write in English, in short sentences. Name buttons and labels exactly as the app shows them, in **bold**. Screenshots are in `docs/images/`; retake the ones your change makes outdated.

Specs, plans and other working notes go to `internal/`, not to `docs/`.

## Releases and `make update`

A copy updates by running its own `scripts/update.sh`, the one it has before the update. A change to `scripts/update.sh` therefore takes effect one release later: the release that brings it is still installed by the old script. `make update` refuses to run in a worktree; test it in a separate clone.

## Worktrees

You can work on several branches at once with git worktrees. `make up-worktree` starts a worktree on its own ports (`WORKTREE_PORT`, `WORKTREE_AI_PROXY_PORT` in `.env`, by default 17840 and 8770) with its own `./data`. Only one worktree runs at a time: starting another stops the previous one. `make down-worktree` stops it, and `make logs-worktree` shows its logs.

A new worktree needs its own virtual environment and a `.env`:

```bash
make setup-python
ln -s /path/to/main/checkout/.env .env
```

Don't link the main checkout's `.venv`: the backend is installed in editable mode, so a linked `.venv` would run the main checkout's code.
