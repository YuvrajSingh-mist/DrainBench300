# Run artifacts

## Run folders are grouped by date-time batch

The harness automatically inserts a date-time stamp as the top-level segment right under `runs/`. Runs always land at `runs/<date-time>/<label>/` — no need to specify an output directory, and no flag to opt out. This keeps every batch invocation in its own top-level folder, so re-running the same command seconds later doesn't mix with the previous batch's run folders.

## What each run folder contains

Core artifacts:

- `meta.json`
- `preflight.json`
- `postflight.json`
- `samples.ndjson`
- `run_metrics.json`
- `agent.log.txt`
- `output.txt`
- `output.json`

Optional artifacts when enabled:

- `screen.mp4`
- `screenrecord.stdout.txt`
- `screenrecord.stderr.txt`
- `llm_proxy_metrics.jsonl`
- `llm_proxy.stdout.txt`
- `llm_proxy.stderr.txt`
- `llm_metrics.json`
- `ask_user_metrics.jsonl` (when the task's `ask_user` tool is called)
- `trajectories/` (when `--save-trajectory` is `step` or `action`)

`output.txt`/`output.json` store the final task-facing result straight from mobilerun's `ResultEvent` (`success`, `reason`, `steps`) — no scraping terminal text for it. `agent.log.txt` captures mobilerun's own debug logging for that run.

## Metric meanings

- `elapsed_seconds`: full end-to-end wall time
- `llm_prompt_tokens_sum`: total input tokens across all agent turns
- `llm_completion_tokens_sum`: total output tokens across all agent turns
- `llm_total_tokens_sum`: total prompt + completion tokens across the run

Per-call detail (token usage, timing, finish reason per agent turn) is in `llm_proxy_metrics.jsonl`. `run_metrics.json` keeps only the run-level aggregates.
