# Configuration

Most settings live in the app's [Settings](../guide/settings.md) screen. This page covers what is configured outside the app: the `.env` file, environment variables, and the AI prompts.

## `.env`

`make` creates `.env` from [`.env.example`](../../.env.example) the first time you run it. Edit it, then restart with `make down && make up`.

| Variable | Default | Meaning |
|---|---|---|
| `DICTIONARIES_DIR` | (none) | **Required.** Absolute path to the [dictionary](dictionaries.md) folder. It must exist |
| `PORT` | `17832` | Port of the app |
| `AI_PROXY_PORT` | `8766` | Port of the AI proxy |
| `INSTANCE_ENV_NAME` | `dev` | A label shown as a badge in the top bar and in the [macOS app](../guide/macos-app.md)'s name; `prod` is left out of the app's name. It changes nothing else |
| `MENU_BAR_ICON` | `0` | `1` makes the macOS app live in the menu bar. Run `make app` after changing it |
| `WORKTREE_PORT`, `WORKTREE_AI_PROXY_PORT` | `17840`, `8770` | Ports for development worktrees. See [Contributing](../development/contributing.md#worktrees) |

`make` passes every variable in `.env` to the app's processes, so you can also set the variables below in `.env`.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `DATA_DIR` | `./data` | Where the database, media and downloaded videos are stored |
| `MEDIA_ROOT` | `$DATA_DIR/media` | Where screenshots, audio and pictures are stored. The app deletes files here that it doesn't know about, so don't point it at a shared folder |
| `ANKI_URL` | `http://localhost:8765` | AnkiConnect's address |
| `PROMPTS_CONFIG_PATH` | `config/prompts.yaml` | The AI prompts file (see below) |
| `LOG_LEVEL` | `INFO` | Log level of all processes, e.g. `DEBUG` |
| `AI_PROXY_URL` | set by `make up` | Where the app finds the AI proxy |
| `FRONTEND_DIST` | `frontends/web/dist` | The built web frontend the app serves |

## Data folder

Everything you create in the app lives in `DATA_DIR` (`./data` by default):

| Path | Contents |
|---|---|
| `app.db` | The database: sources, cards, decisions, settings |
| `media/<source id>/` | Screenshots, audio clips, speech and pictures |
| `videos/` | Downloaded YouTube videos. They are deleted once their screenshots are cut |
| `backups/` | A copy of the database before each migration. The last 5 are kept |
| `open_reviews/` | The order of open reviews |

Local video files and other files you add are not copied. The app stores their paths and reads them in place.

To back up your work, stop the app and copy the `data` folder.

## AI prompts

The prompts for meanings, polish and topics are in [`config/prompts.yaml`](../../config/prompts.yaml). You can edit them, or point `PROMPTS_CONFIG_PATH` to your own copy. The answers must keep the same fields, because the app parses them.

### Translation language

Card translations are into **Russian**. To translate into another language, change the `translation` instruction in `config/prompts.yaml`:

```yaml
translation: |-
  For the 'translation' field, provide a short Spanish translation of the word (1-3 words). ...
```

New meanings will use the new language. To redo existing ones, use **✨ → Meanings → regenerate all** in Review.

## AI and network

- AI requests go from the AI proxy to Claude through the `claude` command-line tool and your Claude Code login.
- Before each AI request, the AI proxy checks the country of your public IP address with [ipinfo.io](https://ipinfo.io). From Russia, AI requests are refused with **Blocked country: RU. Turn on VPN.**
- Picture search queries Wiktionary, Bing and Yandex. Pronunciations are downloaded from the URLs in the dictionaries. YouTube subtitles and videos are downloaded with [yt-dlp](https://github.com/yt-dlp/yt-dlp). The speech model is downloaded from Hugging Face on first use.
- The app server and the AI proxy listen on all network interfaces, without authentication. Anyone on your network can open the app and use the AI proxy, which runs on your Claude login.
