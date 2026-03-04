.PHONY: run-dev serve-dev ui-dev verify-dev test-dev test-dev-blocking test-dev-nonblocking run calibrate calibrate-argentina-best-fit serve ui test test-blocking test-nonblocking

run-dev:
	@if [ "$(COUNTRY)" = "AR" ]; then \
		SYSTEM_CONFIG_PATH=configs/system.argentina.yaml LAYERS_CONFIG_PATH=configs/layers.argentina.yaml python -m inframap.agent.cli; \
	else \
		python -m inframap.agent.cli; \
	fi

run: run-dev

calibrate:
	python -m inframap.agent.calibrate

calibrate-argentina-best-fit:
	SYSTEM_CONFIG_PATH=configs/system.argentina.yaml LAYERS_CONFIG_PATH=configs/layers.argentina.yaml COUNTRY=AR python -m inframap.agent.calibrate

serve-dev:
	python -m inframap.serve

serve: serve-dev

ui-dev:
	@echo "Open http://localhost:8000/ui after running 'make serve-dev'"

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
