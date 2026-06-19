"""Parser de notebooks Jupyter (.ipynb) para análisis en Paradigm."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

import nbformat
from nbformat import NotebookNode

_MAX_OUTPUT_CHARS = 2_000
_MAX_CODE_CHARS = 4_000
_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ParsedCell:
    index: int
    cell_type: str  # "markdown" | "code" | "raw"
    source: str
    outputs_summary: str | None = None
    has_plot: bool = False
    has_error: bool = False
    execution_count: int | None = None


@dataclass
class ParsedNotebook:
    filename: str
    title: str | None
    cells: list[ParsedCell] = field(default_factory=list)
    n_markdown: int = 0
    n_code: int = 0
    n_with_output: int = 0
    n_with_plot: int = 0
    n_errors: int = 0

    @property
    def cell_count(self) -> int:
        return len(self.cells)


def _cell_source(cell: NotebookNode) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _summarize_outputs(outputs: list) -> tuple[str | None, bool, bool]:
    """Devuelve (texto_resumido, has_plot, has_error)."""
    if not outputs:
        return None, False, False

    parts: list[str] = []
    has_plot = False
    has_error = False

    for out in outputs:
        otype = out.get("output_type", "")
        if otype == "stream":
            text = out.get("text", "")
            if isinstance(text, list):
                text = "".join(text)
            parts.append(str(text))
        elif otype in ("execute_result", "display_data"):
            data = out.get("data", {}) or {}
            if "text/plain" in data:
                tp = data["text/plain"]
                if isinstance(tp, list):
                    tp = "".join(tp)
                parts.append(str(tp))
            if any(k in data for k in ("image/png", "image/jpeg", "image/svg+xml")):
                has_plot = True
                parts.append("[Gráfico/visualización generada]")
        elif otype == "error":
            has_error = True
            parts.append(f"ERROR {out.get('ename', '?')}: {out.get('evalue', '')}")

    joined = _truncate("\n".join(p for p in parts if p.strip()), _MAX_OUTPUT_CHARS)
    return (joined or None), has_plot, has_error


def _infer_title(cells: list[ParsedCell], metadata: dict) -> str | None:
    meta_title = (metadata or {}).get("title")
    if meta_title:
        return str(meta_title).strip() or None
    for cell in cells:
        if cell.cell_type != "markdown":
            continue
        for line in cell.source.splitlines():
            line = line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip()
    return None


def parse_notebook(
    source: bytes | str | Path | BinaryIO,
    *,
    filename: str = "notebook.ipynb",
) -> tuple[ParsedNotebook | None, str | None]:
    """
    Parsea un .ipynb. Retorna (ParsedNotebook, None) o (None, mensaje_error).
    """
    try:
        if isinstance(source, Path):
            nb = nbformat.read(str(source), as_version=4)
        elif isinstance(source, bytes):
            nb = nbformat.reads(source.decode("utf-8"), as_version=4)
        elif isinstance(source, str):
            nb = nbformat.reads(source, as_version=4)
        else:
            raw = source.read()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            nb = nbformat.reads(raw, as_version=4)
    except Exception as exc:
        return None, f"No se pudo leer el notebook: {exc}"

    parsed_cells: list[ParsedCell] = []
    n_markdown = n_code = n_with_output = n_with_plot = n_errors = 0

    for idx, cell in enumerate(nb.cells):
        ctype = cell.get("cell_type", "unknown")
        src = _cell_source(cell)
        outputs_summary: str | None = None
        has_plot = has_error = False
        exec_count = None

        if ctype == "markdown":
            n_markdown += 1
        elif ctype == "code":
            n_code += 1
            exec_count = cell.get("execution_count")
            outputs_summary, has_plot, has_error = _summarize_outputs(cell.get("outputs", []))
            if outputs_summary:
                n_with_output += 1
            if has_plot:
                n_with_plot += 1
            if has_error:
                n_errors += 1
            src = _truncate(src, _MAX_CODE_CHARS)

        parsed_cells.append(
            ParsedCell(
                index=idx,
                cell_type=ctype,
                source=src,
                outputs_summary=outputs_summary,
                has_plot=has_plot,
                has_error=has_error,
                execution_count=exec_count,
            )
        )

    meta = nb.get("metadata", {}) or {}
    title = _infer_title(parsed_cells, meta)

    return ParsedNotebook(
        filename=filename,
        title=title,
        cells=parsed_cells,
        n_markdown=n_markdown,
        n_code=n_code,
        n_with_output=n_with_output,
        n_with_plot=n_with_plot,
        n_errors=n_errors,
    ), None


def extract_headings(parsed: ParsedNotebook) -> list[str]:
    headings: list[str] = []
    for cell in parsed.cells:
        if cell.cell_type != "markdown":
            continue
        for match in _HEADING_RE.finditer(cell.source):
            headings.append(match.group(1).strip())
    return headings


def build_llm_context(parsed: ParsedNotebook, *, max_chars: int = 14_000) -> str:
    """Arma contexto rico para el LLM: títulos, markdown, código clave y outputs."""
    lines: list[str] = [
        f"NOTEBOOK: {parsed.filename}",
        f"Título inferido: {parsed.title or '(sin título)'}",
        f"Celdas: {parsed.cell_count} ({parsed.n_markdown} markdown, {parsed.n_code} code)",
        f"Outputs: {parsed.n_with_output} | Gráficos: {parsed.n_with_plot} | Errores: {parsed.n_errors}",
    ]

    headings = extract_headings(parsed)
    if headings:
        lines.append("Títulos/secciones: " + " · ".join(headings[:12]))

    lines.append("")
    for cell in parsed.cells:
        if cell.cell_type not in ("markdown", "code"):
            continue
        header = f"--- Celda {cell.index} [{cell.cell_type}]"
        if cell.execution_count is not None:
            header += f" (In [{cell.execution_count}])"
        header += " ---"
        lines.append(header)
        lines.append(cell.source)
        if cell.outputs_summary:
            lines.append(f"[Output]: {cell.outputs_summary}")
        if cell.has_plot:
            lines.append("[Incluye gráfico]")
        if cell.has_error:
            lines.append("[Celda con error de ejecución]")
        lines.append("")

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 80] + "\n\n[... contexto truncado por límite de tokens ...]"
    return text
