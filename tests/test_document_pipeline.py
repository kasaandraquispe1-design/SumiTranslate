import re
import tempfile
import unittest
from pathlib import Path

from backend.formats.document_pipeline import _translate_segments, translate_pdf_document


class DocumentPipelineTests(unittest.TestCase):
    @staticmethod
    def fake_translate(prompt: str) -> str:
        body = prompt.split("DOCUMENT SEGMENTS:\n", 1)[1].split("\n\nOUTPUT ONLY", 1)[0]
        return body.replace("Hello", "Hola").replace("This is a title", "Este es un título")

    def test_segment_translation_preserves_structure(self):
        outputs, validation = _translate_segments(
            [("000001", "Hello $x^2$"), ("000002", "This is a title")],
            "en",
            "es",
            self.fake_translate,
        )
        self.assertEqual(outputs, ["Hola $x^2$", "Este es un título"])
        self.assertTrue(validation["passed"])

    def test_pdf_reconstruction_keeps_page_count_and_translates_text(self):
        import pymupdf

        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "source.pdf"
            source = pymupdf.open()
            page = source.new_page(width=400, height=300)
            page.insert_text((50, 70), "Hello $x^2$", fontsize=14)
            page.draw_rect((40, 100, 180, 160), color=(0.4, 0.2, 0.7), width=1)
            source.save(source_path)
            source.close()

            output, info = translate_pdf_document(
                source_path,
                "en",
                "es",
                self.fake_translate,
            )

            self.assertEqual(info["pages"], 1)
            self.assertTrue(info["validation"]["passed"])
            result = pymupdf.open(stream=output, filetype="pdf")
            self.assertEqual(result.page_count, 1)
            extracted = result[0].get_text()
            self.assertIn("Hola", extracted)
            self.assertIn("$x^2$", extracted)
            self.assertGreater(len(result[0].get_drawings()), 0)
            result.close()


if __name__ == "__main__":
    unittest.main()
