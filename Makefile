.PHONY: help all demo install install-app synthetic mart quality export-pbi export-tab validate ml

PYTHON ?= python

help:
	@echo "Paradigm — available targets:"
	@echo "  make install      Install pipeline dependencies (requirements.txt)"
	@echo "  make install-app  Install Streamlit demo dependencies (requirements-app.txt)"
	@echo "  make all          Full pipeline: synthetic -> mart -> quality -> BI -> ML"
	@echo "  make demo         Launch Streamlit v2 Live Demo"
	@echo ""
	@echo "Atomic targets:"
	@echo "  make synthetic    Generate data/synthetic/*.csv"
	@echo "  make mart         Build data/processed/paradigm_mart.db"
	@echo "  make quality      Run 14 data quality checks"
	@echo "  make export-pbi   Export CSVs for Power BI"
	@echo "  make export-tab   Export CSVs for Tableau"
	@echo "  make validate     Validate executive KPIs"
	@echo "  make ml           Train no-show prioritization models"

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

all: synthetic mart quality export-pbi export-tab validate ml

demo: install-app
	$(PYTHON) -m streamlit run streamlit_app.py
