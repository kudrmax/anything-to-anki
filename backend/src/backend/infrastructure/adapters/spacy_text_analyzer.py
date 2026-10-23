from __future__ import annotations

from typing import TYPE_CHECKING

import spacy
from spacy import about as spacy_about
from spacy.language import Language

from backend.domain.entities.token_data import TokenData
from backend.domain.ports.text_analyzer import TextAnalyzer
from backend.infrastructure.adapters.text_pieces import text_pieces

if TYPE_CHECKING:
    from spacy.tokens import Doc

PARAGRAPH_BOUNDARIES = "paragraph_boundaries"
PARAGRAPH_BREAK = "\n\n"
# spaCy's memory grows with the text it parses at once. Measured on a whole book, the peak
# of the process: 10 GB for its limit of a million characters, 2 GB for a hundred thousand,
# 0.9 GB for ten thousand, at the same speed. A longer text goes in pieces.
PIECE_LENGTH = 10_000


@Language.component(PARAGRAPH_BOUNDARIES)
def paragraph_boundaries(doc: Doc) -> Doc:
    """A sentence never runs past a blank line: a heading or a list item stands alone."""
    for token in doc[:-1]:
        if token.is_space and PARAGRAPH_BREAK in token.text:
            doc[token.i + 1].is_sent_start = True
    return doc


class SpaCyTextAnalyzer(TextAnalyzer):
    """Analyzes text using spaCy, producing NLP-agnostic TokenData objects.

    A text longer than `piece_length` is parsed piece by piece, cut at blank lines where
    possible, so spaCy never holds more than a piece; its tokens read as of one text.
    """

    def __init__(
        self, model_name: str = "en_core_web_sm", piece_length: int | None = None,
    ) -> None:
        self._nlp: Language = spacy.load(model_name)
        self._nlp.add_pipe(PARAGRAPH_BOUNDARIES, before="parser")
        self._piece_length = min(piece_length or PIECE_LENGTH, self._nlp.max_length)

    @property
    def version(self) -> str:
        """spaCy's version and the model's: what the parse of a text depends on."""
        return f"{spacy_about.__version__}:{self._nlp.meta['version']}"

    def analyze(self, text: str) -> list[TokenData]:
        tokens: list[TokenData] = []
        sentences = 0
        for start, end in text_pieces(text, self._piece_length):
            doc = self._nlp(text[start:end])
            tokens.extend(_tokens(doc, len(tokens), sentences, start))
            sentences += sum(1 for _ in doc.sents)
        return tokens


def _tokens(doc: Doc, first_index: int, first_sentence: int, first_char: int) -> list[TokenData]:
    """The doc's tokens, numbered on from the tokens, sentences and text before the doc."""
    sent_indices: dict[int, int] = {}
    for sent_idx, sent in enumerate(doc.sents):
        for token in sent:
            sent_indices[token.i] = sent_idx

    return [
        TokenData(
            index=first_index + token.i,
            text=token.text,
            lemma=token.lemma_,
            pos=token.pos_,
            tag=token.tag_,
            head_index=first_index + token.head.i,
            children_indices=tuple(first_index + child.i for child in token.children),
            is_punct=token.is_punct,
            is_stop=token.is_stop,
            is_alpha=token.is_alpha,
            is_propn=token.pos_ == "PROPN",
            sent_index=first_sentence + sent_indices.get(token.i, 0),
            dep=token.dep_,
            whitespace_after=token.whitespace_,
            char_start=first_char + token.idx,
        )
        for token in doc
    ]
