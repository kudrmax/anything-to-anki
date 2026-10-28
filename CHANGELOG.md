# Changelog

What changed in each release of AnythingToAnki, newest first.

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
