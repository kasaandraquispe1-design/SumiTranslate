"""Document format adapters for Sumire Translate.

Compatibility patches are installed here so the public document pipeline
keeps the same API while DOCX images and PDF table geometry remain stable.
"""

try:
    from . import document_pipeline as _document_pipeline

    # DOCX: preserve embedded drawings/images while replacing text.
    try:
        from .docx_image_safe import translate_docx_document_safe
        _document_pipeline.translate_docx_document = lambda path, source_lang, target_lang, translate_fn: translate_docx_document_safe(
            path, source_lang, target_lang, translate_fn, _document_pipeline
        )
    except Exception:
        pass

    # PDF: map every extracted table cell to its real row/column rectangle.
    try:
        from .pdf_table_fix import table_cell_rect
        _document_pipeline._table_cell_rect = table_cell_rect
    except Exception:
        pass
except Exception:
    # Never prevent the rest of Sumire from starting if an optional patch fails.
    pass
