import os
from dataclasses import dataclass
from pathlib import Path

import torch
from jinja2.sandbox import ImmutableSandboxedEnvironment

if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(str(Path(torch.__file__).parent / "lib"))

from llama_cpp import Llama  # noqa: E402

MODELS = {"qwen": Path(__file__).parent / "qwen2.5-3b-instruct-q4_k_m.gguf"}


@dataclass
class LLMOutput:
    text: str
    input_tokens: int
    output_tokens: int


class LanguageModel:
    """Stateless wrapper: one prompt in, one greedy completion out."""

    def __init__(self, name: str):
        self.llm = Llama(model_path=str(MODELS[name]), n_gpu_layers=-1, n_ctx=8192, seed=0, verbose=False)
        env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        self.template = env.from_string(self.llm.metadata["tokenizer.chat_template"])
        self.generate("Reply with OK.", max_new_tokens=4)

    def _wrap(self, prompt: str) -> str:
        return self.template.render(messages=[{"role": "user", "content": prompt}], add_generation_prompt=True)

    def count_tokens(self, text: str) -> int:
        return len(self.llm.tokenize(text.encode("utf-8"), add_bos=False, special=True))

    def generate(self, prompt: str, max_new_tokens: int = 256, stop: list[str] | None = None) -> LLMOutput:
        self.llm.reset()
        out = self.llm.create_completion(
            self._wrap(prompt), max_tokens=max_new_tokens, temperature=0.0, stop=stop or []
        )
        text = out["choices"][0]["text"]
        for s in stop or []:
            text = text.split(s)[0]
        usage = out["usage"]
        return LLMOutput(text, usage["prompt_tokens"], usage["completion_tokens"])
