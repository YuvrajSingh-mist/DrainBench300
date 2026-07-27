# DrainBench Harness

## What this does

`drainbench_runner.py` runs one task and collects:

- battery snapshots from `adb shell dumpsys battery`
- thermal snapshots from `adb shell dumpsys thermalservice`
- a full host-side recording using `scrcpy --record`
- stdout/stderr for the benchmark command itself

It writes one run folder per task under `runs/`.

## Why this implementation

- `dumpsys battery` gives you stable host-side access to battery level, charge counter, and vendor battery readings while keeping the benchmark untethered over Wi-Fi ADB.
- `dumpsys thermalservice` exposes HAL-backed `CPU`, `GPU`, `BATTERY`, and `SKIN` temperatures plus overall thermal status.
- This phone blocks `adb shell screenrecord` file writes, so host-side `scrcpy --record` is the reliable path for per-task social-share recordings.

## Example

Set your wireless ADB serial once:

```bash
export DRAINBENCH_SERIAL=172.18.11.243:5555
```

Run a task through the harness:

```bash
python3 drainbench_runner.py \
  --label gmail-self-email \
  --sample-interval 1.0 \
  -- \
  /Users/yuvrajsingh9886/.local/bin/mobilerun run \
  "Open the email app and send an email to the current account holder with the exact message body: hi. Do not send email to anyone else." \
  --temperature 0 --steps 20 --debug -d 172.18.11.243:5555
```

## Outputs

Each run folder contains:

- `meta.json`
- `preflight.json`
- `postflight.json`
- `samples.ndjson`
- `summary.json`
- `command.stdout.txt`
- `command.stderr.txt`
- `screen.mp4` when recording is enabled

## Suggested reporting fields

Use `summary.json` as the main benchmark artifact:

- `elapsed_seconds`
- `command_exit_code`
- `battery_level_start_pct`
- `battery_level_end_pct`
- `charge_counter_delta_uah`
- `skin_temp_max_c`
- `battery_temp_max_c`
- `cpu_temp_max_c`
- `thermal_status_max`

## Notes

- Keep USB unplugged during the measured run.
- Start timing only after wireless ADB is confirmed.
- `vendor_battery_current_raw` is preserved as a device-specific raw value; use it comparatively on the same phone rather than as a universal unit.
- `scrcpy` capture in this harness is started with `--no-audio`.
