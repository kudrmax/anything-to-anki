from __future__ import annotations

from backend.application.utils.typed_path import normalize_typed_path
from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.source_input import LocalFile, PastedText, SourceInput, Url

URL_SCHEMES = ("http://", "https://")
PATH_START = "/"
SUBTITLES_NEED_VIDEO_MESSAGE = "A .srt file can only be attached to a video"


def typed_input(text: str, subtitles_path: str | None = None) -> SourceInput:
    """What the user put in the one input field: a link, a file path, or text to read.

    A single line starting with a scheme is a link; one that names an absolute path (also
    quoted or escaped, as copied from a terminal) is a file, even a missing one, so a typo
    in a path is reported rather than read as text. Anything else is text.
    """
    stripped = text.strip()
    single_line = bool(stripped) and "\n" not in stripped
    subtitles = subtitles_path.strip() if subtitles_path and subtitles_path.strip() else None
    if single_line and stripped.lower().startswith(URL_SCHEMES):
        source_input: SourceInput = Url(stripped)
    elif single_line and normalize_typed_path(stripped).startswith(PATH_START):
        return LocalFile(stripped, subtitles_path=subtitles)
    else:
        source_input = PastedText(text)
    if subtitles is not None:
        raise InvalidSourceInputError(SUBTITLES_NEED_VIDEO_MESSAGE)
    return source_input
