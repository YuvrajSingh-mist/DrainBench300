# Evaluation Policy

## Reproducibility

- benchmarked runs should use a fixed model, fixed flags, and fixed task text
- benchmarked runs should use the same 50-step action budget unless a separate experiment explicitly studies budget sensitivity
- wireless ADB is preferred for measured runs
- environment drift must be documented when it affects comparability

## Deterministic tasks

- score by observable success or failure
- use final outputs, run artifacts, and state evidence

## Open-ended tasks

- report separately from deterministic tasks
- use explicit rubric items
- do not collapse rubric-based and deterministic scores into one opaque number

## Benchmark maintenance

- prefer evaluator fixes over retroactively changing old results
- document task volatility and environment changes
- keep regression tests for parsers and scorers
