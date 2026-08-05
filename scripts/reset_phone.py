#!/usr/bin/env python3
"""Reset the DrainBench benchmark phone to its pre-run baseline (non-rooted).

Undoes agent-created run artifacts (settings, blocked numbers, calendar events,
contact edits, run downloads) and verifies the fabricated seed baseline is still
present. Does NOT wipe the seed data.

SAFETY: dry-run by default. Pass --apply to actually make changes. Only run on
the dedicated benchmark device (fabricated persona data), never a personal phone.

Usage:
  uv run python scripts/reset_phone.py --serial 100.108.15.119:5555 --profile public_v2            # dry-run
  uv run python scripts/reset_phone.py --serial 100.108.15.119:5555 --profile public_v2 --apply    # reset
  uv run python scripts/reset_phone.py --serial 100.108.15.119:5555 --profile public_v2 --verify-only
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# --- profile: known run-artifact + seed facts for the public 50-task dataset ---
PROFILES: dict[str, dict] = {
    "public_v2": {
        # settings to restore: key:value where key = "system|secure|global:name"
        "settings": {"system:screen_off_timeout": "1800000"},
        # numbers the agent blocked during runs (run artifacts) - these get removed
        "blocked_numbers_to_remove": [
            "+912071167023", "+917968179241", "+917968179245", "+911600108194",
        ],
        # calendar event titles the agent created (run artifacts) - soft-deleted
        "calendar_titles_to_remove": [
            "Dentist appointment", "Dentist Appointment",
            "Wish Yuvraj Singh a happy birthday!", "Card Payment Due",
            "Maa's Birthday", "Yuvraj Singh's Birthday", "Hariom Sharma EVS's Birthday",
        ],
        # Downloads paths the agent created during runs - removed (quotes preserved)
        "downloads_to_remove": [
            "/sdcard/Download/Food Photos≠Memories 2021-23",
            "/sdcard/Download/PURCHASE_ORDER (1).xlsx",
            "/sdcard/Download/PURCHASE_ORDER (1) (1).xlsx",
            "/sdcard/Download/PURCHASE_ORDER (1) (2).xlsx",
            "/sdcard/Download/Q3_Report.pdf",
        ],
        # seed files that MUST be present after reset (baseline verify)
        "seed_files": [
            "/sdcard/Download/PURCHASE_ORDER.xlsx",
            "/sdcard/Download/SPORTS_VIDEO_DATA.xlsx",
            "/sdcard/Download/budget.xlsx",
            "/sdcard/Download/quote.xlsx",
        ],
        # seed calendar events that MUST be present on the Google-synced calendar
        "seed_calendar_titles": [
            "shareholder AlphaCorp Q2 Review",
            "shareholder BetaTech Strategy",
            "shareholder GammaFund Governance",
        ],
        # the contact that runs mangle (easy-contacts-001) - restored to this name
        "contact_email": "akashveyron33@gmail.com",
        "contact_display": "Akash Kumar",
        "contact_given": "Akash",
        "contact_last": "Kumar",
    },
}

CAL_URI = "content://com.android.calendar/events"
CONTACTS_DATA_URI = "content://com.android.contacts/data"
CONTACTS_URI = "content://com.android.contacts/contacts"
BLOCKED_URI = "content://com.android.blockednumber/blocked"


def sh(serial: str, cmd: str, check: bool = False) -> str:
    """Run a command on the device shell, return stdout."""
    proc = subprocess.run(
        ["adb", "-s", serial, "shell", cmd], capture_output=True, text=True
    )
    if check and proc.returncode != 0:
        print(f"  !! adb failed ({proc.returncode}): {cmd}")
        print("  " + proc.stderr.strip()[:300])
    return proc.stdout


def connect_ok(serial: str) -> bool:
    out = subprocess.run(
        ["adb", "-s", serial, "shell", "echo", "OK"], capture_output=True, text=True
    )
    return out.returncode == 0 and "OK" in out.stdout


def quote(s: str) -> str:
    """Single-quote a string for the remote sh, escaping embedded single quotes."""
    return "'" + s.replace("'", "'\\''") + "'"


def reset_settings(serial: str, settings: dict[str, str], apply: bool) -> None:
    for key, value in settings.items():
        ns, _, name = key.partition(":")
        cur = sh(serial, f"settings get {ns} {name}").strip()
        action = f"settings put {ns} {name} {value}   (was: {cur!r})"
        if apply:
            sh(serial, action, check=True)
            print(f"  [ok]  {action}")
        else:
            print(f"  [dry] {action}")


def unblock_numbers(serial: str, numbers: list[str], apply: bool) -> None:
    rows = sh(serial, f"content query --uri {BLOCKED_URI}")
    for num in numbers:
        present = re.search(rf"e164_number={re.escape(num)}", rows)
        if apply:
            if present:
                sh(
                    serial,
                    f"content delete --uri {BLOCKED_URI} --where \"original_number='{num}'\"",
                    check=True,
                )
                print(f"  [ok]  unblocked {num}")
            else:
                print(f"  [--]  {num} not blocked (already clean)")
        else:
            print(f"  [dry] unblock {num} (present={bool(present)})")


def remove_calendar_events(serial: str, titles: list[str], apply: bool) -> None:
    rows = sh(serial, f"content query --uri {CAL_URI} --projection _id:title:deleted")
    ids: list[str] = []
    for line in rows.splitlines():
        m = re.search(r"_id=(\d+),", line)
        t = re.search(r"title=([^,]*),", line)
        d = re.search(r"deleted=([01])", line)
        if not (m and t and d):
            continue
        if d.group(1) == "1":
            continue  # already deleted
        title = t.group(1).strip()
        if any(title == want for want in titles):
            ids.append(m.group(1))
    if apply and ids:
        where = ",".join(ids)
        sh(serial, f"content delete --uri {CAL_URI} --where \"_id IN ({where})\"", check=True)
        print(f"  [ok]  soft-deleted {len(ids)} run-artifact events: {ids}")
    elif apply:
        print("  [--]  no run-artifact calendar events to delete")
    else:
        print(f"  [dry] soft-delete run-artifact events (matched ids): {ids or 'none'}")


def restore_contact(serial: str, prof: dict, apply: bool) -> None:
    rows = sh(
        serial,
        f"content query --uri {CONTACTS_DATA_URI} --projection _id:raw_contact_id:mimetype:data1:data2:data3:data4 --where \"mimetype='vnd.android.cursor.item/email_v2'\"",
    )
    raw_id = None
    for line in rows.splitlines():
        m = re.search(r"data1=([^,]*),", line)
        r = re.search(r"raw_contact_id=(\d+),", line)
        if m and r and m.group(1).strip() == prof["contact_email"]:
            raw_id = r.group(1)
            break
    if raw_id is None:
        print("  [--]  target contact not found; nothing to restore")
        return
    name_rows = sh(
        serial,
        f"content query --uri {CONTACTS_DATA_URI} --projection _id:mimetype:data1:data2:data3:data4 --where \"raw_contact_id={raw_id}\"",
    )
    name_id = org_id = None
    for line in name_rows.splitlines():
        if "vnd.android.cursor.item/name" in line:
            m = re.search(r"_id=(\d+),", line)
            name_id = m.group(1) if m else name_id
        if "vnd.android.cursor.item/organization" in line and "Sahoo" in line:
            m = re.search(r"_id=(\d+),", line)
            org_id = m.group(1) if m else org_id
    if apply:
        if name_id:
            sh(
                serial,
                f"content update --uri {CONTACTS_DATA_URI} --bind \"data1:s:{prof['contact_display']}\" --bind \"data2:s:{prof['contact_given']}\" --bind \"data3:s:{prof['contact_last']}\" --bind \"data4:s:\" --where \"_id={name_id}\"",
                check=True,
            )
        if org_id:
            sh(serial, f"content delete --uri {CONTACTS_DATA_URI} --where \"_id={org_id}\"", check=True)
        print(f"  [ok]  restored contact {prof['contact_display']} (name_row={name_id}, org_row={org_id})")
    else:
        print(f"  [dry] restore contact -> {prof['contact_display']} (name_row={name_id}, org_row={org_id})")


def remove_downloads(serial: str, paths: list[str], apply: bool) -> None:
    for path in paths:
        if apply:
            sh(serial, f"rm -rf {quote(path)}", check=True)
            print(f"  [ok]  rm {path}")
        else:
            print(f"  [dry] rm {path}")


def verify(serial: str, prof: dict) -> bool:
    ok = True
    print("== baseline verify ==")
    for key, value in prof["settings"].items():
        ns, _, name = key.partition(":")
        cur = sh(serial, f"settings get {ns} {name}").strip()
        good = cur == value
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'} settings {ns}:{name} = {cur!r} (want {value!r})")
    rows = sh(serial, f"content query --uri {BLOCKED_URI}")
    for num in prof["blocked_numbers_to_remove"]:
        gone = not re.search(rf"e164_number={re.escape(num)}", rows)
        ok &= gone
        print(f"  {'PASS' if gone else 'FAIL'} blocked {num} absent")
    ev = sh(serial, f"content query --uri {CAL_URI} --projection _id:title:_sync_id:deleted")
    for title in prof["seed_calendar_titles"]:
        present = title in ev and "deleted=1" not in _line_for(ev, title)
        ok &= present
        synced = bool(re.search(rf"title={re.escape(title)}[^,]*, _sync_id=[^,]", ev))
        print(f"  {'PASS' if present else 'FAIL'} calendar seed '{title}' present (synced={synced})")
    for path in prof["seed_files"]:
        has = sh(serial, f"ls {quote(path)}").strip() != ""
        ok &= has
        print(f"  {'PASS' if has else 'FAIL'} seed file {path}")
    ca = sh(serial, f"content query --uri {CONTACTS_URI} --projection _id:display_name")
    name_ok = prof["contact_display"].lower() in ca.lower()
    ok &= name_ok
    print(f"  {'PASS' if name_ok else 'FAIL'} contact '{prof['contact_display']}' present")
    return ok


def _line_for(haystack: str, title: str) -> str:
    for line in haystack.splitlines():
        if title in line:
            return line
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset benchmark phone to pre-run baseline (dry-run by default).")
    parser.add_argument("--serial", required=True, help="ADB serial (device id or ip:port)")
    parser.add_argument("--profile", default="public_v2", choices=sorted(PROFILES))
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default is dry-run)")
    parser.add_argument("--verify-only", action="store_true", help="Only verify baseline; make no changes")
    args = parser.parse_args()

    if args.serial not in ("RS7XKZDI8HTOJNYL", "100.108.15.119:5555"):
        print(f"WARN: serial {args.serial} is not the known benchmark device; continuing anyway.")

    if not connect_ok(args.serial):
        print(f"FATAL: cannot reach {args.serial} (run `adb connect {args.serial}` or `adb -s RS7XKZDI8HTOJNYL tcpip 5555`)")
        return 1

    prof = PROFILES[args.profile]
    if not args.verify_only:
        print(f"== reset (profile={args.profile}, apply={args.apply}) ==")
        reset_settings(args.serial, prof["settings"], args.apply)
        unblock_numbers(args.serial, prof["blocked_numbers_to_remove"], args.apply)
        remove_calendar_events(args.serial, prof["calendar_titles_to_remove"], args.apply)
        restore_contact(args.serial, prof, args.apply)
        remove_downloads(args.serial, prof["downloads_to_remove"], args.apply)
        print("== UI-only manual cleanups (no ADB) — see .agents/skills/reset-phone/SKILL.md ==")

    ok = verify(args.serial, prof)
    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
