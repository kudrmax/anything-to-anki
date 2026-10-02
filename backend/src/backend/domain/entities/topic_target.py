from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicTarget:
    """Something worth learning for a topic source.

    `phrase` is the target as the learner would look it up (a word, a phrasal
    verb or a collocation). `example` is a generated sentence with the target
    marked as **bold** — used when no added source contains the target.
    """

    source_id: int
    position: int
    phrase: str
    example: str
    id: int | None = None
