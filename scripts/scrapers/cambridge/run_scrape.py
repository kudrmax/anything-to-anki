#!/usr/bin/env python3
"""Idempotent multithreaded Cambridge Dictionary scraper.

Scrapes CEFR levels, definitions, examples, IPA, audio URLs, usage labels,
domains, phrasal verbs, and idioms from Cambridge Dictionary.

Results are saved to a JSONL file (one JSON line per word).
Words not found in dictionary go to a "not found" file.
Words that fail due to network/rate-limit go to a "network errors" file.
Already scraped words are skipped on re-run.

Usage:
    python scripts/scrapers/cambridge/run_scrape.py
    python scripts/scrapers/cambridge/run_scrape.py --retry-errors
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scraper import RESULT_FORMAT, RateLimitError, define  # noqa: E402


SCRIPT_DIR = Path(__file__).parent
SCRIPTS_ROOT = SCRIPT_DIR.parent.parent
PROJECT_ROOT = SCRIPTS_ROOT.parent
DEFAULT_INPUT = PROJECT_ROOT / "dictionaries" / "wordlists" / "subtlex_words.txt"
DEFAULT_OUTPUT = PROJECT_ROOT / "dictionaries" / "cambridge.jsonl"
DEFAULT_NOT_FOUND = SCRIPT_DIR / "errors" / "not_found.txt"
DEFAULT_NETWORK_ERRORS = SCRIPT_DIR / "errors" / "network_errors.txt"

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2.0
RATE_LIMIT_PAUSE = 30.0
PROGRESS_EVERY = 1

# Global rate limit event — when set, all threads pause
_rate_limit_lock = threading.Lock()
_rate_limited_until = 0.0


def _wait_for_rate_limit() -> None:
    """If we're currently rate-limited, wait until the pause expires."""
    global _rate_limited_until
    while True:
        with _rate_limit_lock:
            remaining = _rate_limited_until - time.time()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1.0))


def _set_rate_limit(seconds: float) -> None:
    """Set a global rate limit pause — all threads will wait."""
    global _rate_limited_until
    with _rate_limit_lock:
        new_until = time.time() + seconds
        if new_until > _rate_limited_until:
            _rate_limited_until = new_until


def load_scraped_words(output_path: Path) -> set[str]:
    """Load set of already scraped words from JSONL."""
    words: set[str] = set()
    if not output_path.exists():
        return words
    with open(output_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                words.add(data["word"])
            except (json.JSONDecodeError, KeyError):
                continue
    return words


def load_word_set(path: Path) -> set[str]:
    """Load set of words from a text file (one per line)."""
    words: set[str] = set()
    if not path.exists():
        return words
    with open(path, encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if word:
                words.add(word)
    return words


def load_input_words(input_path: Path) -> list[str]:
    """Load word list from input file (one word per line)."""
    words: list[str] = []
    seen: set[str] = set()
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()
            if word and word not in seen:
                words.append(word)
                seen.add(word)
    return words


def transform_raw_result(word: str, raw: list[RESULT_FORMAT]) -> dict[str, Any]:
    """Transform Blackdeer parser output into our JSONL format."""
    entries: list[dict[str, Any]] = []

    # Only use the first dictionary block (English).
    # Subsequent blocks (e.g. Learner's) duplicate entries without CEFR levels.
    for dict_block in raw[:1]:
        for headword, pos_list in dict_block.items():
            for pos_data in pos_list:
                data = pos_data["data"]
                n_senses = len(data["definitions"])

                senses: list[dict[str, Any]] = []
                for i in range(n_senses):
                    senses.append({
                        "definition": data["definitions"][i],
                        "level": data["levels"][i] if i < len(data["levels"]) else "",
                        "examples": data["examples"][i] if i < len(data["examples"]) else [],
                        "labels_and_codes": data["labels_and_codes"][i] if i < len(data["labels_and_codes"]) else [],
                        "usages": data["usages"][i] if i < len(data["usages"]) else [],
                        "domains": data["domains"][i] if i < len(data["domains"]) else [],
                        "regions": data["regions"][i] if i < len(data["regions"]) else [],
                        "image_link": data["image_links"][i] if i < len(data["image_links"]) else "",
                    })

                uk_ipas: list[str] = []
                for ipa_list in data["UK_IPA"]:
                    uk_ipas.extend(ipa_list)
                us_ipas: list[str] = []
                for ipa_list in data["US_IPA"]:
                    us_ipas.extend(ipa_list)
                uk_audio: list[str] = []
                for audio_list in data["UK_audio_links"]:
                    uk_audio.extend(audio_list)
                us_audio: list[str] = []
                for audio_list in data["US_audio_links"]:
                    us_audio.extend(audio_list)

                entries.append({
                    "headword": headword,
                    "pos": pos_data["POS"],
                    "uk_ipa": list(dict.fromkeys(uk_ipas)),
                    "us_ipa": list(dict.fromkeys(us_ipas)),
                    "uk_audio": list(dict.fromkeys(uk_audio)),
                    "us_audio": list(dict.fromkeys(us_audio)),
                    "senses": senses,
                })

    return {
        "word": word,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    }


# Scrape result types
RESULT_OK = "ok"
RESULT_NOT_FOUND = "not_found"
RESULT_NETWORK_ERROR = "network_error"


def scrape_word(word: str) -> tuple[str, dict[str, Any] | None, str, str]:
    """Scrape a single word with retries.

    Returns: (word, result_or_None, result_type, error_detail)
    result_type is one of: RESULT_OK, RESULT_NOT_FOUND, RESULT_NETWORK_ERROR
    """
    last_error = ""
    for attempt in range(MAX_RETRIES):
        _wait_for_rate_limit()
        try:
            raw = define(word, dictionary_type="english", timeout=10.0)
            if not raw or all(not block for block in raw):
                return word, None, RESULT_NOT_FOUND, "empty_result"
            result = transform_raw_result(word, raw)
            return word, result, RESULT_OK, ""
        except RateLimitError:
            pause = RATE_LIMIT_PAUSE * (attempt + 1)
            _set_rate_limit(pause)
            print(f"\n  [403] Rate limited on '{word}', "
                  f"global pause {pause:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})",
                  file=sys.stderr)
            time.sleep(pause)
            last_error = "rate_limited"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_BASE ** attempt)

    return word, None, RESULT_NETWORK_ERROR, last_error


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Cambridge Dictionary")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Input word list (one word per line)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Output JSONL file")
    parser.add_argument("--not-found", type=Path, default=DEFAULT_NOT_FOUND,
                        help="Words not in Cambridge Dictionary")
    parser.add_argument("--network-errors", type=Path, default=DEFAULT_NETWORK_ERRORS,
                        help="Words that failed due to network/rate-limit")
    parser.add_argument("--workers", type=int, default=2,
                        help="Number of parallel workers")
    parser.add_argument("--retry-errors", action="store_true",
                        help="Re-scrape words from network errors file")
    args = parser.parse_args()

    # Ensure output directories exist
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Load state
    scraped = load_scraped_words(args.output)
    not_found_words = load_word_set(args.not_found)
    network_error_words = load_word_set(args.network_errors)
    input_words = load_input_words(args.input)

    # Build work list
    retry_set: set[str] = set()
    if args.retry_errors:
        retry_set = network_error_words.copy()

    to_scrape: list[str] = []
    for word in input_words:
        if word in scraped:
            continue
        if word in not_found_words:
            continue
        if word in network_error_words and word not in retry_set:
            continue
        to_scrape.append(word)

    total = len(to_scrape)
    skipped = len(input_words) - total
    print(f"Input: {len(input_words)} | Scraped: {len(scraped)} | "
          f"Not found: {len(not_found_words)} | Network errors: {len(network_error_words)} | "
          f"To scrape: {total} | Retrying: {len(retry_set)}", file=sys.stderr)

    if total == 0:
        print("Nothing to scrape.", file=sys.stderr)
        return

    # Locks and counters
    write_lock = threading.Lock()
    not_found_lock = threading.Lock()
    network_lock = threading.Lock()
    ok_count = 0
    nf_count = 0
    net_count = 0
    processed = 0
    start_time = time.time()

    retried_ok: set[str] = set()

    output_file = open(args.output, "a", encoding="utf-8")
    not_found_file = open(args.not_found, "a", encoding="utf-8")
    network_file = open(args.network_errors, "a", encoding="utf-8")

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(scrape_word, w): w for w in to_scrape}

            for future in as_completed(futures):
                word, result, result_type, error_detail = future.result()

                if result_type == RESULT_OK:
                    line = json.dumps(result, ensure_ascii=False)
                    with write_lock:
                        output_file.write(line + "\n")
                        output_file.flush()
                    ok_count += 1
                    if word in retry_set:
                        retried_ok.add(word)

                elif result_type == RESULT_NOT_FOUND:
                    with not_found_lock:
                        if word not in not_found_words:
                            not_found_file.write(word + "\n")
                            not_found_file.flush()
                            not_found_words.add(word)
                    nf_count += 1

                elif result_type == RESULT_NETWORK_ERROR:
                    with network_lock:
                        if word not in network_error_words:
                            network_file.write(word + "\n")
                            network_file.flush()
                            network_error_words.add(word)
                    net_count += 1

                processed += 1
                if processed % PROGRESS_EVERY == 0 or processed == total:
                    elapsed = time.time() - start_time
                    rate = elapsed / processed if processed > 0 else 0
                    eta_seconds = rate * (total - processed)
                    eta_h, eta_rem = divmod(int(eta_seconds), 3600)
                    eta_min, eta_sec = divmod(eta_rem, 60)
                    eta_str = f"{eta_h}h{eta_min:02d}m" if eta_h else f"{eta_min}m{eta_sec:02d}s"
                    pct = processed / total * 100
                    print(f"\r[{processed}/{total}] {pct:.1f}% | "
                          f"{rate:.2f}s/word | {eta_str} left | "
                          f"OK: {ok_count} NF: {nf_count} NET: {net_count}",
                          end="", file=sys.stderr)

    finally:
        output_file.close()
        not_found_file.close()
        network_file.close()

    print(file=sys.stderr)

    # Clean up retried words from network errors file
    if retried_ok:
        remaining = load_word_set(args.network_errors) - retried_ok
        with open(args.network_errors, "w", encoding="utf-8") as f:
            for word in sorted(remaining):
                f.write(word + "\n")
        print(f"Removed {len(retried_ok)} retried words from network errors.", file=sys.stderr)

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.0f}s. OK: {ok_count}, Not found: {nf_count}, "
          f"Network errors: {net_count}", file=sys.stderr)


if __name__ == "__main__":
    main()
