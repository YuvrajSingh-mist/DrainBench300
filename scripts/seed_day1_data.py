#!/usr/bin/env python3
"""Seed the Day-1 fabricated data onto the device (sanity-check run, 2026-08-05).

For every seedable-by-ADB task the script:
  1. materialises the literal fabricated files into
     seeds/full_tasks/day_1/<task_id>/seed_files/  (transparency artifact), and
  2. pushes them to the device with the correct mtime (so Gallery/Messages sort them
     as "today", "~1h ago", ">1 month old" respectively).

Things that cannot be seeded via ADB (app-private / blocked content-insert) are
attempted and their result reported honestly:
  - SMS insert (content://sms)  - usually blocked on non-rooted
  - call-log insert (content://call_log/calls) - usually allowed

Run:  uv run python scripts/seed_day1_data.py --serial RS7XKZDI8HTOJNYL
"""

from __future__ import annotations

import argparse
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from DailyBench.user_config import load_user_config  # noqa: E402

DAY_DIR = REPO_ROOT / "seeds" / "full_tasks" / "day_1"
VAULT = "/sdcard/Obsidian/Papers vault oneplus "  # NB: trailing space is real
CAMERA = "/sdcard/DCIM/Camera"
SCREENSHOTS = "/sdcard/DCIM/Screenshots"
CONFIG_PATH = REPO_ROOT / "config" / "user.yaml"

NOW = time.time()
TODAY = time.strftime("%Y-%m-%d", time.localtime(NOW))
ONE_HOUR_AGO = NOW - 3600
OLD_MONTH = "2026-05-20"  # well over a month before 2026-08-05


# ---------------------------------------------------------------------------
# minimal pure-Python PNG writer (solid color, no deps)
# ---------------------------------------------------------------------------
def write_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    idat = zlib.compress(raw)
    path.write_bytes(sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def mtime_seconds(stamp: str) -> int:
    """Parse an ISO local timestamp into epoch seconds (matches the shell date)."""
    return int(time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S")))


# ---------------------------------------------------------------------------
# seed definitions: task_id -> list of (filename, [w,h], rgb, mtime_iso, dest_dir)
# ---------------------------------------------------------------------------
def make_seed_images() -> None:
    def img(task: str, fname: str, rgb: tuple[int, int, int], mtime: str, dest: str, size=(64, 64)):
        if not (DAY_DIR / task / "manifest.json").exists():
            print(f"  [skip] {task}: no manifest (not in runnable day) - not materialising {fname}")
            return None, mtime, dest
        d = DAY_DIR / task / "seed_files"
        d.mkdir(parents=True, exist_ok=True)
        p = d / fname
        if not p.exists():
            write_png(p, size[0], size[1], rgb)
        return p, mtime, dest

    # pizza search (medium__gallery__001) - 5 pizza shots, taken today
    pizza_colors = [(180, 40, 30), (200, 90, 40), (160, 30, 20), (220, 120, 60), (190, 70, 35)]
    for i, c in enumerate(pizza_colors, 1):
        img("medium__gallery__001", f"pizza{i}.jpg", c, "2026-08-05 00:30:00", CAMERA, (96 + i * 8, 64))

    # today's burst for the GIF task (medium__gallery-telegram__001) - 5 photos today
    burst_colors = [(30, 90, 180), (60, 160, 90), (200, 160, 30), (120, 70, 180), (220, 90, 140)]
    for i, c in enumerate(burst_colors, 1):
        img("medium__gallery-telegram__001", f"today_{i}.jpg", c, f"2026-08-05 00:{20+i:02d}:00", CAMERA, (80, 80))

    # ~1h-ago photo to hide (easy__gallery__001)
    img("easy__gallery__001", "hide_me.jpg", (140, 140, 140), "2026-08-05 00:25:00", CAMERA, (96, 64))

    print("materialised seed images into seed_files/")


def adb(serial: str, *args: str) -> tuple[int, str]:
    res = subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True)
    return res.returncode, (res.stdout + res.stderr).strip()


def push_with_mtime(serial: str, local: Path, remote_dir: str, mtime_iso: str) -> None:
    remote = f"{remote_dir}/{local.name}"
    adb(serial, "push", str(local), remote)
    ts = time.strftime("%Y%m%d%H%M.%S", time.localtime(mtime_seconds(mtime_iso)))
    adb(serial, "shell", "touch", "-t", ts, remote)
    print(f"  pushed {local.name} -> {remote}  (mtime {mtime_iso})")


def mtime_for(fname: str) -> str:
    """Deterministic mtime per filename so Gallery sorts the seeds as intended."""
    if fname.startswith("old_shot_"):
        n = int(fname[len("old_shot_"):].split(".")[0])
        return f"2026-05-{20 + n:02d} 10:00:00"  # 2026-05-21..24 -> >1 month old
    if fname == "hide_me.jpg":
        return "2026-08-05 00:25:00"              # ~1h before now (01:25)
    return "2026-08-05 00:30:00"                   # today (pizza / burst)


def push_seed_images(serial: str) -> None:
    print("pushing images...")
    for task_dir in DAY_DIR.iterdir():
        if not task_dir.is_dir():
            continue
        sf = task_dir / "seed_files"
        if not sf.is_dir():
            continue
        for f in sorted(sf.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                dest = SCREENSHOTS if f.name.startswith("old_shot") else CAMERA
                adb(serial, "shell", "mkdir", "-p", dest)
                push_with_mtime(serial, f, dest, mtime_for(f.name))
    # rescan media so Gallery picks them up
    adb(serial, "shell", "content", "call", "--uri", "content://media/none", "--method", "scan_volume", "--arg", "external_primary")
    print("  media rescan triggered")


def push_obsidian_seed(serial: str, cfg: dict[str, str]) -> None:
    note_title = cfg["stock note title"]
    print(f"pushing Obsidian '{note_title}' note...")
    sf = DAY_DIR / "hard__google-search-obsidian-telegram__057" / "seed_files"
    note = next((sf / f for f in sorted(sf.iterdir())
                 if f.suffix == ".md" and f.name != "DEVICE_PATHS.md"), None) if sf.is_dir() else None
    if note is None or not note.exists():
        print("  (missing seed_files/ - build manifests first)")
        return
    remote = f"{VAULT}{note_title}.md"
    adb(serial, "shell", "mkdir", "-p", VAULT)
    adb(serial, "push", str(note), remote)
    print(f"  pushed -> {remote}")
    print("  note contents:")
    print(note.read_text(encoding="utf-8"))


GOOGLE_CALENDAR_ID = "16"  # yuvraj.mist@gmail.com - the one the Google Calendar app displays


def seed_calendar_events(serial: str) -> None:
    """Seed the Day-1 calendar tasks into the Google-synced calendar (cal_id=16).

    Coverts the three calendar tasks:
      easy__calendar__001        -> an existing event today the agent can add a location to
      medium__calendar__001      -> a recurring NO-attendee event that recurs today,
                                    plus an OUTDATED recurring series (ended last month)
      hard__calendar-telegram-obsidian__002 -> a meeting this week at 08:30 (before 9am,
                                    so the reschedule branch is exercised)
    """
    import datetime as _dt

    today = _dt.date(2026, 8, 5)  # device date
    wd = today.strftime("%a").upper()[:2]  # 'WE'
    ms = int(_dt.datetime(2026, 8, 5, tzinfo=_dt.timezone.utc).timestamp() * 1000)

    def ins(title: str, dtstart_ms: int, dtend_ms: int, rrule: str | None = None) -> None:
        cmd = ["content", "insert", "--uri", "content://com.android.calendar/events",
               "--bind", f"calendar_id:i:{GOOGLE_CALENDAR_ID}",
               "--bind", f"title:s:{title}",
               "--bind", f"dtstart:l:{dtstart_ms}",
               "--bind", f"dtend:l:{dtend_ms}",
               "--bind", "allDay:i:0", "--bind", "hasAlarm:i:0",
               "--bind", "eventTimezone:s:Asia/Kolkata"]
        if rrule:
            # single-quote wrap: the DEVICE shell strips the quotes, so the ';' in
            # the rrule reaches `content` intact instead of being split into commands.
            cmd += ["--bind", f"rrule:s:'{rrule}'"]
        adb(serial, "shell", *cmd)

    h = 3600_000
    day0 = ms - (ms % 86_400_000)  # midnight today UTC (close enough for sanity)
    # idempotent: drop any previously-seeded rows first (title-delete removes ONE
    # matching row per call, so repeat until none remain)
    for t in ("Add_Location_Demo", "Weekly_Standup", "Old_Gym_Class", "Project_Review", "TeamSync", "ProbeEvent"):
        for _ in range(6):
            adb(serial, "shell", "content", "delete", "--uri", "content://com.android.calendar/events",
                "--where", f"'title=\"{t}\"'")
    # 1. existing event today (easy__calendar__001)
    ins("Add_Location_Demo", day0 + 11 * h, day0 + 12 * h)
    # 2a. recurring NO-attendee weekly event that recurs today (medium__calendar__001)
    ins("Weekly_Standup", day0 - 9 * 24 * h + 9 * h, day0 - 9 * 24 * h + 10 * h,
        rrule=f"FREQ=WEEKLY;BYDAY={wd};COUNT=52")
    # 2b. OUTDATED recurring series (ended last month) -> agent should delete it
    ins("Old_Gym_Class", day0 - 90 * 24 * h + 7 * h, day0 - 90 * 24 * h + 8 * h,
        rrule=f"FREQ=WEEKLY;BYDAY={wd};UNTIL=20260701T000000Z")
    # 3. meeting this week 08:30 (before 9am) for the hard reschedule task
    ins("Project_Review", day0 + 8 * h + 30 * 60_000, day0 + 9 * h + 30 * 60_000)
    print("seeded calendar events into cal_id=16 (Google-synced)")


def cleanup_test_events(serial: str) -> None:
    """Remove the throwaway test events created while probing (local-account TeamSync)."""
    adb(serial, "shell", "content", "delete", "--uri", "content://com.android.calendar/events",
        "--where", "title='TeamSync'")


def attempt_content_seeds(serial: str, cfg: dict[str, str]) -> None:
    """Try SMS + call-log inserts; report honestly if the non-rooted device blocks them."""
    print("attempting SMS insert (usually blocked on non-rooted)...")
    body = (f"Your {cfg['search word']} for Saturday is confirmed. "
            "Show this at the gate.")
    rc, out = adb(serial, "shell", "content", "insert", "--uri", "content://sms",
                  "--bind", "address:s:+919876501234",
                  "--bind", f"body:s:{body}",
                  "--bind", "date:l:" + str(int(NOW) * 1000), "--bind", "read:i:1")
    print(f"  SMS insert rc={rc}: {out[:120] or 'OK'}")

    print("attempting call-log insert (usually allowed)...")
    rc2, out2 = adb(serial, "shell", "content", "insert", "--uri", "content://call_log/calls",
                    "--bind", f"number:s:{cfg['digits']}000001", "--bind", "type:i:1",
                    "--bind", "date:l:" + str(int(NOW) * 1000), "--bind", "duration:i:45")
    print(f"  call-log insert rc={rc2}: {out2[:120] or 'OK'}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", required=True)
    parser.add_argument("--no-push", action="store_true", help="Only materialise seed files, don't touch the device.")
    args = parser.parse_args()
    if not (DAY_DIR / "manifests.json").exists():
        raise SystemExit("No seeds/full_tasks/day_1/manifests.json - run scripts/build_day_seed_manifest.py --day 1 first")

    make_seed_images()
    if args.no_push:
        return 0
    cfg = load_user_config(CONFIG_PATH)
    push_seed_images(args.serial)
    push_obsidian_seed(args.serial, cfg)
    cleanup_test_events(args.serial)
    seed_calendar_events(args.serial)
    attempt_content_seeds(args.serial, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
