# Few-shot Comparison Report

- Model type: `vision`
- Model id: `(from config)`
- Relevant CSV: `/Users/xiaofanlu/Documents/github_repos/med_deepresearch/src/agent_v2/results/med-diagnosis-relevant-search-vector-similarity.csv`

## Overall

| Mode | Correct | Total | Accuracy |
|---|---:|---:|---:|
| baseline | 2 | 5 | 40.0% |
| fewshot | 1 | 5 | 20.0% |

## Per-case Comparison

| Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |
|---|---|---|---|---|---|---|
| 10128 | E | D | N | D | N | = |
| 10142 | C | A | N | A | N | = |
| 10146 | A | C | N | C | N | = |
| 10186 | A | A | Y | C | N | -1 |
| 10653 | C | C | Y | C | Y | = |
