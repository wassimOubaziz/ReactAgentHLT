import math
import re
import string
from collections import Counter

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
SPECIAL = {"yes", "no", "noanswer"}


def normalize(text: str) -> str:
    """Official HotPotQA normalization: lowercase, strip punctuation and articles, fix whitespace."""
    text = "".join(ch for ch in text.lower() if ch not in string.punctuation)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def _overlap(pred: str, gold: str) -> tuple[float, float]:
    """Token precision and recall; yes/no/noanswer mismatches score 0."""
    p, g = normalize(pred), normalize(gold)
    if p != g and (p in SPECIAL or g in SPECIAL):
        return 0.0, 0.0
    pt, gt = p.split(), g.split()
    same = sum((Counter(pt) & Counter(gt)).values())
    if same == 0:
        return 0.0, 0.0
    return same / len(pt), same / len(gt)


def em(pred: str, gold: str) -> float:
    return float(normalize(pred) == normalize(gold))


def precision(pred: str, gold: str) -> float:
    return _overlap(pred, gold)[0]


def recall(pred: str, gold: str) -> float:
    return _overlap(pred, gold)[1]


def f1(pred: str, gold: str) -> float:
    p, r = _overlap(pred, gold)
    return 2 * p * r / (p + r) if p + r else 0.0


def last_number(text: str) -> str | None:
    found = NUMBER.findall(text.replace(",", "").replace("$", ""))
    return found[-1] if found else None


def gsm8k_correct(pred: str, gold: str) -> bool:
    found = last_number(pred)
    return found is not None and math.isclose(float(found), float(gold), abs_tol=1e-6)
