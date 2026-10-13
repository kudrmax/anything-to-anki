from __future__ import annotations

from typing import TYPE_CHECKING

import spacy
from spacy.language import Language

from backend.domain.entities.token_data import TokenData
from backend.domain.ports.text_analyzer import TextAnalyzer

if TYPE_CHECKING:
    from spacy.tokens import Doc

PARAGRAPH_BOUNDARIES = "paragraph_boundaries"
PARAGRAPH_BREAK = "\n\n"


@Language.component(PARAGRAPH_BOUNDARIES)
def paragraph_boundaries(doc: Doc) -> Doc:
    """A sentence never runs past a blank line: a heading or a list item stands alone."""
    for token in doc[:-1]:
        if token.is_space and PARAGRAPH_BREAK in token.text:
            doc[token.i + 1].is_sent_start = True
    return doc


class SpaCyTextAnalyzer(TextAnalyzer):
    """Analyzes text using spaCy, producing NLP-agnostic TokenData objects."""

    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self._nlp: Language = spacy.load(model_name)
        self._nlp.add_pipe(PARAGRAPH_BOUNDARIES, before="parser")

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
                    dep=token.dep_,
                    whitespace_after=token.whitespace_,
                    char_start=token.idx,
                )
            )

        return tokens
