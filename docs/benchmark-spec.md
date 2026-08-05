# Benchmark Specification

DailyBench300 is a mobile-agent benchmark focused on Droidrun / Mobilerun style execution on a real Android device.

## Scope

- platform: Android phone
- control mode: primarily no-vision, accessibility/state-driven
- model serving: external OpenAI-compatible endpoint
- measurement:
  - end-to-end task latency
  - phone battery and thermal data
  - model token data

## Benchmark unit

One benchmark unit is one task run through the harness into one timestamped run folder under [runs](/Users/yuvrajsingh9886/Desktop/DrainBench300/runs).

## Canonical task families

- easy
- medium
- hard-deterministic
- open-ended

The canonical runnable task list lives in [benchmarks/dailyBench-600/tasks_530.md](../benchmarks/dailyBench-600/tasks_530.md) — the deterministic 530-task subset (229 easy / 229 medium / 72 hard = 36 ASK USER / 36 DETERMINISTIC); the full 730-corpus superset is `benchmarks/dailyBench-600/tasks.md`.

## Required run artifacts

Each valid run should contain:

- `meta.json`
- `preflight.json`
- `postflight.json`
- `samples.ndjson`
- `run_metrics.json`
- `agent.log.txt`
- `output.txt`
- `output.json`

Optional artifacts:

- `screen.mp4`
- `llm_proxy_metrics.jsonl`
- `llm_metrics.json`

## Required summary metrics

- `elapsed_seconds`
- `command_exit_code`
- `llm_prompt_tokens_sum`
- `llm_completion_tokens_sum`
- `llm_total_tokens_sum`

## Action-budget policy

- all benchmark tasks use the same default `50`-step action budget
- this fixed cap is part of the benchmark definition and is meant to preserve fairness across buckets

## Evaluation philosophy

- deterministic tasks should be scored by explicit success/failure evidence
- open-ended tasks should be scored separately with rubric-based evaluation
- benchmark maintenance must preserve comparability across runs and dates
