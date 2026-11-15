# ReAct vs CoT vs Standard on small LLMs

Benchmarks four agent strategies (Standard, CoT, ReAct, Focused ReAct) on HotPotQA and GSM8K, following the ReAct paper (Yao et al., 2023) at small scale.

Current scope: **Qwen2.5-3B-Instruct only**, run from a local GGUF file. Gemma models are not run yet.

Status: the full 200-question grid and the dense ablation are complete on the free Q4_K_M model. See `CHECKPOINT.md` and the Results section below. The paid-model run has not started.

> This is the `qwen-benchmark/` folder on the `wassim` branch. Run all commands below from this folder.

## Setup

Tested on Windows, Python 3.12, NVIDIA RTX 3060 Laptop GPU (6 GB VRAM), 14 GB RAM.

1. Install torch with CUDA 12.1 (this is the build the code was tested with):
   ```
   pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121
   ```
2. Install a CUDA build of `llama-cpp-python==0.3.4`. A plain `pip install` on Windows builds without CUDA, so use the prebuilt CUDA wheel for this version.
3. Install the rest:
   ```
   pip install -r requirements.txt
   ```
4. Put the model file in the project root. The name is fixed in `llm.py`:
   `qwen2.5-3b-instruct-q4_k_m.gguf`
5. Datasets are read from the local `dataset/` folder. This repository includes:
   - `dataset/hotpot/hotpot_dev_distractor_v1.json` (evaluation sample)
   - `dataset/gsm8k/main/test-00000-of-00001.parquet` (evaluation sample)
   - `dataset/gsm8k/main/train-00000-of-00001.parquet` and the socratic files (few-shot source)

   The 540 MB `dataset/hotpot/hotpot_train_v1.json` is **not** included. It was only used to choose the few-shot questions and is not read at runtime.
6. The dense retriever downloads `sentence-transformers/all-MiniLM-L6-v2` from Hugging Face on first use (about 90 MB, needs internet once).
7. Gemma models (not used yet) are gated: run `huggingface-cli login` and accept the license on the model page first.

On Windows, `llm.py` adds torch's bundled CUDA 12 DLL folder to the DLL search path before importing llama-cpp. Without this, `llama.dll` fails to load when `CUDA_PATH` points at a different CUDA version.

## Commands

Unit tests:
```
python -m pytest test_basic.py -q
```

Smoke test (10 questions per configuration):
```
python run.py --models qwen --agents default cot react focused --datasets hotpotqa gsm8k --n 10 --retriever sparse
python run.py --models qwen --agents react focused --datasets hotpotqa --n 10 --retriever dense
python analyze.py
```

Full grid (200 questions per configuration; the first 10 of the same seeded sample are reused, so the smoke-test results are kept):
```
python run.py --models qwen --agents default cot react focused --datasets hotpotqa gsm8k --n 200 --retriever sparse
python run.py --models qwen --agents react focused --datasets hotpotqa --n 200 --retriever dense
python analyze.py
```

Runs are resumable: question ids already in `results/*.jsonl` are skipped. Each run writes one line per question to `results/{dataset}__{model}__{agent}__{retriever}.jsonl` and writes `results/run_info.json` once.

Use `--results-dir` to keep runs apart. The free model's run is in `results/`; a paid run goes to a new folder so nothing is overwritten:

```
python run.py --models qwen --agents default cot react focused --datasets hotpotqa gsm8k --n 200 --retriever sparse --results-dir results/qwen-paid
python analyze.py --results-dir results/qwen-paid
```

`python analyze.py` with no argument reads every `results/**` folder and compares runs. See `CHECKPOINT.md` for the current state, the resume plan, and the known issues. `python resume_check.py` verifies row counts and runs pytest without loading the model.

## Viewer

A local page that runs one live question and shows the full trace slowly: prompt, model output, thought, action, search passages with scores, observation, repeated-action warnings, and the final result.

```
python viewer.py
```

Then open http://127.0.0.1:8000. Pick a dataset, an agent (Standard, CoT, ReAct, Focused ReAct), an example or your own question, and a speed. ReAct and Focused ReAct show the retrieved passages for HotPotQA; the sparse/dense choice applies there. The page drives the real agents, it does not replay recorded results, so each run costs the same time as the benchmark. The first run loads the model (about 5 s); a dense index is built on the first dense run. Flask is required (`pip install flask`, already present here).

The trace is animated in slow motion. The run opens with a route card for the chosen agent, then each LLM call types out on screen. A tool call opens a small console that types `Search[query]` or `Calculate[expr]` and spins while the tool runs. For Search, a 10-row candidate table appears and a cursor scans it row by row, revealing BM25 or cosine scores and bars. The top 3 — the passages actually passed to the model — get a `sent` badge; official HotPotQA supporting passages get a `gold` badge, with a summary of how many were in the top 10 and in the top 3. The extra candidates are viewer-only: the agent still receives the top 3. Calculate shows the evaluated expression. Every observation is appended to the sidebar scratchpad, repeated actions raise a loop warning, and Focused ReAct shows the early-stop banner and a "forced answer" badge on its final call. The page ends with a stamped final answer and a result card; HotPotQA also shows token F1 beside the exact-match verdict.

Speed controls the replay pacing, not generation: *Instant* removes the waits, *Fast* is about 0.36×, *Slow motion* is about 1.7×, and *Very slow* is about 3.1× the base animation time. The status line reports replay wall time; the result card reports the actual agent run time. Animations are client-side only, so the benchmark measurement is unchanged. With `prefers-reduced-motion` the pacing and scan effects are skipped.

## Files

- `llm.py`: `LanguageModel`, a stateless wrapper around the GGUF model (llama-cpp, GPU, greedy decoding). Renders the prompt with the model's chat template as one user message.
- `tools.py`: `Search` (BM25 or MiniLM; top 3 to the agent, top 10 for the viewer's retrieval scan) and `calculate` (simpleeval, never `eval`).
- `data.py`: loads the seeded HotPotQA and GSM8K samples from local files.
- `metrics.py`: EM, token precision, recall, F1 (official HotPotQA normalization), and GSM8K numeric match.
- `agent.py`: `Agent` base class (per-run counters, timing), `Result`, and the shared answer parsers.
- `default.py`: `StandardAgent`, answers without thinking.
- `cot.py`: `CoTAgent`, thinks step by step, then answers.
- `react.py`: `ReActAgent`, Thought / Action / Observation loop with `max_steps=7`.
- `focused_react.py`: `FocusedReActAgent`, ReAct with question reiteration and early stopping.
- `run.py`: experiment grid CLI, writes `results/`.
- `analyze.py`: builds `figures/` (PNG figures and tables).
- `viewer.py`, `viewer.html`, `viewer.css`, `viewer.js`: the local trace viewer and its endpoints.
- `test_basic.py`: pytest checks for metrics, calculator, ReAct and answer parsers, early stopping, and sampling.
- `requirements.txt`: pinned versions of the packages the code imports.

## Metric definitions

- **Latency:** `time.perf_counter()` around `solve()`. It includes every LLM call, tool call and parsing. It excludes model loading, index building and the warm-up call.
- **Input tokens:** sum of prompt tokens over all LLM calls. ReAct re-sends the growing scratchpad each step.
- **Output tokens:** sum of generated tokens over all LLM calls.
- **Thinking tokens:** tokens of the thought text only. CoT: text before `Answer:`. ReAct / Focused: the `Thought:` parts. This is a subset of output tokens. It is counted by re-tokenizing the thought text.
- **Observation tokens:** tokens of tool outputs, counted once when produced.
- **Steps:** number of LLM calls, including the forced final call of Focused ReAct.
- **EM:** exact match after normalization (HotPotQA). For GSM8K, `em` is the numeric correctness as 0/1, so Figure 1 can show it.
- **Precision / recall / F1:** token-level on normalized answers (HotPotQA). Null for GSM8K.
- **correct:** EM for HotPotQA; numeric match (last number in the prediction) for GSM8K.

## Hardware

Measurements in `results/run_info.json`: RTX 3060 Laptop GPU (6 GB), torch 2.5.1+cu121, llama-cpp-python 0.3.4 with CUDA, greedy decoding, seed 0, batch size 1.

## Known limitations

- One model, quantized to Q4_K_M. Absolute numbers will differ from bf16 runs of the same model.
- Standard and CoT are closed-book, as in the paper's question-only setup. Their scores are low for a 3B model.
- The HotPotQA search corpus is the paragraphs of the sampled questions (including distractors). It is much smaller than Wikipedia, so retrieval is easier than in the paper.
- Only 2 hand-written few-shot examples per dataset. Prompt sensitivity was not studied.
- Each LLM call re-processes the full prompt (the KV cache is reset before every call). This matches a stateless HF call, but the absolute latency depends on this choice.
- Latency is from one run on one laptop. It is not a benchmark of the hardware.
- With 200 questions per configuration, the bootstrap CIs are wide. Multiple comparisons are not corrected in the McNemar tests.
- The Focused ReAct forced call still fails to produce a usable `Finish[...]` on 8/200 GSM8K, 1/200 HotPotQA sparse and 2/200 HotPotQA dense. The fallback takes the last number of the forced output on GSM8K (which can pick up a number from an action expression) or the last line on HotPotQA. The stop reason `parse_error` marks these cases.
- Greedy decoding can get stuck repeating the same action, which mostly ends in `max_steps` for vanilla ReAct.

## Deviations

Deviations from the brief, the design notes, and the paper. The brief takes precedence over the notes, as stated in the brief.

From the brief:
1. **Backend:** generation uses llama-cpp-python on the provided Q4_K_M GGUF, not transformers in bf16 with `device_map="auto"`. The GGUF fits in 6 GB VRAM; bf16 does not (about 6.2 GB of weights) and would run partly on CPU. Greedy decoding is `temperature=0`. Stop strings use llama's `stop=`, and the text is also cut at the first stop string.
2. **Chat template:** rendered with jinja2 from the GGUF metadata, using the same engine as `apply_chat_template`. Qwen's template inserts a default system prompt ("You are Qwen...") when none is given. This is counted in input tokens for every agent. No system message was added by us.
3. **Models:** only `qwen`. Gemma is out of scope for now.
4. **Data:** loaded from local files, not the Hugging Face `datasets` hub. The sample is a seeded shuffle (`random.Random(0)`) followed by the first `n`, so a smaller sample is a prefix of a larger one.
5. **Agent constructor:** `Agent(lm, dataset, tools)` takes a `dataset` argument. It selects the dataset-specific prompts and fallback parsing.
6. **File layout:** one file per agent (4 files), each with HotPotQA and GSM8K prompt constants. Not 8 files.
7. **Few-shot questions** (train splits only, never from the evaluation sample): HotPotQA `5a879ab05542996e4f30887e` and `5a7d0db955429909bec76924`; GSM8K train rows 0 (Natalia) and 1 (Weng).
8. **Focused ReAct** reuses the 2 ReAct examples and does not have its own constants.
9. **Forced call:** the forced final call of Focused ReAct is counted as an LLM call, so Focused can make 8 calls (7 steps and the forced call).
10. **`parse_error`:** used when a fallback parser was needed (Standard/CoT without `Answer:`, ReAct/Focused without `Finish[...]`). Without this, the stop reason would never occur.
11. **Invalid-action message:** names the dataset's own tool (`Search[...]` or `Calculate[...]`) instead of listing both.
12. **Search output:** each passage line `[Title] text` is cut to 400 characters.
13. **GSM8K `em` column:** holds the numeric correctness (0/1), so EM figures work for both datasets. Precision, recall and F1 are null.
14. **Smoke test size:** 10 questions, as requested (the brief said 5).
15. **Dependencies:** `accelerate` and `datasets` were dropped (not used). `llama-cpp-python` was added.

From the design notes (the brief wins where they differ):
16. No `Response` object with tensors. `LanguageModel` returns plain text and integer counts.
17. No model-specific thinking parser. Thinking is parsed in the agents, and only Qwen is in scope.
18. `Calculate` uses `simpleeval`, not Python `eval`.
19. The agent API is `run` / `solve` / `call`. There is no chat history, `clear_context` or `add_system_prompt`.

From the paper:
20. 2 few-shot exemplars per dataset (the paper uses 6 for HotPotQA). Model is Qwen2.5-3B, not PaLM-540B.
21. `Search` is top-k passage retrieval over the sampled questions' paragraphs (BM25 or MiniLM). The paper uses a Wikipedia API with `search[entity]` and `lookup[string]`; there is no `Lookup` action here.
22. HotPotQA only. The Fever, ALFWorld and WebShop experiments and the Act-only and CoT-SC baselines are not included.
23. `max_steps=7` for ReAct, as in the paper's HotPotQA setup.
24. **Forced-answer fix (post-run):** in the first grid, 95/600 Focused ReAct runs ended in `parse_error` because the forced final call emitted another `Calculate[...]` or `Search[...]` instead of `Finish[...]`. The forced prompt now states that the tools are unavailable and asks for `Action: Finish[<final answer>]`, and `Finish[...]` is accepted without the `Action:` prefix. Placeholder answers (`answer`, `<final answer>`) are rejected. Focused ReAct was rerun on all three configurations; its three result files were replaced and the old ones are in `backup/focused_before_force_fix/`. The other agents are unchanged.

## Results

Free model, N=200 per configuration, greedy decoding, one run. Focused ReAct was rerun after the forced-answer fix described in deviation 24; the other rows are from the original run.

| Dataset | Agent | EM | Mean LLM calls | Mean latency (s) | Tokens per correct |
|---|---|---|---|---|---|
| GSM8K | Standard | 0.175 | 1.0 | 0.15 | 1148 |
| GSM8K | CoT | 0.795 | 1.0 | 3.03 | 636 |
| GSM8K | ReAct | 0.475 | 4.1 | 5.96 | 5896 |
| GSM8K | Focused ReAct | 0.645 | 3.6 | 3.41 | 3725 |
| HotPotQA | Standard | 0.140 | 1.0 | 0.12 | 982 |
| HotPotQA | CoT | 0.130 | 1.0 | 1.37 | 2574 |
| HotPotQA | ReAct (sparse) | 0.155 | 4.8 | 5.63 | 40928 |
| HotPotQA | Focused ReAct (sparse) | 0.255 | 3.5 | 3.22 | 14898 |
| HotPotQA | ReAct (dense) | 0.180 | 4.9 | 6.22 | 36131 |
| HotPotQA | Focused ReAct (dense) | 0.275 | 3.4 | 3.26 | 13310 |

Reading:

- **CoT is the best agent on GSM8K** (0.795 vs 0.175 for Standard, p = 1.9e-31). Focused ReAct (0.645) beats ReAct (0.475, p = 5.8e-05) but is still behind CoT.
- **On HotPotQA, Focused ReAct is the best** (sparse 0.255 vs 0.155 for ReAct, p = 0.0017; dense 0.275 vs 0.180). Standard (0.140) and CoT (0.130) are closed-book, so both are weak, and the difference is not significant (p = 0.83).
- **Cost follows accuracy.** CoT is the most token-efficient correct answer on GSM8K (636 tokens per correct). ReAct is by far the most expensive (5896 tokens per correct on GSM8K, 40928 on HotPotQA), because it re-sends the growing scratchpad and often loops to `max_steps`.
- **Dense beats sparse on retrieval**, 0.75 vs 0.65 recall@3 on HotPotQA, and the end-to-end gap is small (ReAct 0.180 vs 0.155, Focused 0.275 vs 0.255).
- **Stop reasons.** ReAct ends in `max_steps` on 78/200 HotPotQA and 58/200 GSM8K questions, usually by repeating the same action. Focused ReAct reaches an early stop (or the 7-step budget) and makes the forced final call on 87/200 GSM8K, 59/200 HotPotQA sparse and 49/200 HotPotQA dense; the forced call still fails to parse on 8, 1 and 2 of those respectively.

Figures and tables are in `figures/`. Error bars are 95% bootstrap CIs.
