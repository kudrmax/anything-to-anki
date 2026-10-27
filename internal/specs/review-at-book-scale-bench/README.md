# Review at book scale: baseline

Worm (305 chapters) in a copy of the dev database, collection "Worm". Baseline before any stage.
Seed 1, buttons cycle Known / Learn / Skip. Presses refused by the app (word learned from
another source) are skipped and not counted.

| copy | chapters | cards | JSON | open_review (median of 3) | press decide (median / p95) | press reload (median / p95) | presses |
|---|---|---|---|---|---|---|---|
| worm-25 | 25 | 4 778 | 8.4 MB | 1.34 s | 12.2 / 13.8 ms | 1 265 / 1 374 ms | 200 |
| worm-100 | 100 | 27 089 | 47.7 MB | 6.70 s | 14.0 / 16.2 ms | 6 952 / 7 372 ms | 200 |
| worm-all | 305 | 119 856 | 209.6 MB | 31.08 s | 24.1 / 37.7 ms | 31 563 / 32 089 ms | 10 |

Press count is lower for the whole book because every press reloads the whole set (~30 s);
percentiles of its 10 samples are indicative only. Raw timings: `baseline-*.json`.
Progress numbers (decided / total): 0 / 1 012, 0 / 5 909, 0 / 26 605.

## Commands

```
BENCH=<dir outside the repo>
make bench-db EPUB=/Users/mdmkudryashov/Files/PocketBook/Books/Wildbow/Worm.epub CHAPTERS=25 OUT=$BENCH/worm-25.db
make bench-db EPUB=... CHAPTERS=100 OUT=$BENCH/worm-100.db
make bench-db EPUB=... CHAPTERS=0 OUT=$BENCH/worm-all.db
make bench-review DB=$BENCH/worm-25.db  OUT=internal/specs/review-at-book-scale-bench/baseline-25.json PRESSES=200
make bench-review DB=$BENCH/worm-100.db OUT=internal/specs/review-at-book-scale-bench/baseline-100.json PRESSES=200
make bench-review DB=$BENCH/worm-all.db OUT=internal/specs/review-at-book-scale-bench/baseline-all.json PRESSES=10
```

The dev database already held an older "Worm" collection; `bench-db` removes it from the copy
first, so the collection holds only the chapters built.
