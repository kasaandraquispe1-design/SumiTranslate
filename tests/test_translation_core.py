import unittest

from backend.analyzer.document_analyzer import analyze_text
from backend.processing.pipeline import run_pipeline
from backend.protection.math_protector import protect_text, restore_markers
from backend.validation.validator import validate


class TranslationCoreTests(unittest.TestCase):
    def test_protect_and_restore_exact_math(self):
        text = r"Let f(x) be continuous and $x^2 + y^2 = 1$."
        protected, store, count = protect_text(text)
        self.assertEqual(count, len(store))
        self.assertNotIn("x^2 + y^2 = 1", protected)
        self.assertEqual(restore_markers(protected, store), text)

    def test_analyzer_exposes_counts_and_cost(self):
        result = analyze_text("This is a test with $x^2$." )
        self.assertIn("counts", result)
        self.assertIn("protectedElements", result)
        self.assertGreaterEqual(result["cost"], 0)

    def test_pipeline_restores_marker_after_translation(self):
        source = r"This is $x^2$ and it is important."

        def fake_translate(prompt):
            self.assertIn("[[MATH_", prompt)
            return "Esto es [[MATH_001]] y es importante."

        result = run_pipeline(
            text=source,
            source_lang="en",
            target_lang="es",
            translate_fn=fake_translate,
        )
        self.assertIn("$x^2$", result["translated"])
        self.assertTrue(result["validation"]["passed"])


if __name__ == "__main__":
    unittest.main()
