# Updating

AnythingToAnki is released in versions. The app checks for a new one and updates itself with one button.

## Finding out about a new version

Once a day the app looks for a release newer than the one you run. If it finds one, a quiet **Update available** appears in the header. It stays until you update. On a phone-wide window the header has no room for it: a dot on the Settings gear shows instead, and **Settings → Updates** says which version is out.

![Update available in the header](../images/updating/indicator.png)

To look right now, open **Settings → Updates** and press **Check for updates**, or choose **Check for Updates…** in the macOS app's menu. If nothing is new, you see "You're on the latest version".

![Settings → Updates with Changelog and Check for updates](../images/updating/settings-updates.png)

## Updating

1. Click **Update available**. The window lists every version newer than yours, with what changed.
2. Press **Update**.
3. **Updating…** covers the app while it installs the release and restarts. Don't close the app. A page opened or reloaded while the update runs shows **Updating…** too.

   Under it is the list of stages. Finished ones have a check mark, the one running now has a spinner:

   - **Downloading v1.2.0** (it says **Checking for the new version** until the version is known)
   - **Saving a backup**: the installed packages, then the app stops and the database is copied
   - **Installing v1.2.0**: the release and its Python packages, and the macOS app when it changed
   - **Starting the new version**

   If a stage fails, it is marked with a cross, the stages after it are dropped and **Rolling back to v1.1.0** is added as the running stage.
4. The page reloads and shows **What's new**. Close it and it won't appear again.

![The update window with the Update button](../images/updating/update-window.png)

While a long operation runs, such as a big import, pressing **Update** shows the long-operation window instead of updating. Wait for it to finish and press **Update** again.

## What's new and the changelog

**What's new** shows once after an update, with every version since the last one you saw. On a fresh install it doesn't appear.

**Settings → Updates → Changelog** opens the whole history at any time. The same text is in `CHANGELOG.md` and on the project's GitHub Releases page.

## If the update fails

The window says **Update failed**. It names the step that failed with its last lines of output, then the end of the update's log, and the command `make update` with a **Copy** button. Your copy is back on the old version and running. The full log is in `.logs/update.log`, and `make logs` shows it too.

Run `make update` in the project folder to see what went wrong.

### If the app does not come back

While the app is stopped, `make update` answers the page on the app's port with a small status server of its own, so the list keeps moving. It stops just before the app starts again; if it can't start, for example because the port is taken, the update goes on and the list stays on the last stage it showed. The window still can't tell a slow update from one that stopped. **Updating…** always shows a line for that case: if the app doesn't come back, run `make up` in the project folder (with a **Copy** button). The log is in `.logs/update.log`.

The app stays stopped only when the way back itself failed. Then the end of `.logs/update.log` says what is left to do by hand: where the database from before the update is and the commands that finish the rollback.

## From the terminal

```bash
make update
```

`make update` does what the button does:

1. Refuses if you changed tracked files in the project folder. Commit or undo your changes first. It also refuses in a git worktree: run it in the main checkout.
2. Fetches the releases. If you already have the latest one, it prints "Already up to date" and changes nothing. This is also the case when you run the development version from `master`, which is never older than the last release.
3. Keeps a copy of the installed packages, stops the app, saves a copy of the database, switches to the latest release and installs its Python packages. The frontend packages are installed when the app starts.
4. Rebuilds the macOS app if you built it and it changed.
5. Starts the app. The database is migrated on start.

## Rollback

After `make update` the copy is on the new version and running, or on the old version and running. If a step fails, the command puts back the previous version, its packages and the database copy, starts the app again and exits with an error. The packages come from a copy of `.venv` and `frontends/web/node_modules` kept before the update, so the way back needs no network.

`make update` refuses to start if either folder is missing; run `make setup` first. If the frontend packages were out of date before the update (`package-lock.json` changed and the app was not started since), they are put back as they were, and starting the old version installs them again, as `make up` always does. That one step needs the network.

One case leaves the app stopped: a step of the way back itself fails, for example the database copy can't be restored. Starting the old version on a database it may not know would be worse, so the command stops and prints where the database copy and the kept packages are and the commands that finish the job. Until you finish them and move `.pids/update-backup` to the trash, `make update` refuses to run and repeats those commands.

## macOS app

When the update changes the app itself, a note in its title bar says **Restart to finish the update** with a **Restart** button. See [The macOS app](macos-app.md#updates).
