"""Document format adapters for Sumire Translate.

The package installs a small compatibility patch for DOCX reconstruction so
embedded Word images are never lost when text runs are translated.
"""

# Import the existing module first, then replace only its DOCX implementation.
# The public translate_document dispatcher keeps the same API used by the app.
try:
    from . import document_pipeline as _document_pipeline
    from .docx_image_safe import translate_docx_document_safe

    _document_pipeline.translate_docx_document = lambda path, source_lang, target_lang, translate_fn: translate_docx_document_safe(
        path,
        source_lang,
        target_lang,
        translate_fn,
        _document_pipeline,
    )
except Exception:
    # Do not prevent PDF/text startup if the optional DOCX patch cannot load.
    pass
