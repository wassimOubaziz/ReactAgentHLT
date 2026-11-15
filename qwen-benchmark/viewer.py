"""Local viewer: python viewer.py, then open http://127.0.0.1:8000"""
import argparse
import json
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

import agent as agent_module
from cot import CoTAgent
from data import load_gsm8k, load_hotpotqa
from default import StandardAgent
from focused_react import FocusedReActAgent
from llm import MODELS, LanguageModel
from metrics import em, f1, gsm8k_correct
from react import ReActAgent
from tools import Search, calculate, paragraphs

ROOT = Path(__file__).parent
app = Flask(__name__, static_folder=None)
AGENTS = {"default": StandardAgent, "cot": CoTAgent, "react": ReActAgent, "focused": FocusedReActAgent}
LOADERS = {"hotpotqa": load_hotpotqa, "gsm8k": load_gsm8k}
STATE: dict = {"lm": None, "items": {}, "search": {}, "busy": False, "examples": 200}
LOCK = threading.RLock()  # reentrant: load_search -> load_items


def load_items(dataset: str) -> list[dict]:
    with LOCK:
        if dataset not in STATE["items"]:
            STATE["items"][dataset] = LOADERS[dataset](STATE["examples"])
        return STATE["items"][dataset]


def load_search(retriever: str) -> Search:
    with LOCK:
        if retriever not in STATE["search"]:
            STATE["search"][retriever] = Search(paragraphs(load_items("hotpotqa")), kind=retriever, k=3)
        return STATE["search"][retriever]


def build_tools(dataset: str, agent_name: str, retriever: str) -> dict | None:
    if agent_name in ("default", "cot"):
        return None
    return {"Calculate": calculate} if dataset == "gsm8k" else {"Search": load_search(retriever)}


def score(dataset: str, pred: str, gold: str) -> dict:
    if dataset == "gsm8k":
        return {"correct": gsm8k_correct(pred, gold)}
    return {"correct": em(pred, gold) == 1.0, "f1": round(f1(pred, gold), 3)}


def run_worker(body: dict, events: list, condition: threading.Condition) -> None:
    def push(event: dict) -> None:
        with condition:
            events.append(event)
            condition.notify_all()

    try:
        if STATE["lm"] is None:
            push({"kind": "loading", "text": "Loading the model (first run only, about 5 s)..."})
            STATE["lm"] = LanguageModel(body["model"])
        items = load_items(body["dataset"])
        index = int(body.get("index", -1))
        item = items[index] if index >= 0 else {"id": "custom", "question": body["question"], "gold": ""}
        if body.get("retriever") == "dense" and body["agent"] in ("react", "focused"):
            push({"kind": "loading", "text": "Building the dense index (first dense run only)..."})
        tools = build_tools(body["dataset"], body["agent"], body["retriever"])
        push({"kind": "meta", "question": item["question"], "gold": item.get("gold", ""),
              "gold_titles": item.get("gold_titles", []),
              "dataset": body["dataset"], "agent": body["agent"], "retriever": body["retriever"],
              "model": body["model"], "corpus": len(tools["Search"].paras) if tools and "Search" in tools else 0,
              "search_k": tools["Search"].k if tools and "Search" in tools else 0})
        agent = AGENTS[body["agent"]](STATE["lm"], body["dataset"], tools)
        agent_module.SINK = events
        result = agent.run(item["question"])
        agent_module.SINK = None
        push({"kind": "result", "prediction": result.prediction, "gold": item.get("gold", ""), "stop_reason": result.stop_reason,
              "steps": result.steps, "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
              "thinking_tokens": result.thinking_tokens, "observation_tokens": result.observation_tokens,
              "latency_s": round(result.latency_s, 2), **score(body["dataset"], result.prediction, item.get("gold", ""))})
    except Exception as exc:
        push({"kind": "error", "text": f"{type(exc).__name__}: {exc}"})
    finally:
        agent_module.SINK = None
        push({"kind": "done"})


def pop_event(events: list, condition: threading.Condition) -> dict | None:
    with condition:
        condition.wait_for(lambda: bool(events), timeout=0.2)
        return events.pop(0) if events else None


@app.get("/")
def index():
    return send_from_directory(ROOT, "viewer.html")


@app.get("/viewer.css")
def css():
    return send_from_directory(ROOT, "viewer.css")


@app.get("/viewer.js")
def js():
    return send_from_directory(ROOT, "viewer.js")


@app.get("/api/examples")
def examples():
    dataset = request.args.get("dataset", "hotpotqa")
    return jsonify({
        "items": [{"index": i, "question": it["question"], "gold": it.get("gold", "")}
                  for i, it in enumerate(load_items(dataset))],
        "datasets": list(LOADERS), "agents": list(AGENTS), "models": list(MODELS),
    })


@app.post("/api/run")
def run():
    body = request.get_json(force=True)
    if STATE["busy"]:
        return jsonify({"error": "A run is already in progress."}), 409
    events: list = []
    condition = threading.Condition()
    STATE["busy"] = True
    worker = threading.Thread(target=run_worker, args=(body, events, condition), daemon=True)
    worker.start()

    def stream():
        try:
            while True:
                event = pop_event(events, condition)
                if event is None:
                    continue
                yield json.dumps(event) + "\n"
                if event["kind"] == "done":
                    break
        finally:
            STATE["busy"] = False

    return Response(stream(), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agent viewer locally")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--examples", type=int, default=200)
    args = parser.parse_args()
    STATE["examples"] = args.examples
    print(f"Viewer: http://127.0.0.1:{args.port}")
    app.run(host="127.0.0.1", port=args.port, threaded=True)


if __name__ == "__main__":
    main()
