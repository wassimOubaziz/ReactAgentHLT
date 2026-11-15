import time
from dataclasses import dataclass

from llm import LanguageModel
from metrics import last_number

SINK: list | None = None  # collect visual events when a viewer session is active


def log(kind: str, **data) -> None:
    """Append one visual event (no-op unless a viewer subscribed)."""
    if SINK is not None:
        SINK.append({"kind": kind, **data})


def viewing() -> bool:
    """True while a viewer is streaming this run."""
    return SINK is not None


@dataclass
class Result:
    prediction: str
    stop_reason: str
    steps: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    observation_tokens: int
    latency_s: float
    trajectory: str


def fallback_answer(text: str, dataset: str) -> str:
    """Last number for GSM8K, last non-empty line for HotPotQA."""
    if dataset == "gsm8k":
        return last_number(text) or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def parse_answer(text: str, dataset: str) -> tuple[str, bool]:
    """Text after the last 'Answer:' (found=True), otherwise a fallback (found=False)."""
    if "Answer:" in text:
        return text.rsplit("Answer:", 1)[1].strip().split("\n")[0].strip(), True
    return fallback_answer(text, dataset), False


class Agent:
    """Base agent: owns the per-run counters and the LLM bookkeeping."""

    def __init__(self, lm: LanguageModel, dataset: str, tools: dict | None = None):
        self.lm = lm
        self.dataset = dataset
        self.tools = tools or {}
        self._reset()

    def _reset(self) -> None:
        self.steps = self.input_tokens = self.output_tokens = 0
        self.thinking_tokens = self.observation_tokens = 0
        self.trajectory = ""

    def run(self, question: str) -> Result:
        self._reset()
        log("question", question=question, dataset=self.dataset, agent=type(self).__name__)
        start = time.perf_counter()
        prediction, stop_reason = self.solve(question)
        latency = time.perf_counter() - start
        return Result(
            prediction, stop_reason, self.steps, self.input_tokens, self.output_tokens,
            self.thinking_tokens, self.observation_tokens, latency, self.trajectory,
        )

    def solve(self, question: str) -> tuple[str, str]:
        raise NotImplementedError

    def call(self, prompt: str, **kw) -> str:
        log("prompt", prompt=prompt, max_new_tokens=kw.get("max_new_tokens"), stop=kw.get("stop"))
        start = time.perf_counter()
        out = self.lm.generate(prompt, **kw)
        self.steps += 1
        self.input_tokens += out.input_tokens
        self.output_tokens += out.output_tokens
        log("completion", text=out.text, input_tokens=out.input_tokens, output_tokens=out.output_tokens,
            latency_s=round(time.perf_counter() - start, 3))
        return out.text
