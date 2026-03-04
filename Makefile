.PHONY: run-dev serve-dev ui-dev verify-dev test-dev test-dev-blocking test-dev-nonblocking run calibrate calibrate-argentina-best-fit serve ui test test-blocking test-nonblocking

run-dev:
	python -m inframap.agent.cli

run: run-dev

calibrate:
	python -m inframap.agent.calibrate

calibrate-argentina-best-fit:
	COUNTRY=AR python -m inframap.agent.calibrate

serve-dev:
	python -m inframap.serve

serve: serve-dev

ui-dev:
	@echo "Open http://localhost:8000/ui/index.html after running 'make serve-dev'"

ui: ui-dev

verify-dev:
	pytest -q tests/unit/test_ingest_normalize.py tests/integration/test_atomic_publish.py tests/integration/test_api.py
	pytest -q -m "ui_smoke" tests/ui

test: test-dev

test-dev: test-dev-blocking test-dev-nonblocking

test-dev-blocking:
	pytest -q tests/unit tests/integration

test-dev-nonblocking:
	pytest -q -m "ui_smoke or perf_monitoring" tests/ui tests/perf

test-blocking: test-dev-blocking

test-nonblocking: test-dev-nonblocking
