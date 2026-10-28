#!/bin/bash
# Moves this copy to the latest release tag. After `make down` any failure brings the copy
# back to the commit, database and app it had, and starts it again. When the way back is
# not certain, the copy stays stopped and the output says what to do.
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
    LOCK_FILE=.pids/update.script.lock
    RELEASE_TAG_PATTERN='^v[0-9]+\.[0-9]+\.[0-9]+$'
    MACOS_DIR=frontends/macos
    PLIST_BUDDY=/usr/libexec/PlistBuddy
    APP_DIR_KEY=A2AProjectDir
    NO_DATABASE=NO_DATABASE

    stopped=0
    snapshot_taken=0
    checked_out=0
    app_built=0
    snapshot=""
    old_ref=""

    trap on_signal INT TERM HUP

    take_lock
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
    if [ "$snapshot" != "$NO_DATABASE" ] && [ ! -f "$snapshot" ]; then
        echo "ERROR: the database copy was not made (got '$snapshot')." >&2
        roll_back
    fi
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

# A second update in the same copy would stop and switch it under the first one. The lock
# is flock on descriptor 9, which this shell keeps open: the kernel drops it when the
# shell dies, so a crashed run never blocks the next. make runs with 9 closed, or servers
# started by `make up` would hold the lock after the update ends.
take_lock() {
    mkdir -p .pids
    exec 9>>"$LOCK_FILE"
    if ! /usr/bin/perl -MFcntl=:flock \
        -e 'open(my $fh, ">&=", 9) or exit 2; flock($fh, LOCK_EX | LOCK_NB) or exit 1'
    then
        echo "ERROR: another 'make update' is already running in this copy" \
            "(PID $(cat "$LOCK_FILE" 2>/dev/null)). Wait for it to finish." >&2
        exit 1
    fi
    printf '%s' "$$" > "$LOCK_FILE"
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
    "$MAKE" --no-print-directory "$@" 9>&-
}

# A credential helper daemon started by fetch must not inherit the lock either.
git() {
    command git "$@" 9>&-
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

restore_argument() {
    if [ "$snapshot" = "$NO_DATABASE" ]; then echo --none; else echo "$snapshot"; fi
}

# Stops the copy without starting it: something on the way back failed, and starting the
# old code on a database it may not know is worse than a stopped copy.
leave_stopped() {
    echo "ERROR: rollback failed at: $1. The copy is stopped." >&2
    if [ "$snapshot_taken" = 1 ]; then
        echo "The database from before the update: $snapshot" >&2
        echo "To finish by hand: make down; git checkout --force $old_ref;" \
            "make setup-python; make _db-restore SNAPSHOT=$(restore_argument); make up" >&2
    else
        echo "The database was not changed. To finish by hand:" \
            "make down; git checkout --force $old_ref; make up" >&2
    fi
    finish failed
}

roll_back() {
    trap '' INT TERM HUP
    echo "Update failed. Rolling back to $old_ref..." >&2
    # A failed start can leave the new version's processes running, a migration among them.
    make_step down || leave_stopped "make down"
    if [ "$checked_out" = 1 ]; then
        # The tree was clean at the start: only a half-done checkout can have changed it.
        git checkout --quiet --force "$old_ref" || leave_stopped "git checkout"
        make_step setup-python || leave_stopped "make setup-python"
    fi
    if [ "$snapshot_taken" = 1 ]; then
        make_step _db-restore SNAPSHOT="$(restore_argument)" || leave_stopped "database restore"
    fi
    local broken=""
    if [ "$app_built" = 1 ]; then
        make_step app || broken=" The macOS app was not rebuilt: run 'make app'."
    fi
    if ! make_step up; then
        echo "ERROR: the old version did not start. See the output above, then run 'make up'." >&2
        finish failed
    fi
    echo "Rolled back to $old_ref and started.$broken" >&2
    finish failed
}

on_signal() {
    if [ "$stopped" = 1 ]; then roll_back; fi
    refuse "Update interrupted."
}

main "$@"
