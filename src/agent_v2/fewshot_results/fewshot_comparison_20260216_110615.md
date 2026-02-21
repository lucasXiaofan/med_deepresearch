# Few-shot Comparison Report

- Model type: `vision`
- Model id: `(from config)`
- Relevant CSV: `/Users/xiaofanlu/Documents/github_repos/med_deepresearch/src/agent_v2/results/med-diagnosis-relevant-search-vector-similarity.csv`

## Overall

| Mode | Correct | Total | Accuracy |
|---|---:|---:|---:|
| baseline | 4 | 19 | 21.1% |
| fewshot | 5 | 19 | 26.3% |

## Per-case Comparison

| Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |
|---|---|---|---|---|---|---|
| 10128 | E | D | N | D | N | = |
| 10142 | C | C | Y | C | Y | = |
| 10146 | A | C | N | C | N | = |
| 10186 | A | B | N | C | N | = |
| 10653 | C | C | Y | C | Y | = |
| 10790 | C | B | N | B | N | = |
| 10827 | E | E | Y | A | N | -1 |
| 13960 | E | D | N | D | N | = |
| 11532 | E | C | N | C | N | = |
| 11692 | B | D | N | A | N | = |
| 11845 | B | E | N | A | N | = |
| 12166 | E | E | Y | E | Y | = |
| 12185 | B | D | N | A | N | = |
| 12691 | C | E | N | E | N | = |
| 12773 | B | E | N | B | Y | +1 |
| 12781 | D | B | N | D | Y | +1 |
| 12956 | D | E | N | E | N | = |
| 13122 | A | E | N | E | N | = |
| 13497 | A | B | N | B | N | = |
