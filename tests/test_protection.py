import unittest

from backend.processing.pipeline import run_pipeline
from backend.processing.word_counter import count_words
from backend.protection.math_protector import protect_text, restore_markers
from backend.validation.validator import validate_markers


class ProtectionTests(unittest.TestCase):
    def test_numbers_are_protected_and_restored(self):
        source = "The value is 9.81 m/s², the date is 2026-08-17 and the error is 0.05%."
        protected, store, _ = protect_text(source)
        self.assertNotIn("9.81 m/s²", protected)
        self.assertNotIn("2026-08-17", protected)
        self.assertNotIn("0.05%", protected)
        self.assertEqual(restore_markers(protected, store), source)
        self.assertGreaterEqual(sum(x.type == "number" for x in store.values()), 3)

    def test_markdown_table_structure_is_protected_but_cell_text_is_not(self):
        source = "| Name | Value |\n| --- | ---: |\n| Length | 12 cm |"
        protected, store, _ = protect_text(source)
        self.assertIn("Name", protected)
        self.assertIn("Value", protected)
        self.assertIn("Length", protected)
        self.assertNotIn("| Name |", protected)
        self.assertEqual(restore_markers(protected, store), source)
        self.assertTrue(any(x.type == "table" for x in store.values()))

    def test_code_urls_and_citations_are_protected(self):
        source = "Run `python main.py`, visit https://example.org/a?x=1 and see \\cite{Smith2020}."
        protected, store, _ = protect_text(source)
        self.assertNotIn("python main.py", protected)
        self.assertNotIn("https://example.org", protected)
        self.assertNotIn("\\cite{Smith2020}", protected)
        self.assertEqual(restore_markers(protected, store), source)
        types = {x.type for x in store.values()}
        self.assertTrue({"code", "url", "cite"}.issubset(types))

    def test_marker_validation_rejects_removed_or_reordered_markers(self):
        source = "A [[MATH_001]] B [[NUMBER_002]] C"
        self.assertFalse(validate_markers(source, "A [[NUMBER_002]] B [[MATH_001]] C")["passed"])
        self.assertFalse(validate_markers(source, "A [[MATH_001]] B C")["passed"])
        self.assertTrue(validate_markers(source, source)["passed"])

    def test_word_counter_excludes_protected_content(self):
        source = "Translate this sentence: 123 words, $x^2$, and `code` at https://example.org."
        counts = count_words(source)
        self.assertGreater(counts["total"], counts["translatable"])
        self.assertGreater(counts["protected"], 0)
        self.assertIn("math", counts["protectedByType"])
        self.assertIn("url", counts["protectedByType"])

    def test_pipeline_blocks_changed_marker(self):
        source = "This is $x^2$ and the number is 10."

        def bad_translate(_prompt):
            return "Esto es [[MATH_001]] y el número es 999."

        result = run_pipeline(
            text=source,
            source_lang="en",
            target_lang="es",
            translate_fn=bad_translate,
        )
        self.assertFalse(result["validation"]["passed"])
        self.assertIsNone(result["translated"])


if __name__ == "__main__":
    unittest.main()
