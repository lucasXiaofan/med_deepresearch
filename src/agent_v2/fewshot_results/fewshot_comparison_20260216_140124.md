# Few-shot Comparison Report

- Model type: `vision`
- Model id: `google/gemini-3-flash-preview`
- Relevant CSV: `src/agent_v2/results/med-diagnosis-relevant-search-vector-similarity.csv`

## Overall

| Mode | Correct | Total | Accuracy |
|---|---:|---:|---:|
| baseline | 8 | 19 | 42.1% |
| fewshot | 6 | 19 | 31.6% |

## Per-case Comparison

| Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |
|---|---|---|---|---|---|---|
| 10128 | E | D | N | D | N | = |
| 10142 | C | C | Y | C | Y | = |
| 10146 | A | C | N | C | N | = |
| 10186 | A | B | N | - | N | = |
| 10653 | C | C | Y | - | N | -1 |
| 10790 | C | A | N | C | Y | +1 |
| 10827 | E | D | N | - | N | = |
| 13960 | E | D | N | - | N | = |
| 11532 | E | C | N | - | N | = |
| 11692 | B | B | Y | B | Y | = |
| 11845 | B | B | Y | B | Y | = |
| 12166 | E | E | Y | E | Y | = |
| 12185 | B | B | Y | - | N | -1 |
| 12691 | C | E | N | E | N | = |
| 12773 | B | B | Y | - | N | -1 |
| 12781 | D | B | N | D | Y | +1 |
| 12956 | D | E | N | - | N | = |
| 13122 | A | A | Y | - | N | -1 |
| 13497 | A | B | N | B | N | = |
