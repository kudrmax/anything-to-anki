# Changelog

What changed in each release of AnythingToAnki, newest first.

## 1.2.1 — 2026-10-29

The Update button works again, every time.

### Update does nothing? Run one command
If you press **Update** and the window flashes and closes, your app is stuck on an older version. One command in Terminal unsticks it and installs this update. You don't need to know the terminal or where the app is: the command finds the app's folder by itself.

1. Open the Terminal app: press ⌘ Space, type **Terminal** and press Return.
2. Paste this line and press Return:

   ```
   pid=$(pgrep -nf backend.infrastructure.api.app) && cd "$(lsof -a -d cwd -Fn -p "$pid" | sed -n 's/^n//p')" && make down && make update
   ```

3. Wait until Terminal says **Updated to** and the new version, then reload the app's page.

The command looks for the running app, so the app must be running. If you restarted your Mac since the last update, the app is not stuck any more: just press **Update**.

### No longer broken
- The Update button stopped working after the first update made with it: the window closed and the app stayed on its version. Now every update starts.

### Improvements
- Updating is now exactly what you would type by hand: download the release, stop the app, switch to the release, start the app. Starting the app installs the Python and frontend packages the release needs.
- If an update seems stuck, the update window says what to do, step by step: open Terminal, paste the command it shows (with a **Copy** button) and wait. If an update fails, the window shows the error and the command to run it by hand.
  ![](docs/images/changelog/1.2.1/update-by-hand.png)
- A failed update stops at the step that broke and says which one, instead of trying to go back. The database is still backed up before the new version changes it.

## 1.2.0 — 2026-10-29

Arrange the Review card your way, and fill incomplete cards before export with one button.

### Card layout editor
**Settings → Card layout → Open the editor** opens the Review screen on a sample card, with the editor on top. Drag blocks between rows and columns, hide the ones you don't need, add dividers, and click a block to change its size, colour and place in its row. Switch what the sample card has to see how a card looks with or without a video, a picture or a meaning. Changes are saved at once, and **Reset to default** brings back the original layout. Anki cards are not affected.
![](docs/images/changelog/1.2.0/card-layout-editor.png)

### Generate missing before export
On the export page, **Generate missing · N cards** fills in what incomplete cards lack, for every source on the page at once: the meaning and the audio of the phrase. Finished cards move to **Ready** on their own. A card it can't fill says why, for example when the video was never downloaded.
![](docs/images/changelog/1.2.0/generate-missing.png)

### Improvements
- The Review card has a new default layout. The left column holds the word with its transcription, level, frequency and usage, then the translation, definition, synonyms and the picture; the right column holds the context, examples and the audio buttons.
- A part with nothing to show is left out of the card, and an empty column gives its room to the others.

### No longer broken
- On a phone-wide window, Settings and **Update available** no longer slip off the header: a dot on the Settings gear shows that an update is out.

## 1.1.0 — 2026-10-28

The update screen now shows what is happening.

### Update stages
While the app updates, you see each stage: downloading the release, saving a backup, installing, starting the new version. Each stage is checked off as it ends, and you see them even while the app restarts.
![](docs/images/changelog/1.1.0/update-stages.png)

### No longer broken
- A card's usage label (formal, informal…) now matches the one that orders your cards.

## 1.0.1 — 2026-10-28

Small fixes after the first release.

### No longer broken
- **Check for Updates…** in the macOS app menu shows at once that it is checking, instead of a pause and then a sudden answer.
  ![](docs/images/changelog/1.0.1/checking-for-updates.png)
- Screenshots in the changelog and the guides now highlight things in the app's own style.

## 1.0.0 — 2026-10-28

The first release. From now on the app tells you when a new version is out and updates itself with one button.

### Updates from the app
When a new release is out, a quiet **Update available** appears in the header. Click it to read what's new, then press **Update**: the app installs the release, restarts and reloads the page. If anything goes wrong, it rolls back to the version you had, with your data as it was.
![](docs/images/changelog/1.0.0/update-available.png)

### New
- **Settings → Updates** shows your version, checks for updates on demand and opens the full changelog.
  ![](docs/images/changelog/1.0.0/settings-updates.png)
- **What's new** opens once after each update.
- In the macOS app, **Check for Updates…** in the app menu; after an update that changes the app itself, a **Restart** banner finishes it.
- `make update` updates from the terminal the same way.
