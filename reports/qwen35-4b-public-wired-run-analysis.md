# Qwen3.5-4B Public Dataset — Wired Batch Analysis

Date: 2026-07-29
Run: `runs/2026-07-29/public/usb/` — 44 public-sample tasks, wired ADB, `bartowski/Qwen_Qwen3.5-4B-GGUF:Q4_K_M` on mini2, DRY sampling on (`--dry-multiplier 0.8 --dry-base 1.75 --dry-allowed-length 2 --dry-penalty-last-n -1`), `--save-trajectory action`, Phoenix tracing on, `--steps 50`, no `--vision`.

**Result: 13 success / 31 failure** (one task, `medium-chrome-001` at 11:25, has no `output.json` — its process was interrupted by a manual restart mid-session, not a real task failure; excluded from the tally).

This is a root-cause breakdown of every failure, attributed to one of three layers — **LLM** (the model's own generation/judgment), **mobilerun** (the vendored SDK we call into), or **harness** (this repo's own code/policy) — plus a separate bucket for dataset/task-authoring gaps that aren't code bugs at all. Proposed fixes are given per category, ordered by how confident I am they'd actually help.

---

## A. LLM-level issues (the model itself)

### A1. Tool-call XML/JSON-mixing malformation — **confirmed model bug, not fixed by DRY**

Pattern: the model occasionally emits a `<parameter>` tag whose value trails off into JSON syntax instead of a proper close, e.g.:

```
<invoke name="type">
<parameter name="text">wireless earbuds", "clear": true}
</invoke>
```

instead of the correct:

```
<invoke name="type">
<parameter name="text">wireless earbuds</parameter>
<parameter name="clear">true</parameter>
</invoke>
```

Seen on: `easy-chrome-001` (recovered after 1 retry), `medium-chrome-001` (never recovered, hit the 1000s cap), `medium-calculator-001` (recovered after 2 retries, task ultimately succeeded).

This is the same *family* of bug as the earlier `</message>` vs `</parameter>` echo we found with Qwen3-4B-Instruct, but a different specific trigger (mixing in a JSON-style `"clear": true}` fragment rather than echoing a parameter's own name). **DRY sampling did not prevent it**, because the malformed fragment repeats verbatim while the *surrounding reasoning sentence* varies each retry ("I'll use the search bar..." vs "The search bar is focused...") — not enough exact token overlap to trigger DRY's repeat penalty.

Root cause: **LLM**. mobilerun's parser is behaving exactly as documented (strict `</parameter>` matching); loosening it was tried and explicitly reverted earlier this session as the wrong fix — it would silently score around a genuine model limitation instead of measuring it.

**Proposed fix:** none at the harness/mobilerun level (that would be re-litigating the reverted patch). At the model level: this is worth reporting as a concrete, reproducible weak point of Qwen3.5-4B specifically on the `type` tool's optional `clear` parameter. If a future run wants to avoid this specific trigger, the `type` tool could be simplified to never take a second parameter (always clear-and-type, or add a separate `clear_field` tool) — that's a mobilerun tool-schema design question, out of scope for this repo to patch.

### A2. Negative/zero-result miscalibrated as `success: false` — **confirmed, systemic, 5 occurrences**

The model correctly finds a true negative answer, then calls `complete(success=false, ...)` as if a "no/zero" finding were itself a task failure, rather than a validly completed check.

| Task | Real finding | Reported |
|---|---|---|
| `easy-clock-001` | 0 of 6 alarms active | `success: false` |
| `easy-calendar-001` | No events scheduled today | `success: false` |
| `easy-gallery-001` | No GPS data on most recent photo | `success: false` |
| `easy-phone-001` | No calls this week | `success: false` |
| `easy-settings-001` | Bluetooth is off | `success: false` |

All five are genuinely correct answers to "check whether X" questions where X happens to be false/absent. Root cause: **LLM** — a real judgment/calibration gap about what "success" means for a check-type task.

**Fix implemented and verified 2026-07-30.** mobilerun's `MobileAgent` accepts a `prompts: dict[str, str]` override (public API — `PromptResolver` looks up `prompts["fast_agent_system"]` before falling back to its own bundled template; still rendered through the same Jinja2 context, so no other behavior changes). Copied mobilerun's real default `system.jinja2` into this repo as `src/DailyBench/prompts/fast_agent_system.jinja2` (verified byte-identical except for the one addition below via `diff`), added one clarifying bullet under "Important Rules":

> **For check/verification tasks** ("check whether X", "is Y active", "how many Z exist", "does W have..."): correctly determining and reporting the answer is what makes the task successful. Call `complete` with `success=true` even when the answer itself is negative, false, zero, or "none found" — a negative or zero finding is a valid, successfully completed check, not a failure. Only use `success=false` when you genuinely could not determine the answer (e.g. the relevant screen/app was unreachable, or a real precondition was unmet) — not because the answer itself was "no."

and wired it into `cli.py`: `MobileAgent(goal=..., config=..., llms=llm, prompts={"fast_agent_system": FAST_AGENT_SYSTEM_PROMPT})`.

**Verified with a real before/after smoke test**, same phone, same model, temperature 0, re-running two of the exact five miscalibrated tasks above:
- `easy-settings-001` ("check whether Bluetooth is currently connected"): now `success: true`, reason unchanged — *"Bluetooth is OFF and not connected to any device."* (2 steps, same as before, only the success flag changed).
- `easy-clock-001` ("check how many alarms are currently active"): now `success: true`, reason unchanged — *"0 alarms are currently active - all 6 alarms in the list show 'Off' status."* (2 steps).

2/2 flipped correctly with no change in the underlying reasoning or the real answer. Tests updated (`tests/test_cli.py`'s two `MobileAgent` fakes needed a `prompts=None` parameter) and full suite passes (98 passed).

**Also worth keeping regardless of the prompt fix:** since this is still a probabilistic model behavior, not a guarantee, the harness/human-grading step (per `docs/evaluation-policy.md`'s "manual end-state check") still shouldn't take the agent's self-reported `success` at face value for check-type tasks — grade off the *reason* text and the actual device end-state. The prompt fix should reduce how often this matters, not eliminate the need for it.

### A3. Date/year misreading — **confirmed, 3 occurrences**

| Task | Cited | Real |
|---|---|---|
| `easy-files-001` | "My Photo .pdf dated Dec 15 **(2015)**" | Dec 15, **2025** |
| `easy-phone-001` | calls from "June 17, **2024**" / "January 2, **2024**" | June 17 / Jan 2, **2026** |
| `easy-messages-001` | "1 message from today **(Jun 24)**" | today is Jul 29; Jun 24 is over a month old |

**Update 2026-07-30 — investigated with the raw ground-truth data the model actually saw, not just its final answer.** This run had `--save-trajectory action`, which saves the exact UI-element list (`ui_states/*.json`) fed to the model at every step — so instead of guessing whether the source data was ambiguous, I pulled the literal text each of these three claims was based on. The three cases split into two genuinely different root causes:

**Case 1 — `easy-files-001`: a pure model transcription error, source data was correct.** `ui_states/0012.json` at the relevant step contains, verbatim: `"27.30 kB • Dec 15, 2025"` — the full, correct, unambiguous 4-digit year, right there in the model's own context. The model still generated "Dec 15, **1**" and separately appended "(**2015**)" in its response. There is nothing to fix upstream here — this is Qwen3.5-4B garbling a string it was handed intact. Root cause: **LLM**, plain and simple.

**Case 2 & 3 — `easy-phone-001` and `easy-messages-001`: the source data never had a year to begin with, and the agent has no way to ask what today's date actually is.** Checked the raw `ui_states` for both:
- Phone call log, verbatim: `"Emergency number, Main, outgoing call, June 17 at 18:07."` / `"Maa, Mobile, answered call, January 2 at 20:46..."` — **no year anywhere**, for any entry.
- Messages list, verbatim: `"Zepto"` / `"Jun 21"` / `"Jun 7"` — same, no year ever shown.

Both are honest reproductions of how these real Android apps render their lists — Phone and Messages simply don't print a year for entries (a common, real UI convention). So the model isn't misreading a number that's there; it's being asked to answer "is this today / this week" with a piece of information — the year, and even "what day is today" itself — that was never given to it anywhere. And it's not just guessing wrong once: across `easy-messages-001`'s own steps, it calls "today" three different things (Jun 11, then Jun 21, then attaches "2025" once and "2024" once) — pure confabulation, because there's no ground truth anchor anywhere in its context to check itself against.

I traced why: mobilerun's per-step context (`phone_state`, populated in `fast_agent.py`/`droid_agent.py` from `ui_state.phone_state`) only ever carries `packageName` and `currentApp` — never a date. And `AndroidDriver.get_date()` genuinely exists and works at the driver level (we used it directly in `scripts/device_health_check.py` and it's real, live device time) — but grepping mobilerun's `agent/tool_registry.py` for it turns up **nothing**: it's simply never registered as a callable action the agent can invoke. The capability exists in the SDK; it just isn't wired to the agent loop at all.

Root cause: **Case 1 is LLM. Cases 2-3 are mobilerun** (a real, specific, fixable gap — a working driver method that was never exposed as a tool or injected into per-step context), not a model reading-accuracy issue at all.

**Proposed fix:**
- Case 1: none available — genuine model limitation, track as a "citation accuracy" sub-metric if this benchmark ever wants one, independent of task pass/fail.
- Cases 2-3: this is worth reporting upstream to mobilerun directly — either register `get_date()` in `tool_registry.py` as a callable action, or (simpler, cheaper, no extra tool-call round-trip) inject the real current date/time into `phone_state` alongside `packageName`/`currentApp` on every step, the same way `mobilerun.AndroidDriver.get_date()` already can. Given how many of this benchmark's own tasks hinge on "today"/"this week"/"most recent" (the entire public sample alone has this in Gmail, Calendar, Clock, Phone, Messages, Files...), this single gap plausibly touches far more of the benchmark than just these 3 flagged instances — it's a systemic blind spot, not a one-off.

### A4. False "app not installed" claims — **confirmed, 2 occurrences**

| Task | Claim | Reality |
|---|---|---|
| `easy-notes-001` | "Notes app was not found... may not be installed" | `com.oneplus.note` is installed and working (verified earlier this session, and successfully used two tasks later in `medium-notes-001`) |
| `easy-chrome-002` | "Chrome is not installed on this device" (32 steps to reach this) | `com.android.chrome` is installed and was used successfully multiple times earlier in this same batch |

**Update 2026-07-30 — followed up, root cause isolated.** `open_app` is not a deterministic package lookup at all — it's `mobilerun.agent.oneflows.app_starter_workflow.AppStarter`, a **separate LLM call**: it fetches the real installed-app list via `driver.get_apps()`, builds a prompt listing every `"{label} (package: {package})"`, and asks the *same configured LLM* to return `{"package": "..."}` (or `null` if nothing matches) as freeform JSON. So a false "not installed" verdict is a second, independent point of LLM failure, not the main FastAgent's own reasoning.

Two things checked directly:
1. **`get_apps()` has a silent fallback that could explain this**: if mobilerun's own "Portal" companion app doesn't answer, `get_apps()` falls back to raw ADB package listing and — critically — sets `label = package_name` in that path (`{"package": "com.oneplus.note", "label": "com.oneplus.note"}` instead of `{"package": "com.oneplus.note", "label": "Notes"}`), logged only at **DEBUG** level. Asking an LLM to match "Notes" against a 60+ entry list of raw package strings is a much harder task than matching against clean labels.
2. **But this isn't what happened here**: Portal is confirmed live right now (`driver.portal_available == True`, all 67 real launchable apps returned with correct human-readable labels, e.g. `{'package': 'com.oneplus.note', 'label': 'Notes'}`), and grepping both failing tasks' full `agent.log.txt` for any mention of "portal" (which would show the DEBUG fallback line, since this harness runs with debug logging on by default) returns **nothing** — the fallback never fired in either failure.
3. **Reproduced the exact `AppStarter` prompt directly against the real LLM server, 5 times each for "Notes" and "Chrome", using the real current app list**: **10/10 correct** (`com.oneplus.note` / `com.android.chrome` every time, temperature 0).

Root cause: **LLM, but the specific matching sub-task tested clean** — most likely a transient inference-level blip at the exact moment (empty/malformed JSON response, or a dropped completion), consistent with the confirmed `openai.APITimeoutError`/`Empty response content` failures found elsewhere in this same ~8-hour run (§C3), rather than a systematic weakness in Qwen3.5-4B's app-matching ability. Not reproducible on demand.

**Proposed fix:** two independent, cheap wins now that the mechanism is understood:
1. **Promote the Portal-fallback log line from DEBUG to WARNING** (or otherwise surface it) inside mobilerun, since it silently degrades match quality and is currently invisible even with debug logging on — this is a mobilerun-side ask, not something to patch locally.
2. **Add the same "restart task once on an early transport-level LLM failure" policy proposed in §C3** — `AppStarter`'s own `acomplete_with_retries` already retries 3 times internally and still occasionally comes up empty under load; one harness-level restart for a task that dies this early (via `open_app`, step 1-2) is cheap insurance against exactly this class of transient blip.

---

## B. mobilerun-level issues (the vendored SDK)

### B1. Workflow hang inside `finalize`, not `execute_task` — **1 occurrence**

`medium-clock-001` hit the 1000s timeout with `Currently active steps: finalize` — meaning the actual task logic had already finished (or nearly finished) and the hang was in mobilerun's own post-task wrap-up phase (possibly a trace-export call or similar internal cleanup), not in agent reasoning.

Root cause: **mobilerun**. This is the clearest non-LLM, non-harness failure in the whole run.

**Proposed fix:** would need mobilerun's own source/issue tracker to diagnose further (not vendored code we should patch locally, per the standing decision earlier this session to not carry local patches to the SDK). Worth reporting upstream if mobilerun has an issue tracker, with this run's `agent.log.txt` as a reproduction.

---

## C. Harness-level issues (this repo's own code/policy)

### C1. Fixed 1000s task-level timeout is too tight for real task complexity on this hardware — **18 of 31 failures**

The large majority of failures (18/31) are the generic `mobilerun agent raised: Operation timed out after 1000.0 seconds. Currently active steps: execute_task` with **zero parse errors and varied, sensible actions in the log** (confirmed by checking action-repetition counts on a sample of them: `medium-chrome-001`, `medium-google-drive-001`, `medium-google-search-001`, `medium-gallery-001`, `medium-settings-001`, `medium-chrome-002`, `hard-deterministic-gmail-001`, `hard-deterministic-telegram-003`, `open-ended-telegram-002`). These aren't degenerate loops — they're genuinely multi-step, information-dense tasks (compare two web pages, navigate a shared-files list, search a chat history) that this 4B model, at ~25 decode tok/s on mini2, simply doesn't finish inside 1000 wall-clock seconds.

Root cause: **mobilerun default, never overridden by the harness** — `1000` is `MobileAgent.__init__`'s own `timeout: int = 1000` keyword default (`mobilerun/agent/droid/droid_agent.py`). It's a fully public, overridable constructor argument; `cli.py`'s `agent = MobileAgent(goal=args.goal, config=build_mobile_config(args, run_dir), llms=llm)` simply never passes one, so every run silently inherits mobilerun's default regardless of `--steps` or bucket tier.

**Proposed fix (highest-confidence, most impactful available fix — and now confirmed trivial to implement):** this is a one-line change, not new scaling logic to build from scratch: add a `--task-timeout` flag to `dailybench_runner.py` (default something larger than 1000, or scaled from `--steps`) and pass it straight through as `MobileAgent(..., timeout=args.task_timeout)`. Medium/hard tasks are, by the benchmark's own design (`docs/benchmark-spec.md`), 3+ atomic steps and inherently slower; a flat budget shared with 1-step easy tasks is the mismatch, and mobilerun already gives us the exact knob needed to fix it per-run.
- Separately worth doing regardless: treat "hit timeout with varied non-repeating actions" as a distinct outcome from "hit timeout while stuck in a loop" in `summary.json` — they mean very different things (task too slow vs. task broken) and are currently indistinguishable without manually reading the log, which is exactly what this analysis had to do by hand for every failure.

**Update 2026-07-30 — `medium-chrome-001` specifically has a deeper, LLM-level cause, not just "too slow."** Re-examined this one task's log directly: 28 steps in before the 1000s cutoff, 8 real `swipe` actions (genuine scrolling through both baggage-policy pages happened), but **zero `<add_memory>` uses in the entire run**. Section F below explains why that matters: the on-device accessibility tree only ever contains the current viewport, so a task that requires comparing content from two separately-scrolled pages/tabs is *only* solvable by memory-saving facts as you scroll past them, then comparing from memory later — mobilerun's own system prompt says to do exactly this. The model never did, so even given unlimited time this specific run would very likely have reached `complete()` with nothing retained to actually compare. Reclassify this one instance as a **compound harness+LLM** issue: the harness's timeout is still too tight, but "more time" alone wouldn't have fixed this particular task the way it would the others in this bucket.

### C2. `open_app` 60-second timeouts, recurring and compounding — **14 occurrences**

A tool-level `Failed to execute open_app: Operation timed out after 60.0 seconds` fired 14 times across the run, mostly recovered on retry, but sometimes contributed to the larger 1000s task timeout. Real device thermals climbed from ~34-36°C baseline to a peak of ~62°C (CPU/GPU/NPU) over the ~8-hour continuous run, and these hiccups clustered in the back half of the run.

**Update 2026-07-30 — source confirmed precisely, and it's not the same kind of fix as C1.** `open_app` (§A4 above has the full trace) constructs `AppStarter(driver=ctx.driver, llm=ctx.app_opener_llm, timeout=60, ...)` inside mobilerun's `agent/utils/actions.py` — the `60` is a **literal hardcoded value at the call site**, not a passed-through config value like `MobileAgent`'s own `timeout=1000`. There's no public config surface in `MobileConfig`/`AgentConfig`/`FastAgentConfig` that reaches it, so unlike C1, this one genuinely cannot be fixed from our side without monkeypatching mobilerun internals — which was already tried and deliberately reverted earlier this session for good reasons (see A1).

Root cause: **mobilerun** (hardcoded constant, no override path) — compounded by **harness**, by omission — there's no thermal-aware pacing, cooldown, or backoff built into the batch runner; it fires tasks back-to-back for hours with no rest, and these hiccups clustered in the back half of the ~8-hour run alongside the thermal climb to ~62°C.

**Proposed fix:**
- The 60s constant itself: report upstream to mobilerun (same as B1) — not ours to change safely.
- What we *can* control: add an optional cooldown/pacing knob to `dailybench_tasks.py` (e.g. `--cooldown-seconds` between tasks, or a thermal-aware pause reading `dumpsys battery`/thermal sensors between tasks) so long batches don't run the device continuously into throttling territory in the first place — reducing how often the 60s ceiling gets hit at all, even though we can't raise the ceiling itself.

### C3. Transient LLM-request failures counted as hard failures, no retry — **2 clean occurrences**

`medium-files-001` ("Error: Request timed out.", 2 steps) and `medium-phone-001` (same), plus one `ValueError: Empty response content` on `medium-messages-001` — these are `openai.APITimeoutError`/empty-completion errors from the LLM call itself (confirmed via traceback: `openai.APITimeoutError: Request timed out` inside `llm.astream_chat`), not agent/task-logic failures. All three failed fast (2 steps) rather than hanging, and the batch itself stayed healthy and moved on immediately each time (verified live: LLM server was back to sub-400ms response times seconds later).

Root cause: **harness** (no retry/backoff around a single dropped LLM request) compounding a **mobilerun/inference-infrastructure** blip (`acall_with_retries` does have its own internal retry logic, but it still exhausted retries in these 3 cases — likely a genuine momentary load/thermal spike on mini2 rather than a config bug).

**Proposed fix:** these three are cheap, low-risk to fix relative to their impact: a single dropped LLM call shouldn't fail an entire task when it happens on step 1-2 with no real progress lost yet. Worth adding a harness-level "if the LLM raises a transport-level error (timeout/empty-response) very early in a task, restart that task once" policy, distinct from mobilerun's own per-call retry (which already ran and still failed).

---

## D. Dataset/task-authoring gaps (not code bugs)

These three are cases where the *model behaved reasonably* given what it was actually asked and what real data actually exists — the task text itself is the problem, something I should have caught more carefully during the earlier feasibility audit.

- **`easy-calculator-001`** — task says "compute the total cost of 3 items priced individually" but never gives real prices. The model correctly refused to fabricate numbers and reported the task unanswerable (`success: false`, 2 steps) rather than hallucinating — arguably the *correct* behavior, but it means the task can't succeed as worded. Needs real example prices, same treatment as the other placeholder fills done earlier this session.
- **`medium-music-001`** — I substituted "The Weeknd" based on real *recently-played* evidence during the feasibility audit, but recently-played isn't the same as a saved *library*, and the real library is empty ("No results in your library"). My mistake, not the model's or harness's — needs a real artist confirmed to be in an actual saved library/playlist, or the task needs reworking to ask about recently-played instead of "in your library."
- **`easy-contacts-001`** — task says "Shikha Gupta" but the real contact is named "Shikha Gupta **Rg**"; the model's exact-ish search came up empty across 22 steps. Either the task text should use the exact real contact name, or the model needs to try fuzzier/partial-name search — the former is the cheaper, more reliable fix.

---

## E. Separate, unrelated finding: `tasks.md` content loss

While re-verifying the parser during this session's folder-naming work, I found that `benchmarks/dailyBench-600/tasks.md`'s entire "Hard — Deterministic Composite" section (meant to hold 78 numbered tasks) now contains **zero** numbered items — only the heading survives, immediately followed by the Open-Ended heading. This dropped the private dataset from 730 to 652 parsed tasks. This is a content/authoring issue in the source markdown, not a code or model bug, and not something I should guess-restore — flagging it here since it surfaced during this analysis pass and hasn't been addressed yet.

---

## Summary table

| Category | Count | Root cause | Fix confidence |
|---|---|---|---|
| Generic 1000s timeout, varied real actions | 18 | mobilerun default (unoverridden) | Very high — confirmed one-line fix (`MobileAgent(timeout=...)`) |
| `open_app` 60s hiccups | 14 (mostly recovered) | mobilerun (hardcoded, no override) + harness (no cooldown) | Medium — can't raise ceiling, can add pacing |
| Negative-result miscalibration | 5 | LLM | **Fixed & verified** — prompt hardened, 2/2 smoke-tested flips confirmed |
| XML/JSON-mixing malformation | 3 | LLM | Low — accept as genuine signal (already decided) |
| Date/year misreading | 3 (1 LLM, 2 mobilerun) | 1× LLM transcription; 2× mobilerun (`get_date()` never exposed to agent) | Case 1: low (accept). Cases 2-3: **high** — real fixable gap, likely affects far more than 3 tasks |
| False "app not installed" | 2 | LLM (transient, 10/10 reproduced clean) | Resolved via isolation test — see A4 |
| Transient LLM timeout/empty-response | 3 | Harness (no early-failure retry) + infra blip | Medium — add narrow retry |
| Step-exhaustion via UI cycling | 1 | LLM (genuine task difficulty) | Low — accept |
| mobilerun `finalize` hang | 1 | mobilerun | Report upstream |
| Task-design gaps (Calculator/Music/Contacts) | 3 | Dataset authoring (mine) | High — fix task text/data |
