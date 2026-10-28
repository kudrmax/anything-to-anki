# Installation

AnythingToAnki runs locally on your Mac. Nothing is uploaded to a server, except the AI requests that go to Claude through your own Claude Code login.

## Requirements

| What | Why |
|---|---|
| macOS (Apple Silicon or Intel) | The app and its scripts are built for macOS. The optional [macOS app](../guide/macos-app.md) needs macOS 14+ |
| [Homebrew](https://brew.sh) | Installs Python tooling, Node.js, ffmpeg and espeak |
| [Claude Code](https://claude.com/claude-code), logged in | All AI features run through it. No API key is needed |
| [Anki](https://apps.ankiweb.net/) with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on | Where your cards go |
| Dictionary data | CEFR levels, pronunciations and usage labels. See [step 3](#3-dictionaries) |
| About 3 GB of disk space | Python packages (PyTorch for speech, spaCy), Node packages, the speech model, plus room for your media |

Everything else (Python 3.12, Node.js, ffmpeg, the spaCy language model) is installed by `make setup`.

## 1. Get the code

```bash
git clone https://github.com/kudrmax/anything-to-anki.git
cd anything-to-anki
```

## 2. Install dependencies

```bash
make setup
```

This takes several minutes and downloads about 2 GB. It:

- installs `uv`, `node`, `espeak` and `ffmpeg` with Homebrew;
- creates a Python 3.12 virtual environment in `.venv` and installs the backend;
- downloads the spaCy English model;
- installs the web frontend's packages;
- creates `.env` from `.env.example`.

## 3. Dictionaries

The app reads dictionary data from a folder you point it to with `DICTIONARIES_DIR` in `.env`. The data gives the app:

- CEFR levels of words (Cambridge, Oxford 5000, EFLLex, Kelly);
- US and UK pronunciations and IPA;
- usage labels such as *formal* or *informal*.

Ready-made dictionaries are in the [anything-to-anki-dicts](https://github.com/kudrmax/anything-to-anki-dicts) repository. **Access to it is restricted, so you most likely can't download it.** If you have access:

```bash
git clone https://github.com/kudrmax/anything-to-anki-dicts.git ~/anything-to-anki-dicts
```

and set in `.env`:

```bash
DICTIONARIES_DIR=/Users/you/anything-to-anki-dicts/unified
```

**If you don't have access**, build the dictionaries yourself with the converters from [anything-to-anki-parsers](https://github.com/kudrmax/anything-to-anki-parsers). See [Dictionaries → Building your own](../reference/dictionaries.md#building-your-own).

**To try the app first**, point `DICTIONARIES_DIR` to an empty folder. The app works, with less precise word levels and without dictionary pronunciations, usage labels and calibration. See [Dictionaries → Without dictionaries](../reference/dictionaries.md#without-dictionaries).

```bash
mkdir -p ~/anything-to-anki-dicts-empty
```

`DICTIONARIES_DIR` must be an absolute path to a folder that exists.

## 4. Anki and AnkiConnect

1. Install [Anki](https://apps.ankiweb.net/) and start it.
2. In Anki, open **Tools → Add-ons → Get Add-ons…** and enter the code `2055492159` ([AnkiConnect](https://ankiweb.net/shared/info/2055492159)).
3. Restart Anki.

Anki must be running when you export cards. The rest of the app works without it.

You don't need to create note types or decks: the app creates them on the first export. See [Export to Anki](../guide/anki-export.md).

## 5. Claude Code

AI features (meanings, translations, phrase polish, topics) run through the `claude` command-line tool, using your Claude login.

1. Install [Claude Code](https://claude.com/claude-code).
2. Run `claude` in a terminal and log in with `/login`.
3. Check that `claude` is on your `PATH`:

   ```bash
   which claude
   ```

AI usage counts against your Claude plan. The app shows how much it used on the [Usage](../guide/queue-and-usage.md#usage) screen.

## 6. Start

```bash
make up
```

This builds the web frontend and starts three processes: the AI proxy, the app server and the background worker. When it is ready, it prints the address:

```
AnythingToAnki  [instance: dev]
→ http://localhost:17832
```

Open [http://localhost:17832](http://localhost:17832). The address with your local IP, also printed, works from a phone on the same Wi-Fi.

The first start takes longer: the app creates its database in `./data`, and builds the dictionary cache.

To stop the app:

```bash
make down
```

To see the logs of all three processes:

```bash
make logs
```

## 7. First steps

1. Open **Settings → Vocabulary** and set **Your CEFR level**, the level you are learning now. Then press **Save settings**.
2. Optionally, [calibrate](../guide/vocabulary.md#calibration) your vocabulary.
3. Add your first source: follow [Your first source](first-source.md).

## Optional: the macOS app

A native window with drag and drop and a system-wide Quick Add. See [The macOS app](../guide/macos-app.md).

```bash
make app
```

## Updating

The app tells you when a new release is out: **Update available** appears in the header. Click it, read what is new and press **Update**. You can also run `make update` in the project folder. See [Updating](../guide/updating.md).

The database is migrated automatically on start. A backup is saved to `data/backups/` before each migration.

## Security note

The app server and the AI proxy listen on all network interfaces, without authentication, so you can open the app from your phone. Anyone on the same network can do the same, and can use the AI proxy, which runs on your Claude login. Use the app on networks you trust. See [Configuration](../reference/configuration.md).
