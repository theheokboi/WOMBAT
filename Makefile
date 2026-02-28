.PHONY: run calibrate serve ui test test-blocking test-nonblocking

run:
	python -m inframap.agent.cli

calibrate:
	python -m inframap.agent.calibrate

serve:
	python -m inframap.serve

ui:
	@echo "Open http://localhost:8000/ui after running 'make serve'"

test:
	pytest -q

test-blocking:
	pytest -q tests/unit tests/property tests/golden tests/integration

test-nonblocking:
	pytest -q -m "ui_smoke or perf_monitoring" tests/ui tests/perf
