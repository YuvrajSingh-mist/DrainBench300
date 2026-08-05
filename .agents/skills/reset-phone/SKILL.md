---
name: reset-phone
description: 'Reset the benchmark phone (OnePlus CPH2423) to its pre-run baseline and re-verify the seeded task data before running inference. USE WHEN: resetting the phone, reset device before run, restoring baseline, cleaning up run artifacts, undo a run, seed data, provision device, prepare device for a run, pre-run device reset. DO NOT USE FOR: general ADB debugging, single-task fixes, the emulator (use AVD snapshot cold-boot instead).'
---

# Reset the benchmark phone to baseline (pre-run)

Goal: return the device to the exact fabricated baseline so every inference run
starts from the same state. Two layers, always run in order:

1. **Undo run artifacts** (what the agent created/changed during a run) — scripted.
2. **Verify baseline seeds still present** (the fabricated data the tasks need).

> ⚠️ Destructive-ish: this DELETES agent-created data (events, notes, files,
> blocks, contact edits). It does NOT wipe the fabricated seed data. Never run on
> a personal device — this phone is the dedicated benchmark device (fabricated
> persona "Yuvraj Singh" data only).

## Connection

- Wired: `adb -s RS7XKZDI8HTOJNYL shell echo OK`
- Wireless: `adb -s 100.108.15.119:5555 shell echo OK`
- If wireless refuses ("Connection refused"), re-arm then reconnect:
  `adb -s RS7XKZDI8HTOJNYL tcpip 5555` → `adb connect 100.108.15.119:5555` (retry once — it's a race while adbd restarts).

## Step 1 — Run the reset script (dry-run first, then apply)

```bash
uv run python scripts/reset_phone.py --serial 100.108.15.119:5555 --profile public_v2          # DRY RUN (default, safe)
uv run python scripts/reset_phone.py --serial 100.108.15.119:5555 --profile public_v2 --apply  # actually reset
```

The script:
- Restores settings (e.g. `screen_off_timeout` → 1800000).
- Unblocks numbers the agent blocked (keeps pre-existing blocks).
- Deletes agent-created calendar events (marker/title/creation-window matched) and restores the mangled `Akash Kumar` contact.
- Removes run-created files from Downloads/DCIM.
- Verifies baseline seeds still present (shareholder events on the Google calendar, `PURCHASE_ORDER.xlsx`, `SPORTS_VIDEO_DATA.xlsx`, `budget.xlsx`, `quote.xlsx`, contacts).

## Step 2 — Manual UI-only cleanups (no ADB access — app-private DB / cloud)

These cannot be scripted on a non-rooted device; do them once per run if the
agent touched them (each is a quick UI action, ~5–10 min total).

**Phone apps:**

- **Notes** (`com.oneplus.note`) — delete run-created notes: "Card Payment Due"
  (task 32), "Budget Tracker" (task 33), "Birthday Reminders" (task 34), and the
  "IndiGo Flight: BBI-BOM Aug 15-20" note (created by task 13 `hard-chrome-notes-001`
  as "Flight Booking", then renamed by task 23 `easy-notes-001` — it's a run
  artifact, so strict pre-run reset = delete it, NOT rename back).
- **Obsidian** — delete run notes (e.g. "Birthday Reminders"); the vault is
  app-private (`/data/data/md.obsidian`), so do it in-app.
- **Photos/Gallery** — delete run-created albums ("Invoices" task 4, "Trip 2026"
  task 48); unstar the 2 starred photos (task 48); don't restore photos the agent
  deleted (GIFs/screenshot from tasks 37/36) unless you want them back.
- **YT Music** — delete the "Chill Vibes" playlist (task 39).
- **Telegram** — unmute the "Forever 21" group (task 12).
- **Digital Wellbeing** — remove the 30-min app timers the agent set
  (Gallery, Messages, YT Music, WhatsApp, Chrome; task 45).
- **Camera** — delete the run-recorded "Camera Video" clip if it shows up
  (task 35).

**Cloud (Gmail / Drive):**

- **Gmail** — unstar starred emails + remove the label the agent created
  (tasks 1/2); delete the sent-with-attachment email (task 35 to
  `hafari4025@aghism.com`).
- **Gmail "Recent Mail Searches" — NOT a reset item (verified on-device
  2026-08-04).** The list under the search bar holds the user's personal
  searches (e.g. `hey`, `hi`, `work`, `not taking app`), not seed data. Long-press
  does NOT show a Remove menu (it just runs the search), and Gmail General
  settings have NO search-history option. Only `pm clear com.google.android.gm`
  (logs you out + full re-sync) or deleting account Search history at
  `myactivity.google.com` (affects all Google apps) would clear them — neither is
  worth it. The suggestions ARE visible to the agent (accessibility tree), but
  they can't leak ASK USER facts (those are never searched) and don't change
  end-state grading → low-risk, do NOT block a run on this.
- **Drive** — delete the `Copy of SPORTS_VIDEO_DATA` leftovers (task 29);
  re-download the 5 files the agent uploaded from "Too heavy files from
  Downloads" back to the phone (task 26), then delete that Drive folder.
- **Call-log gap (task 43)** — not seeded by design: the operator must make one
  real call to an unsaved number on run day (see `docs/fabricated-test-data.md`).

## Step 3 — Verify baseline (gate)

- `scripts/reset_phone.py --verify-only --serial <serial> --profile public_v2`
- Baseline must include, e.g.: 3 `shareholder *` events on the **Google-synced**
  calendar (`yuvraj.mist@gmail.com`, with `_sync_id`), `screen_off_timeout=1800000`,
  seed files present, contact "Akash Kumar" present.
- If verify fails, do NOT start the run — fix the device first (fail-fast).

## Step 4 — Run inference

Launch the batch as documented in `docs/fabricated-test-data.md` §5
(`--dataset benchmarks/dailyBench-600/DailyBench_public_v2.json --all ...`).

## Context / gotchas (learned 2026-08-04)

- Google Calendar app only shows **`_sync_id`-backed** (Google-synced) events —
  events seeded on the local account are invisible to it. Seeds must live on the
  Google account (`cal_id=16` `yuvraj.mist@gmail.com`), not `cal_id=1`.
- `content insert/delete` on this non-rooted device: CALENDAR + CALL-LOG WORK
  (verified 2026-08-05) — but quoting matters: wrap `rrule` values AND title
  where-clauses in single quotes so the device shell doesn't split on `;`/spaces
  (`--bind rrule:s:'FREQ=WEEKLY;BYDAY=WE;COUNT=52'`, `--where 'title="X"'`).
  SMS insert is genuinely BLOCKED (silently no-ops). New seeds → content provider
  or UI automation.
- Calendar "shareholder" visibility miss root cause + fix: see
  `/memories/repo/device-audit.md`.
- For the full 730-task dataset, prefer an **emulator + AVD snapshot** (cold-boot
  from snapshot = exact state, zero provisioning). This skill is for the real
  phone (public 50).
