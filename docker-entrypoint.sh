#!/bin/sh
# Symlink ~/.claude.json into the named volume so auth persists across rebuilds.
# The Claude CLI reads/writes ~/.claude.json, but only ~/.claude/ is a named volume.
if [ ! -L /root/.claude.json ]; then
    ln -sf /root/.claude/.claude.json /root/.claude.json
fi
exec "$@"
