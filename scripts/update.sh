#!/bin/bash
# Moves this copy to the latest release tag. After `make down` any failure brings the copy
# back to the commit, database and app it had, and starts it again.
#
# Runs in the copy's folder. Ends by writing `done` or `failed` to .pids/update.state,
# which the app reads after the restart.
#
# Everything is inside main(): bash reads a script as it runs, and the checkout below
# rewrites this very file.

set -uo pipefail

main() {
    MAKE="${MAKE:-make}"
    APPS_DIR="${UPDATE_APPS_DIR:-$HOME/Applications}"
    STATE_FILE=.pids/update.state
    PID_FILE=.pids/update.pid
    RELEASE_TAG_PATTERN='^v[0-9]+\.[0-9]+\.[0-9]+$'
    MACOS_DIR=frontends/macos
    PLIST_BUDDY=/usr/libexec/PlistBuddy
    APP_DIR_KEY=A2AProjectDir

    stopped=0
    snapshot_taken=0
    checked_out=0
    app_built=0
    snapshot=""
    old_ref=""

    trap on_signal INT TERM HUP

    write_state running
    printf '%s' "$$" > "$PID_FILE"

    require_clean_tree
    if ! git fetch --tags origin; then
        refuse "Could not reach origin. Check the connection and run 'make update' again."
    fi

    local tag
    tag=$(latest_release_tag)
    if [ -z "$tag" ]; then
        echo "No release on origin yet. Nothing to update."
        finish done
    fi
    if git merge-base --is-ancestor "$tag" HEAD; then
        echo "Already up to date ($tag)."
        finish done
    elif [ $? -ne 1 ]; then
        refuse "Could not compare this copy with $tag."
    fi

    old_ref=$(git symbolic-ref --quiet --short HEAD || git rev-parse HEAD)
    local old_commit
    old_commit=$(git rev-parse HEAD)
    echo "Updating to $tag..."

    stopped=1
    make_step down || roll_back
    snapshot=$(make_step --silent _db-snapshot | tail -n 1) || roll_back
    snapshot_taken=1
    checked_out=1
    git checkout --quiet "$tag" || roll_back
    make_step setup-python || roll_back
    if macos_code_changed "$old_commit" "$tag" && app_of_this_copy_installed; then
        app_built=1
        make_step app || roll_back
    fi
    make_step up || roll_back

    echo "Updated to $tag."
    finish done
}

write_state() {
    mkdir -p .pids
    printf '%s' "$1" > "$STATE_FILE"
}

finish() {
    write_state "$1"
    if [ "$1" = done ]; then exit 0; fi
    exit 1
}

refuse() {
    echo "ERROR: $1" >&2
    finish failed
}

make_step() {
    "$MAKE" --no-print-directory "$@"
}

require_clean_tree() {
    local changes
    if ! changes=$(git status --porcelain --untracked-files=no); then
        refuse "This folder is not a git copy of the app."
    fi
    if [ -n "$changes" ]; then
        echo "ERROR: this copy has uncommitted changes:" >&2
        echo "$changes" >&2
        refuse "Commit or stash them, then run 'make update' again."
    fi
}

latest_release_tag() {
    git tag --list 'v*' \
        | { grep -E "$RELEASE_TAG_PATTERN" || true; } \
        | sort -t . -k 1.2,1n -k 2,2n -k 3,3n \
        | tail -n 1
}

macos_code_changed() {
    # Exit code 1 means a difference; anything else unexpected counts as one too.
    ! git diff --quiet "$1" "$2" -- "$MACOS_DIR"
}

app_of_this_copy_installed() {
    local here plist dir
    here=$(pwd -P)
    for plist in "$APPS_DIR"/*.app/Contents/Info.plist; do
        [ -f "$plist" ] || continue
        dir=$("$PLIST_BUDDY" -c "Print :$APP_DIR_KEY" "$plist" 2>/dev/null) || continue
        [ -d "$dir" ] || continue
        if [ "$(cd "$dir" && pwd -P)" = "$here" ]; then return 0; fi
    done
    return 1
}

roll_back() {
    trap '' INT TERM HUP
    echo "Update failed. Rolling back to $old_ref..." >&2
    local broken=""
    if [ "$snapshot_taken" = 1 ]; then
        make_step _db-restore SNAPSHOT="$snapshot" || broken="$broken database"
    fi
    if [ "$checked_out" = 1 ]; then
        # The tree was clean at the start: only a half-done checkout can have changed it.
        git checkout --quiet --force "$old_ref" || broken="$broken checkout"
        make_step setup-python || broken="$broken setup-python"
        if [ "$app_built" = 1 ]; then
            make_step app || broken="$broken app"
        fi
    fi
    make_step up || broken="$broken up"
    if [ -n "$broken" ]; then
        echo "ERROR: rollback failed at:$broken. See the output above; 'make up' starts the copy." >&2
    else
        echo "Rolled back to $old_ref and started." >&2
    fi
    finish failed
}

on_signal() {
    if [ "$stopped" = 1 ]; then roll_back; fi
    refuse "Update interrupted."
}

main "$@"
