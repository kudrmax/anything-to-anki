"""Dump all Target values from AnythingToAnki deck via AnkiConnect (read-only).

Outputs a TSV file (lemma<TAB>pos) that can be fed into analyze_known_words.py.
POS is determined by running spaCy on the Sentence field (context-aware).

Requires Anki running with AnkiConnect plugin.

Usage (from project root):
    source .venv/bin/activate && PYTHONPATH=backend/src python scripts/dump_anki_targets.py
    # produces scripts/anki_learned_words.tsv
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
import spacy

DECK_NAME = "AnythingToAnki"
TARGET_FIELD = "Target"
SENTENCE_FIELD = "Sentence"
_HTML_ENTITY_RE = re.compile(r"&\w+;|&#\d+;|&#x[\da-fA-F]+;")
ANKI_URL = "http://localhost:8765"
ANKI_TIMEOUT = 30.0
OUTPUT_PATH = Path(__file__).resolve().parent / "anki_learned_words.tsv"


def _clean_html(raw: str) -> str:
    """Strip HTML tags, replace entities/tags with spaces, normalize whitespace."""
    import html
    text = _HTML_ENTITY_RE.sub(" ", raw)  # &nbsp; etc → space
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)  # <br> → space
    text = re.sub(r"<[^>]+>", " ", text)  # other tags → space
    text = html.unescape(text)  # remaining entities
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class AnkiCard:
    target: str
    sentence: str


def _anki_invoke(action: str, **params: object) -> object:
    payload = {"action": action, "version": 6, "params": params}
    response = httpx.post(ANKI_URL, json=payload, timeout=ANKI_TIMEOUT)
    response.raise_for_status()
    result = response.json()
    if result.get("error"):
        raise RuntimeError(f"AnkiConnect error: {result['error']}")
    return result.get("result")


def fetch_cards() -> list[AnkiCard]:
    """Fetch Target + Sentence from all cards in the deck. Read-only."""
    note_ids = _anki_invoke("findNotes", query=f'deck:"{DECK_NAME}"')
    if not note_ids:
        return []

    notes_info = _anki_invoke("notesInfo", notes=note_ids)
    cards: list[AnkiCard] = []
    for note in notes_info:  # type: ignore[union-attr]
        fields = note.get("fields", {})
        target_raw = fields.get(TARGET_FIELD, {}).get("value", "").strip()
        sentence_raw = fields.get(SENTENCE_FIELD, {}).get("value", "").strip()
        target = _clean_html(target_raw)
        sentence = _clean_html(sentence_raw)
        if target:
            cards.append(AnkiCard(target=target, sentence=sentence))
    return cards


def resolve_pos(nlp: spacy.language.Language, card: AnkiCard) -> str | None:
    """Find the target word in the sentence via spaCy and return its POS tag."""
    if not card.sentence:
        return None

    doc = nlp(card.sentence)
    target_lower = card.target.lower()

    # Try exact lemma match first
    for token in doc:
        if token.lemma_.lower() == target_lower:
            return token.pos_

    # Try text match (for phrasal verbs etc.)
    for token in doc:
        if token.text.lower() == target_lower:
            return token.pos_

    # Multi-word target: match first word
    if " " in target_lower:
        first_word = target_lower.split()[0]
        for token in doc:
            if token.lemma_.lower() == first_word or token.text.lower() == first_word:
                return token.pos_

    return None


def main() -> None:
    try:
        version = _anki_invoke("version")
    except Exception:
        print("ERROR: AnkiConnect not available. Is Anki running?")
        sys.exit(1)

    print(f"AnkiConnect version: {version}")
    print(f"Deck: {DECK_NAME}")

    cards = fetch_cards()
    if not cards:
        print(f"ERROR: No cards found in deck '{DECK_NAME}'")
        sys.exit(1)

    print(f"Fetched {len(cards)} cards")
    print("Loading spaCy model...")
    nlp = spacy.load("en_core_web_sm")

    # Resolve POS for each card
    resolved: dict[str, str] = {}  # target -> POS
    unresolved: list[AnkiCard] = []

    for card in cards:
        if card.target in resolved:
            continue
        pos = resolve_pos(nlp, card)
        if pos:
            resolved[card.target] = pos
        else:
            unresolved.append(card)

    # Report
    print(f"\nResolved POS: {len(resolved)}")
    if unresolved:
        print(f"Unresolved (no POS from sentence): {len(unresolved)}")
        for card in unresolved:
            print(f"  {card.target:<25s} sentence: {card.sentence[:60]}...")

    unique = sorted(resolved.items())
    with open(OUTPUT_PATH, "w") as f:
        for lemma, pos in unique:
            f.write(f"{lemma}\t{pos}\n")

    print(f"\nWritten {len(unique)} entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
