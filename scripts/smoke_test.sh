#!/usr/bin/env bash
# Smoke-tests the full DailyBench300 stack before a real benchmark run:
#
#   1. local prerequisites (adb, curl, uv, the mobilerun SDK import)
#   2. the OpenAI-compatible LLM server (llama.cpp, vLLM, Ollama's OpenAI shim, ...)
#   3. ADB reachability over USB (wired) and over TCP/IP (wireless)
#   4. mobilerun/Portal health on whichever device(s) are reachable
#   5. optionally, one real end-to-end DailyBench task through the harness itself
#
# Fully agnostic: every URL/serial is overridable via env var or flag - nothing here
# is hardcoded to one phone or one model host. mobilerun is driven purely through its
# Python SDK here (no `mobilerun` CLI involved anywhere), matching the rest of this
# harness - step 4 shells out to scripts/device_health_check.py, a small SDK-only
# helper built on `mobilerun.AndroidDriver` (see
# https://docs.mobilerun.ai/framework/sdk/adb-tools). See also
# https://docs.mobilerun.ai/framework/quickstart and
# https://docs.mobilerun.ai/framework/sdk/configuration (LLM provider / api_base setup).
#
# Usage: scripts/smoke_test.sh [options]     (run --help for the full option list)

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# ---------------------------------------------------------------------------
# Configuration - env var default, overridable by flag. Nothing here assumes a
# specific phone, model host, or LLM backend.
# ---------------------------------------------------------------------------
LLM_URL="${LLM_UPSTREAM:-${LLM_URL:-http://127.0.0.1:8081/v1}}"
MODEL="${MODEL:-}"
USB_SERIAL="${USB_SERIAL:-}"
WIRELESS_SERIAL="${WIRELESS_SERIAL:-${DAILYBENCH_SERIAL:-}}"
WIRELESS_PORT="${WIRELESS_PORT:-5555}"
CURL_TIMEOUT="${SMOKE_TIMEOUT:-10}"
SMOKE_PROXY_PORT="${SMOKE_PROXY_PORT:-18099}"
SMOKE_STEPS="${SMOKE_STEPS:-3}"
SMOKE_GOAL="${SMOKE_GOAL:-Go to the home screen}"

RUN_LLM=1
RUN_WIRED=1
RUN_WIRELESS=1
RUN_AGENT_SMOKE=1
LIST_MODELS_ONLY=0

usage() {
  cat <<'EOF'
Usage: scripts/smoke_test.sh [options]

Smoke-tests the LLM server plus wired and wireless ADB/mobilerun connectivity
for DailyBench300, ending (by default) with one real one-step agent run through
the harness itself. Every target is configurable - nothing is hardcoded to one
phone or model host.

Options:
  --llm-url URL           OpenAI-compatible base URL, e.g. http://host:8081/v1
                          (env: LLM_UPSTREAM or LLM_URL; default: http://127.0.0.1:8081/v1)
  --model NAME            Model name for the LLM + agent smoke tests (env: MODEL).
                          If omitted, the first model ID from the server's own
                          GET /models response is used automatically. To pick a
                          specific one yourself, run --list-models first.
  --list-models           Print every model ID the --llm-url server reports
                          (GET /models) and exit - use this to find the exact
                          string to pass to --model, then rerun with it.
  --usb-serial SERIAL     Explicit wired ADB serial to test (auto-detected if omitted)
  --wireless-serial IP:PORT
                          Explicit wireless ADB serial to test
                          (env: WIRELESS_SERIAL or DAILYBENCH_SERIAL)
  --wireless-port PORT    Port to use when enabling `adb tcpip` mode (default: 5555)
  --timeout SECONDS       curl/network timeout in seconds (default: 10)
  --steps N               Step budget for the end-to-end agent smoke run (default: 3)
  --goal TEXT             Prompt for the end-to-end agent smoke run
                          (default: "Go to the home screen")
  --skip-llm              Skip the LLM server smoke test
  --skip-wired            Skip the wired ADB smoke test
  --skip-wireless         Skip the wireless ADB smoke test
  --skip-agent-run        Skip the real one-step MobileAgent end-to-end smoke test
  -h, --help              Show this help and exit

All of the above are also settable via env var (see the "env:" notes and the
"Configuration" block at the top of this script for the exact names). Flags win
over env vars.

Naming exactly one of --usb-serial / --wireless-serial automatically skips the
other transport's check (no need for a redundant --skip-wired/--skip-wireless) -
pass both, or neither, to check both transports.

Examples:
  # Everything auto-detected from env vars already exported by the README setup:
  ./scripts/smoke_test.sh

  # See exactly which model IDs a server offers, then pick one yourself:
  ./scripts/smoke_test.sh --llm-url http://192.168.1.50:8080/v1 --list-models
  ./scripts/smoke_test.sh --llm-url http://192.168.1.50:8080/v1 --model "<id from the list above>"

  # Point at a different llama.cpp box, skip the real agent run:
  ./scripts/smoke_test.sh --llm-url http://192.168.1.50:8080/v1 --model my-model --skip-agent-run

  # Only check a specific wireless phone, nothing else:
  ./scripts/smoke_test.sh --skip-llm --skip-wired --skip-agent-run --wireless-serial 192.168.1.23:5555
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --llm-url) LLM_URL="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --list-models) LIST_MODELS_ONLY=1; shift ;;
    --usb-serial) USB_SERIAL="$2"; shift 2 ;;
    --wireless-serial) WIRELESS_SERIAL="$2"; shift 2 ;;
    --wireless-port) WIRELESS_PORT="$2"; shift 2 ;;
    --timeout) CURL_TIMEOUT="$2"; shift 2 ;;
    --steps) SMOKE_STEPS="$2"; shift 2 ;;
    --goal) SMOKE_GOAL="$2"; shift 2 ;;
    --skip-llm) RUN_LLM=0; shift ;;
    --skip-wired) RUN_WIRED=0; shift ;;
    --skip-wireless) RUN_WIRELESS=0; shift ;;
    --skip-agent-run) RUN_AGENT_SMOKE=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

# --list-models is a standalone lookup, not a check - print the server's model
# IDs and exit immediately, before any of the pass/warn/fail machinery below.
if [[ "$LIST_MODELS_ONLY" -eq 1 ]]; then
  models_err_log="$(mktemp)"
  models_json="$(curl -sS --max-time "$CURL_TIMEOUT" "${LLM_URL%/}/models" 2>"$models_err_log")"
  curl_status=$?
  if [[ $curl_status -ne 0 || -z "$models_json" ]]; then
    echo "Could not reach ${LLM_URL%/}/models: $(cat "$models_err_log")" >&2
    rm -f "$models_err_log"
    exit 1
  fi
  rm -f "$models_err_log"
  model_ids="$(printf '%s' "$models_json" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    ids = [m.get("id", "?") for m in data.get("data", [])]
    print("\n".join(ids))
except Exception as exc:
    print(f"__PARSE_ERROR__ {exc}")
' 2>/dev/null)"
  if [[ "$model_ids" == __PARSE_ERROR__* || -z "$model_ids" ]]; then
    echo "No models listed at ${LLM_URL%/}/models (or the response couldn't be parsed)." >&2
    exit 1
  fi
  echo "Models available at ${LLM_URL%/}/models:"
  echo "$model_ids" | sed 's/^/  /'
  echo
  echo "Pass one of the above to --model, e.g.:"
  echo "  ./scripts/smoke_test.sh --llm-url \"$LLM_URL\" --model \"$(head -n1 <<<"$model_ids")\""
  exit 0
fi

# Naming exactly one transport's serial is itself a scoping decision: passing
# --wireless-serial without --usb-serial means "just check this wireless device",
# not "and also whatever happens to be on USB right now" - so the other transport
# is skipped automatically instead of requiring a redundant --skip-wired/--skip-wireless.
# Pass both serials (or neither, to auto-detect both) to check both transports.
WIRED_AUTO_SKIPPED=0
WIRELESS_AUTO_SKIPPED=0
if [[ -n "$WIRELESS_SERIAL" && -z "$USB_SERIAL" && "$RUN_WIRED" -eq 1 ]]; then
  RUN_WIRED=0
  WIRED_AUTO_SKIPPED=1
fi
if [[ -n "$USB_SERIAL" && -z "$WIRELESS_SERIAL" && "$RUN_WIRELESS" -eq 1 ]]; then
  RUN_WIRELESS=0
  WIRELESS_AUTO_SKIPPED=1
fi

# ---------------------------------------------------------------------------
# Pretty output + pass/warn/fail bookkeeping
# ---------------------------------------------------------------------------
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""
fi

section() { printf '\n%s== %s ==%s\n' "$C_BOLD" "$1" "$C_RESET"; }
pass() { PASS_COUNT=$((PASS_COUNT + 1)); printf '  %s[PASS]%s %s\n' "$C_GREEN" "$C_RESET" "$1"; }
warn() { WARN_COUNT=$((WARN_COUNT + 1)); printf '  %s[WARN]%s %s\n' "$C_YELLOW" "$C_RESET" "$1"; }
fail() { FAIL_COUNT=$((FAIL_COUNT + 1)); printf '  %s[FAIL]%s %s\n' "$C_RED" "$C_RESET" "$1"; }
info() { printf '  %s\n' "$1"; }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Print the serial of the first wired (non ip:port) device in `adb devices -l`
# whose state is exactly "device" (skips "unauthorized"/"offline"/"no permissions").
find_wired_serial() {
  local line serial state
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    serial="$(awk '{print $1}' <<<"$line")"
    state="$(awk '{print $2}' <<<"$line")"
    [[ "$state" == "device" ]] || continue
    [[ "$serial" == *:* ]] && continue
    printf '%s\n' "$serial"
    return 0
  done < <(adb devices -l 2>/dev/null | tail -n +2)
  return 1
}

resolved_wired_serial=""
resolved_wireless_serial=""

# Run a command bounded to $CURL_TIMEOUT seconds, killing it if it doesn't finish -
# macOS ships no `timeout`/`gtimeout` by default. Needed for raw `adb` calls
# specifically: unlike curl (--max-time) and device_health_check.py (its own
# asyncio.wait_for), a bare `adb -s <serial> shell ...` against an address that's
# silently dropped rather than actively refused (e.g. an unreachable/black-holed
# IP) can hang for the OS's full TCP connect timeout, far past any timeout this
# script would otherwise apply.
with_timeout() {
  local secs="$1"
  shift
  "$@" &
  local cmd_pid=$!
  (
    sleep "$secs"
    kill -9 "$cmd_pid" 2>/dev/null
  ) &
  local watchdog_pid=$!
  local status=0
  wait "$cmd_pid" 2>/dev/null || status=$?
  kill "$watchdog_pid" 2>/dev/null
  wait "$watchdog_pid" 2>/dev/null
  return "$status"
}

# Run scripts/device_health_check.py (SDK-only: AndroidDriver connect + portal +
# get_date + screenshot) against one serial, and re-report each of its CHECK lines
# through this script's own pass/warn/fail bookkeeping. Returns 0 for an overall
# PASS or WARN verdict, 1 for FAIL - so e.g. "Portal unavailable" (a warning, not
# fatal) doesn't get miscounted as a hard failure.
run_device_health_check() {
  local serial="$1" log_path line name status message
  log_path="$(mktemp)"
  # device_health_check.py bounds its own checks internally via --timeout; the outer
  # with_timeout here is defense-in-depth against `uv run` startup itself hanging.
  with_timeout "$((${CURL_TIMEOUT%.*} + 15))" uv run python scripts/device_health_check.py --serial "$serial" --timeout "$CURL_TIMEOUT" >"$log_path" 2>&1
  while IFS= read -r line; do
    [[ "$line" == "CHECK "* ]] || continue
    name="$(awk '{print $2}' <<<"$line")"
    status="$(awk '{print $3}' <<<"$line")"
    message="$(cut -d' ' -f4- <<<"$line")"
    case "$status" in
      PASS) pass "$name: $message" ;;
      WARN) warn "$name: $message" ;;
      FAIL) fail "$name: $message (log: $log_path)" ;;
      *) info "$line" ;;
    esac
  done <"$log_path"
  if grep -q "^RESULT FAIL" "$log_path"; then
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# 0. Prerequisites
# ---------------------------------------------------------------------------
section "Prerequisites"

require_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    pass "$1 found ($(command -v "$1"))"
  else
    fail "$1 not found on PATH - $2"
  fi
}

require_cmd adb "install Android platform-tools"
require_cmd curl "install curl"
require_cmd uv "install uv: https://docs.astral.sh/uv/getting-started/installation/"

if command -v scrcpy >/dev/null 2>&1; then
  pass "scrcpy found ($(command -v scrcpy))"
else
  warn "scrcpy not found - screen recording will be unavailable (not required for this smoke test)"
fi

if [[ ! -f "$REPO_DIR/pyproject.toml" ]]; then
  fail "pyproject.toml not found at $REPO_DIR - run this script from inside the DailyBench300 checkout"
else
  pass "running from repo root ($REPO_DIR)"
fi

info "uv run python -c 'import mobilerun' ..."
if uv run python -c "import mobilerun" >/tmp/DailyBench_smoke_mobilerun_import.log 2>&1; then
  pass "mobilerun SDK imports cleanly"
else
  fail "mobilerun SDK failed to import - run 'uv sync --extra dev --extra tracing --extra hf' first (log: /tmp/DailyBench_smoke_mobilerun_import.log)"
fi

# ---------------------------------------------------------------------------
# 1. LLM server (any OpenAI-compatible backend - llama.cpp, vLLM, Ollama, ...)
# ---------------------------------------------------------------------------
if [[ "$RUN_LLM" -eq 1 ]]; then
  section "LLM server: $LLM_URL"
  info "See https://docs.mobilerun.ai/framework/sdk/configuration for how mobilerun talks to OpenAI-compatible endpoints."

  models_err_log="$(mktemp)"
  models_json="$(curl -sS --max-time "$CURL_TIMEOUT" "${LLM_URL%/}/models" 2>"$models_err_log")"
  curl_status=$?
  if [[ $curl_status -eq 0 && -n "$models_json" ]]; then
    pass "GET ${LLM_URL%/}/models responded"
    model_ids="$(printf '%s' "$models_json" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    ids = [m.get("id", "?") for m in data.get("data", [])]
    print("\n".join(ids))
except Exception as exc:
    print(f"__PARSE_ERROR__ {exc}")
' 2>/dev/null)"
    if [[ "$model_ids" == __PARSE_ERROR__* ]]; then
      info "models: (could not parse response: ${model_ids#__PARSE_ERROR__ })"
    elif [[ -z "$model_ids" ]]; then
      info "models: (no models listed)"
    else
      info "models: $(paste -sd, - <<<"$model_ids" | sed 's/,/, /g')"
      if [[ -z "$MODEL" ]]; then
        MODEL="$(head -n1 <<<"$model_ids")"
        info "--model not given - auto-selected \"$MODEL\" (the first model the server listed); pass --model to use a different one"
      fi
    fi
  else
    fail "GET ${LLM_URL%/}/models failed - is the server running and reachable at $LLM_URL? ($(cat "$models_err_log"))"
  fi
  rm -f "$models_err_log"

  if [[ -z "$MODEL" ]]; then
    warn "MODEL not set and none could be auto-selected - skipping the real chat-completion smoke test (pass --model or export MODEL)"
  else
    info "POST ${LLM_URL%/}/chat/completions with model=$MODEL ..."
    payload="$(python3 -c '
import json, sys
print(json.dumps({
    "model": sys.argv[1],
    "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
    "max_tokens": 16,
    "temperature": 0,
}))
' "$MODEL")"
    chat_err_log="$(mktemp)"
    SECONDS=0
    completion_json="$(curl -sS --max-time "$CURL_TIMEOUT" -H "Content-Type: application/json" -d "$payload" "${LLM_URL%/}/chat/completions" 2>"$chat_err_log")"
    curl_status=$?
    elapsed=$SECONDS
    if [[ $curl_status -eq 0 && -n "$completion_json" ]]; then
      reply="$(printf '%s' "$completion_json" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data["choices"][0]["message"]["content"].strip())
except Exception as exc:
    print(f"__UNPARSEABLE__ {exc}")
' 2>/dev/null)"
      if [[ "$reply" != __UNPARSEABLE__* && -n "$reply" ]]; then
        pass "chat completion succeeded in ${elapsed}s - reply: \"$reply\""
      else
        fail "chat completion returned an unparseable response ($reply): $completion_json"
      fi
    else
      fail "POST ${LLM_URL%/}/chat/completions failed ($(cat "$chat_err_log"))"
    fi
    rm -f "$chat_err_log"
  fi
else
  section "LLM server"
  info "skipped (--skip-llm)"
fi

# ---------------------------------------------------------------------------
# 2. ADB + mobilerun: wired (USB)
# ---------------------------------------------------------------------------
if [[ "$RUN_WIRED" -eq 1 ]]; then
  section "ADB + mobilerun: wired (USB)"
  info "Reference: https://docs.mobilerun.ai/framework/sdk/adb-tools (AndroidDriver)."

  serial="$USB_SERIAL"
  if [[ -z "$serial" ]]; then
    info "No --usb-serial given; auto-detecting from 'adb devices -l' ..."
    serial="$(find_wired_serial || true)"
  fi

  if [[ -z "$serial" ]]; then
    warn "no wired ADB device found - plug one in over USB, or pass --usb-serial (skipping wired checks)"
  else
    if [[ "$serial" == *:* ]]; then
      warn "--usb-serial '$serial' looks like a wireless ip:port serial, not a wired device ID - double-check it (see the transport-mismatch note in README.md)"
    fi

    if with_timeout "$CURL_TIMEOUT" adb -s "$serial" shell true >/dev/null 2>&1; then
      pass "adb shell reachable on $serial"
      model_name="$(with_timeout "$CURL_TIMEOUT" adb -s "$serial" shell getprop ro.product.model 2>/dev/null | tr -d '\r')"
      android_version="$(with_timeout "$CURL_TIMEOUT" adb -s "$serial" shell getprop ro.build.version.release 2>/dev/null | tr -d '\r')"
      info "device: ${model_name:-unknown} (Android ${android_version:-unknown})"
    else
      fail "adb shell not reachable on $serial - check the USB cable / accept the RSA authorization prompt on the phone"
    fi

    info "uv run python scripts/device_health_check.py --serial $serial (AndroidDriver: connect, portal, get_date, screenshot) ..."
    if run_device_health_check "$serial"; then
      resolved_wired_serial="$serial"
    fi
  fi
else
  section "ADB + mobilerun: wired (USB)"
  if [[ "$WIRED_AUTO_SKIPPED" -eq 1 ]]; then
    info "skipped (a --wireless-serial was given without --usb-serial; pass both to check both transports)"
  else
    info "skipped (--skip-wired)"
  fi
fi

# ---------------------------------------------------------------------------
# 3. ADB + mobilerun: wireless (TCP/IP)
# ---------------------------------------------------------------------------
if [[ "$RUN_WIRELESS" -eq 1 ]]; then
  section "ADB + mobilerun: wireless (TCP/IP)"
  info "Reference: README.md 'Wireless ADB' section."

  serial="$WIRELESS_SERIAL"
  if [[ -n "$serial" ]]; then
    info "Using explicit wireless serial: $serial"
  else
    info "No --wireless-serial given; bootstrapping wireless ADB from a connected USB device ..."
    bootstrap_serial="${USB_SERIAL:-$(find_wired_serial || true)}"
    if [[ -z "$bootstrap_serial" ]]; then
      warn "no USB device available to bootstrap wireless ADB from - connect once over USB first, or pass --wireless-serial ip:port directly (skipping wireless checks)"
    else
      phone_ip="$(with_timeout "$CURL_TIMEOUT" adb -s "$bootstrap_serial" shell "ip -f inet addr show wlan0 | sed -n 's/.*inet \\([0-9.]*\\)\\/.*/\\1/p' | head -1" 2>/dev/null | tr -d '\r')"
      if [[ -z "$phone_ip" ]]; then
        fail "could not read $bootstrap_serial's wlan0 IP over USB - is the phone connected to Wi-Fi?"
      else
        with_timeout "$CURL_TIMEOUT" adb -s "$bootstrap_serial" tcpip "$WIRELESS_PORT" >/dev/null 2>&1
        sleep 1
        connect_log="$(mktemp)"
        info "adb connect ${phone_ip}:${WIRELESS_PORT} ..."
        if with_timeout "$CURL_TIMEOUT" adb connect "${phone_ip}:${WIRELESS_PORT}" >"$connect_log" 2>&1 && grep -qi "connected" "$connect_log"; then
          serial="${phone_ip}:${WIRELESS_PORT}"
          pass "connected wirelessly to $serial"
        else
          fail "wireless connect failed (log: $connect_log)"
        fi
      fi
    fi
  fi

  if [[ -n "$serial" ]]; then
    if [[ "$serial" != *:* ]]; then
      warn "--wireless-serial '$serial' doesn't look like an ip:port serial - double-check it (see the transport-mismatch note in README.md)"
    fi

    if with_timeout "$CURL_TIMEOUT" adb -s "$serial" shell true >/dev/null 2>&1; then
      pass "adb shell reachable on $serial"
    else
      fail "adb shell not reachable on $serial"
    fi

    info "uv run python scripts/device_health_check.py --serial $serial (AndroidDriver: connect, portal, get_date, screenshot) ..."
    if run_device_health_check "$serial"; then
      resolved_wireless_serial="$serial"
    fi
  fi
else
  section "ADB + mobilerun: wireless (TCP/IP)"
  if [[ "$WIRELESS_AUTO_SKIPPED" -eq 1 ]]; then
    info "skipped (a --usb-serial was given without --wireless-serial; pass both to check both transports)"
  else
    info "skipped (--skip-wireless)"
  fi
fi

# ---------------------------------------------------------------------------
# 4. End-to-end: one real DailyBench task through the harness itself
# ---------------------------------------------------------------------------
if [[ "$RUN_AGENT_SMOKE" -eq 1 ]]; then
  section "End-to-end agent smoke run"

  agent_serial="${resolved_wireless_serial:-${resolved_wired_serial:-}}"
  if [[ -z "$agent_serial" ]]; then
    warn "no device passed the checks above - skipping the end-to-end agent smoke run"
  elif [[ -z "$MODEL" ]]; then
    warn "MODEL not set - skipping the end-to-end agent smoke run (pass --model or export MODEL)"
  else
    agent_log="$(mktemp)"
    info "uv run dailybench_runner.py against $agent_serial (goal: \"$SMOKE_GOAL\", steps=$SMOKE_STEPS) ..."
    if uv run dailybench_runner.py \
      --serial "$agent_serial" \
      --label smoke-test \
      --out-dir runs/smoke-test \
      --llm-upstream-base "$LLM_URL" \
      --llm-proxy-port "$SMOKE_PROXY_PORT" \
      --model "$MODEL" \
      --steps "$SMOKE_STEPS" \
      --goal "$SMOKE_GOAL" \
      >"$agent_log" 2>&1
    then
      run_dir="$(grep -o 'Run directory: .*' "$agent_log" | tail -1 | sed 's/Run directory: //')"
      pass "end-to-end agent run completed - run folder: ${run_dir:-see $agent_log}"
    else
      fail "end-to-end agent run failed (log: $agent_log)"
    fi
  fi
else
  section "End-to-end agent smoke run"
  info "skipped (--skip-agent-run)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
section "Summary"
printf '  %s%d passed%s, %s%d warned%s, %s%d failed%s\n' \
  "$C_GREEN" "$PASS_COUNT" "$C_RESET" "$C_YELLOW" "$WARN_COUNT" "$C_RESET" "$C_RED" "$FAIL_COUNT" "$C_RESET"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
exit 0
