# Grounding the schedule in real app-usage data

Every DrainBench day is meant to look like an **ordinary person's real phone use**. So the number of apps a benchmark day asks the agent to touch should be anchored to how many apps a real person actually touches in a day. This document records that baseline, with citable sources, and explains the design choice it drives. Verified 2026-08-03.

## The real-world baseline

> The average smartphone user has **~80 apps installed but uses only ~9-10 per day and ~30 per month**, according to data.ai's (formerly App Annie) annual *State of Mobile* report.

That headline figure is consistent across the independent sources below:

| Figure | Source | Link |
|---|---|---|
| ~80 installed; **9-10 used/day**, ~30/month | data.ai (App Annie), *State of Mobile* (primary) | https://www.data.ai/en/insights/market-data/state-of-mobile-2023/ |
| "80 apps installed but uses only 9-10 per day and 30 per month" (cites data.ai State of Mobile) | getfaithlock, *App Addiction Statistics* (2026) | https://www.getfaithlock.com/resources/app-addiction-statistics |
| "average smartphone owner uses **10 apps per day and 30 per month**" | BuildFire, *Mobile App Download & Usage Statistics* (Jul 2026) | https://buildfire.com/app-statistics/ |
| "Users open mobile apps **9.5 times per day** on average" (2024); 4h39m/day in apps | GitNux, *App Usage Statistics* (2026, fact-checked) | https://gitnux.org/app-usage-statistics/ |
| "opens roughly **10 apps daily**, out of about **34 apps used per month**" | getpanto.ai, *Mobile App Usage Statistics* (2026) | https://www.getpanto.ai/blog/mobile-app-usage-statistics |

**Supporting context:**
- Roughly **90% of mobile time is spent inside apps** rather than mobile browsers (eMarketer, cited at https://www.getfaithlock.com/resources/app-addiction-statistics).
- A small handful of apps (roughly 5-6) captures most of a user's daily attention (https://www.getfaithlock.com/resources/app-addiction-statistics).
- People check their phones ~58 times/day and spend ~4h37m/day on them (Exploding Topics, *Time Spent Using Smartphones*, 2026: https://explodingtopics.com/blog/smartphone-usage-stats).

### Precision caveat
The published figures are **averages across users, not strict medians**. Because heavy users skew averages upward, the true **median is likely at or below ~9 apps/day**. Citing "**~9-10 apps/day**" as the *typical* value is therefore a safe, conservative claim.

## What this drives in the benchmark

The schedule should not make a simulated day denser than reality. Three candidate designs, measured by **distinct apps present per day**:

| Design | Apps/day | vs. real ~9-10 |
|---|---|---|
| Original 21-day draft (30 tasks/day) | 17-18 | ~80-100% above |
| First 28-day draft (630 tasks, decoupled) | 12-15 | ~35-50% above |
| 630-task superset, co-located | 11-12 | ~15-25% above |
| **Final runnable design (530-task subset)** | **~9.6 (7-11)** | **~match** |

### Why the superset floor is 11-12 at 630 tasks, and how 530 lands at reality

DrainBench's full corpus is **630 schedule tasks over 28 days across 22 apps** (15 easy + 15 medium per app). Realistically an app contributes **at most 2 tasks on any day** (one easy + one medium). Therefore each app must be active on at least 15 of 28 days, giving:

- total app-days ≥ 22 × 15 = 330
- apps/day ≥ 330 / 28 ≈ **11.79**

So 11-12 apps/day is the mathematical minimum for the 630-task corpus. The **runnable schedule is instead a deterministic 530-task subset** (scripts/build_530_subset.py), which cuts to the density the real-world baseline predicts: it lands at **~9.6 distinct apps/day (min 7, max 11) and ~19 tasks/day (16-23)**, i.e. right at the real ~9-10 baseline, while preserving the easy/medium/hard split (229/229/72), the 50/50 ASK USER / DETERMINISTIC hard split (36/36), the cross-app medium share (~30 of 229), and all 22 apps. (The note-taking load is shared 50/50 between Notes and Obsidian, so the two together occupy the same app-days a single note app would.)

### Design consequence
To land at 530, each app's tasks are selected **round-robin across its active days** (fewest-kept-so-far wins, deterministic tie-breaks), so every app keeps a spread of active days across the month rather than clustering early, and is **entirely absent the rest**. That keeps per-day density realistic (~19 tasks across ~9-10 apps) while still preventing an agent from camping on any one app's screen across the whole run.
