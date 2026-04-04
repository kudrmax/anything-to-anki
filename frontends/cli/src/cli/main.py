from __future__ import annotations

import argparse
import sys

from backend.application.dto.analysis_dtos import AnalyzeTextRequest, WordCandidateDTO
from backend.infrastructure.container import Container


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VocabMiner — extract vocabulary candidates from text"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to input text file (reads stdin if omitted)",
    )
    parser.add_argument(
        "--level",
        type=str,
        default="B1",
        help="Your CEFR level: A1, A2, B1, B2, C1, C2 (default: B1)",
    )
    args = parser.parse_args()

    # Read input text
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            raw_text = f.read()
    else:
        raw_text = sys.stdin.read()

    if not raw_text.strip():
        print("Error: empty input text", file=sys.stderr)
        sys.exit(1)

    # Run pipeline
    container = Container()
    use_case = container.analyze_text_use_case()

    request = AnalyzeTextRequest(raw_text=raw_text, user_level=args.level)
    response = use_case.execute(request)

    # Print results
    if not response.candidates:
        print(f"No candidates found above level {args.level}.")
        print(f"Total tokens: {response.total_tokens}, unique lemmas: {response.unique_lemmas}")
        return

    print(f"Candidates above {args.level} level ({len(response.candidates)} found):")
    print(f"Total tokens: {response.total_tokens}, unique lemmas: {response.unique_lemmas}")
    print()
    _print_table(response.candidates)


def _print_table(candidates: list[WordCandidateDTO]) -> None:
    """Print candidates as a formatted table."""
    headers = ["#", "Word", "CEFR", "Zipf", "Sweet?", "Purity", "Occ", "Fragment"]
    rows: list[list[str]] = []

    for i, c in enumerate(candidates, 1):
        rows.append([
            str(i),
            c.lemma,
            c.cefr_level,
            f"{c.zipf_frequency:.1f}",
            "yes" if c.is_sweet_spot else "",
            c.fragment_purity,
            str(c.occurrences),
            c.context_fragment[:60] + ("..." if len(c.context_fragment) > 60 else ""),
        ])

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for j, cell in enumerate(row):
            col_widths[j] = max(col_widths[j], len(cell))

    # Print header
    header_line = " | ".join(h.ljust(col_widths[j]) for j, h in enumerate(headers))
    print(header_line)
    print("-+-".join("-" * w for w in col_widths))

    # Print rows
    for row in rows:
        line = " | ".join(cell.ljust(col_widths[j]) for j, cell in enumerate(row))
        print(line)


if __name__ == "__main__":
    main()
