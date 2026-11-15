# Checkpoint

Last update: 2026-11-15, after the Focused forced-answer fix and rerun.

## State

**Done.**
- Main grid: 4 agents x 2 datasets, 200 questions each, sparse retriever. 2,000 rows.
- Dense ablation: ReAct and Focused ReAct on HotPotQA, 200 questions each. 400 rows.
- Focused ReAct rerun on all three configurations after the forced-answer fix (600 rows replaced; the old files are in `backup/focused_before_force_fix/`).
- Analysis: all 11 figures, `summary.csv`, `summary.md`, `significance.csv`, `tokens_per_correct.csv`, `failures.md`.
- `pytest`: 11 passed.
- `python resume_check.py`: CHECKPOINT OK (10/10 configurations at 200/200, unique ids).
- Results verified by hand: token counts and step counts match the recorded values on four sampled trajectories.

**Not done.**
- Paid-model run: skipped by decision. No paid figures exist; `llm.py` only has the local GGUF.

## What was run

Environment: Python 3.12.10, torch 2.5.1+cu121, llama-cpp-python 0.3.4 (CUDA), RTX 3060 Laptop (6 GB), 14 GB RAM.

Model: `qwen2.5-3b-instruct-q4_k_m.gguf` (free local GGUF), greedy decoding, seed 0, batch size 1, `n_ctx=8192`.

Commands (already executed):
```
python run.py --models qwen --agents default cot react focused --datasets hotpotqa gsm8k --n 200 --retriever sparse
python run.py --models qwen --agents react focused --datasets hotpotqa --n 200 --retriever dense
python analyze.py
```

Focused rerun after the forced-answer fix:
```
python run.py --models qwen --agents focused --datasets hotpotqa gsm8k --n 200 --retriever sparse
python run.py --models qwen --agents focused --datasets hotpotqa --n 200 --retriever dense
python analyze.py
```

Wall time: main grid about 1 h 35 min, dense ablation about 23 min, Focused rerun about 35 min. The rerun's sparse command also exited 1 from PowerShell's `2>&1` handling of llama.cpp's stderr; all 600 rows are present.

## Files

`results/*.jsonl` — one file per configuration, 200 rows each, resumable. `results/run_info.json` — versions, GPU, seed, date.
`figures/` — PNG figures and tables from the free run.
`resume_check.py` — verifies row counts and runs pytest without loading the model.
`CHECKPOINT.md` — this file.

## Known issues and open decisions

1. **Exit code 1 on the main and rerun commands.** The main grid and the Focused rerun returned exit code 1, but the dense run alone returned 0. There is no traceback and all rows are present. A re-run of a completed configuration returns 0. Cause is PowerShell's `2>&1` handling of llama.cpp's stderr warnings, not a Python failure. Verify with `python resume_check.py`.
2. **Focused ReAct forced call (fixed).** The first grid had 95/600 `parse_error` rows (30 GSM8K, 33 HotPotQA sparse, 32 dense) because the forced call emitted another `Calculate[...]`/`Search[...]`. The prompt now says the tools are unavailable and asks for `Action: Finish[<final answer>]`; `Finish[...]` is accepted without the prefix and placeholders are rejected. After the rerun: 8/200 GSM8K, 1/200 HotPotQA sparse, 2/200 dense. The remaining ones still use the fallback, documented in the README.
3. **ReAct `max_steps`.** 78/200 on HotPotQA, 58/200 on GSM8K. The trajectories show repeated identical actions (greedy decoding loops), not parser failures. Expected behavior for vanilla ReAct. Focused ReAct cuts these short, which is its purpose.
4. **Global packages.** `sentence-transformers` was installed for the dense retriever. transformers is pinned at 4.57.6; huggingface-hub is 0.36.2. `pip check` reports that the unrelated `gradio` packages want hub >= 1.16. This project does not use gradio. Leave as is, or use a dedicated venv (recommended) with `--system-site-packages` to reuse torch.

## Paid model (skipped)

The paid comparison is skipped by decision. Only the local Qwen GGUF is wired into `llm.py`, so `--models qwen --results-dir results/qwen-paid` would duplicate the free run. If a real paid provider is added later, write to a separate folder and analyze it with `--results-dir`:

```
python run.py --models <paid> --agents default cot react focused --datasets hotpotqa gsm8k --n 200 --retriever sparse --results-dir results/<paid>
python analyze.py --results-dir results/<paid>
```

## Next steps

1. No further benchmark runs are planned.
2. The viewer is documented in the README (`python viewer.py`, then http://127.0.0.1:8000); it animates every agent end-to-end, including a top-10 retrieval scan with gold/sent markers, plus a speed control and a reduced-motion fallback.
3. If a paid provider is added later, follow the section above and update the README Results table.

## Headline numbers (free model, N=200)

| Dataset | Agent | EM | Mean LLM calls | Mean latency (s) |
|---|---|---|---|---|
| GSM8K | Standard | 0.175 | 1.0 | 0.15 |
| GSM8K | CoT | 0.795 | 1.0 | 3.03 |
| GSM8K | ReAct | 0.475 | 4.1 | 5.96 |
| GSM8K | Focused ReAct | 0.645 | 3.6 | 3.41 |
| HotPotQA | Standard | 0.140 | 1.0 | 0.12 |
| HotPotQA | CoT | 0.130 | 1.0 | 1.37 |
| HotPotQA | ReAct (sparse) | 0.155 | 4.8 | 5.63 |
| HotPotQA | Focused ReAct (sparse) | 0.255 | 3.5 | 3.22 |
| HotPotQA | ReAct (dense) | 0.180 | 4.9 | 6.22 |
| HotPotQA | Focused ReAct (dense) | 0.275 | 3.4 | 3.26 |

Significant McNemar tests (free model): GSM8K CoT vs Standard p = 1.9e-31; GSM8K ReAct vs CoT p = 5.4e-14; GSM8K Focused vs ReAct p = 5.8e-05; HotPotQA Focused vs ReAct p = 0.0017. HotPotQA CoT vs Standard p = 0.83 and ReAct vs CoT p = 0.53 are not significant.
