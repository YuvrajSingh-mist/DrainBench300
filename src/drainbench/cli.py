"""CLI entrypoint for one DrainBench run."""

from __future__ import annotations

import argparse
import os
import subprocess
import time

from .adb import capture_sample, read_jsonl, utc_now, wait_briefly
from .files import make_run_dir, write_json, write_text
from .processes import start_llm_proxy, start_scrcpy, stop_process
from .sampler import Sampler
from .summary import extract_task_output, summarize


def build_parser() -> argparse.ArgumentParser:
    """Build the DrainBench CLI parser."""
    parser = argparse.ArgumentParser(description="Run one benchmarked Droidrun task with device and LLM metrics.")
    parser.add_argument("--serial", default=os.environ.get("DRAINBENCH_SERIAL"))
    parser.add_argument("--label", required=True)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--out-dir", default="runs")
    parser.add_argument("--screen-bit-rate", default="8M")
    parser.add_argument("--screen-size", default=None)
    parser.add_argument("--no-screen-record", action="store_true")
    parser.add_argument("--llm-upstream-base", default=None)
    parser.add_argument("--llm-proxy-port", type=int, default=8090)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main() -> int:
    """Run one fully instrumented benchmark task and write one run folder."""
    args = build_parser().parse_args()
    if not args.serial:
        raise SystemExit("ADB serial required via --serial or DRAINBENCH_SERIAL")
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        raise SystemExit("Benchmark command required after --")
    run_dir = make_run_dir(args.out_dir, args.label)
    meta = {"run_id": run_dir.name, "label": args.label, "serial": args.serial, "started_at_utc": utc_now(), "command": command, "sample_interval_seconds": args.sample_interval}
    write_json(run_dir / "meta.json", meta)
    write_json(run_dir / "preflight.json", capture_sample(args.serial))
    llm_entries: list[dict] = []
    llm_proxy = None
    if args.llm_upstream_base:
        llm_proxy, port, llm_log = start_llm_proxy(run_dir, args.llm_upstream_base, args.llm_proxy_port)
        command = [part.replace("http://127.0.0.1:8090/v1", f"http://127.0.0.1:{port}/v1") for part in command]
        meta.update({"command": command, "llm_proxy_port": port, "llm_proxy_base": f"http://127.0.0.1:{port}/v1", "llm_proxy_upstream_base": args.llm_upstream_base, "llm_log_jsonl": str(llm_log)})
        write_json(run_dir / "meta.json", meta)
        wait_briefly(2)
    recording = None if args.no_screen_record else start_scrcpy(args.serial, run_dir, args.screen_bit_rate, args.screen_size)
    sampler = Sampler(args.serial, args.sample_interval, run_dir / "samples.ndjson")
    sampler.start()
    start_monotonic = time.monotonic()
    with (run_dir / "command.stdout.txt").open("w") as out_handle, (run_dir / "command.stderr.txt").open("w") as err_handle:
        proc = subprocess.Popen(command, stdout=out_handle, stderr=err_handle)
        return_code = proc.wait()
    elapsed = time.monotonic() - start_monotonic
    sampler.stop()
    if recording is not None:
        meta["screenrecord_exit_code"] = stop_process(recording, sigint=True)
    if llm_proxy is not None:
        meta["llm_proxy_exit_code"] = stop_process(llm_proxy)
        llm_entries = read_jsonl(meta["llm_log_jsonl"], 0)
        write_json(run_dir / "llm_metrics.json", llm_entries)
    write_json(run_dir / "postflight.json", capture_sample(args.serial))
    meta.update({"ended_at_utc": utc_now(), "elapsed_seconds": elapsed, "command_exit_code": return_code, "sampler_errors": sampler.errors})
    write_json(run_dir / "meta.json", meta)
    stdout_text = (run_dir / "command.stdout.txt").read_text(encoding="utf-8", errors="ignore")
    write_text(run_dir / "output.txt", extract_task_output(stdout_text))
    summary = summarize(sampler.samples, meta, llm_entries)
    write_json(run_dir / "summary.json", summary)
    print(f"Run directory: {run_dir}")
    print((run_dir / "summary.json").read_text())
    return return_code
