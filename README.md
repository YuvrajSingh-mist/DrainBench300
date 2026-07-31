# DailyBench300

A benchmark harness that runs Android agent tasks (via the [mobilerun SDK](https://docs.mobilerun.ai/framework/sdk)) against a real phone and a real LLM, and captures phone + model performance metrics for every run.

## Architecture

- **Phone**: agent execution only.
- **mini2** (or any model host): serves the LLM over an OpenAI-compatible endpoint.
- **This repo**: benchmark harness, dataset, and run artifacts — drives the phone over ADB and the model over HTTP.

That split is the most stable setup found for repeatable runs. The harness talks to the phone entirely through the `mobilerun` Python SDK (`AndroidDriver`/`MobileAgent`), in-process — there's no external `mobilerun` CLI binary involved anywhere.

## Prerequisites

Installed locally (system tools, not `uv`-managed):

- `adb`
- `scrcpy`
- Python 3.11–3.13 (required by the `mobilerun` package)

## Setup

This repo is `uv`-managed end to end: no bare `pip`/`python3` — every install and every script/test run goes through `uv`.

```bash
uv sync --extra dev --extra tracing --extra hf
```

- `dev` — `pytest`, for `make test`
- `tracing` — `arize-phoenix`, only needed for `--tracing` (see [docs/advanced-features.md](docs/advanced-features.md))
- `hf` — `huggingface_hub`, only needed for pushing dataset exports to Hugging Face

Then set up your API keys - copy the template and fill in your own values:

```bash
cp .env.example .env
```

```dotenv
# .env
OPENAI_API_KEY=sk-...      # only needed for the ask_user tool (Hard/ASK USER tasks)
OPENROUTER_API_KEY=...     # only needed if using OpenRouter instead of a local model host
HF_TOKEN=hf_...            # only needed for pushing dataset exports to Hugging Face
```

`.env` is gitignored and loaded automatically by both entrypoints (`dailybench_runner.py`/`dailybench_tasks.py`) via `python-dotenv` — no `export`, no `--env-file`, nothing else to configure. Leave any line blank if you don't need that feature yet; each one is independently optional (see the comments in `.env.example`).

## Tracing (Phoenix)

[Arize Phoenix](https://github.com/Arize-ai/phoenix) captures every LLM call, tool execution, and agent step as OpenTelemetry traces — essential for debugging runs, comparing model behavior, and auditing token usage. The `mobilerun` SDK auto-instruments traces when it detects a Phoenix server running locally.

### Start the Phoenix server

```bash
uv run phoenix serve --port 6006
```

This must be running **before** you start any benchmark run. The server's web UI will be at [http://localhost:6006](http://localhost:6006).

> **Note:** Phoenix stores its data in `~/.phoenix/phoenix.db` by default (a SQLite database). Traces accumulate across runs — you can query them directly with `sqlite3` or use the Phoenix UI to explore span trees, token counts, and latency.

### How traces flow

1. `phoenix serve` starts a gRPC (port 4317) and HTTP (port 6006/v1/traces) collector
2. `dailybench_runner.py` / `dailybench_tasks.py` set `PHOENIX_HOST=localhost` and `PHOENIX_PORT=4317` automatically when they detect the server — no `--tracing` flag needed
3. The `mobilerun` SDK sends every step (LLM chat, tool call, app launch, etc.) as spans to Phoenix
4. View the full trace tree at [http://localhost:6006](http://localhost:6006)

### Cost tracking (OpenRouter pricing)

Phoenix prices LLM spans by matching `llm.model_name` against a built-in model catalog (OpenAI/Anthropic/Gemini/…). OpenRouter slugs like `qwen/qwen3.6-plus` aren't in that catalog, so their cost shows as **$0.00** even though token counts are recorded. Register real OpenRouter pricing so new spans get costed:

```bash
uv run scripts/register_openrouter_pricing.py --model qwen/qwen3.6-plus
```

This fetches live per-token prices from OpenRouter's model API and upserts them into `~/.phoenix/phoenix.db` as user-defined models; Phoenix's cost daemon picks them up within ~5 seconds. Options:

- `--all` — register every model in OpenRouter's catalog
- `--model A --model B` — register specific slugs (repeatable)
- `--prompt-price-per-m 0.15 --completion-price-per-m 0.60` — set prices manually (USD per 1M tokens) without calling the API

Existing spans are not retroactively repriced — run the script once, and new spans for those models carry real cost.

### Querying traces without the UI

The Phoenix database is a standard SQLite file. Copy it before querying to avoid locks:

```bash
cp ~/.phoenix/phoenix.db /tmp/phoenix_copy.db
sqlite3 /tmp/phoenix_copy.db "
SELECT p.name as project,
       COUNT(DISTINCT t.id) as traces,
       COUNT(s.id) as spans,
       SUM(s.llm_token_count_prompt + s.llm_token_count_completion) as total_tokens
FROM projects p
JOIN traces t ON t.project_rowid = p.id
LEFT JOIN spans s ON s.trace_rowid = t.id
GROUP BY p.name;
"
```

The main tables are `traces`, `spans`, `projects`, and `span_annotations`. See [docs/advanced-features.md](docs/advanced-features.md) for more tracing configuration.

## Quick start

```bash
cd /Users/yuvrajsingh9886/Desktop/DrainBench300
export DAILYBENCH_SERIAL=172.24.2.66:5555
export LLM_UPSTREAM=http://100.75.134.64:8081/v1  # mini2 over Tailscale; LAN IP drifts
export MODEL='bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF:Q4_K_M'
```

Prefer a hosted model over running your own? Point `LLM_UPSTREAM`/`MODEL` at [OpenRouter](https://openrouter.ai) instead of a local host — no model server to manage:

```bash
export LLM_UPSTREAM=https://openrouter.ai/api
export MODEL='qwen/qwen3.6-plus'
```

This needs `OPENROUTER_API_KEY` set in `.env`. See [docs/advanced-features.md](docs/advanced-features.md) for the full setup.

Confirm the phone and model server are reachable:

```bash
adb devices -l
curl -s "$LLM_UPSTREAM/models"
```

Then run the pre-flight check before any real benchmark run (or after changing phones/model hosts):

```bash
./scripts/smoke_test.sh
```

It checks, in order: local prerequisites (`adb`/`curl`/`uv`/the `mobilerun` SDK import), the LLM server (`GET /models` + a real chat completion, auto-selecting the first listed model if `--model` isn't given), wired ADB + a device health check on a USB device, wireless ADB + the same check over TCP/IP (bootstrapping with `adb tcpip`/`adb connect` from a USB device if no wireless serial is given), and finally one real one-step agent run through `dailybench_runner.py` itself. Every target is a flag or env var — nothing is hardcoded to one phone or model host. Naming exactly one of `--usb-serial`/`--wireless-serial` automatically skips the other transport's check:

```bash
./scripts/smoke_test.sh --llm-url http://192.168.1.50:8080/v1 --model my-model
./scripts/smoke_test.sh --skip-llm --skip-agent-run --wireless-serial 192.168.1.23:5555
./scripts/smoke_test.sh --help   # full flag/env var reference
```

The device health check itself is pure SDK: [scripts/device_health_check.py](scripts/device_health_check.py) connects with `mobilerun.AndroidDriver` and exercises `get_date()`/`screenshot()` for real, mirroring [docs.mobilerun.ai/framework/sdk/adb-tools](https://docs.mobilerun.ai/framework/sdk/adb-tools).

### Known-good target (last verified working configuration)

- phone: OnePlus `CPH2423`, Android `15`, SoC `MT6895`
- model host: `mini2` at `http://100.75.134.64:8081/v1`
- model: `bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF:Q4_K_M`

## Wireless ADB

Connect once over USB, then run:

```bash
adb devices -l
PHONE_IP=$(adb shell "ip -f inet addr show wlan0 | sed -n 's/.*inet \\([0-9.]*\\)\\/.*/\\1/p' | head -1" | tr -d '\r')
adb tcpip 5555
adb connect ${PHONE_IP}:5555
adb devices -l
export DAILYBENCH_SERIAL="${PHONE_IP}:5555"
```

Use wireless ADB for real battery / thermal runs so the USB cable does not skew results.

## Running a benchmark

List a task slice from the dataset:

```bash
uv run dailybench_tasks.py --bucket easy --app gmail --list
```

Dry-run it first to see the exact commands that would execute:

```bash
uv run dailybench_tasks.py \
  --bucket easy --app gmail \
  --skip-unresolved \
  --serial "$DAILYBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL" \
  --dry-run
```

Then run it for real (drop `--dry-run`):

```bash
uv run dailybench_tasks.py \
  --bucket easy --app gmail \
  --skip-unresolved \
  --serial "$DAILYBENCH_SERIAL" \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --model "$MODEL"
```

Or run a single one-off task with full harness artifacts:

```bash
uv run dailybench_runner.py \
  --serial "$DAILYBENCH_SERIAL" \
  --label gmail-unread-count \
  --sample-interval 0.1 \
  --llm-upstream-base "$LLM_UPSTREAM" \
  --llm-proxy-port 8090 \
  --model "$MODEL" \
  --temperature 0 \
  --steps 50 \
  --goal "Check how many unread emails are in the inbox"
```

All runs land under `runs/<date-time>/<label>/` automatically — no need to specify an output directory.

Stop interrupted runs:

```bash
pkill -f "dailybench_tasks.py" || true
pkill -f "dailybench_runner.py" || true
pkill -f "scripts/openai_proxy_logger.py" || true
pkill -f "scrcpy" || true
```

Full flag reference for both entry points, including the app-reset fairness behavior, repeats caveat, and step-budget policy: [docs/cli-reference.md](docs/cli-reference.md).

## Task dataset

Tasks live in [benchmarks/dailyBench-600/tasks.md](benchmarks/dailyBench-600/tasks.md) — the active source (`docs/tasks.md` is an older dataset, no longer exported by default). After editing it, re-export:

```bash
uv run scripts/export_tasks_dataset.py
```

This writes `benchmarks/dailyBench-600/DailyBench_730_v4.json` and `benchmarks/dailyBench-600/DailyBench_730_v4.jsonl`. The JSONL file is the easiest artifact to push to Hugging Face datasets (`uv sync --extra hf` first).

## Run artifacts

Run folders are grouped under `runs/<date-time>/...` automatically, and contain phone/model metrics, logs, and the task's final result. Full contents and metric definitions: [docs/run-artifacts.md](docs/run-artifacts.md).

## Repo layout

- [dailybench_runner.py](dailybench_runner.py): thin CLI wrapper
- [dailybench_tasks.py](dailybench_tasks.py): dataset-backed segmented runner
- [.env.example](.env.example): API key template - copy to `.env` (gitignored) and fill in your own keys
- [src/DailyBench](src/DailyBench): harness package
- [pyproject.toml](pyproject.toml): package metadata
- [Makefile](Makefile): common test commands
- [scripts/openai_proxy_logger.py](scripts/openai_proxy_logger.py): per-run proxy/logger
- [scripts/export_tasks_dataset.py](scripts/export_tasks_dataset.py): markdown-to-dataset exporter
- [scripts/smoke_test.sh](scripts/smoke_test.sh): pre-flight check for the LLM server, wired/wireless ADB + mobilerun, and one real end-to-end task
- [scripts/device_health_check.py](scripts/device_health_check.py): SDK-only device health check used by `smoke_test.sh`
- [benchmarks/dailyBench-600](benchmarks/dailyBench-600): the active task schedule, public sample, and exported datasets
- [benchmarks/droidrun300](benchmarks/droidrun300): benchmark content pointers
- [docs](docs): CLI reference, advanced features, run artifacts, methodology, and task authoring notes
- [reports](reports): benchmark reports and notes
- [tests](tests): pytest coverage for CLI, parsing, helpers, and process wiring
- [runs](runs): run artifacts

## Testing

Run `uv sync --extra dev` once first (or `make sync` for every extra). All of these use the `.venv` uv manages:

```bash
make test
make test-fast
make test-cli
./scripts/run_tests.sh
```

## Further documentation

- [docs/cli-reference.md](docs/cli-reference.md) — full flag tables, app-reset fairness, repeats caveat, step-budget policy
- [docs/advanced-features.md](docs/advanced-features.md) — starting the mini2 model server, tracing, trajectory recording
- [docs/run-artifacts.md](docs/run-artifacts.md) — run folder contents and metric definitions
- [docs/benchmark-spec.md](docs/benchmark-spec.md), [docs/evaluation-policy.md](docs/evaluation-policy.md), [docs/task-authoring.md](docs/task-authoring.md), [docs/leaderboard-format.md](docs/leaderboard-format.md)
- [reports/failures.md](reports/failures.md), [reports/droidrun300-benchmark.md](reports/droidrun300-benchmark.md), [reports/trace.md](reports/trace.md)
