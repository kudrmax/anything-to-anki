# Slang Normalization Design

## Problem

spaCy `en_core_web_sm` fails to correctly lemmatize and POS-tag many informal English contractions. Out of 12 tested slang forms, 8 failed — producing wrong lemmas (`wanna` → lemma `wanna`), wrong POS (`tryna` tagged as NOUN, `Y'all` as PROPN), or broken dependency trees. This breaks downstream target extraction: words aren't found, CEFR/frequency lookups fail, fragments get wrong boundaries.

### spaCy behavior on slang (tested)

| Input | spaCy lemma | POS | Status |
|-------|-------------|-----|--------|
| goin' | go | VERB | OK |
| gonna | go + to (split) | VERB + PART | OK |
| gotta | get + to (split) | VERB + PART | OK |
| 'em | them | PRON | OK |
| wanna | wanna | VERB | FAIL |
| Y'all | Y'all | PROPN | FAIL |
| tryna | tryna | NOUN | FAIL |
| Whatcha | Whatcha | PROPN | FAIL |
| dunno | dunno | VERB | FAIL |
| Lemme | Lemme | PROPN | FAIL |
| coulda | coulda | NOUN | FAIL |
| kinda | kinda | ADV | PARTIAL |

## Solution

Text-level normalization **before** spaCy analysis. A new `TextNormalizer` port with `SlangNormalizer` adapter that expands informal contractions into standard English using regex rules.

### Design decisions

- **Normalize before spaCy, not after.** spaCy needs standard English input to produce correct POS tags, dependency trees, and lemmas. Post-hoc fixes can't recover a broken parse tree.
- **One version of text.** Normalized text is used both for analysis and display on cards. User confirmed this is acceptable — normalized phrases are even preferable for learning.
- **Case-insensitive matching.** `Wanna`, `WANNA`, `wanna` all normalize. First-letter capitalization is preserved in the replacement (`Wanna` → `Want to`).
- **No typo correction.** Only exact slang forms, not misspellings like `wannna`.
- **Compact dictionary now, extensible later.** Start with ~18 rules covering the most common contractions. Adding a rule = one line.

## Architecture

### Port

`backend/src/backend/domain/ports/text_normalizer.py`

```python
class TextNormalizer(ABC):
    """Port for normalizing informal text before NLP analysis (layer 2.5)."""

    @abstractmethod
    def normalize(self, text: str) -> str:
        """Expand informal contractions and slang into standard English."""
```

### Adapter

`backend/src/backend/infrastructure/adapters/slang_normalizer.py`

```python
class SlangNormalizer(TextNormalizer):
    """Expands informal English contractions using regex rules."""

    def normalize(self, text: str) -> str:
        """Apply all slang rules sequentially, preserving first-letter case."""
```

Module-level constant `_SLANG_RULES: tuple[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]], ...]` — ordered list of `(compiled_pattern, replacement)`.

### Rules dictionary (starter set)

Specific word rules (applied first):

| Pattern | Replacement | Category |
|---------|-------------|----------|
| `\bwanna\b` | `want to` | contraction |
| `\bgunna\b` | `going to` | contraction |
| `\btryna\b` | `trying to` | contraction |
| `\bdunno\b` | `do not know` | contraction |
| `\blemme\b` | `let me` | contraction |
| `\bgimme\b` | `give me` | contraction |
| `\bcoulda\b` | `could have` | contraction |
| `\bwoulda\b` | `would have` | contraction |
| `\bshoulda\b` | `should have` | contraction |
| `\bkinda\b` | `kind of` | contraction |
| `\bsorta\b` | `sort of` | contraction |
| `\bwhatcha\b` | `what are you` | contraction |
| `\bgotcha\b` | `got you` | contraction |
| `\by'all\b` | `you all` | pronoun |
| `\bain't\b` | `is not` | negation (context-dependent: could be am/are/has/have not; `is not` chosen as most frequent default) |
| `\b'em\b` | `them` | pronoun |

General pattern rule (applied last):

| Pattern | Replacement | Category |
|---------|-------------|----------|
| `\b(\w+)in'\b` | `\1ing` | dropped -g |

Note: `gonna` and `gotta` are NOT in the dictionary — spaCy already handles them correctly by splitting into two tokens.

### Rule application order

1. Specific word rules first (longest match wins if overlapping, but current rules don't overlap)
2. General `(\w+)in'` → `\1ing` pattern last (to avoid conflicting with specific rules)

### Case preservation

When the original word starts with an uppercase letter, the replacement also starts uppercase:
- `Wanna` → `Want to`
- `WANNA` → `WANT TO` (all-caps preserved)
- `wanna` → `want to`

Implemented as a helper function applied during `re.sub` via a callable replacement.

### Pipeline integration

`AnalyzeTextUseCase.execute()`:

```
raw_text
  → text_cleaner.clean()        # Layer 2: remove markup, timecodes, duplicates
  → text_normalizer.normalize()  # Layer 2.5: expand slang contractions
  → text_analyzer.analyze()      # Layer 3: spaCy tokenization, POS, deps
  → candidate extraction          # Layer 4+
```

### DI registration

`container.py`: register `SlangNormalizer` as singleton, inject into `AnalyzeTextUseCase`.

## Testing

### Unit tests (`SlangNormalizer`)

- Each rule from the dictionary produces correct output
- Case-insensitive matching works (`Wanna` → `Want to`, `DUNNO` → `DO NOT KNOW`)
- First-letter capitalization is preserved
- No false positives: `wanna` inside a longer word is not replaced (word boundary check)
- Multiple contractions in one sentence are all expanded
- Text without contractions passes through unchanged
- General `in'` rule: `goin'` → `going`, `runnin'` → `running`, `doin'` → `doing`

### Integration tests (pipeline)

- Full `clean → normalize → analyze` pipeline with previously-failing inputs
- Verify spaCy produces correct lemma and POS after normalization:
  - `"I wanna buy something"` → after normalize → spaCy gives `want` (VERB) + `to` (PART) + `buy` (VERB)
  - `"He's tryna help"` → `trying` (VERB) + `to` (PART) + `help` (VERB)
  - `"I dunno what happened"` → `do` (VERB) + `not` (PART) + `know` (VERB)
  - `"Y'all should come"` → `you` (PRON) + `all` (DET)
- Verify that candidate extraction finds correct targets in normalized text
