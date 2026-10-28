# Updating

AnythingToAnki is released in versions. The app checks for a new one and updates itself with one button.

## Finding out about a new version

Once a day the app looks for a release newer than the one you run. If it finds one, a quiet **Update available** appears in the header. It stays until you update.

![Update available in the header](../images/updating/indicator.png)

To look right now, open **Settings → Updates** and press **Check for updates**, or choose **Check for Updates…** in the macOS app's menu. If nothing is new, you see "You're on the latest version".

![Settings → Updates with Changelog and Check for updates](../images/updating/settings-updates.png)

## Updating

1. Click **Update available**. The window lists every version newer than yours, with what changed.
2. Press **Update**.
3. **Updating…** covers the app while it installs the release and restarts. Don't close the app.
4. The page reloads and shows **What's new**. Close it and it won't appear again.

![The update window with the Update button](../images/updating/update-window.png)

**Update** is refused while a long operation runs, such as a big import. Wait for it to finish and try again.

## What's new and the changelog

**What's new** shows once after an update, with every version since the last one you saw. On a fresh install it doesn't appear.

**Settings → Updates → Changelog** opens the whole history at any time. The same text is in `CHANGELOG.md` and on the project's GitHub Releases page.

## If the update fails

The window says **Update failed**, shows the last lines of the log and the command `make update` with a **Copy** button. Your copy is still on the old version and running. The full log is in `.logs/update.log`.

Run `make update` in the project folder to see what went wrong.

## From the terminal

```bash
make update
```

`make update` does what the button does:

1. Refuses if you changed tracked files in the project folder. Commit or undo your changes first.
2. Fetches the releases. If you already have the latest one, it prints "Already up to date" and changes nothing. This is also the case when you run the development version from `master`, which is never older than the last release.
3. Stops the app, saves a copy of the database, switches to the latest release and installs its packages.
4. Rebuilds the macOS app if you built it and it changed.
5. Starts the app. The database is migrated on start.

## Rollback

After `make update` the copy is either on the new version and running, or on the old version and running. If a step fails, the command restores the database copy and the previous version, starts the app again and exits with an error. If it can't be sure the way back is safe, it leaves the app stopped and says what to do.

## macOS app

When the update changes the app itself, a note in its title bar says **Restart to finish the update** with a **Restart** button. See [The macOS app](macos-app.md#updates).
