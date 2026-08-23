"""Robust PDF table geometry patch for Sumire Translate.

PyMuPDF's Table.cells is a flat row-major array and can contain None for
merged/empty cells. Building global x/y edges from that array can therefore
assign a later cell to the wrong column. This helper always prefers the
actual row-major cell rectangle and falls back to a geometry grid only when
necessary.
"""
from __future__ import annotations


def table_cell_rect(table, row_index: int, col_index: int, row_count: int, col_count: int):
    import pymupdf

    cells = list(getattr(table, "cells", []) or [])
    # The normal PyMuPDF representation is row-major. Use the exact cell
    # rectangle whenever it exists; this is the most reliable mapping.
    if col_count > 0:
        idx = row_index * col_count + col_index
        if 0 <= idx < len(cells) and cells[idx] is not None:
            cell = cells[idx]
            if len(cell) >= 4:
                return pymupdf.Rect(float(cell[0]), float(cell[1]), float(cell[2]), float(cell[3]))

    # Some versions/layouts expose a different flat width. In that case find
    # a cell whose center belongs to the requested row/column grid position.
    bbox = pymupdf.Rect(table.bbox)
    target_x = bbox.x0 + (col_index + 0.5) * bbox.width / max(col_count, 1)
    target_y = bbox.y0 + (row_index + 0.5) * bbox.height / max(row_count, 1)
    candidates = []
    for cell in cells:
        if cell is None or len(cell) < 4:
            continue
        rect = pymupdf.Rect(float(cell[0]), float(cell[1]), float(cell[2]), float(cell[3]))
        if rect.x0 <= target_x <= rect.x1 and rect.y0 <= target_y <= rect.y1:
            candidates.append(rect)
    if candidates:
        return candidates[0]

    # Final deterministic fallback. This keeps the table in its original
    # row/column order rather than allowing extracted text to drift.
    width = bbox.width / max(col_count, 1)
    height = bbox.height / max(row_count, 1)
    return pymupdf.Rect(
        bbox.x0 + col_index * width,
        bbox.y0 + row_index * height,
        bbox.x0 + (col_index + 1) * width,
        bbox.y0 + (row_index + 1) * height,
    )


def install() -> None:
    """Patch document_pipeline without changing its public API."""
    from backend.formats import document_pipeline
    document_pipeline._table_cell_rect = table_cell_rect
