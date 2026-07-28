# Failures Summary

Date: 2026-07-27

This file summarizes the main failed or abandoned paths from the Droidrun / on-device model work so far.

## 1. Mini2 as the actual inference host was the wrong target

What happened:

- We successfully brought up model-serving flows on `mini2`.
- That included testing LiteRT-LM Python CLI server mode on the Mac mini.

Why it failed for the real goal:

- The actual goal was phone-local model execution, not Mac-mini-local execution.
- Using `mini2` as the inference host solved the wrong problem.

Takeaway:

- `mini2` is useful as a build/staging machine.
- It should not be confused with the phone-local inference target.

## 2. LiteRT-LM macOS binary on mini2 failed due to missing dylibs

What happened:

- We downloaded the LiteRT-LM macOS arm64 binary release on `mini2`.

Why it failed:

- The raw binary did not run because required dynamic libraries were missing.

Takeaway:

- The standalone release binary path was not reliable on that machine.
- The Python CLI route was the workable fallback on `mini2`.

## 3. LiteRT-LM Python on mini2 initially failed on system Python

What happened:

- We tried installing/running `litert-lm` with the system Python on `mini2`.

Why it failed:

- The system Python version was too old for the package behavior we hit.
- The CLI crashed around unsupported Python features.

Takeaway:

- We needed an isolated newer Python runtime.
- `uv` + Python 3.13 was the successful workaround.

## 4. Homebrew Python 3.14 on mini2 was broken

What happened:

- We tried using Homebrew Python 3.14 on `mini2`.

Why it failed:

- It had a broken `pyexpat` / `libexpat` issue and could not reliably run the CLI.

Takeaway:

- Homebrew Python on that box was not trustworthy for this workflow.
- `uv`-managed Python was safer.

## 5. Initial LiteRT-LM Android build on mini2 failed with `macosx10.11`

What happened:

- We attempted the official Android source build for LiteRT-LM on `mini2`.

Why it failed:

- Bazel Apple support defaulted to `macosx10.11`.
- mini2 only had newer Command Line Tools SDKs.
- `xcrun` could not find the old SDK.

Takeaway:

- The build needed an explicit modern SDK override.
- The successful fix was `--macos_sdk_version=26.2`.

## 6. Full Xcode was not installed on mini2

What happened:

- We checked the Apple toolchain state on `mini2`.

Why it mattered:

- Only Command Line Tools were installed.
- That made the host toolchain behavior more fragile during Bazel’s Apple helper steps.

Takeaway:

- We were lucky that the SDK-version override was enough.
- This host is still somewhat brittle for Apple/Bazel work.

## 7. ADB availability was inconsistent during the phone handoff

What happened:

- After the Android bundle was built and copied back, the phone was not immediately reachable.

Why it failed:

- USB visibility and old wireless ADB state were inconsistent.
- The old Wi-Fi serial did not reconnect when retried.

Takeaway:

- The build pipeline succeeded before the device pipeline did.
- Phone-local work depended on reattaching the device later.

## 8. LiteRT phone-local path was not a ready-made OpenAI-compatible server

What happened:

- We built and pushed `litert_lm_main` to the phone.
- We successfully ran the model locally on-device.

Why it failed for Droidrun integration:

- `litert_lm_main` is a native runner binary, not a documented Android REST server.
- Droidrun/Mobilerun expects a provider/API layer.

Takeaway:

- Phone-local LiteRT execution worked.
- Direct drop-in Droidrun backend compatibility did not.

## 9. LiteRT GPU path on phone was not good for agent-style decode

What happened:

- We benchmarked the same LiteRT model on CPU and GPU on the phone.

What failed:

- GPU init was extremely slow.
- GPU decode speed was worse than CPU decode speed.

Observed result:

- CPU was more attractive for short interactive requests.
- GPU only looked better on prefill-heavy parts.

Takeaway:

- This GPU path was not good enough for the intended agent workflow.
- The result did not justify pushing harder on LiteRT GPU for Droidrun.

## 10. LiteRT GPU teardown was messy

What happened:

- The GPU run completed, but logged an EGL cleanup warning.

Why it matters:

- It suggests the path works, but is not especially polished/stable.

Takeaway:

- Even when successful, the GPU path looked rough around lifecycle cleanup.

## 11. Local phone model + Droidrun architecture mismatch

What happened:

- We wanted users to select a model and run it easily on-phone via Droidrun.

Why it failed in practice:

- Droidrun is strongest when talking to an external provider/server.
- Phone-local runtimes on Android are fragmented and not packaged in a user-friendly way.

Takeaway:

- The most practical architecture right now is:
  - Droidrun on phone
  - model hosted locally elsewhere
  - phone treated as the controlled client device

## 12. MLC looked promising, but not turnkey for Android localhost serving

What happened:

- We researched MLC because it has better odds of using the Mali GPU well.

Why it did not immediately solve the problem:

- Official Android support is real.
- Official REST/OpenAI-compatible support is real.
- But the Android path is SDK/app oriented, not a ready-made “install and run local server APK” path.

Takeaway:

- MLC is still the strongest next experimental on-device option.
- But it is not currently a simple end-user flow for Droidrun integration.

## 13. MediaTek NPU route was not clearly available for this exact phone

What happened:

- We researched whether MT6895 / Dimensity 8000-family hardware had a realistic public NPU route.

Why it failed as a near-term plan:

- There was not a clean public, current, reproducible LLM workflow for this exact device family that we could trust.

Takeaway:

- The public NPU path for this phone is too unclear for now.
- It is not a dependable user-facing setup.

## 14. Newer Android agent APK path was abandoned for trust reasons

What happened:

- We looked at newer Android agent frameworks that might be easier than Droidrun.
- An APK was downloaded and we briefly tried installation.

Why it failed:

- The APK install itself failed with `INSTALL_PARSE_FAILED_NOT_APK`.
- More importantly, the trust model was bad for granting deep phone access to a much less established app.

Takeaway:

- Experimental phone-agent APKs are not appropriate to trust by default.
- Droidrun/Mobilerun remains the safer practical control layer here.

## 15. “Everything on the phone” is not yet the best default product path

What happened:

- We explored running the whole stack on-device because that was the ideal.

Why it failed as the default recommendation:

- Too many rough edges:
  - model packaging
  - runtime/backend mismatch
  - server/API mismatch
  - difficult user setup
  - weak trust story for experimental apps
  - inconsistent performance

Takeaway:

- The field does not yet have a clean, mature, trustworthy end-to-end Android phone-agent stack that matches all requirements.
- For users today, hosting the model locally somewhere else is the better default.

## Current best conclusion

Best practical path:

- keep Droidrun/Mobilerun as the phone-control framework
- host the model on a Mac mini / laptop / server
- benchmark phone thermals, battery, and task behavior from the phone side
- keep on-device model execution as a research track, not the default user flow
