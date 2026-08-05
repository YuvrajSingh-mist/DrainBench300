#!/usr/bin/env python3
"""Deterministically reduce DrainBench 730 -> 530 tasks, preserving the
easy/medium/hard split, the 50/50 ASK USER / DETERMINISTIC hard split, the
cross-app medium share, and app coverage -- while landing each day at the
real-world ~9-10 distinct-app density (see docs/app-usage-grounding.md).

Method (no RNG; fully deterministic given the source dataset):
- Hard (100 -> 72 = 36 ASK USER / 36 DETERMINISTIC): drop exactly ONE hard task
  per day. All-AU days and all-DET days force their drop type; the remaining
  AU/DET drop budget is spread over the mixed days so the global 50/50 split
  survives exactly (36/36).
- Easy (315 -> 229) and single-app medium (274 -> 199): per-day largest-remainder
  allocation of the target, then within each day pick round-robin by app
  (fewest-kept-so-far wins, app name as tie-break) so every app keeps a spread of
  active days across the month instead of clustering.
- Cross-app (two-app) medium (41 -> 30): kept at the same share (~13%), allocated
  per-day and picked round-robin by the composite app pair.
- Original task_ids are preserved (gaps are intentional: they trace back to the
  parent 730 set); per-task fields are carried over unchanged.

Usage:
    uv run python scripts/build_530_subset.py [--out ...] [--dry-run]
"""
import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

SRC = "benchmarks/dailyBench-600/DailyBench_730_v4.json"
OUT = "benchmarks/dailyBench-600/DailyBench_530_v1.json"

EASY_TARGET = 229
MED_TARGET = 229
HARD_TARGET = 72  # -> 36 ASK USER / 36 DETERMINISTIC


def largest_remainder(items, weights, target):
    """Allocate `target` slots across items proportional to `weights` using the
    largest-remainder method. Returns {item: count} summing exactly to target."""
    total_w = sum(weights.values())
    raw = {it: w * target / total_w for it, w in weights.items()}
    alloc = {it: math.floor(v) for it, v in raw.items()}
    remaining = target - sum(alloc.values())
    order = sorted(items, key=lambda it: (raw[it] - alloc[it], it), reverse=True)
    for it in order[:remaining]:
        alloc[it] += 1
    return alloc


def allocate_per_day(counts, target):
    """Largest-remainder allocation of `target` slots across days."""
    return largest_remainder(list(counts), counts, target)


def pick_by_day(tasks, target, kept_so_far, key_app):
    """Per-day largest-remainder allocation of `target`, then within each day
    pick round-robin by app: apps with the fewest kept-so-far win (tie-break:
    app name, then task_id). Keeps every app spread across the month."""
    by_day = defaultdict(list)
    for t in tasks:
        by_day[t["day"]].append(t)
    counts = {d: len(lst) for d, lst in by_day.items()}
    alloc = allocate_per_day(counts, target)
    kept = []
    for day in sorted(by_day):
        lst = sorted(by_day[day], key=lambda t: (key_app(t), t["task_id"]))
        apps = defaultdict(list)
        for t in lst:
            apps[key_app(t)].append(t)
        order = sorted(apps, key=lambda a: (kept_so_far.get(a, 0), a))
        want = alloc[day]
        picked = []
        for app in order:
            if len(picked) >= want:
                break
            picked.append(apps[app][0])  # 1 task per app per day (mostly)
            kept_so_far[app] = kept_so_far.get(app, 0) + 1
        if len(picked) < want:  # safety: day shorter than allocation
            for app in order:
                for t in apps[app]:
                    if len(picked) >= want:
                        break
                    if t not in picked:
                        picked.append(t)
        kept.extend(picked)
    return kept


def pick_hard(tasks):
    """Drop exactly one hard task per day. All-AU and all-DET days force their
    drop type; the remaining AU/DET drop budget is spread over the mixed days so
    the global split lands exactly 36 ASK USER / 36 DETERMINISTIC."""
    by_day = defaultdict(list)
    for t in tasks:
        by_day[t["day"]].append(t)

    AU_DROP = 50 - (HARD_TARGET // 2)                 # 14
    DET_DROP = 50 - (HARD_TARGET - HARD_TARGET // 2)  # 14

    forced_au, forced_det, mixed = [], [], []
    for day in sorted(by_day):
        has_au = any(t["is_ask_user"] for t in by_day[day])
        has_det = any(not t["is_ask_user"] for t in by_day[day])
        if not has_au:
            forced_det.append(day)
        elif not has_det:
            forced_au.append(day)
        else:
            mixed.append(day)

    au_mixed = AU_DROP - len(forced_au)      # 10
    det_mixed = DET_DROP - len(forced_det)   # 9
    drop_type = {}
    for i, day in enumerate(mixed):
        drop_type[day] = "AU" if i < au_mixed else "DET"

    dropped_ids = set()
    for day in sorted(by_day):
        if day in forced_au:
            tp = "AU"
        elif day in forced_det:
            tp = "DET"
        else:
            tp = drop_type[day]
        pool = [t for t in by_day[day]
                if t["is_ask_user"] == (tp == "AU")]
        victim = max(pool, key=lambda t: t["task_number_within_dataset_app"])
        dropped_ids.add(victim["task_id"])

    kept = [t for t in tasks if t["task_id"] not in dropped_ids]
    dropped = [t for t in tasks if t["task_id"] in dropped_ids]
    return kept, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--dry-run", action="store_true",
                    help="print verification only, do not write")
    args = ap.parse_args()

    with open(SRC) as f:
        data = json.load(f)
    tasks = data["tasks"]
    order = {id(t): i for i, t in enumerate(tasks)}

    easy_all = [t for t in tasks if t["bucket"] == "easy"]
    med_all = [t for t in tasks if t["bucket"] == "medium"]
    hard_all = [t for t in tasks if t["bucket"] == "hard"]

    assert len(easy_all) == 315 and len(med_all) == 315 and len(hard_all) == 100

    # --- hard: 72 (36 AU / 36 DET), drop 1/day ---
    hard_kept, hard_dropped = pick_hard(hard_all)

    # --- medium: cross-app proportional + single-app remainder ---
    cross = [t for t in med_all if t.get("is_cross_app") or t.get("num_apps", 1) > 1]
    single = [t for t in med_all if t not in cross]
    cross_keep = max(1, round(len(cross) * MED_TARGET / len(med_all)))  # ~30

    kept_so_far_cross = defaultdict(int)
    med_cross_kept = pick_by_day(
        cross, cross_keep, kept_so_far_cross,
        key_app=lambda t: "+".join(sorted(t["apps"])))

    kept_so_far_med = defaultdict(int)
    med_single_kept = pick_by_day(
        single, MED_TARGET - len(med_cross_kept), kept_so_far_med,
        key_app=lambda t: t["app"])
    med_kept = med_single_kept + med_cross_kept

    # --- easy: 229 ---
    kept_so_far_easy = defaultdict(int)
    easy_kept = pick_by_day(easy_all, EASY_TARGET, kept_so_far_easy,
                            key_app=lambda t: t["app"])

    kept = sorted(easy_kept + med_kept + hard_kept,
                  key=lambda t: (t["day"], order[id(t)]))

    # --- bake ask_user facts inline so the subset is self-contained ---
    facts_path = Path("benchmarks/dailyBench-600/ask_user_facts_730.json")
    if facts_path.exists():
        facts = json.loads(facts_path.read_text(encoding="utf-8"))
        baked = 0
        for t in kept:
            if t["task_id"] in facts:
                t["ask_user_fact"] = facts[t["task_id"]]
                baked += 1
        print(f"  ask_user facts baked inline: {baked}")

    # ---------- verification ----------
    bc = Counter(t["bucket"] for t in kept)
    au = sum(1 for t in kept if t.get("is_ask_user"))
    det = sum(1 for t in kept if t["bucket"] == "hard" and not t["is_ask_user"])
    per_day = defaultdict(lambda: Counter())
    apps_day = defaultdict(set)
    for t in kept:
        per_day[t["day"]][t["bucket"]] += 1
        apps_day[t["day"]].update(t["apps"])

    base_apps = sorted({t["app"] for t in easy_kept} | {t["app"] for t in med_single_kept})
    base_easy_cov = Counter(t["app"] for t in easy_kept)
    base_med_cov = Counter(t["app"] for t in med_single_kept)
    missing_easy = [a for a in base_apps if base_easy_cov[a] == 0]
    missing_med = [a for a in base_apps if base_med_cov[a] == 0]

    print(f"kept total: {len(kept)}  (target 530)")
    print(f"  easy={bc['easy']} (229)  medium={bc['medium']} (229)  hard={bc['hard']} (72)")
    print(f"  hard ASK USER={au}  DETERMINISTIC={det}  (36/36)")
    print(f"  cross-app medium kept: {len(med_cross_kept)} of {len(cross)}")
    print(f"  base apps covered: {len(base_apps)}/22"
          + (f"  MISSING easy:{missing_easy} med:{missing_med}"
             if missing_easy or missing_med else ""))
    print("\nper-day: easy / medium / hard = total | distinct apps")
    lows = highs = 0
    for day in sorted(per_day):
        c = per_day[day]
        n = sum(c.values())
        if n < 15:
            lows += 1
        if n > 24:
            highs += 1
        print(f"  d{day:>2}: {c['easy']:>2}/{c['medium']:>2}/{c['hard']:>2} = {n:>2} | {len(apps_day[day]):>2} apps")
    app_counts = [len(apps_day[d]) for d in apps_day]
    print(f"\n  days under 15 tasks: {lows}   days over 24 tasks: {highs}")
    print(f"  apps/day: min {min(app_counts)}  max {max(app_counts)}  avg {sum(app_counts)/len(app_counts):.1f}")
    print(f"  min tasks any base app kept: {min(Counter(t['app'] for t in easy_kept + med_single_kept).values())}")

    ok = (len(kept) == 530 and bc["easy"] == 229 and bc["medium"] == 229
          and bc["hard"] == 72 and au == 36 and det == 36
          and not missing_easy and not missing_med and lows == 0 and highs == 0)
    print(f"\nall checks {'PASS' if ok else 'FAIL'}")

    if args.dry_run or not ok:
        sys.exit(0 if ok else 1)

    out_data = {
        "dataset_name": "DrainBench 530 (28-day survival schedule)",
        "dataset_version": "v1",
        "parent": "DailyBench_730_v4.json",
        "source_path": SRC,
        "task_count": len(kept),
        "bucket_counts": {k: bc[k] for k in ("easy", "medium", "hard")},
        "selection": "scripts/build_530_subset.py: hard drop-1/day (36 AU/36 DET); "
                     "easy+medium per-app largest-remainder with even spacing; "
                     "cross-app medium kept proportionally by day",
        "tasks": kept,
    }
    with open(args.out, "w") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)
    print(f"\nwrote {args.out}")
    # JSONL sibling: one task per line, same format as the export pipeline's
    # save_dataset_files (so both artifacts stay consistent).
    jsonl_out = Path(args.out).with_suffix(".jsonl")
    with jsonl_out.open("w", encoding="utf-8") as handle:
        for task in kept:
            handle.write(json.dumps(task, ensure_ascii=False) + "\n")
    print(f"wrote {jsonl_out} ({len(kept)} lines)")


if __name__ == "__main__":
    main()
