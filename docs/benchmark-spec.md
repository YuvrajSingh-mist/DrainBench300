# Benchmark Specification

DrainBench300 is a mobile-agent benchmark focused on Droidrun / Mobilerun style execution on a real Android device.

## Scope

- platform: Android phone
- control mode: primarily no-vision, accessibility/state-driven
- model serving: external OpenAI-compatible endpoint
- measurement:
  - end-to-end task latency
  - phone battery and thermal data
  - model token and timing data

## Benchmark unit

One benchmark unit is one task run through the harness into one timestamped run folder under [runs](/Users/yuvrajsingh9886/Desktop/DrainBench300/runs).

## Canonical task families

- easy
- medium
- hard-deterministic
- open-ended

The current canonical task list lives in [docs/tasks.md](/Users/yuvrajsingh9886/Desktop/DrainBench300/docs/tasks.md).

## Required run artifacts

Each valid run should contain:

- `meta.json`
- `preflight.json`
- `postflight.json`
- `samples.ndjson`
- `summary.json`
- `command.stdout.txt`
- `command.stderr.txt`
- `output.txt`

Optional artifacts:

- `screen.mp4`
- `llm_proxy_metrics.jsonl`
- `llm_metrics.json`

## Required summary metrics

- `elapsed_seconds`
- `command_exit_code`
- `llm_total_tokens_sum`
- `llm_ttft_ms`
- `llm_prefill_tokens_per_second`
- `llm_decode_tokens_per_second`

## Action-budget policy

- all benchmark tasks use the same default `50`-step action budget
- this fixed cap is part of the benchmark definition and is meant to preserve fairness across buckets

## Evaluation philosophy

- deterministic tasks should be scored by explicit success/failure evidence
- open-ended tasks should be scored separately with rubric-based evaluation
- benchmark maintenance must preserve comparability across runs and dates
