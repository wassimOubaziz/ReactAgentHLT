"""Verify the checkpoint without loading the model. Run: python resume_check.py"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
EXPECTED = {
    ("gsm8k", "default", "none"), ("gsm8k", "cot", "none"), ("gsm8k", "react", "none"), ("gsm8k", "focused", "none"),
    ("hotpotqa", "default", "none"), ("hotpotqa", "cot", "none"),
    ("hotpotqa", "react", "sparse"), ("hotpotqa", "focused", "sparse"),
    ("hotpotqa", "react", "dense"), ("hotpotqa", "focused", "dense"),
}


def main() -> int:
    problems = []
    for dataset, agent, retriever in sorted(EXPECTED):
        path = ROOT / "results" / f"{dataset}__qwen__{agent}__{retriever}.jsonl"
        if not path.exists():
            problems.append(f"missing file: {path.name}")
            continue
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        n = len(rows)
        ids = {r["id"] for r in rows}
        if len(ids) != n:
            problems.append(f"{path.name}: {n - len(ids)} duplicate ids")
        if n != 200:
            problems.append(f"{path.name}: {n}/200 rows")
        print(f"{path.name}: {n}/200 rows, {len(ids)} unique ids")

    missing = EXPECTED - {
        (path.name.split("__")[0], path.name.split("__")[2], path.name.split("__")[3][:-6])
        for path in (ROOT / "results").glob("*.jsonl")
    }
    if missing:
        problems.append(f"missing configurations: {sorted(missing)}")

    proc = subprocess.run([sys.executable, "-m", "pytest", "test_basic.py", "-q"], cwd=ROOT, capture_output=True, text=True)
    print(proc.stdout.strip().splitlines()[-1])
    if proc.returncode:
        problems.append("pytest failed")

    print("\nCHECKPOINT OK" if not problems else "\nPROBLEMS:\n" + "\n".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
