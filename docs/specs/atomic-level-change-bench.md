# Atomic level change: measurements

Whole Worm in a copy of the dev database (`make bench-db … CHAPTERS=0`): 326 sources, 119 856 cards at B1. Run in the real app (`make up-worktree`), the change started by `PATCH /api/settings`, status and RSS of the API process sampled every second.

## B1 → B2, to the end

| | |
|---|---|
| PATCH answered | 9 ms |
| whole change | 137 s (before: ~10 s setting write + ~169 s per-source passes, not atomic) |
| analysis (0 → 70 %) | ~100 s |
| one write: apply 326 sources (70 → 90 %) | ~30 s |
| card states rebuilt + commit (90 % → done) | ~7 s |
| RSS before / during analysis / peak | 1.22 GB / ≤ 1.24 GB / 2.35 GB at the card state rebuild |
| cards after | 81 172; `make card-states-check`: 0 differences |

Percent grew about evenly in time (12 % at 11 s, 43 % at 54 s, 65 % at 98 s, 84 % at 120 s), so the shares 70 / 20 / 10 stay.

## Cancel and interruption

- B2 → C1 with another field in the form, cancelled at 54 %: level and the other field unchanged, writes accepted at once.
- `kill -9` of the API at 75 % (inside the one write) and at 25 % (analysis), then `make up-worktree`: level B2, no lock row, writes accepted, `card-states-check` 0 differences, 81 172 cards.
