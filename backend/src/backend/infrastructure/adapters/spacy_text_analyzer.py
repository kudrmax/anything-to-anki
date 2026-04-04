from __future__ import annotations

from typing import TYPE_CHECKING

import spacy

from backend.domain.entities.token_data import TokenData
from backend.domain.ports.text_analyzer import TextAnalyzer

if TYPE_CHECKING:
    from spacy.language import Language


class SpaCyTextAnalyzer(TextAnalyzer):
    """Analyzes text using spaCy, producing NLP-agnostic TokenData objects."""

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self._nlp: Language = spacy.load(model_name)

    def analyze(self, text: str) -> list[TokenData]:
        doc = self._nlp(text)
        tokens: list[TokenData] = []

        # Build sent_index mapping
        sent_indices: dict[int, int] = {}
        for sent_idx, sent in enumerate(doc.sents):
            for token in sent:
                sent_indices[token.i] = sent_idx

        for token in doc:
            children_indices = tuple(child.i for child in token.children)
            tokens.append(
                TokenData(
                    index=token.i,
                    text=token.text,
                    lemma=token.lemma_,
                    pos=token.pos_,
                    tag=token.tag_,
                    head_index=token.head.i,
                    children_indices=children_indices,
                    is_punct=token.is_punct,
                    is_stop=token.is_stop,
                    is_alpha=token.is_alpha,
                    is_propn=token.pos_ == "PROPN",
                    sent_index=sent_indices.get(token.i, 0),
                )
            )

        return tokens
