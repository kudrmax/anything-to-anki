#!/bin/bash
# Moves this copy to the latest release tag. After `make down` any failure brings the copy
# back to the commit, database, packages and app it had, and starts it again. When the way
# back is not certain, the copy stays stopped and the output says what to do.
#
# Runs in the copy's folder. Ends by writing `done` or `failed` to .pids/update.state,
# which the app reads after the restart. Everything it and its steps print is written
# straight to .logs/update.log; a follower copies the log to the terminal.
#
# Everything is inside main(): bash reads a script as it runs, and the checkout below
# rewrites this very file.

set -uo pipefail

main() {
    MAKE="${MAKE:-make}"
    APPS_DIR="${UPDATE_APPS_DIR:-$HOME/Applications}"
    TRASH="${UPDATE_TRASH:-trash}"
    STATE_FILE=.pids/update.state
    PID_FILE=.pids/update.pid
    LOCK_FILE=.pids/update.script.lock
    START_LOCK_FILE=.pids/update.lock
    ERROR_FILE=.pids/update.error
    STEP_NAME_FILE=.pids/update.step
    STEP_START_FILE=.pids/update.step.start
    SNAPSHOT_OUT_FILE=.pids/update.snapshot.out
    FOLLOW_STOP_FILE=.pids/update.follow.stop
    LOG_FILE=.logs/update.log
    BACKUP_DIR=.pids/update-backup
    RECOVERY_FILE=.pids/update-backup/RECOVERY
    RELEASE_TAG_PATTERN='^v[0-9]+\.[0-9]+\.[0-9]+$'
    MACOS_DIR=frontends/macos
    VENV_DIR=.venv
    NODE_MODULES_DIR=frontends/web/node_modules
    # npm's own record of what it installed; `make up` reinstalls when the lock is newer.
    NODE_MODULES_STAMP=frontends/web/node_modules/.package-lock.json
    PACKAGE_LOCK=frontends/web/package-lock.json
    PLIST_BUDDY=/usr/libexec/PlistBuddy
    APP_DIR_KEY=A2AProjectDir
    NO_DATABASE=NO_DATABASE
    # Enough of a failed step's output to show its error, short enough for the app's popup.
    ERROR_TAIL_LINES=30
    # How soon the terminal shows a new line of the log.
    FOLLOW_POLL_S=0.1
    # How much of the log the follower reads at once; any size works.
    FOLLOW_CHUNK_BYTES=65536

    # The update runs unattended from the app: a git asking for a password would hang it.
    export GIT_TERMINAL_PROMPT=0

    stopped=0
    snapshot_taken=0
    checked_out=0
    app_built=0
    backups_taken=0
    keep_backups=0
    node_modules_fresh=0
    snapshot=""
    old_ref=""
    old_name=""
    follower=""

    trap on_signal INT TERM HUP

    take_lock
    start_log
    write_state running
    : > "$ERROR_FILE"
    printf '%s' "$$" > "$PID_FILE"

    refuse_in_worktree
    refuse_after_a_stopped_update
    require_installed_packages
    require_clean_tree
    if ! run_step "git fetch" git fetch --tags --force origin; then
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
    old_name=$(git describe --tags --exact-match HEAD 2>/dev/null || echo "$old_ref")
    local old_commit
    old_commit=$(git rev-parse HEAD)
    echo "Updating to $tag..."

    back_up_packages

    stopped=1
    make_step down || roll_back
    # The path is the step's last line of stdout, read from a file: a pipe would wait for
    # every process that inherited it.
    local snapshot_status=0
    make_step --silent _db-snapshot > "$SNAPSHOT_OUT_FILE" || snapshot_status=$?
    cat "$SNAPSHOT_OUT_FILE"
    [ "$snapshot_status" = 0 ] || roll_back
    snapshot=$(tail -n 1 "$SNAPSHOT_OUT_FILE")
    if [ "$snapshot" != "$NO_DATABASE" ] && [ ! -f "$snapshot" ]; then
        fail_step "database copy" "ERROR: the database copy was not made (got '$snapshot')."
    fi
    snapshot_taken=1
    checked_out=1
    run_step "git checkout" git checkout --quiet "$tag" || roll_back
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
# shell dies, so a crashed run never blocks the next. The app takes the lock before it
# starts the script and hands it over on descriptor 9, so the update counts as running
# from the click on. make runs with 9 closed, or servers started by `make up` would hold
# the lock after the update ends.
#
# The app checks whether an update runs by taking the lock shared for a moment. Both that
# check and this attempt happen under the start lock, so the check can never make this
# attempt fail.
take_lock() {
    mkdir -p .pids
    if lock_inherited; then return; fi
    exec 9>>"$LOCK_FILE"
    if ! /usr/bin/perl -MFcntl=:flock -e '
        open(my $start, ">>", $ARGV[0]) or exit 2;
        flock($start, LOCK_EX) or exit 2;
        open(my $fh, ">&=", 9) or exit 2;
        flock($fh, LOCK_EX | LOCK_NB) or exit 1;
    ' "$START_LOCK_FILE"
    then
        echo "ERROR: another 'make update' is already running in this copy." \
            "Wait for it to finish." >&2
        exit 1
    fi
}

lock_inherited() {
    /usr/bin/perl -e '
        open(my $fh, ">&=", 9) or exit 1;
        my @held = stat($fh);
        my @file = stat($ARGV[0]) or exit 1;
        exit(($held[0] == $file[0] && $held[1] == $file[1]) ? 0 : 1);
    ' "$LOCK_FILE" 2>/dev/null
}

# Output goes straight to the log file, never through a pipe: a pipe's reader waits until
# every process holding it is gone, and a step can leave one behind (a credential helper,
# an ssh master). The log is complete before the lock is released. The terminal gets the
# log through a follower that reads the file; finish() waits for it to catch up.
start_log() {
    mkdir -p "$(dirname "$LOG_FILE")"
    : >> "$LOG_FILE"
    : > "$FOLLOW_STOP_FILE"
    local start
    start=$(log_size)
    follow_log "$start" &
    follower=$!
    exec >>"$LOG_FILE" 2>&1
    echo "=== make update $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
}

log_size() {
    wc -c < "$LOG_FILE" | tr -d ' '
}

# Prints the log from the given byte on until the script asks it to stop (by writing to
# the stop file) or dies, then prints what is left. A Ctrl-C reaches the whole terminal group: the follower
# ignores it, so the rollback stays visible.
follow_log() {
    exec /usr/bin/perl -e '
        my ($path, $offset, $script, $poll, $stop_file, $chunk_size) = @ARGV;
        $SIG{INT} = $SIG{TERM} = $SIG{HUP} = $SIG{PIPE} = "IGNORE";
        open(my $log, "<", $path) or exit 1;
        sysseek($log, $offset, 0);
        $| = 1;
        my $chunk;
        while (1) {
            my $last = -s $stop_file || !kill(0, $script);
            while (sysread($log, $chunk, $chunk_size)) { print $chunk or exit 0 }
            last if $last;
            select(undef, undef, undef, $poll);
        }
    ' "$LOG_FILE" "$1" "$$" "$FOLLOW_POLL_S" "$FOLLOW_STOP_FILE" "$FOLLOW_CHUNK_BYTES" 9>&-
}

stop_follower() {
    [ -n "$follower" ] || return 0
    echo stop > "$FOLLOW_STOP_FILE"
    wait "$follower" 2>/dev/null
}

write_state() {
    mkdir -p .pids
    printf '%s' "$1" > "$STATE_FILE"
}

finish() {
    if [ "$keep_backups" != 1 ]; then discard_backups; fi
    write_state "$1"
    stop_follower
    if [ "$1" = done ]; then exit 0; fi
    exit 1
}

refuse() {
    echo "ERROR: $*" >&2
    echo "$*" > "$ERROR_FILE"
    finish failed
}

# Remembers where a step's output starts in the log, so a failure can say what broke
# without the rest of the log around it.
run_step() {
    local name=$1
    shift
    printf '%s' "$name" > "$STEP_NAME_FILE"
    log_size > "$STEP_START_FILE"
    "$@" 9>&-
}

make_step() {
    local target
    for target in "$@"; do
        case "$target" in -*) ;; *) break ;; esac
    done
    run_step "make $target" "$MAKE" --no-print-directory "$@"
}

fail_step() {
    printf '%s' "$1" > "$STEP_NAME_FILE"
    log_size > "$STEP_START_FILE"
    echo "$2" >&2
    roll_back
}

# A credential helper daemon started by fetch must not inherit the lock either.
git() {
    command git "$@" 9>&-
}

refuse_in_worktree() {
    if [ "$(git rev-parse --git-dir 2>/dev/null)" != "$(git rev-parse --git-common-dir 2>/dev/null)" ]; then
        refuse "make update is for the dev and prod copies, not a worktree. Run it in the main checkout."
    fi
}

# A run that left the copy stopped marks its kept packages with the recovery recipe, which
# moves them back; another run would replace them, so the recovery comes first. Kept
# packages without the marker are only a backup whose trashing failed.
refuse_after_a_stopped_update() {
    [ -e "$BACKUP_DIR" ] || return 0
    if [ -f "$RECOVERY_FILE" ]; then
        refuse "An earlier update did not finish and kept the packages from before it in" \
            "$BACKUP_DIR. Finish its recovery first: $(cat "$RECOVERY_FILE") Then move" \
            "$BACKUP_DIR to the trash and run 'make update' again."
    fi
    echo "Moving the leftover $BACKUP_DIR of an earlier run to the trash."
    "$TRASH" "$BACKUP_DIR" || refuse "Could not move the leftover $BACKUP_DIR to the trash."
}

# Both folders are cloned before the update and swapped back on the way back.
require_installed_packages() {
    local dir
    for dir in "$VENV_DIR" "$NODE_MODULES_DIR"; do
        if [ ! -d "$dir" ]; then
            refuse "$dir is missing. Run 'make setup', then 'make update' again."
        fi
    done
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

# Installing packages needs the network, and the way back must not: the packages of the
# running version are cloned (APFS copy-on-write, so almost free) and swapped back on
# rollback instead of being installed again.
back_up_packages() {
    mkdir -p "$BACKUP_DIR"
    backups_taken=1
    if [ -e "$NODE_MODULES_STAMP" ] && [ "$NODE_MODULES_STAMP" -nt "$PACKAGE_LOCK" ]; then
        node_modules_fresh=1
    fi
    clone_into_backup "$VENV_DIR" venv || refuse "Could not back up $VENV_DIR."
    clone_into_backup "$NODE_MODULES_DIR" node_modules || refuse "Could not back up $NODE_MODULES_DIR."
}

clone_into_backup() {
    if cp -cRp "$1" "$BACKUP_DIR/$2" 2>/dev/null; then return 0; fi
    if [ -e "$BACKUP_DIR/$2" ]; then "$TRASH" "$BACKUP_DIR/$2" || return 1; fi
    cp -Rp "$1" "$BACKUP_DIR/$2"
}

restore_packages() {
    swap_back "$VENV_DIR" venv || return 1
    swap_back "$NODE_MODULES_DIR" node_modules || return 1
    # The checkout gave package-lock.json a new time: without this `make up` would see the
    # restored packages as stale and reinstall them from the network.
    if [ "$node_modules_fresh" = 1 ]; then
        touch -r "$PACKAGE_LOCK" "$NODE_MODULES_STAMP" && touch -A 01 "$NODE_MODULES_STAMP"
    fi
}

swap_back() {
    local live=$1 clone="$BACKUP_DIR/$2"
    [ -e "$clone" ] || return 0
    if [ -e "$live" ]; then
        mv "$live" "$BACKUP_DIR/$2.failed" || return 1
    fi
    mv "$clone" "$live"
}

discard_backups() {
    if [ "$backups_taken" = 1 ] && [ -e "$BACKUP_DIR" ]; then
        "$TRASH" "$BACKUP_DIR" || echo "WARNING: could not move $BACKUP_DIR to the trash." >&2
    fi
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

record_error() {
    local start
    start=$(cat "$STEP_START_FILE" 2>/dev/null || echo 0)
    {
        echo "Failed step: $(cat "$STEP_NAME_FILE" 2>/dev/null)"
        tail -c "+$((start + 1))" "$LOG_FILE" | tail -n "$ERROR_TAIL_LINES"
    } > "$ERROR_FILE"
}

packages_restore_hint() {
    local hint=""
    if [ -e "$BACKUP_DIR/venv" ]; then
        hint="$hint trash $VENV_DIR; mv $BACKUP_DIR/venv $VENV_DIR;"
    fi
    if [ -e "$BACKUP_DIR/node_modules" ]; then
        hint="$hint trash $NODE_MODULES_DIR; mv $BACKUP_DIR/node_modules $NODE_MODULES_DIR;"
    fi
    echo "$hint"
}

# Stops the copy without starting it: something on the way back failed, and starting the
# old code on a database it may not know is worse than a stopped copy.
leave_stopped() {
    keep_backups=1
    echo "Rollback failed at: $1. The copy is stopped." >> "$ERROR_FILE"
    echo "ERROR: rollback failed at: $1. The copy is stopped." >&2
    local packages recipe
    packages=$(packages_restore_hint)
    if [ "$snapshot_taken" = 1 ]; then
        if [ "$snapshot" = "$NO_DATABASE" ]; then
            echo "There was no database before the update." >&2
        else
            echo "The database from before the update: $snapshot" >&2
        fi
        recipe="make down; git checkout --force $old_ref;$packages"
        recipe="$recipe make _db-restore SNAPSHOT=$(restore_argument); make up"
    else
        echo "The database was not changed." >&2
        recipe="make down; git checkout --force $old_ref;$packages make up"
    fi
    echo "To finish by hand: $recipe; trash $BACKUP_DIR" >&2
    if [ -d "$BACKUP_DIR" ]; then echo "$recipe." > "$RECOVERY_FILE"; fi
    finish failed
}

roll_back() {
    trap '' INT TERM HUP
    record_error
    echo "Update failed. Rolling back to $old_name..." >&2
    # A failed start can leave the new version's processes running, a migration among them.
    make_step down || leave_stopped "make down"
    if [ "$checked_out" = 1 ]; then
        # The tree was clean at the start: only a half-done checkout can have changed it.
        run_step "git checkout" git checkout --quiet --force "$old_ref" \
            || leave_stopped "git checkout"
        restore_packages || leave_stopped "restoring the packages"
    fi
    if [ "$snapshot_taken" = 1 ]; then
        make_step _db-restore SNAPSHOT="$(restore_argument)" || leave_stopped "database restore"
    fi
    local broken=""
    if [ "$app_built" = 1 ]; then
        make_step app || broken=" The macOS app was not rebuilt: run 'make app'."
    fi
    if ! make_step up; then
        echo "The old version did not start." >> "$ERROR_FILE"
        echo "ERROR: the old version did not start. See the output above, then run 'make up'." >&2
        finish failed
    fi
    echo "Rolled back to $old_name and started.$broken" >&2
    finish failed
}

on_signal() {
    if [ "$stopped" = 1 ]; then roll_back; fi
    refuse "Update interrupted."
}

main "$@"
