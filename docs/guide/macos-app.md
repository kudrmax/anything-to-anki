# The macOS app

AnythingToAnki runs in any browser at `http://localhost:17832`. The optional macOS app wraps the same page in a native window and adds a few things a browser can't do:

- **Drag and drop** files from Finder, and a **Choose file…** button.
- **Quick Add**: save a phrase from any app through the macOS **Services** menu.
- It starts the app's servers on launch, so you don't need the terminal.
- Optional **menu bar** mode.

## Building it

The app needs Xcode or the Xcode Command Line Tools (`xcode-select --install`) and macOS 14 or later.

```bash
make app
```

This builds the app and puts it into `~/Applications`. Start it from Launchpad or Spotlight.

The app's name includes `INSTANCE_ENV_NAME` from `.env`. With `INSTANCE_ENV_NAME=dev` it is called **AnythingToAnki Dev**; with `INSTANCE_ENV_NAME=prod` it is called just **AnythingToAnki**. The same name appears in the Services menu.

The app remembers the project folder and port. Run `make app` again after you move the project folder or change `PORT` in `.env`.

## How it starts

On launch, the app checks whether the servers are running. If not, it runs `make up` in the project folder and waits up to two minutes. On quit, it runs `make down`, but only if it started the servers itself.

`make up` runs in a login shell, which reads `~/.zprofile` but not `~/.zshrc`. If the app can't find `claude`, `brew` or `node`, add them to your `PATH` in `~/.zprofile`.

If the servers fail to start, the window shows the error and the last lines of the output.

## Menu bar mode

Set `MENU_BAR_ICON=1` in `.env` and run `make app` again. The app then lives in the menu bar: closing the window hides it from the Dock, and the menu bar icon has **Open** and **Quit**.

## Quick Add

Quick Add saves a phrase you meet anywhere: in Safari, in a book, in a PDF.

1. Select the phrase in any app.
2. Open the app menu → **Services → Add to AnythingToAnki** (the name follows the app's name). You can assign a keyboard shortcut to it in **System Settings → Keyboard → Keyboard Shortcuts → Services**.
3. A small window opens with the phrase. Select the word, phrasal verb or collocation you want to learn. Hold `⌘` to pick separated words, like `give … up`.
4. Press **Save** (`Enter`).

The phrase goes to the built-in **Saved phrases** source, and the word is marked **Learn**.

## Other features

- **Settings** with `⌘,`, also in the app menu.
- **Zoom** with `⌘+`, `⌘-` and `⌘0`.
- **Reload** with `⌘R`.
