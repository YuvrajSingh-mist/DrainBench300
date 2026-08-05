#!/usr/bin/env python3
"""Completeness verifier for the user config.

Checks that config/user.yaml resolves EVERY value a run actually needs, so a new
user gets "you still need to fill X" instead of a silent wrong-value run:

  REQUIRED (exit 1 if any gap):
    - every task prompt placeholder ([...]) on the runnable Day-1 subset,
    - every ASK USER fact template ({...}) in ask_user_facts_730.json,
    - every fabricated-seed {key} in the Day-1 seed spec + seed-file templates.

  ADVISORY (reported, not fatal):
    - prompt placeholders on days 2-28 that aren't parameterized yet,
    - config keys that no task/fact/seed uses (possible typo).

Run:  uv run python scripts/verify_config.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from DailyBench.user_config import SCHEMA, load_user_config, template_keys  # noqa: E402

DATASET_730 = REPO_ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_730_v4.json"
DATASET_530 = REPO_ROOT / "benchmarks" / "dailyBench-600" / "DailyBench_530_v1.json"
FACTS = REPO_ROOT / "benchmarks" / "dailyBench-600" / "ask_user_facts_730.json"
MANIFEST_SCRIPT = REPO_ROOT / "scripts" / "build_day_seed_manifest.py"
CONFIG_PATH = REPO_ROOT / "config" / "user.yaml"

# {key} names that are natural-language directives, NOT config placeholders
# (e.g. "{today's date}" in the note-title template). Ignored by the verifier.
NON_CONFIG_TEMPLATES = {"today's date"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def collect_keys(obj) -> set[str]:
    """Every {key} referenced in a nested dict/list/str."""
    if isinstance(obj, str):
        return set(template_keys(obj))
    if isinstance(obj, dict):
        keys: set[str] = set()
        for v in obj.values():
            keys |= collect_keys(v)
        return keys
    if isinstance(obj, list):
        keys = set()
        for v in obj:
            keys |= collect_keys(v)
        return keys
    return set()


def main() -> int:
    cfg = load_user_config(CONFIG_PATH)
    missing_required: list[str] = []

    # ---- prompt placeholders (730 corpus; Day-1 REQUIRED, others advisory) ----
    corpus = json.loads(DATASET_730.read_text(encoding="utf-8"))["tasks"]
    runnable = json.loads(DATASET_530.read_text(encoding="utf-8"))["tasks"]
    runnable_day1_ids = {t["task_id"] for t in runnable if t.get("day") == 1}

    per_day_unresolved: dict[int, set[str]] = defaultdict(set)
    day1_gaps: list[str] = []
    for t in corpus:
        day = t.get("day")
        for ph in t.get("placeholders") or []:
            if ph in cfg:
                continue
            if day == 1 and t["task_id"] in runnable_day1_ids:
                day1_gaps.append(f"  day1 {t['task_id']}: placeholder [{ph}] has no config value")
            else:
                per_day_unresolved[day].add(ph)

    # ---- ASK USER facts (REQUIRED) ----
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    for task_id, fact in facts.items():
        for key in template_keys(fact):
            if key in NON_CONFIG_TEMPLATES:
                continue
            if key not in cfg:
                missing_required.append(f"fact {task_id}: {key!r} (in {fact!r})")

    # ---- Day-1 seeds (REQUIRED) ----
    man = load_module("build_day_seed_manifest", MANIFEST_SCRIPT)
    for task_id, spec in man.DAY1_TASKS.items():
        for key in sorted(collect_keys(spec)):
            if key in NON_CONFIG_TEMPLATES:
                continue
            if key not in cfg:
                missing_required.append(f"seed {task_id}: {key!r}")
    for task_id, files in man.SEED_FILE_TEMPLATES.items():
        for key in sorted(collect_keys(files)):
            if key not in cfg:
                missing_required.append(f"seed-file {task_id}: {key!r}")

    # ---- unused config keys (advisory) ----
    used = set()
    for t in corpus:
        used.update(t.get("placeholders") or [])
    for task_id, fact in facts.items():
        used.update(template_keys(fact))
    for spec in man.DAY1_TASKS.values():
        used |= collect_keys(spec)
    for files in man.SEED_FILE_TEMPLATES.values():
        used |= collect_keys(files)
    unused = sorted(set(cfg) - used)
    unknown = sorted(set(cfg) - set(SCHEMA))

    # ---- report ----
    print(f"config: {CONFIG_PATH} ({len(cfg)} keys)")
    print(f"\nREQUIRED checks:")
    print(f"  Day-1 prompt placeholders: "
          + ("ALL RESOLVED" if not day1_gaps else f"{len(day1_gaps)} GAP(S)"))
    for g in day1_gaps:
        print(g)
    print(f"  ASK USER facts: " + ("ALL RESOLVED" if not missing_required else "GAPS BELOW"))
    for m in missing_required:
        print("   -", m)

    print(f"\nADVISORY (days 2-28, not yet parameterized):")
    if per_day_unresolved:
        for day in sorted(per_day_unresolved):
            phs = sorted(per_day_unresolved[day])
            print(f"  day {day:>2}: {len(phs)} placeholder(s) to fill: {', '.join(phs[:12])}"
                  + (" ..." if len(phs) > 12 else ""))
    else:
        print("  (none)")
    if unknown:
        print(f"\n  config keys not in schema (possible typo): {', '.join(unknown)}")
    if unused:
        print(f"  config keys never used by any placeholder/fact/seed: {', '.join(unused)}")

    ok = not day1_gaps and not missing_required
    print(f"\nRESULT: {'PASS - Day 1 is fully configured' if ok else 'FAIL - fill the required gaps above'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
