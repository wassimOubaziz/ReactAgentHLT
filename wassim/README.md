# wassim

Local text-generation engine. It loads either a `.gguf` file through llama.cpp or a Hugging Face model folder through transformers.

## Install

```powershell
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 `
  --index-url https://download.pytorch.org/whl/cu124
pip install "transformers>=5.0" accelerate jinja2 safetensors sentencepiece
pip install llama-cpp-python==0.3.4
```

## Run

From the project root:

```powershell
python -m wassim.test_engine --model "models\LFM3-1.7B"
python -m wassim.test_engine --model "models\qwen2.5-3b-instruct-q4_k_m.gguf"
```

Directly from the `wassim` folder:

```powershell
python test_engine.py --model "D:\ReactAgentHLT_wassim\models\LFM3-1.7B"
```

## Use in code

```python
from wassim.engine import ModelEngine

engine = ModelEngine("D:/models/my-model")
result = engine.generate(
    [{"role": "user", "content": "Hello"}],
    max_new_tokens=64,
    stop_strings=("Observation:",),
)
print(result.text)
engine.unload()
```

`generate` accepts a string or chat messages. Optional parameters: `max_new_tokens`, `stop_strings`, `should_stop`, `on_token`.

## Model paths

- `.gguf` file -> llama.cpp.
- Folder with `config.json` -> transformers.
- Any text-generation model supported by the installed backend.
- Gated models (for example Gemma) need `hf auth login` and a license acceptance.
- On a 6 GB GPU, use GGUF or quantized models for 7B and larger.

## Thinking

Models that support `enable_thinking` or `thinking` in their chat template have it **off** by default. Turn it on with:

```powershell
python -m wassim.test_engine --model "models\LFM3-1.7B" --enable-thinking
```

Models without a thinking switch are unaffected.

## Tested

```text
LFM3-1.7B: Finish[4], Finish[6], Hello, world!
Qwen2.5-3B Q4: Finish[4], Finish[6], Hello World!
```

Run the test after any dependency or model change.
