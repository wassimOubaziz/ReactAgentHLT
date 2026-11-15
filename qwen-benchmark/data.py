import json
import random
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "dataset"


def _sample(total: int, n: int) -> list[int]:
    """Seeded shuffle, then the first n: the n-sample is a prefix of any larger sample."""
    order = list(range(total))
    random.Random(0).shuffle(order)
    return order[:n]


def load_hotpotqa(n: int) -> list[dict]:
    data = json.loads((DATA / "hotpot" / "hotpot_dev_distractor_v1.json").read_text(encoding="utf-8"))
    return [
        {
            "id": data[i]["_id"],
            "question": data[i]["question"],
            "gold": data[i]["answer"],
            "context": data[i]["context"],
            "gold_titles": list(dict.fromkeys(t for t, _ in data[i]["supporting_facts"])),
        }
        for i in _sample(len(data), n)
    ]


def load_gsm8k(n: int) -> list[dict]:
    df = pd.read_parquet(DATA / "gsm8k" / "main" / "test-00000-of-00001.parquet")
    return [
        {
            "id": str(i),
            "question": df.iloc[i]["question"],
            "gold": df.iloc[i]["answer"].split("####")[-1].strip().replace(",", ""),
        }
        for i in _sample(len(df), n)
    ]
