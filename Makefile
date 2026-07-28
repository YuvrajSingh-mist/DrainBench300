PYTHON ?= python3

.PHONY: test
test:
	$(PYTHON) -m pytest

.PHONY: test-fast
test-fast:
	$(PYTHON) -m pytest tests/test_summary.py tests/test_adb.py tests/test_files.py

.PHONY: test-cli
test-cli:
	$(PYTHON) -m pytest tests/test_cli.py tests/test_processes.py

.PHONY: help
help:
	@printf "Targets:\n"
	@printf "  make test       Run the full pytest suite\n"
	@printf "  make test-fast  Run fast parser/helper coverage\n"
	@printf "  make test-cli   Run harness CLI/process coverage\n"
