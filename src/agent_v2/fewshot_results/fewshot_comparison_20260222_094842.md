# Few-shot Comparison Report

- Model type: `vision`
- Model id: `x-ai/grok-4.1-fast`
- Relevant CSV: `src/agent_v2/results/med-diagnosis-relevant-search.csv`

## Overall

| Mode | Correct | Total | Accuracy |
|---|---:|---:|---:|
| baseline | 20 | 50 | 40.0% |
| fewshot | 34 | 50 | 68.0% |

## Per-case Comparison

| Case | GT | Baseline | Baseline Correct | Few-shot | Few-shot Correct | Change |
|---|---|---|---|---|---|---|
| 19172 | C | C | Y | C | Y | = |
| 19090 | A | A | Y | A | Y | = |
| 19087 | B | B | Y | B | Y | = |
| 19078 | C | B | N | B | N | = |
| 10128 | E | D | N | D | N | = |
| 10142 | C | C | Y | C | Y | = |
| 10146 | A | C | N | C | N | = |
| 10186 | A | B | N | A | Y | +1 |
| 10280 | E | E | Y | E | Y | = |
| 10653 | C | C | Y | C | Y | = |
| 10790 | C | B | N | C | Y | +1 |
| 10827 | E | B | N | E | Y | +1 |
| 13960 | E | D | N | D | N | = |
| 11532 | E | C | N | E | Y | +1 |
| 11575 | A | B | N | A | Y | +1 |
| 11678 | C | A | N | C | Y | +1 |
| 11692 | B | D | N | A | N | = |
| 11845 | B | E | N | A | N | = |
| 12166 | E | E | Y | E | Y | = |
| 12185 | B | E | N | B | Y | +1 |
| 12691 | C | E | N | E | N | = |
| 12773 | B | E | N | B | Y | +1 |
| 12781 | D | B | N | D | Y | +1 |
| 12956 | D | E | N | D | Y | +1 |
| 13122 | A | E | N | E | N | = |
| 13497 | A | B | N | B | N | = |
| 13534 | C | C | Y | B | N | -1 |
| 13775 | B | B | Y | B | Y | = |
| 14455 | A | A | Y | A | Y | = |
| 15136 | A | A | Y | A | Y | = |
| 15315 | A | B | N | A | Y | +1 |
| 15630 | C | C | Y | C | Y | = |
| 15699 | C | D | N | C | Y | +1 |
| 15727 | B | B | Y | B | Y | = |
| 16138 | E | E | Y | E | Y | = |
| 16251 | A | A | Y | A | Y | = |
| 16526 | E | E | Y | E | Y | = |
| 16686 | C | D | N | D | N | = |
| 16720 | C | C | Y | C | Y | = |
| 16760 | B | A | N | C | N | = |
| 17337 | C | C | Y | C | Y | = |
| 17406 | A | A | Y | A | Y | = |
| 17930 | A | A | Y | A | Y | = |
| 9232 | E | A | N | A | N | = |
| 9246 | A | D | N | A | Y | +1 |
| 9299 | C | A | N | A | N | = |
| 9435 | C | A | N | B | N | = |
| 9556 | C | B | N | C | Y | +1 |
| 9823 | E | B | N | E | Y | +1 |
| 9905 | B | E | N | E | N | = |
