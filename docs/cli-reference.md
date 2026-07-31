# CLI reference

Full flag tables for the two harness entry points. See [README.md](../README.md) for the common quick-start commands.

## `dailybench_runner.py` — single-run harness

| Flag | Default | Meaning |
|---|---|---|
| `--serial` | `$DAILYBENCH_SERIAL` | ADB serial (USB device ID or `ip:port` for wireless) |
| `--label` | *(required)* | Run label; used directly as the run folder name (e.g. `easy-gmail-001`) |
| `--sample-interval` | `0.1` | Seconds between battery/thermal samples (0.1s = every 100ms) |
| `--screen-bit-rate` | `8M` | `scrcpy` recording bit rate |
| `--screen-size` | *(none)* | `scrcpy` `--max-size` cap, if set |
| `--no-screen-record` | off | Skip `scrcpy` screen recording entirely |
| `--llm-upstream-base` | *(none)* | Real model server base URL; when set, the harness starts a local logging proxy in front of it |
| `--llm-proxy-port` | `8090` | Preferred local proxy port (falls back to a free port if taken) |
| `--goal` | *(required)* | The task prompt/instruction for the agent |
| `--model` | `$MODEL` | Model name passed to the `MobileAgent`'s LLM |
| `--temperature` | `0.0` | Sampling temperature |
| `--top-p` | `0.95` | Nucleus sampling top-p, forwarded to the LLM request |
| `--seed` | `42` | Fixed sampling seed, forwarded to the LLM request, for run-to-run reproducibility |
| `--steps` | `50` | Step budget (`AgentConfig.max_steps`) |
| `--vision` | off | Enable vision (screenshots) for the agent; off by default for this harness |
| `--reasoning` | off | Use mobilerun's manager/executor planning workflow instead of the fast-agent loop |
| `--no-debug` | off | Disable mobilerun's verbose debug logging (on by default) |
| `--tracing` | off | Enable Arize Phoenix tracing (see [advanced-features.md](advanced-features.md)) |
| `--phoenix-url` | *(none)* | Phoenix collector endpoint; sets the `phoenix_url` env var mobilerun reads |
| `--phoenix-project` | *(none)* | Phoenix project name; sets the `phoenix_project_name` env var |
| `--save-trajectory` | `none` | Local trajectory recording level: `none`, `step`, or `action` |
| `--no-app-reset` | off | Skip the post-run fairness reset — leaves the app in whatever state the task ended in |
| `--task-timeout` | `1000` | Wall-clock seconds before mobilerun's own `MobileAgent(timeout=...)` aborts the task |
| `--ask-user-context` | *(empty)* | The hidden ground-truth fact for this task's `ask_user` tool (Hard/`ASK USER` tasks only — the dataset's `note` field); empty means the simulated user has nothing to reveal |
| `--ask-user-model` | `gpt-5.4-mini` | OpenAI model used to play the simulated user for `ask_user` |
| `--ask-user-base-url` | *(OpenAI's default)* | Override the OpenAI API base URL for `ask_user` (e.g. to point at a local stand-in) |

## `dailybench_tasks.py` — dataset-backed batch runner

| Flag | Default | Meaning |
|---|---|---|
| `--dataset` | `benchmarks/dailyBench-600/DailyBench_730_v4.json` | Which exported task dataset to read |
| `--bucket` | *(none)* | Filter to `easy`/`medium`/`hard`/`hard-deterministic`/`open-ended` (`hard` is the current dialect's shuffled DETERMINISTIC+ASK USER battery; `hard-deterministic`/`open-ended` are the older dialect's split buckets) |
| `--app` | *(none)* | Filter to one app slug (e.g. `gmail`) |
| `--task-id` | `[]` | Repeatable; run only these specific task IDs |
| `--var` | `[]` | Repeatable `key=value`; fills in `[placeholder]` values in task prompts |
| `--limit` | *(none)* | Cap the number of selected tasks |
| `--all` | off | Select every task in the dataset (required if no other selector is given) |
| `--list` | off | Print the selected tasks and exit, without running anything |
| `--dry-run` | off | Print the exact commands that would run, without executing them |
| `--skip-unresolved` | off | Skip (rather than error on) tasks whose placeholders have no `--var` value |
| `--serial` | `$DAILYBENCH_SERIAL` | ADB serial, forwarded to every task run |
| `--sample-interval` | `0.1` | Forwarded to each task run |
| `--llm-upstream-base` | `$LLM_UPSTREAM` | Forwarded to each task run |
| `--llm-proxy-port-base` | `8090` | First proxy port; each task/repeat invocation gets `base + running index` |
| `--model` | `$MODEL` | Model name, forwarded as `dailybench_runner.py --model` |
| `--temperature` | `0.0` | Sampling temperature |
| `--steps` | `50` | Fixed step budget for every task, regardless of bucket (see [Step-budget policy](#step-budget-policy)) |
| `--repeats` | `1` | Run each selected task this many times; opt-in since runs are already deterministic at temperature 0 (see caveat below) |
| `--no-screen-record` | off | Skip `scrcpy` for every task in the batch |
| `--vision` | off | Enable vision (screenshots) for the agent; off by default for this harness |
| `--reasoning` | off | Use mobilerun's manager/executor planning workflow instead of the fast-agent loop |
| `--no-debug` | off | Disable mobilerun's verbose debug logging (on by default) |
| `--tracing` | off | Enable Arize Phoenix tracing (needs `phoenix serve` running first) |
| `--phoenix-url` | *(none)* | Phoenix collector endpoint; sets the `phoenix_url` env var |
| `--phoenix-project` | *(none)* | Phoenix project name; sets the `phoenix_project_name` env var |
| `--save-trajectory` | `none` | Local trajectory recording level: `none`, `step`, or `action` |
| `--no-app-reset` | off | Skip the post-run fairness reset for every task in the batch (see below) |
| `--cooldown-seconds` | `10.0` | Fixed pause between tasks so the device doesn't run continuously into thermal/load territory; `0` disables it |
| `--ask-user-facts` | `benchmarks/dailyBench-600/ask_user_facts.json` | Fallback per-`task_id` facts for Hard/`ASK USER` tasks, used only when a task's own dataset row has no `ask_user_fact` (see [Custom tools](advanced-features.md#custom-tools-srcdailybenchcustom_toolspy)); missing file means no facts configured (fine for DETERMINISTIC-only selections) |
| `--ask-user-model` | `gpt-5.4-mini` | Forwarded to every task run's `ask_user` tool |
| `--ask-user-base-url` | *(OpenAI's default)* | Forwarded to every task run's `ask_user` tool |

### App-reset fairness

After each task finishes, the harness force-stops whatever app ended up in the foreground (`am force-stop`) and returns to the home screen, before writing the run's final artifacts. Without this, a task can silently inherit UI/navigation state left behind by the previous task's agent (mid-scroll in Gmail, a half-typed compose draft, a different app entirely) instead of starting clean. It's on by default; the launcher, systemui, and mobilerun's own Portal app are never touched. The stopped package (or `null` if nothing eligible was in the foreground) is recorded in `meta.json` as `app_reset_stopped_package`. A reset failure is logged but never fails the run.

### Repeats caveat

`--repeats` re-runs the identical task back-to-back against a live, stateful mailbox/app. It's fully valid for hardware metrics (thermals, battery), but for destructive or state-toggling tasks (delete, archive, mark read/unread, send/reply), reps after the first face a different starting state than rep 1 — treat repeat-based success rates on those tasks with caution.

### Step-budget policy

- Default action budget: `50` steps for every task.
- This is intentionally fixed across easy, medium, hard-deterministic, and open-ended buckets.
- The benchmark uses one global action budget to avoid bucket-specific budget advantages.
