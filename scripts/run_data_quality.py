"""
Ejecuta checks de calidad sobre data/processed/paradigm_mart.db y escribe reports/quality_report.md.

Requiere haber generado el mart:
    python scripts/build_sqlite_mart.py

Uso (desde la raíz del repo):
    python scripts/run_data_quality.py

Código de salida: 0 si no hay checks FAIL; 1 si algún FAIL (WARN no falla el proceso).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python" / "src"))

from paradigm.io.paths import DEFAULT_QUALITY_REPORT  # noqa: E402
from paradigm.quality.runner import run_and_report  # noqa: E402


def main() -> None:
    _, code = run_and_report()
    print(f"Reporte escrito: {DEFAULT_QUALITY_REPORT}")
    sys.exit(code)


if __name__ == "__main__":
    main()
