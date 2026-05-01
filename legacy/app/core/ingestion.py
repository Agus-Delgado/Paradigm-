"""Load CSV/XLSX uploads into a pandas DataFrame."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

CSV_SEPARATORS = (",", ";", "\t")
ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")


def load_uploaded_file(uploaded_file) -> tuple[pd.DataFrame | None, str | None]:
    """
    Read a Streamlit UploadedFile. Returns (df, None) on success or (None, error_message).
    """
    if uploaded_file is None:
        return None, "No se seleccionó ningún archivo."

    name = getattr(uploaded_file, "name", "") or ""
    suffix = Path(name).suffix.lower()

    try:
        raw = uploaded_file.read()
    except Exception as exc:
        return None, f"No se pudo leer el archivo: {exc}"

    if not raw.strip():
        return None, "El archivo está vacío o solo contiene espacios en blanco."

    if suffix == ".csv":
        return _read_csv_bytes(raw)
    if suffix in (".xlsx", ".xls"):
        return _read_excel_bytes(raw, name)

    return None, f"Formato no soportado: {suffix or 'desconocido'}. Usá archivos .csv o .xlsx."


def _csv_candidate_better(ncols: int, sep_idx: int, best_ncols: int, best_sep_idx: int) -> bool:
    if ncols > best_ncols:
        return True
    if ncols < best_ncols:
        return False
    return sep_idx < best_sep_idx


def _read_csv_bytes(raw: bytes) -> tuple[pd.DataFrame | None, str | None]:
    last_decode_error: Exception | None = None
    best_df: pd.DataFrame | None = None
    best_ncols = -1
    best_sep_idx = 99

    for encoding in ENCODINGS:
        encoding_failed = False
        for sep_idx, sep in enumerate(CSV_SEPARATORS):
            try:
                df = pd.read_csv(io.BytesIO(raw), encoding=encoding, sep=sep)
            except UnicodeDecodeError as exc:
                last_decode_error = exc
                encoding_failed = True
                break
            except Exception:
                continue
            ncols = len(df.columns)
            if ncols > 0 and _csv_candidate_better(ncols, sep_idx, best_ncols, best_sep_idx):
                best_df = df
                best_ncols = ncols
                best_sep_idx = sep_idx

        if encoding_failed:
            continue

    if best_df is None:
        if last_decode_error is not None:
            return None, f"No se pudo decodificar el CSV (encoding). Último error: {last_decode_error}"
        return None, "No se pudo interpretar el CSV. Revisá separador, formato o encoding."

    if len(best_df.columns) == 0:
        return None, (
            "No se detectaron columnas en el CSV. "
            "Probá otro separador (coma, punto y coma o tabulador) o revisá el encoding del archivo."
        )

    return best_df, None


def read_csv_bytes(raw: bytes) -> tuple[pd.DataFrame | None, str | None]:
    """
    Lee CSV desde bytes con la misma heurística que la carga por upload (encoding y separador).
    """
    if not raw.strip():
        return None, "El archivo está vacío o solo contiene espacios en blanco."
    return _read_csv_bytes(raw)


def load_csv_path(path: Path | str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Carga un CSV desde disco; mismo pipeline lógico que un archivo subido (.csv).
    """
    p = Path(path)
    if not p.is_file():
        return None, f"No se encontró el archivo: {p}"
    try:
        raw = p.read_bytes()
    except OSError as exc:
        return None, f"No se pudo leer el archivo: {exc}"
    return read_csv_bytes(raw)


def _read_excel_bytes(raw: bytes, filename: str) -> tuple[pd.DataFrame | None, str | None]:
    buf = io.BytesIO(raw)
    try:
        xl = pd.ExcelFile(buf, engine="openpyxl")
    except Exception as exc:
        return None, f"No se pudo abrir el Excel: {exc}"

    if not xl.sheet_names:
        return None, "El archivo Excel no tiene hojas."

    first = xl.sheet_names[0]
    try:
        df = pd.read_excel(xl, sheet_name=first, engine="openpyxl")
    except Exception as exc:
        return None, f"Error al leer la hoja «{first}»: {exc}"

    if len(df.columns) == 0:
        return None, "La primera hoja no tiene columnas detectables o está vacía."

    return df, None
