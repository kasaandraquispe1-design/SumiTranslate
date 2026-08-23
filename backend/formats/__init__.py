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

    # Streamlit expects the public document API to return:
    #     (document_bytes, document_format, info)
    # The internal PDF/DOCX adapters return (document_bytes, info).
    # Normalize that contract here. This fixes:
    # "not enough values to unpack (expected 3, got 2)"
    # without changing the working translation/reconstruction engines.
    try:
        _original_translate_document = _document_pipeline.translate_document

        def _translate_document_compat(path, source_lang, target_lang, translate_fn):
            result = _original_translate_document(path, source_lang, target_lang, translate_fn)
            if isinstance(result, tuple) and len(result) == 2:
                document_bytes, info = result
                info = dict(info or {})
                document_format = info.get("format") or str(path).lower().rsplit(".", 1)[-1]
                return document_bytes, document_format, info
            return result

        _document_pipeline.translate_document = _translate_document_compat
    except Exception:
        pass
except Exception:
    # Never prevent the rest of Sumire from starting if an optional patch fails.
    pass
