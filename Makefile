.PHONY: run-dev serve-dev ui-dev verify-dev verify-fast verify-ui verify-full verify-experimental test-dev test-dev-blocking test-dev-nonblocking run serve ui export-facilities-sqlite archive-progress-logs test test-blocking test-nonblocking

run-dev:
	python -m inframap.agent.cli

run: run-dev

serve-dev:
	python -m inframap.serve

serve: serve-dev

ui-dev:
	@echo "Open http://localhost:8000/ui/index.html after running 'make serve-dev'"

ui: ui-dev

export-facilities-sqlite:
	PYTHONPATH=src python scripts/export_facilities_sqlite.py

verify-dev: verify-fast

verify-fast:
	pytest -q tests/unit/test_ingest_normalize.py tests/integration/test_atomic_publish.py tests/integration/test_api_smoke.py
	pytest -q -m "ui_smoke" tests/ui

verify-ui:
	pytest -q -m "ui_smoke" tests/ui

verify-full:
	pytest -q tests/unit/test_ingest_normalize.py tests/integration/test_atomic_publish.py tests/integration/test_api.py
	pytest -q -m "ui_smoke" tests/ui

verify-experimental:
	pytest -q tests/property tests/perf

archive-progress-logs:
	PYTHONPATH=src python scripts/archive_progress_logs.py

test: test-dev

test-dev: test-dev-blocking test-dev-nonblocking

test-dev-blocking:
	pytest -q tests/unit tests/integration

test-dev-nonblocking:
	pytest -q -m "ui_smoke or perf_monitoring" tests/ui tests/perf

test-blocking: test-dev-blocking

test-nonblocking: test-dev-nonblocking
