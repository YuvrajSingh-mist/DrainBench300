.PHONY: test
test:
	uv run pytest

.PHONY: test-fast
test-fast:
	uv run pytest tests/test_summary.py tests/test_adb.py tests/test_files.py

.PHONY: test-cli
test-cli:
	uv run pytest tests/test_cli.py tests/test_processes.py

.PHONY: sync
sync:
	uv sync --extra dev --extra tracing --extra hf

.PHONY: smoke-test
smoke-test:
	./scripts/smoke_test.sh

.PHONY: help
help:
	@printf "Targets:\n"
	@printf "  make sync        Create/update the uv-managed .venv with all extras\n"
	@printf "  make test        Run the full pytest suite\n"
	@printf "  make test-fast   Run fast parser/helper coverage\n"
	@printf "  make test-cli    Run harness CLI/process coverage\n"
	@printf "  make smoke-test  Pre-flight check: LLM server, wired/wireless ADB + mobilerun, one real task\n"
