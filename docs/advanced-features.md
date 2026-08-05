# Advanced features

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
curl -s http://100.75.134.64:8081/v1/models
```

The best-tested prompt batch for this workload was `-b 2048 -ub 2048`.

## Or use a hosted model (OpenRouter)

No model server to run yourself — point the harness at [OpenRouter](https://openrouter.ai) instead of a local host:

```bash
export LLM_UPSTREAM=https://openrouter.ai/api
export MODEL='qwen/qwen3.6-plus'
```

This needs `OPENROUTER_API_KEY` set in `.env` (see the README's Setup section) — the harness's `OpenAILike` client sends it as the request's `Authorization: Bearer` header, and the local proxy (`scripts/openai_proxy_logger.py`) forwards that header straight through to OpenRouter. `cli.py` picks `OPENROUTER_API_KEY` over `OPENAI_API_KEY` for this specifically, since `OPENAI_API_KEY` is reserved for the unrelated `ask_user` tool's real OpenAI calls.

OpenRouter is supported by mobilerun natively — see [mobilerun's CLI docs](https://docs.mobilerun.ai/framework/guides/cli) for the `--provider OpenRouter` option, or use the `OpenAILike` path above to go through the harness's own proxy/logger.

## Tracing (Arize Phoenix) and trajectory recording

Both are mobilerun SDK features, exposed as harness flags on `dailybench_tasks.py` so they're set consistently across a whole batch and recorded per-run for reproducibility.

**Tracing** streams LLM calls, agent steps, and tool invocations to a local [Arize Phoenix](https://docs.mobilerun.ai/framework/features/tracing) dashboard. It needs a Phoenix server running before you start a batch:

```bash
uv sync --extra tracing   # installs arize-phoenix into .venv (skip if already synced)
uv run phoenix serve      # serves the dashboard at http://localhost:6006
```

Then enable it on the batch runner:

```bash
uv run dailybench_tasks.py \
  --bucket easy --app gmail --skip-unresolved \
  --serial "$DAILYBENCH_SERIAL" --llm-upstream-base "$LLM_UPSTREAM" --model "$MODEL" \
  --tracing \
  --phoenix-url http://localhost:6006 \
  --phoenix-project DailyBench
```

`--phoenix-url`/`--phoenix-project` set the `phoenix_url`/`phoenix_project_name` env vars mobilerun reads (lowercase, per its docs) inside each `dailybench_runner.py` process; omit them to use mobilerun's own defaults (`http://0.0.0.0:6006`, no project grouping).

**OpenRouter cost:** Phoenix's bundled model catalog doesn't include OpenRouter slugs, so their spans show $0.00 cost. Register real pricing once with [scripts/register_openrouter_pricing.py](../scripts/register_openrouter_pricing.py) — e.g. `uv run scripts/register_openrouter_pricing.py --model qwen/qwen3.6-plus` (see the README's Tracing section for all options). New spans for those models then carry real cost.

**Trajectory recording** saves local screenshots + UI-state artifacts per step or per atomic action — independent of tracing, and it stays entirely on disk (nothing leaves your machine):

```bash
--save-trajectory step    # one artifact per agent planning step
--save-trajectory action  # one artifact per atomic action (tap/swipe/type/...) — more detail, more disk
--save-trajectory none    # default; no trajectory files
```

The harness points mobilerun's `LoggingConfig.trajectory_path` explicitly at that task's own run folder, so trajectory output lands inside `runs/<date-time>/.../<label>/trajectories/` alongside `meta.json`/`run_metrics.json`, not scattered at the repo root.

## Custom tools (`src/DailyBench/custom_tools.py`)

Registered via mobilerun's own `MobileAgent(custom_tools={...})` kwarg ([docs.mobilerun.ai](https://docs.mobilerun.ai) custom-tools guide) — a `{name: {function, parameters, description}}` dict merged into the agent's tool registry alongside its built-in tools. Every `dailybench_runner.py` run registers three:

- **`get_current_datetime`** — the device's real current date/time via `adb shell date` (reuses mobilerun's own `AndroidDriver.get_date()`, which exists at the driver level but was never exposed as a callable tool — see `reports/qwen35-4b-public-wired-run-analysis.md` finding A3). Call this for any "today"/"this week"/"right now" task instead of guessing from on-screen content.
- **`get_current_location`** — the device's last known fix via `adb shell dumpsys location`, regex-parsed for lat/lon. Android itself redacts this to ~2-decimal precision, which is the right level of coarseness for these tasks; no reverse-geocoding is attempted.
- **`ask_user`** — a real OpenAI chat completion playing the human user, for the Hard battery's `ASK USER` tasks. Its system prompt is adapted from the AndroidWorld/MobileAgent-family "simulated user" template: the task goal (read live from `ctx.shared_state.instruction`), the run's `--ask-user-context` (the one deliberately-omitted fact the task needs — see the dataset's `note` field for what each Hard task is missing), and the real current date/time. It's instructed to answer only from that fact and refuse anything else — never invent information. Configure it with `--ask-user-context "..."` per task, `--ask-user-model` (default `gpt-5.4-mini`), and `OPENAI_API_KEY` in the environment; `--ask-user-base-url` exists purely for pointing it at a local stand-in server in tests. Tasks that never call it (the overwhelming majority) incur no API cost — the OpenAI client is constructed lazily, only on first actual call.

Both device-read tools are read-only and side-effect-free; `ask_user` makes a real network call each time it's invoked, so a misbehaving agent that loops on it will burn real OpenAI usage — the `--steps` budget is still the backstop.

Since `ask_user` is a genuine `async def` that `await`s a real network call before returning, the FastAgent loop's own `await ToolRegistry.execute(...)` genuinely suspends on it — the agent is paused mid-run until the (simulated) user's answer comes back, exactly like a blocking `input()` would pause it, just without needing a live human to type into a terminal for every one of the 39+11 tasks in an unattended batch run. A real human-in-the-loop variant (blocking on stdin, a queue, a web callback) is a straightforward swap of the function body if that's ever wanted — the pause behavior comes from `async`/`await`, not from the specific I/O source.

### Where the answer comes from (`ask_user_fact`)

`relevant_information` (the one fact each `ASK USER` task is deliberately missing — see the dataset's `note` field for what's missing) is authored once per source markdown as a plain `{task_id: fact}` mapping. Consumers derive the file from the source instead of hardcoding a path (`task_dataset.ask_user_facts_path`): `--source tasks.md` uses `benchmarks/dailyBench-600/ask_user_facts_730.json`, `--source public.md` uses `benchmarks/dailyBench-600/ask_user_facts.json`:

```json
{
  "hard__gmail-contacts__002": "The report your manager is asking about is named 'Q2_Budget.xlsx'. Your manager's name is Priya Sharma, email b123153@iiit-bh.ac.in.",
  "hard__calendar__003": "The dentist appointment is on 2026-08-05 at 3:30 PM, at Dr. Mehta's Dental Clinic."
}
```

`scripts/export_public_dataset.py` merges the public facts file (`ask_user_facts.json`, via `ask_user_facts_path("public.md")`) straight into the published dataset as each task's `ask_user_fact` column (`merge_ask_user_facts`) - public.md is explicitly "not the eval set, a structural preview only," so publishing the answer alongside it doesn't compromise anything real. **This is deliberately different from what the real private benchmark does**: `tasks.md`'s facts live in `ask_user_facts_730.json` and are kept out of the published `DailyBench_730_v4` dataset (its rows have no `ask_user_fact`; the batch runner reads the sidecar at run time), since leaking the real eval's answers would let a submitter memorize them instead of the agent genuinely asking.

`dailybench_tasks.py` (the batch runner) reads each task's own `ask_user_fact` field first and, for every task whose `ahi == "ASK USER"`, automatically forwards it as that task's `--ask-user-context` — no manual typing per task. If a dataset row has no `ask_user_fact` (as the future private benchmark's published rows deliberately won't), it falls back to a local `--ask-user-facts` sidecar file instead. A task with neither still runs (empty context — the simulated user just has nothing to reveal and will say so) but prints a warning. Running `dailybench_runner.py` directly (a single task, outside the batch runner) still takes `--ask-user-context` as a plain flag with no lookup, for quick manual testing.
