# Changelog

What changed in each release of AnythingToAnki, newest first.

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
