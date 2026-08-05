# DrainBench Public Run — Full Analysis (2026-08-03-162853)

**Moved out of `reports/failures.md` into its own file (2026-08-04).**

---

## Overview

**Config**: `DailyBench_public_v2.json`, `--source public.md`, model `qwen/qwen3.6-plus` (OpenRouter), device `100.108.15.119:5555` (wireless ADB over Tailscale, **unplugged / on battery**), `--steps 200`, `--task-timeout 0`, Phoenix project `fullpublic-20260802`, ask_user model `gpt-5.4-mini`. Run root `runs/2026-08-03-162853` (resumed from position 32).

## Task-complexity profile (dataset audit, from `benchmarks/dailyBench-600/tasks.md`)

Context for the run results — how hard the tasks are by construction. Rough
subgoal count = prompt clauses (split on commas/em-dashes/`and`, ignoring app
prefixes and parentheticals).

| bucket | subgoal (clause) count distribution | dominant range |
|---|---|---|
| easy (315) | 1×163, 2×143, 3×9 | **1–2 subgoals** |
| medium (315) | 3×153, 4×146, 5×13, 6×3 | **3–4 subgoals** |
| hard-DETERMINISTIC (50) | 2×1, 3×1, 4×3, 5×30, 6×12, 7×3 | **5–6 subgoals** |

**ASK USER facts**: all 50 ASK USER tasks ask the user for **exactly one fact**
each (0 ask for two) — so a single missed `ask_user` call fails the whole task,
which is exactly what the run's interaction failures show (tasks 12, 27 skipped
the ask entirely; SR-0 → fail).

**Vars coverage** (`tasks_vars.local.env`): prompts use **46 `[placeholder]`s**;
**20 are covered by the run vars** and the remaining 26 are task-intrinsic
semantic slots answered by the simulated user or seeded on device (e.g. `name`,
`number`, `item`, `dish`, `song`, `time`, `route`, `amount`, `product`,
`business`) — every declared var entry is used (0 unused).

**Why this matters for the run**: subgoal count tracks the failures — the
2-subgoal easy tasks almost all passed (95%), the 3–4-subgoal medium tasks
showed the Telegram-send / Sheets-cell / picker-loop failures (78.9% → several
were harness- or semantic-caused), and the 5–6-subgoal DET-hard tasks are where
step-caps, the 429, and the false-passes clustered (62.5% nominal, lower once
false-passes are excluded).

## Public.md conformance (the 50-task preview vs the 730-task profile)

The run ran `public.md` (`DailyBench_public_v2.json`), so the distribution of
*this* dataset is what the run actually exercised. Audit of `public.md` vs the
`tasks.md` profile above — **conforms on every structural axis; 4 minor
cosmetic deviations; no tasks needed borrowing from tasks.md.**

| Dimension | tasks.md (730) | public.md (50) | Conform |
|---|---|---|---|
| Buckets | 315/315/100 | 20 / 19 / 11 | ✅ |
| Hard split | 50 ASK / 50 DET | 6 ASK / 5 DET | ✅ |
| Hard apps/task | 2–3 (12 single-app ⚠️) | 2×7, 3×4 — **0 single-app** | ✅ (cleaner) |
| Hard/day | 4 (D1–16) → 3 (D17–28) | 4 / 4 / 3 | ✅ |
| ASK USER facts | ≤2 (mostly 1) | 1–2 (2 ask "for both") | ✅ |
| Integrity | 0 em dashes | all dayed, unique ids, no dupes — **11 em dashes** | ⚠️ cosmetic |
| Cross-app mediums | 39/315 (12%) | 5/19 (26%) | ⚠️ heavier (curated) |
| DET-hard subgoals | 5–6 (30×5) | 6 / 8 / 9 / 9 / 11 clauses | ⚠️ wordier prompts |
| Placeholders→vars | 20/46 covered | 6 used, **all covered** | ✅ |
| Apps | 21 categories | 21 apps (incl. Obsidian, Camera, Files, Settings) | ✅ |

Deviations (all minor, none requiring task swaps): (1) 11 em dashes not scrubbed;
(2) public DET-hard prompts are wordier (6–11 clause count vs 5–6 target, though
effective subgoals are lower); (3) cross-app mediums proportionally heavier (26%
vs 12% — deliberate preview richness); (4) Obsidian tracked as its own app here
vs folded into Notes in the 730 resolved-app table. The public set is actually
**stricter** than tasks.md on hard-app counts: **0 single-app hard tasks**.

### Executive summary

- **Fully successful (verified): 27 / 50 (54%)** — the canonical number, from
  trajectory replay (every deliverable evidenced) with all 50 tasks in the
  denominator.
- 47 of 50 produced a verdict (tasks 48–50 did not: 48 crashed on device-offline,
  49–50 never started) → **27/47 (57.4%)** of runs with a verdict.
- **As-recorded flag SR was 40/47 (85.1%)** but that counts false-passes as wins
  and drops the 3 incomplete runs — do **not** use it.
- **Batch ABORTED at ~01:59 (Aug 4)**: device went **offline** mid-task-48;
  `adb connect` timed out. Phone started at 100% battery unplugged and cumulative
  drain across the run was **-91%** — battery died. Tasks 49–50 did not run.
- **Guardrail: CLEAN for all 48 tasks** — no unapproved contact messaged, no
  unapproved group created, no calls placed (incl. risk task 48, which only
  touched Telegram **Saved Messages/self**).

### Final verified metrics (CANONICAL)

Every figure below comes from replaying the per-run trajectory JSON
(`ToolExecutionEvent` action histories) — **not** from the `success` flags.

| metric | value |
|---|---|
| **Success Rate (verified)** | **54.0%** (27/50) |
| SR (verified) of runs with a verdict | 57.4% (27/47) |
| SR by bucket — easy | 85.0% (17/20) |
| SR by bucket — medium | 42.1% (8/19) |
| SR by bucket — hard | 18.2% (2/11) |
| SR (verified) — GUI-only | 61.4% (27/44) |
| SR (verified) — fully-successful among ASK USER | **0.0% (0/6)** |
| ask_user compliance (SR-0: called `ask_user` ≥1) | 50.0% (2/4 completed; 33% of 6) |
| Total `ask_user` calls in the run | **3** |
| **User Interaction Quality (UIQ, success-free fact-match, verified)** | **0.429** (3/7) |
| — UIQ success-gated variant (task-success-tied, deprecated) | 0.000 |
| Average Completion Steps | 51.74 |
| Average total tokens | 697.2 k |
| Average elapsed seconds | 645.1 s |

Outcome split of all 50: **27 fully successful · 10 caveats (partial/wrong/unverifiable)
· 7 clean failures · 4 false-passes · 2 no-run (49–50).**

**Important — the agent DID call `ask_user` (3 times total), it did NOT sit at 0:
**
- `hard-calendar-clock-003` — **2 calls** (got dentist date/time) → asked correctly, but
  snooze FAILED / backup alarm wrong / 3 duplicate events → not fully successful.
- `hard-obsidian-calendar-clock-008` — **1 call** (got "March 12th") → asked correctly,
  but the 9:00 alarm is **absent on device** → not fully successful.
- `hard-contacts-telegram-google-maps-009` — **0 calls** (used stale leftovers).
- `hard-messages-contacts-002` — **0 calls** (self-picked contacts).
- `hard-photos-telegram-005` — **0 calls**, never created the group (crashed).
- `hard-calendar-gmail-obsidian-010` — never ran.

So **ask_user compliance = 2/4 (50%)** among the tasks that ran with a verdict
(2/6 = 33% counting all six), and **fully-successful among ASK USER = 0/6** —
the 0 is about *fully completing the task*, not about never asking.

**UIQ (success-free fact-match, verified) = 3/7 = 0.429** — the formula was
redefined to **not depend on task success**. A question counts as "right" if the
simulated user's returned answer matched the task's ground-truth fact, regardless
of whether the overall task completed:

    UIQ = # ask_user calls whose answer matched the ground truth
          / ( # ask_user calls + # interaction tasks that never asked
              + # GUI-only tasks that needlessly invoked ask_user )

- Tasks 10 (`calendar-clock-003`, 2 calls) and 34 (`obsidian-008`, 1 call) each
  asked the right question (answers "2026-08-05 at 9:30 AM" and "March 12th"
  match their facts) → **3 right answers**, even though both tasks failed on
alarm sub-deliverables.
- Tasks 12, 27, 48, 49 never asked → each adds a missed-expected-question slot to
  the denominator (4 total).
- Numerator = 3, denominator = 3 calls + 4 never-asked + 0 GUI-triggered = 7 →
  **UIQ = 0.429**. The old success-gated formula (`q_i = s_i / c_i`) gave 0.000;
  the as-recorded 0.375 was an artifact of treating `success=true` flags as wins.

### Official metric suite (as-recorded — raw `scripts/dailybench_report.py --source public.md` output, for transparency only)

| metric | value |
|---|---|
| **Success Rate (SR)** | **83.0%** (39/47) |
| SR — GUI-only | 86.0% (37/43) |
| SR — interaction / **ASK USER** | 50.0% (2/4) |
| SR by bucket — easy | 95.0% (19/20) |
| SR by bucket — medium | 78.9% (15/19) |
| SR by bucket — hard | 62.5% (5/8) |
| Average Completion Steps | 51.74 |
| Average User Queries | 0.75 |
| User Interaction Quality (UIQ, success-gated) | 0.375 |
| User Interaction Quality (UIQ, success-free fact-match) | 0.600 |
| Average elapsed seconds | 645.1 s |
| Average total tokens | 697.2 k |

> ⚠️ **This SR is the as-recorded script metric — NOT the verified success rate.**
> It is inflated for two reasons: (1) it counts any `success=true` as a pass, so
> the **false-passes count as wins** (medium-youtube-telegram-001,
> hard-files-notes-telegram-007, hard-contacts-telegram-maps-009 [+48]);
> (2) it **drops the 3 runs without `output.json`** (tasks 48/49/50) from the
> denominator, using 47 not 50. The trajectory-verified **fully-successful rate
> is 27/50 (54%)** — see the scorecard below. Keep both, but never cite 83.0%
> as the success rate. The two as-recorded counts reconcile as: **40/47 (85.1%)**
> is the raw `success=true` flag count (exec summary), while the script's
> **39/47 (83.0%)** additionally applies the SR-0 rule, which flips
> `hard-contacts-telegram-google-maps-009` (0 `ask_user` on an ASK USER task)
> from ✅ to ❌ — that is the 1-task difference. The script's success-free UIQ
> **0.600** covers only the 4
> interaction records that produced `output.json` (3 correct / 3 calls + 2
> never-asked); the verified all-50 value **0.429** additionally counts tasks 48
> and 49 as never-asked (3 / 3 + 4).

Notes on the interaction (ASK USER) split — the metric counts an interaction task as success **only if the agent actually called `ask_user`** (else 0):
- `hard__calendar-clock__003` (task 10): 2 ask_user calls → PASS
- `hard__obsidian-calendar-clock__008` (task 34): 1 ask_user call → PASS
- `hard__contacts-telegram-google-maps__009` (task 12): **0 ask_user** (used stale leftovers) → FAIL under metric
- `hard__messages-contacts__002` (task 27): **0 ask_user** (self-selected contacts) → FAIL under metric
- `hard__photos-telegram__005` (task 48) and `hard__calendar-gmail-obsidian__010` (task 49) have **no `output.json`** (crash / no-run) so are **excluded** from the metric — a 2/6 interaction pass would be **33%** if counted.
- GUI-only SR is inflated by the 3 incomplete runs being excluded from the 47-run total.

### Full failure table (all metrics)

| day | task | verdict | reason-type | steps | exit | secs | tokens(k) | ask_user | batΔ% | batT°C | cpuT°C | skin°C | mAh |
|-----|------|---------|-------------|------:|-----:|-----:|----------:|--------:|------:|-------:|-------:|-------:|----:|
| 1 | hard-google-maps-telegram-006 | FAIL | Telegram send unresponsive | 71 | 1 | 1062 | 761 | 0 | -3 | 36.0 | 74.9 | 41.3 | 122 |
| 2 | easy-files-001 | FAIL | step-cap (Sheets/xlsx) | 200 | 1 | 2159 | 2929 | 0 | -6 | 36.3 | 70.4 | 42.7 | 209 |
| 2 | hard-messages-contacts-002 | FAIL* | ASK USER contract | 22 | 1 | — | — | 0 | — | — | — | — | — |
| 2 | medium-calculator-obsidian-001 | FAIL | 429 rate-limit | 172 | 1 | 1957 | 2430 | 0 | -5 | 36.3 | 74.6 | 41.1 | 192 |
| 2 | medium-calendar-001 | FAIL | calendar-search miss | 10 | 1 | 173 | 51 | 0 | 0 | 34.7 | 60.8 | 38.7 | 16 |
| 3 | medium-camera-001 | FAIL | step-cap (Files loop) | 200 | 1 | 2711 | 2988 | 0 | **-10** | **38.3** | **97.6** | **50.3** | **340** |
| 3 | medium-phone-001 | FAIL | precondition unmet | 37 | 1 | 503 | 399 | 0 | -2 | 35.1 | 67.0 | 38.9 | 44 |
| 3 | hard-photos-telegram-005 | **FAIL / crash** | FALSE-PASS + device offline | 119 | 1 | — | — | 0 | — | — | — | — | — |
| 3 | hard-calendar-gmail-obsidian-010 | NO-RUN | device offline | — | 1 | — | — | — | — | — | — | — | — |
| 3 | hard-photos-settings-011 | NO-RUN | device offline | — | 1 | — | — | — | — | — | — | — | — |

\* `hard-messages-contacts-002` (Wedding Plans) was **manually marked FAIL** by operator: agent never called `ask_user` (0 calls), self-selected 7 family contacts, tapped Start-chat→Create-group, interrupted at step 22 — no group created, device clean. Group creation was task-sanctioned so **not a guardrail violation**; the failure is the skipped mandatory ask.

### Failure detail

1. **hard-google-maps-telegram-006 (D1)** — honest FAIL. Route/pharmacy comparison done (Green Earth wins), but **Telegram Send unresponsive** despite 20+ attempts; message stayed in input field. Same recurring uiautomator Telegram-send issue as tasks 7 & 33.
2. **easy-files-001 (D2)** — step-cap FAIL (200). SPORTS_VIDEO_DATA.xlsx never readable: Sheets renders as one ViewGroup, formula-bar range-nav workaround ~4 steps/cell → too slow in 200-step budget. Leftover "Copy of SPORTS_VIDEO_DATA" files in Drive (cleanup needed).
3. **hard-messages-contacts-002 (D2)** — ASK USER contract violated (see above), manually FAILed.
4. **medium-calculator-obsidian-001 (D2)** — **OpenRouter 429** upstream rate-limit (`qwen/qwen3.6-plus` shared-pool) at step ~172; runner survived but task lost. Spreadsheet Amount never read (harness limitation).
5. **medium-calendar-001 (D2)** — Calendar search returned **"No entries found" for 'shareholder'** although AlphaCorp/BetaTech/GammaFund events ARE seeded (on `cal_id=1` **local account**, `visible=1`, Aug 3/4/5). **ROOT CAUSE CONFIRMED on-device (2026-08-04):** the seeded events live on the device-*local* calendar account, but the Calendar app in use is **Google Calendar** (`com.google.android.calendar`), which does **not** index/search local-account calendars — searching "shareholder" in the app reproduced **"No entries found"** while the events exist in the provider DB. So this is a **seeding/config issue, not an agent failure** — the agent's honest fail (`success=false`, no false-pass) is correct. Same recurring miss seen earlier. Fix: seed these events on a Google-synced calendar (e.g. `yuvraj.mist@gmail.com`), or drive a calendar app that shows local-account events. **APPLIED 2026-08-04:** moved the 3 shareholder events onto the Google-synced calendar (`cal_id=16` `yuvraj.mist@gmail.com`, now `_sync_id`-backed) and updated the task prompt (public.md + `DailyBench_public_v2.json`) to start "In the Google Calendar app, …"; searching "shareholder" in Google Calendar now returns all 3 events (verified on-device).
6. **medium-camera-001 (D3)** — step-cap FAIL. Front-cam 4K video recorded + renamed ✅; first Gmail w/ attachment sent ✅; but **Files "move to custom folder" loop** (~120 steps) + late re-attempts failed (attachment stuck "Adding…", trailing space). **Hottest task of the run** (see thermal).
7. **medium-phone-001 (D3)** — honest FAIL (success=false, correct behavior): **no calls today** → "Courier Service" save impossible; still **blocked 4 spam numbers** (+91 20 7116 7023, 9241, 9245, 1600 10 8194). Partial → FAIL.
8. **hard-photos-telegram-005 (D3, risk task)** — FALSE-PASS + crash. Created "Trip 2026" Photos album + shared **album link to Saved Messages (self)** + starred 2 photos, but **NEVER created the Telegram group "Trip 2026"** / never selected Yuvraj Singh Jio + Yuvraj Airtel (core deliverable missed); ~80 steps burned in Saved-Messages pin loop, then `complete(success=true)`. Device went offline at step 119 → postflight crash → **no `output.json`/`run_metrics.json`**.
9. **hard-calendar-gmail-obsidian-010 (D3)** — client quote email + Obsidian copy: **did not run** (preflight `capture_sample` crashed — device offline).
10. **hard-photos-settings-011 (D3)** — lock-screen collage: **did not run** (device offline).

### False-pass / caveat flags (success=true but not fully genuine)

- `medium-youtube-telegram-001` (D1): SMS to Maa not actually sent (relied on leftover).
- `hard-files-notes-telegram-007` (D2): Telegram Send unresponsive — text still in field at step 26, FALSE-PASSED.
- `hard-contacts-telegram-google-maps-009` (D1): addr/ETA from stale leftovers (K W GROUP clean).
- `easy-contacts-001` (D2): Akash Kumar renamed to "Kumar Sahoo" = rename, not middle-initial add.
- `medium-settings-001` (D3): 2-week app usage not captured (DW only daily) — today's data only.
- `medium-shopping-delivery-browser-001` (D3): "share image link" = clipboard copy, no message sent.
- `hard-obsidian-calendar-clock-008` (D2): "Maa's Birthday" alarm unverified on device.

---

### Battery & thermal analysis

**Baseline**: initial_device_sample = battery **100%**, battery_temp **33.6°C**, charge_counter **3,802,000 µAh**, AC/USB/wireless **unplugged** (phone ran the whole run on battery).

**Run-level totals (47 metric tasks)**: **8.42 h**, **32.55 M LLM tokens**, **2,905 mAh** (~345 mA avg), cumulative battery **-91%** (avg **-1.94%/task**). This sustained drain is what killed the phone at ~01:59 → batch abort.

**Per-day**:

| day | tasks | pass/fail | hours | tokens | mAh | batΔ% |
|-----|------:|----------:|------:|-------:|----:|------:|
| 1 | 16 | 15/1 | 2.97 | 12.67M | 915 | -28 |
| 2 | 18 | 14/4 | 3.11 | 11.65M | 1094 | -34 |
| 3 | 13 | 11/2 | 2.35 | 8.24M | 896 | -29 |

**Worst battery consumers (per task)**: `medium-camera-001` **-10% / 340 mAh** ≫ `easy-files-001` -6% / 209 ≫ `medium-calculator-obsidian` -5% / 192 = `hard-calendar-clock-003` -6% / 184 ≫ `medium-gmail` -4% / 178 = `medium-gallery` -5% / 172. Camera task alone burned 340 mAh (4K front-cam recording + repeated Gmail attachment attempts).

**Thermals**:
- **Battery temp stayed safe throughout**: 34.0–**38.3°C** (max during camera). No battery overheating.
- **CPU temp** 55–**97.6°C**; **skin temp** 38–**50.3°C**.
- **Critical outlier: `medium-camera-001`** — cpu **97.6°C**, skin **50.3°C**, battery **38.3°C**, sustained near-throttle (4K recording + heavy UI loop). This is the only task that hit critical thermal territory; expect silicon throttling there.
- Sustained-heavy browser/sheet tasks sit cpu 70–76°C / skin 41–43°C: `hard-chrome-notes` (75.9/42.7), `medium-files-google-drive` (75.9/41.3), `medium-notes` (75.2/42.5), `medium-shopping` (75.2/42.8), `maps-telegram` (74.9/41.3), `calc-obsidian` (74.6/41.1).
- Light tasks (easy-*, settings): cpu 55–69°C, skin 38–41°C.
- `thermal_status_max` reported 0 everywhere (no formal throttling flag) — but 97.6°C CPU indicates real silicon stress during the camera task.

**Energy efficiency**: 32.55 M tokens / 2,905 mAh ≈ **11.2k tokens per mAh**.

### Root causes & recommendations

1. **Telegram send via uiautomator is unreliable** — 3 tasks affected (7, 11, 33). Recommend a different send-verification path or on-device verification.
2. **Sheets/xlsx cell reading broken** via uiautomator (tasks 16, 25, 35) — range-navigation workaround too slow.
3. **Calendar search misses seeded events** (tasks 20, and preemptively 49) — data present but invisible to agent search.
4. **ASK USER contract** is the biggest single-point failure (task 27) — agent skipped the mandatory ask.
5. **429 upstream rate-limits** can kill long tasks (task 16) — add own key / provider routing.
6. **Battery**: phone ran unplugged from 100%→~0% over ~8.5 h. **Keep the phone charging during long batches**; the camera task's 340 mAh burst shows recording tasks drain fast.
7. **Thermals**: camera recording is extreme (97.6°C CPU). Consider scheduling such tasks with cooling margins; otherwise acceptable.
8. **Resume**: after reconnecting device + charging, resume with `--resume-from hard__calendar-gmail-obsidian__010` to run tasks 49–50 (and re-run 48, which false-passed and has no output).

---

## Verification audit — per-task (reported success vs trajectory)

Method: every task's `output.json` verdict was cross-checked against (a) its goal
(meta.json), (b) the agent's own final `complete` message (agent.log), (c) live
trajectory monitoring during the run (all day3 + most day2 tasks were watched
step-by-step), and (d) output reasons. Where the phone is offline, on-device
end-state (e.g. a Telegram message actually landing, the task-34 alarm saving)
is **flagged UNVERIFIED** rather than assumed.

Verdict key: ✅ GENUINE · ⚠️ CAVEAT (success but partial/wrong-item/unverifiable)
· ❌ FALSE-PASS (success=true but a required deliverable not done) ·
✅ FAIL (success=false, genuinely failed) · ⏭ NO-RUN/INCOMPLETE.

### day1 (16 dirs)

| task | reported | audited | basis / note |
|---|---|---|---|
| easy-chrome-001 | ✅ | ✅ GENUINE | in-stock Sony buds, delivery Aug 7–13; claim+log consistent |
| easy-gmail-001 | ✅ | ✅ GENUINE | starred Myntra email; claim+log consistent |
| easy-google-drive-001 | ✅ | ✅ GENUINE | most-recently-modified folder; simple read |
| easy-google-maps-001 | ✅ | ✅ GENUINE | ETA 5:36 PM to Airport; simple read |
| easy-google-photos-001 | ✅ | ✅ GENUINE | "Invoices" album created with 3 screenshots (this run had them) |
| easy-telegram-001 | ✅ | ✅ GENUINE | muted "Forever 21" group (safe action) |
| easy-youtube-001 | ✅ | ✅ GENUINE | Matt Wolfe latest = AI-news video |
| medium-chrome-001 | ✅ | ✅ GENUINE | Delta vs United; Delta stricter |
| medium-gmail-001 | ✅ | ✅ GENUINE | starred 3 shared docs + label; 163 steps, claim specific |
| medium-google-drive-001 | ✅ | ⚠️ CAVEAT | "PDF not xlsx" — downloaded Q3_Report; format/type mismatch vs task |
| medium-google-photos-001 | ✅ | ⚠️ CAVEAT | "Food Photos" folder created but barely (191/200 steps) |
| medium-youtube-telegram-001 | ✅ | ❌ FALSE-PASS | **SMS to Maa not actually sent** (relied on leftover); claim overstates |
| hard-chrome-notes-001 | ✅ | ✅ GENUINE | IndiGo ₹14,766 vs AI ₹14,877; pinned "Flight Booking" note |
| hard-calendar-clock-003 | ✅ | ⚠️ CAVEAT | dentist 08-05 09:30 ✅; **snooze FAILED, backup alarm wrong (09:30), 3 duplicate events, no cleanup** |
| hard-google-maps-telegram-006 | ❌ | ✅ FAIL (correct) | honest fail — Telegram send never registered (20+ tries) |
| hard-contacts-telegram-google-maps-009 | ✅ | ❌ FALSE-PASS (SR-0) | ASK USER task, **0 ask_user calls**, addr/ETA from stale leftovers; end-state unverified |

### day2 (18 dirs)

| task | reported | audited | basis / note |
|---|---|---|---|
| easy-google-search-001 | ✅ | ✅ GENUINE | top-3 coffee shops |
| medium-google-search-telegram-001 | ✅ | ✅ GENUINE | messaged Yuvraj Singh (share-sheet send confirmed) |
| easy-calculator-001 | ✅ | ⚠️ CAVEAT | total $49.24 is mathematically right, but flagged "leftover 49.24" (calc UI not really used) |
| medium-calculator-obsidian-001 | ❌ | ✅ FAIL (correct; infra) | OpenRouter **429 rate-limit** at step ~172; Amount never read (harness) |
| easy-clock-001 | ✅ | ✅ GENUINE | 0 active alarms |
| medium-clock-001 | ✅ | ✅ GENUINE | 7:30 set+enabled, vibrate, full volume; snooze correctly skipped (no conflict) |
| easy-calendar-001 | ✅ | ✅ GENUINE | 0 lunchtime events |
| medium-calendar-001 | ❌ | ✅ FAIL (correct) | honest fail — "shareholder" search returned nothing despite seeded events (visibility miss) |
| easy-contacts-001 | ✅ | ⚠️ CAVEAT | rename → "Kumar Sahoo", **not a middle-initial add**; end-state unverified |
| medium-calendar-contacts-001 | ✅ | ⚠️ CAVEAT | Harshit is an **ANNIVERSARY** (misread as birthday); reminder created but title references wrong person |
| easy-notes-001 | ✅ | ✅ GENUINE | rename genuine (pin was pre-existing) |
| medium-notes-001 | ✅ | ⚠️ CAVEAT | picked wrong checklist note; loose "water bottle" mapping; stopped at sign-in gate |
| easy-files-001 | ❌ | ✅ FAIL (correct; harness) | step-cap 200; xlsx cell text unreadable via uiautomator |
| medium-files-google-drive-001 | ✅ | ✅ GENUINE | uploaded 5 heaviest to "Too heavy files from Downloads", deleted local |
| hard-files-notes-telegram-007 | ✅ | ❌ FALSE-PASS | budget analysis + note done, but **Telegram Send unresponsive — message never sent**; claimed success |
| hard-messages-contacts-002 | ❌ | ✅ FAIL (correct; manual) | ASK USER, **0 ask_user calls**, self-picked 7 contacts; no group created (guardrail clean) |
| hard-messages-notes-004 | ✅ | ✅ GENUINE | 5 alerts → pinned note + Calendar event + reminder (~30 steps wasted on save flakiness) |
| hard-obsidian-calendar-clock-008 | ✅ | ⚠️ CAVEAT | ask_user contract perfect (1 call, March 12); event+note done; **alarm unverified on device** |

### day3 (16 dirs)

| task | reported | audited | basis / note |
|---|---|---|---|
| easy-gallery-001 | ✅ | ✅ GENUINE | deleted most recent screenshot |
| easy-messages-001 | ✅ | ✅ GENUINE | 18 unread bank msgs (HDFC 17 + Equitas 1) |
| easy-music-001 | ✅ | ✅ GENUINE | The Weeknd "Open Hearts (Single Version)" played |
| easy-phone-001 | ✅ | ✅ GENUINE | 1 number ending 89: +91 74829 16689 |
| easy-settings-001 | ✅ | ✅ GENUINE | screen timeout → 1 minute |
| easy-shopping-delivery-browser-001 | ✅ | ✅ GENUINE | Galaxy Buds FE out of stock, no restock date — honest answer |
| medium-camera-001 | ❌ | ✅ FAIL (correct; partial) | video recorded+renamed ✅, 1st Gmail w/ attachment sent ✅; folder-move deliverable unmet → step-cap |
| medium-gallery-001 | ✅ | ✅ GENUINE | kept 6s video, deleted 2 GIFs |
| medium-messages-001 | ✅ | ✅ GENUINE | SMS to Dad ₹9,597.01 — **math verified** |
| medium-music-001 | ✅ | ✅ GENUINE | "Chill Vibes" playlist + 5 tracks + shuffle |
| medium-phone-001 | ❌ | ✅ FAIL (correct; precondition) | no calls today → Courier-Service save impossible; blocked 4 spam numbers (partial) |
| medium-settings-001 | ✅ | ⚠️ CAVEAT | **2-week usage NOT captured** (DW daily-only); set 30-min timers on top apps |
| medium-shopping-delivery-browser-001 | ✅ | ⚠️ CAVEAT | Nike $120 cheaper → Add to Bag ✅; "share link" = **clipboard copy, no message sent** |
| hard-photos-telegram-005 | (none) | ❌ FALSE-PASS + INCOMPLETE | album+Saved-Messages share+star done, but **"Trip 2026" group never created**; then device offline → no output.json |
| hard-calendar-gmail-obsidian-010 | (none) | ⏭ NO-RUN | device offline at preflight |
| hard-photos-settings-011 | (none) | ⏭ NO-RUN | device offline at preflight |

### Corrected totals

- Reported successes: **40**. After audit (within the 47 with a verdict):
  **GENUINE = 27**, **CAVEAT = 10**, **FALSE-PASS = 3** (medium-youtube-telegram-001,
  hard-files-notes-telegram-007, hard-contacts-telegram-google-maps-009 [SR-0]).
  A 4th false-pass, hard-photos-telegram-005, is excluded from the 47 (no
  output.json) but did false-pass before crashing.
- Reported failures: **7** — all verified as genuine/appropriate fails (2 step-cap,
  1 429 rate-limit, 1 Telegram-send, 1 calendar-search-miss, 1 precondition,
  1 ASK-USER contract; medium-camera + medium-phone are partial).
- So the **clean pass rate** is ~27/47 (57%) as strictly graded, or ~37/47 (79%)
  counting caveats as passes — the headline 83.0% SR overstates because it counts
  false-passes and treats incomplete runs as absent.
- **Unverifiable on-device** (phone offline — verify later): Telegram/SMS delivery
  for tasks 7, 11, 33 & medium-search-telegram; task-34 alarm save; task-21 contact
  name state; task-12 address/ETA source.

---

## Trajectory-verified scorecard — ONLY fully successful runs count

Every run's `trajectories/<run>/trajectory.json` (`ToolExecutionEvent` = tool +
args + success + result) was replayed to confirm what the agent *actually did*,
not what it claimed. **A run counts as fully successful only if every required
deliverable is evidenced in the action history.** (On-device end-state could not
be re-checked: `adb connect 100.108.15.119:5555` times out — phone/Tailscale/
wireless-ADB needs re-enabling.)

### Trajectory-confirmed findings (the ones that flip or confirm)

- `medium-youtube-telegram-001` (D1) ❌ **FALSE-PASS — confirmed.** Opened Maa's
  chat, **never typed or tapped send**, went Home, `complete(true)`. No SMS sent.
- `hard-contacts-telegram-google-maps-009` (D1) ❌ **FALSE-PASS — confirmed.**
  Only typed+sent the ETA follow-up (s13–15); the **address message was never
  typed/sent** (relied on a stale leftover thread); **0 ask_user** on an ASK-USER
  task. Full address deliverable missing.
- `hard-files-notes-telegram-007` (D2) ❌ **FALSE-PASS — confirmed.** Typed the
  overdue message, then Send was tapped 9× + Enter + long-press (s17–28) with the
  text **still in the input field**; note created; `complete(true)`.
- `hard-photos-telegram-005` (D3) ❌ **FALSE-PASS — confirmed.** Photos album
  "Trip 2026" created, album **link shared to Saved Messages (self)** via
  "Share in 1 chat", then ~90 steps of pin loop. **No Telegram group was ever
  created** — grep across ALL trajectories finds zero group-creation actions.
- `medium-messages-001` (D3) ✅ **GENUINE — confirmed.** Typed ₹9,597.01 SMS to
  Dad + tapped Send (s45–46); math verified.
- `medium-phone-001` (D3) ❌ **FAIL correct — confirmed.** No today calls; **4
  real blocks** (s8–35); honest `success=false`.
- `hard-messages-contacts-002` (D2) ❌ **FAIL correct — confirmed.** 17 scroll
  swipes → Start chat → New group, **0 ask_user**, interrupted, no `complete`.
- `easy-contacts-001` (D2) ⚠️ **CAVEAT — confirmed botched.** Edited to
  First="Kumar", typed "Sahoo" into the **phone field** (s10), cleared Last name
  (s12) → not a middle-initial add.

### Fully-successful count (strict)

| day | fully successful | total dirs |
|-----|-----------------:|-----------:|
| day1 | 10 | 16 |
| day2 | 8 | 18 |
| day3 | 9 | 16 |
| **all** | **27** | **50** |

**27 / 50 (54%) of all tasks, or 27 / 47 (57.4%) of runs that produced a verdict,
were fully successful** (every deliverable evidenced in the trajectory).

Remaining split of the 50: **10 caveats** (partial/wrong-item/unverifiable:
medium-google-drive, medium-google-photos, hard-calendar-clock, easy-calculator,
easy-contacts, medium-calendar-contacts, medium-notes, hard-obsidian-calendar-
clock, medium-settings, medium-shopping), **7 clean failures**, **4 false-passes**
(3 with output + hard-photos-telegram-005), **2 no-run** (tasks 49–50). The
reported SR (83.0%) and the MobileWorld interaction metrics **do not reflect this**
— they count false-passes as wins and drop the incomplete runs from the
denominator.

### On-device verification (wired ADB, 2026-08-04) — confirms, doesn't change count

Phone reconnected via USB (`RS7XKZDI8HTOJNYL`). Read-only checks:

- ✅ `easy-settings-001` **confirmed** — `settings get system screen_off_timeout`
  → **60000 ms (1 minute)**. Fully successful.
- ⚠️ `easy-contacts-001` **confirmed botched** — the Akash Kumar contact no longer
  exists as "Akash Kumar" or "Kumar Sahoo"; the edit (First="Kumar", "Sahoo" into
  a phone field, last name cleared) mangled the contact. Not a middle-initial add.
- ⚠️ `hard-obsidian-calendar-clock-008` **alarm NOT saved** — Clock shows only the
  6 pre-existing 04:00–04:30 alarms (all off); the claimed **9:00 "Maa's Birthday"
  alarm is absent**. Event + reminders + Obsidian note were genuine; the alarm
  sub-deliverable failed. Stays a caveat.
- ⚠️ `hard-calendar-clock-003` **alarms NOT saved** — 09:30/10:30 alarms absent
  (matches snooze-failed + wrong-backup notes). Calendar event genuine; alarm
  deliverables failed. Stays a caveat.
- ✅ `medium-clock-001` — 7:30 alarm not in the current list because it **fired
  at 07:30 this morning** (Aug 4) and one-time alarms are dropped; trajectory +
  live monitor confirmed the setup. Stays fully successful.
- ⚠️/❌ SMS/Telegram delivery could not be read from `content://sms` (RCS/app-
  private DB) — trajectory evidence stands: medium-messages-001 typed+Send to Dad
  (RCS, not in sms box), medium-youtube-telegram-001 & the Telegram tasks never
  delivered.

**Net: fully-successful count remains 27/50 (54%).** The on-device pass confirmed
easy-settings-001 and hardened the alarm caveats; it did not promote or demote any
run into/out of the fully-successful set.

### Full re-verification (wireless ADB, 2026-08-04) — numbers confirmed

Wireless ADB reconnected (`100.108.15.119:5555`, Tailscale tun0 up, adbd `*:5555`
listening) — on-device checks are possible again without a cable.

**Metrics recomputed from run artifacts on 2026-08-04 (all confirmed):**

- Avg Completion Steps **51.74** ✓ (sum of `output.json.steps` / 47).
- Avg total tokens **697.2 k** (sum of `llm_proxy_metrics.jsonl` `usage.total_tokens`
  over 47 = 32.77M). *Corrected from the earlier 692.6 k, which undercounted by
  excluding the model's reasoning tokens.*
- As-recorded SR **83.0% (39/47)** ✓ (script output).
- Verified UIQ (success-free fact-match, all-50) **0.429 (3/7)** ✓.

**On-device end-state sweep (wireless ADB) — run artifacts all cleaned/absent:**

| check | result |
|---|---|
| screen_off_timeout | 1800000 ms (30 min, pre-run) ✓ |
| blocked numbers | only pre-existing `+917275181377` ✓ (run's 4 removed) |
| calendar events | all **8** agent-created events soft-deleted (6 from this run
  + 2 pre-run dentist from the earlier attempt) ✓ |
| contact `easy-contacts-001` | restored to **"Akash Kumar"** ✓ |
| Downloads / MediaStore | no run-created files/albums remain ✓ (`food` bucket =
  seeded DCIM, kept) |
| alarms | only pre-existing 04:00–04:30 remain ✓ (7:30 fired & dropped; 9:00
  Maa alarm never saved) |

**Still not reachable via ADB (app-private DB / cloud — user-manual):** Notes app
rename-back + deletes, Obsidian note, Photos "Invoices"/"Trip 2026" albums,
YT Music "Chill Vibes" playlist, Telegram unmute, Digital Wellbeing timers,
Gmail/Drive cleanup, Gallery-trash restore, and SMS/Telegram delivery proof
(RCS/app-private DB).
