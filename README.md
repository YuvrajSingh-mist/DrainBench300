# DrainBench300

This repo benchmarks Droidrun / Mobilerun tasks with:

- wireless ADB phone sampling
- `scrcpy` screen recording
- mini2-hosted `llama.cpp`
- per-run OpenAI-compatible proxy logging
- run folders with phone + model metrics

Current architecture:

- phone: agent execution only
- mini2: model serving only
- this Mac repo: benchmark harness and artifacts

That split is the most stable setup we found for repeatable runs.

## Command Cheatsheet

Use these from the repo root:

```bash
cd /Users/yuvrajsingh9886/Desktop/DrainBench300
export OPENAI_API_KEY=dummy
export DRAINBENCH_SERIAL=172.24.2.66:5555
export LLM_UPSTREAM=http://192.168.1.23:8081/v1
export MODEL='bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF:Q4_K_M'
```

Check the phone and model server:

```bash
adb devices -l
curl -s "$LLM_UPSTREAM/models"
```

Export the dataset after editing [docs/tasks.md](/Users/yuvrajsingh9886/Desktop/DrainBench300/docs/tasks.md):

```bash
python3 scripts/export_tasks_dataset.py
```

List a task slice:

```bash
python3 drainbench_tasks.py --bucket easy --app gmail --list
```

Dry-run a task slice:

```bash
python3 drainbench_tasks.py \
  --bucket easy \
  --app gmail \
  --skip-unresolved \
  --serial "$DRAINBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL" \
  --out-dir runs/gmail/easy \
  --dry-run
```

Run Gmail easy tasks with placeholders skipped:

```bash
python3 drainbench_tasks.py \
  --bucket easy \
  --app gmail \
  --skip-unresolved \
  --serial "$DRAINBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL" \
  --out-dir runs/gmail/easy
```

Run Gmail easy tasks with placeholder values:

```bash
python3 drainbench_tasks.py \
  --bucket easy \
  --app gmail \
  --serial "$DRAINBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL" \
  --out-dir runs/gmail/easy \
  --var sender="Alice" \
  --var contact="Bob"
```

Run a single task with full harness artifacts:

```bash
python3 drainbench_runner.py \
  --serial "$DRAINBENCH_SERIAL" \
  --label gmail-unread-count \
  --out-dir runs/gmail/single \
  --sample-interval 1.0 \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --llm-proxy-port 8090 \
  -- \
  /Users/yuvrajsingh9886/.local/bin/mobilerun run \
  -d "$DRAINBENCH_SERIAL" \
  -p OpenAILike \
  -m "$MODEL" \
  --api_base http://127.0.0.1:8090/v1 \
  --temperature 0 \
  --steps 50 \
  --no-vision \
  --no-reasoning \
  --debug \
  "Check how many unread emails are in the inbox"
```

USB debug run:

```bash
export DRAINBENCH_SERIAL=RS7XKZDI8HTOJNYL
python3 drainbench_tasks.py \
  --bucket easy \
  --app gmail \
  --skip-unresolved \
  --serial "$DRAINBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL" \
  --out-dir runs/gmail/easy/usb
```

Wireless benchmark run:

```bash
export DRAINBENCH_SERIAL=172.24.2.66:5555
python3 drainbench_tasks.py \
  --bucket easy \
  --app gmail \
  --skip-unresolved \
  --serial "$DRAINBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL" \
  --out-dir runs/gmail/easy/wireless
```

Stop interrupted runs:

```bash
pkill -f "drainbench_tasks.py" || true
pkill -f "drainbench_runner.py" || true
pkill -f "mobilerun run" || true
pkill -f "scripts/openai_proxy_logger.py" || true
pkill -f "scrcpy" || true
```

## Current known-good target

- phone: OnePlus `CPH2423`
- Android: `15`
- SoC: `MT6895`
- model host: `mini2`
- model endpoint: `http://192.168.1.23:8081/v1`
- model: `bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF:Q4_K_M`

## Repo layout

- [drainbench_runner.py](/Users/yuvrajsingh9886/Desktop/DrainBench300/drainbench_runner.py): thin CLI wrapper
- [src/drainbench](/Users/yuvrajsingh9886/Desktop/DrainBench300/src/drainbench): harness package
- [drainbench_tasks.py](/Users/yuvrajsingh9886/Desktop/DrainBench300/drainbench_tasks.py): dataset-backed segmented runner
- [pyproject.toml](/Users/yuvrajsingh9886/Desktop/DrainBench300/pyproject.toml): package metadata
- [Makefile](/Users/yuvrajsingh9886/Desktop/DrainBench300/Makefile): common test commands
- [scripts/openai_proxy_logger.py](/Users/yuvrajsingh9886/Desktop/DrainBench300/scripts/openai_proxy_logger.py): per-run proxy/logger
- [scripts/export_tasks_dataset.py](/Users/yuvrajsingh9886/Desktop/DrainBench300/scripts/export_tasks_dataset.py): markdown-to-dataset exporter
- [datasets](/Users/yuvrajsingh9886/Desktop/DrainBench300/datasets): JSON / JSONL task dataset artifacts
- [benchmarks/droidrun300](/Users/yuvrajsingh9886/Desktop/DrainBench300/benchmarks/droidrun300): benchmark content pointers
- [docs](/Users/yuvrajsingh9886/Desktop/DrainBench300/docs): benchmark methodology, policy, and task list
- [reports](/Users/yuvrajsingh9886/Desktop/DrainBench300/reports): benchmark reports and notes
- [tests](/Users/yuvrajsingh9886/Desktop/DrainBench300/tests): pytest coverage for CLI, parsing, helpers, and process wiring
- [runs](/Users/yuvrajsingh9886/Desktop/DrainBench300/runs): run artifacts

## One-time setup

Install tools:

```bash
uv tool install mobilerun
mobilerun setup
mobilerun ping
```

Also make sure these are installed locally:

- `adb`
- `scrcpy`
- Python 3.10+

Provider rule for this repo:

- use `-p OpenAILike`
- do not use `-p OpenAI`

Reason: the harness talks to a local OpenAI-compatible endpoint, not the real OpenAI API.

## Wireless ADB

Connect once over USB, then run:

```bash
adb devices -l
PHONE_IP=$(adb shell "ip -f inet addr show wlan0 | sed -n 's/.*inet \\([0-9.]*\\)\\/.*/\\1/p' | head -1" | tr -d '\r')
adb tcpip 5555
adb connect ${PHONE_IP}:5555
adb devices -l
export DRAINBENCH_SERIAL="${PHONE_IP}:5555"
```

Known-good wireless serial from this session:

```bash
export DRAINBENCH_SERIAL=172.24.2.66:5555
```

Use wireless ADB for real battery / thermal runs so the USB cable does not skew results.

## Start the mini2 model server

```bash
ssh mini2 '
export PATH="/opt/homebrew/bin:$PATH"
pkill -f llama-server || true
nohup llama-server \
  -hf bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF:Q4_K_M \
  --host 0.0.0.0 \
  --port 8081 \
  -c 32768 \
  -ngl 99 \
  -fa on \
  -ctk q8_0 \
  -ctv q8_0 \
  -t 4 \
  -tb 4 \
  -np 1 \
  -b 2048 \
  -ub 2048 \
  --jinja \
  --metrics \
  > ~/llama_logs/qwen4b_8081.log 2>&1 < /dev/null &
'
```

Then verify:

```bash
curl -s http://192.168.1.23:8081/v1/models
```

The best-tested prompt batch for this workload was `-b 2048 -ub 2048`.

## Run one benchmark

```bash
cd /Users/yuvrajsingh9886/Desktop/DrainBench300

export OPENAI_API_KEY=dummy
export DRAINBENCH_SERIAL=172.24.2.66:5555
export LLM_UPSTREAM=http://192.168.1.23:8081/v1
export MODEL='bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF:Q4_K_M'

python3 drainbench_runner.py \
  --serial "$DRAINBENCH_SERIAL" \
  --label some-task \
  --sample-interval 1.0 \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --llm-proxy-port 8090 \
  -- \
  /Users/yuvrajsingh9886/.local/bin/mobilerun run \
  -d "$DRAINBENCH_SERIAL" \
  -p OpenAILike \
  -m "$MODEL" \
  --api_base http://127.0.0.1:8090/v1 \
  --temperature 0 \
  --steps 50 \
  --no-vision \
  --no-reasoning \
  --debug \
  "your task here"
```

## What each run folder contains

Core artifacts:

- `meta.json`
- `preflight.json`
- `postflight.json`
- `samples.ndjson`
- `summary.json`
- `command.stdout.txt`
- `command.stderr.txt`
- `output.txt`

Optional artifacts when enabled:

- `screen.mp4`
- `screenrecord.stdout.txt`
- `screenrecord.stderr.txt`
- `llm_proxy_metrics.jsonl`
- `llm_proxy.stdout.txt`
- `llm_proxy.stderr.txt`
- `llm_metrics.json`

`output.txt` stores the final task-facing result, so tasks that are expected to display an answer have a single easy place to read it.

For wrapped Mobilerun terminal output, the parser now keeps the full final success or failure message, not just the first terminal line.

## Local test commands

```bash
make test
make test-fast
make test-cli
./scripts/run_tests.sh
```

## Export the task dataset

```bash
python3 scripts/export_tasks_dataset.py
```

This writes:

- `datasets/drainbench_730_v3.json`
- `datasets/drainbench_730_v3.jsonl`

The JSONL file is the easiest artifact to upload to Hugging Face datasets.

## Step-budget policy

- default action budget: `50` steps for every task
- this is intentionally fixed across easy, medium, hard-deterministic, and open-ended buckets
- the benchmark uses one global action budget to avoid bucket-specific budget advantages

## Run selected task segments

List a slice first:

```bash
python3 drainbench_tasks.py --bucket easy --app gmail --list
```

Dry-run the exact commands:

```bash
python3 drainbench_tasks.py \
  --bucket easy \
  --app gmail \
  --limit 3 \
  --dry-run \
  --serial "$DRAINBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL"
```

Run a whole slice while skipping tasks that still need placeholder values:

```bash
python3 drainbench_tasks.py \
  --bucket easy \
  --app gmail \
  --skip-unresolved \
  --serial "$DRAINBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL" \
  --no-screen-record
```

Run every task in the dataset:

```bash
python3 drainbench_tasks.py \
  --all \
  --skip-unresolved \
  --serial "$DRAINBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL"
```

## Metric meanings

- `elapsed_seconds`: full end-to-end wall time
- `llm_ttft_ms`: first model prefill latency for the run
- `llm_prompt_tokens_sum`: total input tokens across all agent turns
- `llm_completion_tokens_sum`: total output tokens across all agent turns
- `llm_total_tokens_sum`: total prompt + completion tokens across the run
- `llm_prefill_tokens_per_second`: total prompt tokens divided by total prompt time
- `llm_decode_tokens_per_second`: total completion tokens divided by total decode time

So yes: whole-run metrics are aggregated, not just copied from the last call.

## Remaining reference files

- [reports/failures.md](/Users/yuvrajsingh9886/Desktop/DrainBench300/reports/failures.md)
- [reports/droidrun300-benchmark.md](/Users/yuvrajsingh9886/Desktop/DrainBench300/reports/droidrun300-benchmark.md)
- [reports/trace.md](/Users/yuvrajsingh9886/Desktop/DrainBench300/reports/trace.md)
