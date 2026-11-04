import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("case_import", Path(__file__).parents[1] / "import-case-library.py")
case_import = importlib.util.module_from_spec(spec)
spec.loader.exec_module(case_import)


class SourceMatchingTests(unittest.TestCase):
    def test_secondary_source_stays_with_its_table(self):
        document = ("Parameter estimates are shown in Table 16.8.\n\n"
                    "The data presented in Table 16.9 is from Carter (1986).")
        result = case_import.source_for("421-002", "Table 16.8 Parameter estimates", document, document)
        self.assertEqual(result["relation"], "direct")
        result = case_import.source_for("421-002", "Table 16.9 Throttle data", document, document)
        self.assertEqual(result["relation"], "secondary")
        self.assertIn("Carter (1986)", result["original_reference"])

    def test_dataset_origin_does_not_become_the_source_of_a_new_result_figure(self):
        document = ("Table 1 shows data tested in the laboratory [11]. "
                    "Figure 2 shows the iteration trace.\n\n[11] Hirose, 1991.")
        self.assertEqual(case_import.source_for("182-105", "Table 1 Data", document, document)["relation"], "secondary")
        self.assertEqual(case_import.source_for("182-105", "Figure 2 Trace", document, document)["relation"], "direct")

    def test_caption_follows_its_image_group(self):
        document = ("Figure 1. Earlier figure.\n\nUnrelated paragraph.\n\n"
                    "![](182-105-图片/one.jpg)\n\n![](182-105-图片/two.jpg)\n\n"
                    "Figure 2. Iteration traces.\n")
        images = list(case_import.IMAGE.finditer(document))
        for index in range(len(images)):
            self.assertEqual(case_import.grouped_figure_caption(document, images, index), "Figure 2. Iteration traces.")

    def test_credit_after_caption_label_is_retained(self):
        document = "Figure 1.2. Reliability issues. From Blischke and Murthy (2000)."
        source = case_import.source_for("421-002", document, document, document)
        self.assertEqual(source["relation"], "secondary")
        self.assertIn("Blischke and Murthy", source["original_reference"])

    def test_caption_is_a_boundary_between_image_groups(self):
        document = ("![](182-105-图片/one.jpg)\nFigure 1. First data.\n\n"
                    "![](182-105-图片/two.jpg)\nFigure 2. Second data.\n")
        images = list(case_import.IMAGE.finditer(document))
        self.assertEqual(case_import.grouped_figure_caption(document, images, 0), "Figure 1. First data.")
        self.assertIsNone(case_import.grouped_figure_caption(document, images, 1))

    def test_reimport_keeps_unchanged_files_and_manual_edits(self):
        def record():
            return {"id": "sample", "name": "原始名称", "data": [1, 2, 3]}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(case_import.save_record(root, record(), "source-hash"), "written")
            file = root / "sample.json"
            original_time = file.stat().st_mtime_ns
            self.assertEqual(case_import.save_record(root, record(), "source-hash"), "unchanged")
            self.assertEqual(file.stat().st_mtime_ns, original_time)
            edited = json.loads(file.read_text(encoding="utf-8"))
            edited["name"] = "人工修改"
            file.write_text(json.dumps(edited, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(case_import.save_record(root, record(), "source-hash"), "preserved_manual")
            self.assertEqual(json.loads(file.read_text(encoding="utf-8"))["name"], "人工修改")

    def test_dataset_links_do_not_inherit_neighbouring_license_context(self):
        text = ("This licence covers third-party data: https://creativecommons.org/licenses/by/4.0/.\n\n"
                "Data availability: data are deposited at https://doi.org/10.5281/zenodo.12345.\n")
        records, _, _ = case_import.build_records("171-003", text, Path("."))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["data"]["url"], "https://doi.org/10.5281/zenodo.12345")

    def test_windows_newlines_bound_the_link_context(self):
        text = ("Data availability: data are available at https://example.org/dataset.\r\n\r\n"
                "References\r\n[1] Ordinary article. https://doi.org/10.1000/article.\r\n")
        records, _, _ = case_import.build_records("171-003", text, Path("."))
        self.assertEqual([record["data"]["url"] for record in records], ["https://example.org/dataset"])

    def test_source_changes_keep_prior_review_evidence_and_require_rechecking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            papers = root / "papers"
            papers.mkdir()
            document = papers / "182-104-pdf原文.md"
            document.write_text("<table><tr><td>12.5</td></tr></table>", encoding="utf-8")
            library = root / "library.json"
            library.write_text(json.dumps({"mode": "source", "sources": [{"root": str(papers), "papers": ["182-104"]}]}), encoding="utf-8")
            args = argparse.Namespace(library=library, cases=root / "cases", paper=None, apply=True)
            case_import.run(args)
            file = args.cases / "coverage/182-104.json"
            coverage = json.loads(file.read_text(encoding="utf-8"))
            coverage.update(status="reviewed", review={"proof": "original-pdf-proof"})
            file.write_text(json.dumps(coverage), encoding="utf-8")
            self.assertEqual(case_import.run(args)["preserved_reviews"], 1)
            document.write_text(document.read_text(encoding="utf-8") + "\nChanged source context.", encoding="utf-8")
            case_import.run(args)
            updated = json.loads(file.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "extracted")
            self.assertEqual(updated["previous_review"]["review"]["proof"], "original-pdf-proof")


if __name__ == "__main__":
    unittest.main()
