# Task Authoring

This benchmark currently keeps the human-authored task list in markdown, but tasks should be written as if they will eventually migrate into structured files.

## Authoring rules

- write tasks in plain user language
- keep app assumptions explicit when needed
- separate deterministic tasks from open-ended tasks
- avoid hidden requirements
- avoid tasks that depend on unstable external state unless volatility is intentional

## Good deterministic task properties

- one clear success condition
- one clear final state or answer
- evaluator can verify success without guessing

## Good open-ended task properties

- realistic user intent
- multiple valid outputs are allowed
- future scoring uses a rubric, not strict string match

## Avoid

- vague “best” without rubric
- tasks requiring unavailable permissions or accounts
- tasks that silently depend on a specific launcher layout unless that layout is part of the benchmark setup
