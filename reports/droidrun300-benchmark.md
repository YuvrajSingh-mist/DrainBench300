# DrainBench
### What does it actually cost — in dollars, battery, and heat — to get an AI agent to use your phone?

---

## Vision

Every mobile AI-agent benchmark today asks one question: **can it complete the task?** Nobody asks the question that actually matters to a person deciding which model to run on their own phone: **what does completing that task cost me — in dollars, battery percentage, and heat — on the hardware I actually own?**

DrainBench exists to be the place that answer lives. Live, on a real phone, across real everyday tasks in apps people actually use — not a synthetic sandbox, not an emulator. The end state: a public leaderboard where someone can look up a model, see its success rate next to its real cost, battery drain, and thermal impact on a known reference device, and pick a model the way they'd check a spec sheet before buying hardware — then publish the runs themselves, openly, to build attention and trust in the project.

## Problem Statement

Mobile GUI-agent benchmarks are a crowded, active research area — AndroidWorld, AndroidArena, MobiBench, AndroidDaily, MobileBench-OL, GUI-CEval, MVISU-Bench, and the open-source agent frameworks built to run them (Droidrun/mobilerun, Mobile-Agent, AppAgent) all exist and are actively maintained. Every one of them, without exception, reports **task success rate** as the headline metric. A couple (MobiBench, MVISU-Bench) have started reporting cost and latency too. **None of them report battery drain or thermal impact of running an agent live on a real device** — and none of them are built specifically around a curated set of everyday tasks that's also safe to demo and publish publicly, since most either use toy open-source stand-in apps (AndroidWorld) or real closed-source apps without regard for automation ToS risk (AndroidDaily).

## What's Actually Different (stated conservatively, not oversold)

| Piece | Already exists elsewhere | What DrainBench does |
|---|---|---|
| Live accessibility-driven agents | Yes — Droidrun/mobilerun, Mobile-Agent, m3a | Built on top of mobilerun rather than reinvented |
| Cost in dollars, on real devices | Yes — MobiBench (offline), MVISU-Bench (live) | Same idea, applied consistently across the whole suite |
| Real-device (not emulator) testing | Yes — MobileBench-OL, GUI-CEval, AndroidDaily | Same, on a defined consumer hardware tier |
| **Battery drain + thermal impact of a live agent loop** | **Not found anywhere in the benchmarks or frameworks surveyed** | **Reported as a first-class, headline metric** |
| Everyday tasks (not synthetic/toy) | Partially — AndroidDaily, MobileWorld use real apps | Grounded task suite (300 queries) built from real usage patterns |
| An app scope safe to demo and publish publicly | Not something any research benchmark had to solve | Deliberately excludes apps with active anti-automation/bot-detection enforcement (Instagram, Facebook, WhatsApp, Messenger, Threads, TikTok, X, Snapchat, WeChat) |

**The one-sentence claim:** DrainBench measures what running an LLM agent actually costs a real phone — in dollars, battery, and heat — across cloud and local models, on everyday tasks in apps people actually use, in a scope safe enough to publish without risking a platform ban. Every individual ingredient exists somewhere else; this combination doesn't.

## Scope

**Framework:** built on [mobilerun](https://github.com/droidrun/mobilerun) (Droidrun) rather than a from-scratch accessibility service — it already solves setup friction (Portal app, wizard-based provider config) and supports the full range of models needed: OpenAI, Anthropic, Gemini, DeepSeek, and local models via Ollama.

**Apps (20, ToS-vetted safe list):** Gmail, Google Maps, Chrome, Google Drive, Google Photos, YouTube, Telegram, Google Search, Calculator, Clock, Calendar, Contacts, Notes, Files, Camera, Gallery, Music, Messages, Phone, Settings.

**Task suite:** 300 queries — 100 easy, 100 medium, 78 hard-deterministic (composite, cross-app, independently verifiable), and 22 open-ended (ambiguous/subjective, graded separately via a calibrated rubric-based LLM-judge panel — never blended into the deterministic success rate).

**Core metrics:** task success rate, cost (USD), latency (TTFT + total), battery/energy drain, and thermal drift — captured per step, on-device, via `BatteryManager` and thermal-zone polling, independent of whatever model is under test.

## Publishing Plan

Run videos published openly, showing the agent operating live on a real device — building public visibility and trust in the project's numbers, while staying inside the app scope that doesn't carry meaningful ToS/account-ban risk.

## Measurement Implementation

For the actual benchmark harness, use untethered Wi-Fi ADB after setup so USB power and cable thermals do not pollute the run.

- Battery sampling: `adb shell dumpsys battery`
- Thermal sampling: `adb shell dumpsys thermalservice`
- Screen capture: host-side `scrcpy --record`

On the current reference phone, `dumpsys thermalservice` exposes HAL-backed `CPU`, `GPU`, `BATTERY`, `SKIN`, `POWER_AMPLIFIER`, and `NPU` temperatures. The phone blocks direct `adb shell screenrecord` file writes, so the harness records from the host side using `scrcpy --record`, which still preserves a clean per-task `.mp4` artifact for publishing.

The implementation in this repo is [drainbench_runner.py](/Users/yuvrajsingh9886/Desktop/DrainBench300/drainbench_runner.py) with usage notes in [bench-usage.md](/Users/yuvrajsingh9886/Desktop/DrainBench300/bench-usage.md).
