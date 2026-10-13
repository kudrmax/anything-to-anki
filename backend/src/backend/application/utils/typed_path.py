from __future__ import annotations

import os
import re

_QUOTES: frozenset[str] = frozenset({"'", '"'})
_SHELL_ESCAPE_RE = re.compile(r"\\(.)")


def normalize_typed_path(typed: str) -> str:
    """A file path as the user pasted it, often copied from a shell: quoted or escaped."""
    path = typed.strip()
    if len(path) >= 2 and path[0] == path[-1] and path[0] in _QUOTES:
        path = path[1:-1]
    else:
        path = _SHELL_ESCAPE_RE.sub(r"\1", path)
    return os.path.expanduser(path)
