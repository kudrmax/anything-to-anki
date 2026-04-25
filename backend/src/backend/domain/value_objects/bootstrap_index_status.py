from __future__ import annotations

from enum import Enum


class BootstrapIndexStatus(Enum):
    """Status of the bootstrap calibration data build."""

    NONE = "none"
    BUILDING = "building"
    READY = "ready"
    ERROR = "error"
