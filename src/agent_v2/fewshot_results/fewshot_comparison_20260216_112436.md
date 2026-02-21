# Few-shot Comparison Report

- Model type: `vision`
- Model id: `google/gemini-3-flash-preview`
- Relevant CSV: `src/agent_v2/results/med-diagnosis-relevant-search.csv`

## Overall

| Mode | Correct | Total | Accuracy |
|---|---:|---:|---:|
| baseline | 9 | 19 | 47.4% |
| fewshot | 9 | 19 | 47.4% |

## Per-case Comparison

| Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |
|---|---|---|---|---|---|---|
| 10128 | E | D | N | D | N | = |
| 10142 | C | C | Y | C | Y | = |
| 10146 | A | C | N | C | N | = |
| 10186 | A | B | N | - | N | = |
| 10653 | C | C | Y | - | N | -1 |
| 10790 | C | A | N | C | Y | +1 |
| 10827 | E | - | N | E | Y | +1 |
| 13960 | E | D | N | - | N | = |
| 11532 | E | C | N | E | Y | +1 |
| 11692 | B | B | Y | - | N | -1 |
| 11845 | B | B | Y | B | Y | = |
| 12166 | E | E | Y | E | Y | = |
| 12185 | B | B | Y | - | N | -1 |
| 12691 | C | E | N | - | N | = |
| 12773 | B | B | Y | B | Y | = |
| 12781 | D | E | N | D | Y | +1 |
| 12956 | D | D | Y | D | Y | = |
| 13122 | A | A | Y | - | N | -1 |
| 13497 | A | B | N | B | N | = |
