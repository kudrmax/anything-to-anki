---
name: release
description: Cuts a release of AnythingToAnki - picks the version, writes the CHANGELOG.md entry with annotated screenshots, bumps the version, tags, pushes and creates the GitHub Release. Use when Max says "выпускай релиз", "сделай релиз", "release" or "cut a release". Never on your own initiative: a merge to master is not a release.
---

# Release

Run only on Max's command. Publish without asking for approval of the text: Max can edit the release on GitHub and fix it in the next commit.

Run everything in the main checkout (`~/projects/anything-to-anki`), on master, as the git rules in the global CLAUDE.md require. Do not switch branches there.

## 1. Preconditions

```bash
git status --porcelain            # must be empty
git pull --ff-only
git fetch --tags origin
git rev-parse HEAD origin/master  # must be equal
```

Stop and tell Max if the tree is dirty, the pull does not fast-forward, or HEAD differs from `origin/master`.

## 2. Collect changes and pick the version

```bash
PREV=$(git tag --list 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -1)
git log "$PREV"..HEAD --no-merges --format='%s'     # no tag yet: git log --no-merges
```

- No previous tag: the version is `1.0.0`.
- Any `feat:` since the tag: raise the minor number (`1.2.3` becomes `1.3.0`).
- Only `fix:` and the like: raise the patch number.
- Nothing user-visible (only `chore:`, `docs:`, `test:`, `refactor:`): tell Max there is nothing to release and stop.

The current version is `version` in the root `pyproject.toml` (not `backend/pyproject.toml`).

## 3. Write the entry

English, because it is user documentation. Format of the [Obsidian changelog](https://obsidian.md/changelog/):

```markdown
## X.Y.Z — YYYY-MM-DD

One sentence: what this release is about.

### Name of a big feature
What it does for the user, in a few sentences.
![](docs/images/changelog/X.Y.Z/feature.png)

### New
- …
### Improvements
- …
### No longer broken
- …
```

- A big feature gets its own section with its own heading, before **New**.
- Write for the user in plain language. Skip internal changes: refactoring, tests, migrations, docs.
- Do not write empty sections.
- Group commits by what the user sees, not one line per commit. Read the diff when a commit subject is unclear.
- Insert the entry right after the intro of `CHANGELOG.md`, above older entries.

## 4. Screenshots

Take them in the running **dev copy** in one pass for all features of the release: `http://localhost:<PORT>`, where `PORT` is in the dev copy's `.env`. Check that it is up; if not, tell Max (do not run `make up` yourself).

- Use a headless browser (Playwright or similar). Never the browser pane Max is watching.
- Every big feature and every notable item gets a screenshot.
- On each screenshot draw an arrow or a frame where to look, with `annotate.js` from this folder. Inject the file into the page, then call it before the screenshot:

```js
window.__annotate({ selector: '[data-testid="…"]', kind: 'frame', label: 'Optional text' })  // or kind: 'arrow'
// take the screenshot
window.__clearAnnotations()
```

- Save as `docs/images/changelog/X.Y.Z/<name>.png` and reference with the path from the repository root, as in the entry above.
- Look at every screenshot before committing. Use only data that is fine to publish.

## 5. Commit, tag, publish

```bash
# bump `version` in the root pyproject.toml to X.Y.Z
git add pyproject.toml CHANGELOG.md docs/images/changelog/X.Y.Z
git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
git push origin master
git push origin vX.Y.Z
```

If a push is rejected, stop and tell Max. Do not force.

Create the GitHub Release with the same text as the entry, without its `## X.Y.Z` heading. Rewrite image links to absolute ones:

```bash
sed -E 's#\]\((docs/images/[^)]+)\)#](https://raw.githubusercontent.com/kudrmax/anything-to-anki/vX.Y.Z/\1)#g' entry.md > "$TMP/notes.md"
gh release create vX.Y.Z --title X.Y.Z --notes-file "$TMP/notes.md"
```

Write the temporary files to the scratchpad directory, not to the repository.

## 6. Afterwards

Tell Max the release URL (`gh release view vX.Y.Z --json url -q .url`).

Prod is not updated by merging or by this skill. It updates with the **Update** button in the app or with `make update` in the prod copy. If the prod copy is not on release tags yet (first release), switch it with `git checkout vX.Y.Z` there, nothing else.
