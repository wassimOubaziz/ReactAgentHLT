import argparse
import gc
import json
import subprocess
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import torch
from tqdm import tqdm

from cot import CoTAgent
from data import load_gsm8k, load_hotpotqa
from default import StandardAgent
from focused_react import FocusedReActAgent
from llm import MODELS, LanguageModel
from metrics import em, f1, gsm8k_correct, precision, recall
from react import ReActAgent
from tools import Search, calculate, paragraphs

AGENTS = {"default": StandardAgent, "cot": CoTAgent, "react": ReActAgent, "focused": FocusedReActAgent}
LOADERS = {"hotpotqa": load_hotpotqa, "gsm8k": load_gsm8k}
RESULTS = Path(__file__).parent / "results"
PACKAGES = ["llama-cpp-python", "torch", "sentence-transformers", "rank-bm25", "simpleeval", "numpy", "pandas", "tqdm"]


def make_tools(dataset: str, items: list[dict], agent_name: str, retriever: str) -> dict | None:
    if agent_name in ("default", "cot"):
        return None
    if dataset == "gsm8k":
        return {"Calculate": calculate}
    return {"Search": Search(paragraphs(items), kind=retriever)}


def score(dataset: str, pred: str, gold: str) -> dict:
    if dataset == "gsm8k":
        correct = gsm8k_correct(pred, gold)
        return {"correct": correct, "em": float(correct), "precision": None, "recall": None, "f1": None}
    return {
        "correct": em(pred, gold) == 1.0, "em": em(pred, gold), "precision": precision(pred, gold),
        "recall": recall(pred, gold), "f1": f1(pred, gold),
    }


def run_config(lm: LanguageModel, model_name: str, dataset: str, items: list[dict],
               agent_name: str, retriever: str, out: Path = RESULTS) -> None:
    path = out / f"{dataset}__{model_name}__{agent_name}__{retriever}.jsonl"
    done = {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
    todo = [item for item in items if item["id"] not in done]
    if not todo:
        return
    agent = AGENTS[agent_name](lm, dataset, make_tools(dataset, items, agent_name, retriever))
    with path.open("a", encoding="utf-8") as f:
        for item in tqdm(todo, desc=path.stem):
            res = agent.run(item["question"])
            row = {
                "id": item["id"], "dataset": dataset, "model": model_name, "agent": agent_name,
                "retriever": retriever, "question": item["question"], "gold": item["gold"],
                "prediction": res.prediction, **score(dataset, res.prediction, item["gold"]),
                "stop_reason": res.stop_reason, "steps": res.steps, "input_tokens": res.input_tokens,
                "output_tokens": res.output_tokens, "thinking_tokens": res.thinking_tokens,
                "observation_tokens": res.observation_tokens, "latency_s": res.latency_s,
                "trajectory": res.trajectory,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()


def write_run_info(out: Path = RESULTS) -> None:
    path = out / "run_info.json"
    if path.exists():
        return
    try:
        git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                             cwd=Path(__file__).parent).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        git = None
    info = {
        "packages": {name: version(name) for name in PACKAGES},
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "seed": 0,
        "date": datetime.now().isoformat(timespec="seconds"),
        "git_hash": git,
    }
    path.write_text(json.dumps(info, indent=2), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description="Run agents on HotPotQA / GSM8K samples; writes results/*.jsonl")
    p.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    p.add_argument("--agents", nargs="+", default=list(AGENTS), choices=list(AGENTS))
    p.add_argument("--datasets", nargs="+", default=list(LOADERS), choices=list(LOADERS))
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--retriever", default="sparse", choices=["sparse", "dense"])
    p.add_argument("--results-dir", default=str(RESULTS), help="output folder (use a new one per model)")
    args = p.parse_args()
    out = Path(args.results_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_run_info(out)
    for model_name in args.models:
        lm = LanguageModel(model_name)
        for dataset in args.datasets:
            items = LOADERS[dataset](args.n)
            for agent_name in args.agents:
                uses_search = dataset == "hotpotqa" and agent_name in ("react", "focused")
                retriever = args.retriever if uses_search else "none"
                run_config(lm, model_name, dataset, items, agent_name, retriever, out)
        del lm
        gc.collect()
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
