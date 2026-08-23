# 🌸 Sumire Translate

**Traduce ideas. Conecta mundos.**

Sumire Translate is a Streamlit document translator designed for academic, scientific and technical material. Its core principle is simple: **translate natural language, never rewrite the mathematical or structural content that must remain exact**.

## ✨ Current pipeline

```text
Text / Document
      ↓
Analyze structure
      ↓
Protect math, numbers, tables, code, URLs and citations
      ↓
Count translatable words
      ↓
Translate with Gemini
      ↓
Validate protected markers
      ↓
Restore exact protected content
      ↓
Reconstruct document
      ↓
Validated result
```

## ⭐ Phase 1 — Text translation

The text pipeline protects deterministic content before it reaches Gemini:

- mathematical notation and LaTeX;
- numbers and units;
- table delimiters;
- code;
- URLs and DOI identifiers;
- citations and references;
- variables, Greek letters and mathematical symbols.

The result is delivered only when structural validation passes.

## 📄 Phase 2 — Documents

PDF and DOCX now use layout-aware reconstruction adapters.

### PDF

For text-based PDFs, Sumire:

1. extracts text blocks with their page coordinates and basic typography;
2. protects non-linguistic content inside each block;
3. translates batches of blocks while preserving structural markers;
4. validates the marker sequence before restoration;
5. removes only the original text layer;
6. writes translated text back into the same page regions;
7. keeps the original PDF page as the visual source of truth.

This preserves the original **page count, page dimensions, images, vector graphics, table lines, numbering positions, captions and reference layout** as far as the PDF text layer allows. Font size is reduced automatically when translated text is longer.

A PDF containing only scanned images is intentionally rejected for now rather than returning a misleading unchanged file. OCR for scanned PDFs is planned as a later phase.

### DOCX

Paragraphs and table cells are translated in place, so the Word document keeps its existing structure, numbering, styles and embedded images. More advanced preservation of inline run formatting is a future refinement.

## 🌍 Languages

Regional variants are explicit. In particular:

- 🇧🇷 **Portugués (Brasil)**
- 🇵🇹 **Portugués (Portugal)**

are separate translation targets because terminology and usage differ.

## 🛡️ Fail-closed validation

Sumire does not silently deliver a damaged translation. If Gemini removes, duplicates or reorders a protected marker, or if deterministic protected content does not survive restoration, the translation is blocked.

## 🧪 Tests

The repository contains unit tests for protection, the translation pipeline and the new document reconstruction layer. GitHub Actions also compiles the Python sources and runs the test suite on pushes and pull requests.

## 🚀 Run locally

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

For Gemini translation, configure `GEMINI_API_KEY` in Streamlit Secrets or the environment.

## ☁️ Streamlit Community Cloud

The application entry point is `streamlit_app.py` at the repository root. Dependencies are declared in `requirements.txt` and the visual theme is configured in `.streamlit/config.toml`.

## 📁 Main structure

```text
SumiTranslate/
├── streamlit_app.py
├── backend/
│   ├── analyzer/
│   ├── core/
│   ├── formats/
│   │   ├── extractor.py
│   │   ├── image_extractor.py
│   │   └── document_pipeline.py   # Phase 2
│   ├── processing/
│   ├── protection/
│   ├── translation/
│   └── validation/
├── tests/
├── requirements.txt
└── .streamlit/config.toml
```

© Sumire Translate — **Traduce ideas. Conecta mundos.**
