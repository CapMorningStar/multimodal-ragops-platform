.PHONY: help setup test test-unit test-integration test-ragas lint format run-api run-ui cost-guard clean

PYTHON ?= python
PIP ?= pip

help:
	@echo "Available commands:"
	@echo "  make setup            Install development dependencies"
	@echo "  make test             Run full test suite"
	@echo "  make test-unit        Run fast unit tests"
	@echo "  make test-integration Run integration tests"
	@echo "  make test-ragas       Run Ragas benchmark suite"
	@echo "  make lint             Run ruff and mypy checks"
	@echo "  make format           Format code using ruff"
	@echo "  make run-api          Run FastAPI local server"
	@echo "  make run-ui           Run Streamlit UI cockpit"
	@echo "  make cost-guard       Run GCP zero-idle-burn audit"
	@echo "  make clean            Clean temporary build artifacts"

setup:
	$(PIP) install -r requirements-dev.txt

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-ragas:
	pytest -m ragops_benchmark -v

lint:
	ruff check .
	mypy src config tests

format:
	ruff format .

run-api:
	uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	streamlit run src/ui/app.py --server.port 8501

cost-guard:
	bash scripts/cost_guard.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
