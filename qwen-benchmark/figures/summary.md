# Summary (mean ± 95% bootstrap CI)

| Dataset | Model | Agent | N | EM | F1 | Input tok | Output tok | Thinking tok | Observation tok | Steps | Latency (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GSM8K | qwen | CoT | 200 | 0.795 ± 0.055 | – | 291.530 ± 2.858 | 213.880 ± 12.272 | 208.890 ± 12.410 | 0.000 ± 0.000 | 1.000 ± 0.000 | 3.026 ± 0.171 |
| GSM8K | qwen | Standard | 200 | 0.175 ± 0.053 | – | 195.530 ± 2.858 | 5.425 ± 0.150 | 0.000 ± 0.000 | 0.000 ± 0.000 | 1.000 ± 0.000 | 0.153 ± 0.003 |
| GSM8K | qwen | Focused ReAct | 200 | 0.645 ± 0.062 | – | 2176.130 ± 148.981 | 226.245 ± 13.688 | 168.885 ± 10.801 | 7.995 ± 1.272 | 3.635 ± 0.188 | 3.406 ± 0.206 |
| GSM8K | qwen | ReAct | 200 | 0.475 ± 0.070 | – | 2466.465 ± 242.301 | 334.110 ± 35.943 | 256.160 ± 30.212 | 14.350 ± 3.243 | 4.095 ± 0.293 | 5.965 ± 0.630 |
| HotPotQA | qwen | CoT | 200 | 0.130 ± 0.047 | 0.203 ± 0.049 | 227.555 ± 0.938 | 107.045 ± 6.789 | 100.780 ± 6.666 | 0.000 ± 0.000 | 1.000 ± 0.000 | 1.370 ± 0.083 |
| HotPotQA | qwen | Standard | 200 | 0.140 ± 0.048 | 0.205 ± 0.050 | 130.555 ± 0.938 | 6.905 ± 0.995 | 0.000 ± 0.000 | 0.000 ± 0.000 | 1.000 ± 0.000 | 0.124 ± 0.011 |
| HotPotQA | qwen | Focused ReAct (dense) | 200 | 0.275 ± 0.060 | 0.414 ± 0.060 | 3492.490 ± 333.677 | 167.875 ± 12.291 | 114.455 ± 8.874 | 625.860 ± 52.084 | 3.370 ± 0.185 | 3.262 ± 0.272 |
| HotPotQA | qwen | Focused ReAct | 200 | 0.255 ± 0.057 | 0.362 ± 0.060 | 3630.165 ± 333.419 | 168.740 ± 12.179 | 114.520 ± 8.823 | 645.945 ± 51.057 | 3.475 ± 0.188 | 3.223 ± 0.262 |
| HotPotQA | qwen | ReAct (dense) | 200 | 0.180 ± 0.055 | 0.241 ± 0.055 | 6260.565 ± 537.192 | 243.025 ± 16.503 | 162.410 ± 11.396 | 1133.900 ± 93.992 | 4.895 ± 0.270 | 6.215 ± 0.483 |
| HotPotQA | qwen | ReAct | 200 | 0.155 ± 0.050 | 0.230 ± 0.052 | 6104.095 ± 548.093 | 239.700 ± 16.431 | 160.585 ± 11.379 | 1111.815 ± 99.394 | 4.775 ± 0.285 | 5.634 ± 0.450 |

## Tokens per correct answer (total input + output tokens / number correct)

| Dataset | Model | Agent | Tokens per correct |
|---|---|---|---|
| GSM8K | qwen | CoT | 636 |
| GSM8K | qwen | Focused ReAct | 3725 |
| GSM8K | qwen | ReAct | 5896 |
| GSM8K | qwen | Standard | 1148 |
| HotPotQA | qwen | CoT | 2574 |
| HotPotQA | qwen | Focused ReAct | 14898 |
| HotPotQA | qwen | Focused ReAct (dense) | 13310 |
| HotPotQA | qwen | ReAct | 40928 |
| HotPotQA | qwen | ReAct (dense) | 36131 |
| HotPotQA | qwen | Standard | 982 |
