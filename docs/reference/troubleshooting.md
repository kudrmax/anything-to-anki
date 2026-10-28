# Troubleshooting

Start with the logs. They show the app server, the worker, the AI proxy and `make update` in one stream:

```bash
make logs
```

For more detail, set `LOG_LEVEL=DEBUG` in `.env` and restart with `make down && make up`.

## Installation and start

| Message | Cause and fix |
|---|---|
| `ERROR: Homebrew not installed` | Install [Homebrew](https://brew.sh), then run `make setup` again |
| `ERROR: .venv not found. Run 'make setup' first.` | Run `make setup` |
| `ERROR: node_modules not found. Run 'make setup' first.` | Run `make setup` |
| `ERROR: ffmpeg not installed. Run 'make setup' first.` | Run `make setup`, or `brew install ffmpeg` |
| `WARNING: .venv is not built on uv-managed Python` | Recreate it: move `.venv` to the Trash, then run `make setup` |
| `ERROR: DICTIONARIES_DIR not set in .env` | Set `DICTIONARIES_DIR` in `.env`. See [Dictionaries](dictionaries.md) |
| `ERROR: DICTIONARIES_DIR=... is not a folder` | `DICTIONARIES_DIR` points to a folder that doesn't exist. Set it to an existing folder |
| `ERROR: port 17832 is held by PID ...` | Another program uses the port. Stop it, or change `PORT` / `AI_PROXY_PORT` in `.env` |
| `ERROR: ai_proxy exited on start` | See the lines below the message. Most often Claude Code isn't logged in: run `claude`, then `/login` |
| `ERROR: app exited on start` | See the lines below the message, and `make logs` |

## AI unavailable

When AI can't be reached, a banner says **AI unavailable — reason**. AI jobs wait and resume on their own once the problem is gone.

| Reason | Fix |
|---|---|
| `Cannot connect to AI proxy. Make sure ai_proxy.py is running on the host.` | The AI proxy is not running. Run `make up`, then check `make logs` |
| A login error from Claude | Run `claude` in a terminal and log in again with `/login`. Then run `make up` |
| A rate limit or billing error from Claude | You have reached your Claude plan's limit. Wait until it resets |
| `Blocked country: RU. Turn on VPN.` | Claude is not available in your region |

The AI proxy finds `claude` on your `PATH`, or at `/opt/homebrew/bin/claude`. If you installed Claude Code somewhere else, make sure `which claude` works in the shell you run `make up` from.

## Adding sources

| Message | Cause and fix |
|---|---|
| **This link can't be read** | Only YouTube links are supported. For an article, paste its text or save it as a file |
| **Subtitles are not available for this video** | The YouTube video has no English subtitles, not even auto-generated ones |
| **No file at this path** | Check the path. It must be absolute, like `/Users/you/file.epub` |
| `Not a text file` | The file's type is not supported. See [What you can add](../guide/sources.md#what-you-can-add) |
| `No subtitles found in video. Please attach a .srt file.` | The video has no text subtitle track. Attach an `.srt` file. If you are sure the video has one, check that `ffprobe` works: `ffprobe -version` |
| **Dropped files reach the app only in the macOS app** | In a browser, paste the file's path instead, or use the [macOS app](../guide/macos-app.md) |
| **Processing failed** | The reason is in `make logs`. Press **Retry** |

## Export to Anki

| Message | Cause and fix |
|---|---|
| **Launch Anki with AnkiConnect to sync** | Start Anki. Check that the AnkiConnect add-on is installed and enabled |
| **Export to Anki is blocked: cards would lose their content** | Your own note type is missing or lacks fields. See [Using your own note type](../guide/anki-export.md#using-your-own-note-type) |
| Some cards **failed** | See `make logs` for Anki's reason |
| A part of the card doesn't show in Anki | You renamed a field after the note type was created. Re-paste the templates from **Settings → Anki → Fields and templates** |

## Generation

| What you see | Cause and fix |
|---|---|
| Cards stay **Queued** | Check the [Queue](../guide/queue-and-usage.md#queue) screen and the AI banner. The worker may not be running: run `make up` |
| **Failed to generate** on a card | Hover it for the reason. Retry it on the card, or with **Retry failed** in the Queue |
| A job fails with `timeout` | It ran longer than 10 minutes. Retry it |
| **Media** is disabled, with **Download video** | A YouTube video must be downloaded before screenshots can be cut. Use **Download video** |
| Media fails for a local video | The video file was moved or deleted. Put it back at the same path |

## The macOS app

| Message | Cause and fix |
|---|---|
| **The server failed to start** | The window shows the end of the output. The app runs `make up` in a login shell, which reads `~/.zprofile` but not `~/.zshrc`; add Homebrew and `claude` to `PATH` in `~/.zprofile` |
| **This app bundle is broken** | Run `make app` again in the project folder |
| The app opens the wrong copy or port | Run `make app` again after moving the project folder or changing `PORT` |
