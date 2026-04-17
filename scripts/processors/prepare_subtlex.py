#!/usr/bin/env python3
"""Extract word list from SUBTLEX-US data file.

Download SUBTLEX-US from:
  https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexus

Place the TSV at: scripts/wordlists/subtlex_us_raw.tsv
Then run: python scripts/processors/prepare_subtlex.py

Output: scripts/wordlists/subtlex_words.txt (one word per line, lowercased, deduplicated)
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "dictionaries" / "wordlists" / "subtlex_us_raw.tsv"
DEFAULT_OUTPUT = PROJECT_ROOT / "dictionaries" / "wordlists" / "subtlex_words.txt"


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT

    if not input_path.exists():
        print(f"Error: {input_path} not found.", file=sys.stderr)
        print("Download SUBTLEX-US from:", file=sys.stderr)
        print("  https://www.ugent.be/pp/experimentele-psychologie/en/research/documents/subtlexus",
              file=sys.stderr)
        sys.exit(1)

    words: list[str] = []
    seen: set[str] = set()
    skipped = 0

    with open(input_path, encoding="utf-8", errors="replace") as f:
        header = f.readline()  # skip header
        for line in f:
            parts = line.strip().split("\t")
            if not parts:
                continue
            word = parts[0].strip().lower()
            if not word or not word.isalpha():
                skipped += 1
                continue
            if word in seen:
                continue
            words.append(word)
            seen.add(word)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for word in words:
            f.write(word + "\n")

    print(f"Extracted {len(words)} unique words (skipped {skipped} non-alpha).", file=sys.stderr)
    print(f"Output: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
