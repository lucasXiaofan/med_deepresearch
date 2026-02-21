# Few-shot Comparison Report

- Model type: `vision`
- Model id: `x-ai/grok-4.1-fast`
- Relevant CSV: `src/agent_v2/results/med-diagnosis-relevant-search.csv`

## Overall

| Mode | Correct | Total | Accuracy |
|---|---:|---:|---:|
| baseline | 3 | 19 | 15.8% |
| fewshot | 6 | 19 | 31.6% |

## Per-case Comparison

| Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |
|---|---|---|---|---|---|---|
| 10128 | E | D | N | - | N | = |
| 10142 | C | C | Y | C | Y | = |
| 10146 | A | C | N | A | Y | +1 |
| 10186 | A | B | N | - | N | = |
| 10653 | C | C | Y | - | N | -1 |
| 10790 | C | A | N | - | N | = |
| 10827 | E | - | N | E | Y | +1 |
| 13960 | E | D | N | - | N | = |
| 11532 | E | C | N | - | N | = |
| 11692 | B | D | N | - | N | = |
| 11845 | B | - | N | - | N | = |
| 12166 | E | E | Y | E | Y | = |
| 12185 | B | E | N | - | N | = |
| 12691 | C | E | N | - | N | = |
| 12773 | B | E | N | E | N | = |
| 12781 | D | B | N | D | Y | +1 |
| 12956 | D | E | N | D | Y | +1 |
| 13122 | A | E | N | E | N | = |
| 13497 | A | B | N | - | N | = |
