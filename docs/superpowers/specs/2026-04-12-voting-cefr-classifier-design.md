# Voting CEFR Classifier

## Problem

cefrpy (единственный текущий источник CEFR-уровней) систематически завышает уровень informal/colloquial слов. Например: nope, yep, wow, oops, gonna, wanna, crap — все получают C2, хотя реально это A2-B1. Причина: cefrpy интерполирует уровни по частотности в академических корпусах (Google N-Gram + CEFR-J), где разговорные слова редки.

## Solution

Заменить единственный источник CEFR-уровней на **систему голосования** из 4 независимых источников. Каждый источник возвращает распределение вероятностей по уровням, результаты усредняются с равными весами (25% каждый). Побеждает уровень с максимальной вероятностью.

## Algorithm

1. Каждый из 4 источников возвращает `dict[CEFRLevel, float]` — распределение вероятностей (сумма = 1.0)
2. Если источник не знает слово — возвращает `{UNKNOWN: 1.0}`
3. Распределения усредняются с равными весами (25% на источник)
4. Уровень с максимальной вероятностью — результат

### Example: "cool"

| Source | Result | Contribution (25%) |
|---|---|---|
| cefrpy | A2 | A2 = 25% |
| EFLLex | A2: 61.5%, B1: 30.8%, B2: 7.7% | A2 = 15.4%, B1 = 7.7%, B2 = 1.9% |
| Oxford 5000 | A2 | A2 = 25% |
| Kelly | B1 | B1 = 25% |

**Totals:** A2 = 65.4%, B1 = 32.7%, B2 = 1.9%. **Winner: A2.**

### Example: "nope" (only cefrpy knows it)

| Source | Result | Contribution (25%) |
|---|---|---|
| cefrpy | C2 | C2 = 25% |
| EFLLex | unknown | UNKNOWN = 25% |
| Oxford 5000 | unknown | UNKNOWN = 25% |
| Kelly | unknown | UNKNOWN = 25% |

**Totals:** UNKNOWN = 75%, C2 = 25%. **Winner: UNKNOWN.**

## Data Sources

### 1. cefrpy (existing)

- Coverage: tens of thousands of words
- Format: Python API (`CEFRAnalyzer`)
- Returns: single CEFR level per word+POS
- License: MIT
- Weakness: inflated levels for informal words

### 2. EFLLex

- Coverage: 15,280 lemmas
- Format: TSV, downloadable from https://cental.uclouvain.be/cefrlex/efllex/
- Returns: **frequency distribution across A1-C1 levels** (not a single level)
- License: CC BY-NC-SA 4.0
- Based on corpus of 13 EFL textbooks

### 3. Oxford 5000

- Coverage: ~5,000 words
- Format: CSV (from GitHub repositories scraping Oxford Learner's Dictionary)
- Returns: single CEFR level (A1-C1)
- Source: https://github.com/winterdl/oxford-5000-vocabulary-audio-definition

### 4. Kelly English

- Coverage: ~9,000 most frequent words
- Format: XLS/CSV
- Returns: single CEFR level (A1-C2)
- License: CC BY-NC-SA 2.0
- Source: https://ssharoff.github.io/kelly/

## Architecture

### New port: `CEFRSource`

```python
# domain/ports/cefr_source.py
class CEFRSource(ABC):
    @abstractmethod
    def get_distribution(self, lemma: str, pos_tag: str) -> dict[CEFRLevel, float]:
        """Return probability distribution across CEFR levels.
        Values must sum to 1.0.
        If word is unknown, return {CEFRLevel.UNKNOWN: 1.0}.
        """
```

### Domain service: `VotingCEFRClassifier`

```python
# domain/services/voting_cefr_classifier.py
class VotingCEFRClassifier(CEFRClassifier):
    def __init__(self, sources: list[CEFRSource]) -> None:
        self._sources = sources

    def classify(self, lemma: str, pos_tag: str) -> CEFRLevel:
        # 1. Collect distributions from all sources
        # 2. Average with equal weights (1/len(sources) each)
        # 3. Return level with highest probability
```

Implements existing `CEFRClassifier` port. Use cases don't change.

### Four adapters (all implement `CEFRSource`)

| Adapter | File | Data |
|---|---|---|
| `CefrpyCEFRSource` | `infrastructure/adapters/cefrpy_cefr_source.py` | cefrpy library |
| `EFLLexCEFRSource` | `infrastructure/adapters/efllex_cefr_source.py` | `backend/data/cefr/efllex.tsv` |
| `OxfordCEFRSource` | `infrastructure/adapters/oxford_cefr_source.py` | `backend/data/cefr/oxford5000.csv` |
| `KellyCEFRSource` | `infrastructure/adapters/kelly_cefr_source.py` | `backend/data/cefr/kelly.csv` |

For single-level sources (cefrpy, Oxford, Kelly): return `{level: 1.0}` or `{UNKNOWN: 1.0}`.
For EFLLex: normalize frequency distribution to probabilities summing to 1.0.

### Container changes

```python
# infrastructure/container.py
data_dir = Path(__file__).parent.parent.parent.parent / "data" / "cefr"
sources: list[CEFRSource] = [
    CefrpyCEFRSource(),
    EFLLexCEFRSource(data_dir / "efllex.tsv"),
    OxfordCEFRSource(data_dir / "oxford5000.csv"),
    KellyCEFRSource(data_dir / "kelly.csv"),
]
self._cefr_classifier = VotingCEFRClassifier(sources)
```

### Files deleted

- `infrastructure/adapters/cefrpy_classifier.py` (replaced by `cefrpy_cefr_source.py`)

### Data files

```
backend/data/cefr/efllex.tsv
backend/data/cefr/oxford5000.csv
backend/data/cefr/kelly.csv
```

Downloaded once, committed to repo. Small files (< 1 MB total).

## Testing

- **Unit tests** for `VotingCEFRClassifier`: mock sources, verify voting logic (all agree, all different, mixed, all UNKNOWN)
- **Integration tests** for each adapter: real data files, spot-check known words (happy→A1/A2, nope→C2/UNKNOWN, cool→A2/B1)
- **Smoke test**: full assembly through container, verify end-to-end classification
