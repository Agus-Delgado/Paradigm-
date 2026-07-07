.PHONY: help all build-all demo run-app install install-app synthetic mart quality export-pbi export-tab validate ml train-forecast eval-gold test-evaluation

PYTHON ?= python

help:
	@echo "Paradigm — available targets:"
	@echo "  make install      Install pipeline dependencies (requirements.txt)"
	@echo "  make install-app  Install Streamlit demo dependencies (requirements-app.txt)"
	@echo "  make all          Full pipeline: synthetic -> mart -> quality -> BI -> ML"
	@echo "  make build-all    Extended pipeline: all + forecast + eval + tests"
	@echo "  make demo         Launch Streamlit v2 Live Demo"
	@echo "  make run-app      Launch Streamlit app (alias of demo)"
	@echo ""
	@echo "Atomic targets:"
	@echo "  make synthetic    Generate data/synthetic/*.csv"
	@echo "  make mart         Build data/processed/paradigm_mart.db"
	@echo "  make quality      Run 14 data quality checks"
	@echo "  make export-pbi   Export CSVs for Power BI"
	@echo "  make export-tab   Export CSVs for Tableau"
	@echo "  make validate     Validate executive KPIs"
	@echo "  make ml           Train no-show prioritization models"
	@echo "  make train-forecast Train demand forecasting model"
	@echo "  make eval-gold    Run conversational gold evaluation"
	@echo "  make test-evaluation Run evaluation test suite"

install:
	$(PYTHON) -m pip install -r requirements.txt

install-app:
	$(PYTHON) -m pip install -r requirements-app.txt

synthetic:
	$(PYTHON) scripts/generate_paradigm_v2_synthetic.py

mart:
	$(PYTHON) scripts/build_sqlite_mart.py

quality:
	$(PYTHON) scripts/run_data_quality.py

export-pbi:
	$(PYTHON) scripts/export_powerbi_source.py

export-tab:
	$(PYTHON) scripts/export_tableau_source.py

validate:
	$(PYTHON) scripts/validate_executive_kpis.py

ml:
	$(PYTHON) scripts/train_no_show.py

train-forecast:
	$(PYTHON) scripts/train_forecast.py

eval-gold:
	$(PYTHON) scripts/run_evaluation_test.py

test-evaluation:
	$(PYTHON) -m unittest tests/test_evaluation.py

all: synthetic mart quality export-pbi export-tab validate ml

build-all: all train-forecast eval-gold test-evaluation

demo: install-app
	$(PYTHON) -m streamlit run streamlit_app.py

run-app: demo
