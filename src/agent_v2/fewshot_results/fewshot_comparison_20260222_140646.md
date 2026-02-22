# Few-shot Comparison Report

- Model type: `vision`
- Model id: `x-ai/grok-4.1-fast`
- Relevant CSV: `src/agent_v2/results/med-diagnosis-relevant-search-filtered-high.csv`

## Overall

| Mode | Correct | Total | Accuracy |
|---|---:|---:|---:|
| baseline | 1 | 16 | 6.2% |
| fewshot | 6 | 16 | 37.5% |

## Per-case Comparison

| Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |
|---|---|---|---|---|---|---|
| 19078 | C | B | N | C | Y | +1 |
| 10128 | E | D | N | E | Y | +1 |
| 10146 | A | C | N | A | Y | +1 |
| 13960 | E | D | N | E | Y | +1 |
| 11692 | B | A | N | D | N | = |
| 11845 | B | E | N | B | Y | +1 |
| 12691 | C | E | N | E | N | = |
| 13122 | A | E | N | E | N | = |
| 13497 | A | B | N | B | N | = |
| 13534 | C | C | Y | B | N | -1 |
| 16686 | C | D | N | D | N | = |
| 16760 | B | A | N | B | Y | +1 |
| 9232 | E | A | N | A | N | = |
| 9299 | C | A | N | A | N | = |
| 9435 | C | A | N | B | N | = |
| 9905 | B | E | N | E | N | = |
