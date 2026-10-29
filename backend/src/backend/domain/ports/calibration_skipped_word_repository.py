from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class CalibrationSkippedWordRepository(ABC):
    """Words calibration showed and the user did not tap: calibration does not ask them again.
    Only calibration reads them; they say nothing about whether the word is known."""

    @abstractmethod
    def add(self, lemmas: Iterable[str]) -> None: ...

    @abstractmethod
    def lemmas(self) -> set[str]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def clear(self) -> None: ...
