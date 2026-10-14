from enum import StrEnum


class InputProblem(StrEnum):
    """Why an Add screen input can't be added as it is."""

    UNSUPPORTED_LINK = "unsupported_link"
    FILE_NOT_FOUND = "file_not_found"
