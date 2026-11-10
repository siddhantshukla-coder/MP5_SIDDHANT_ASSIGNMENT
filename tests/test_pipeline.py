
import json
import tempfile
import unittest
from pathlib import Path

from pipeline import parse, validate
from pipeline.parse import parse_overlap_text, parse_prereq_text
from run_pipeline import main

FIX = Path(__file__).parent / "fixtures"


class TestParsers(unittest.TestCase):
    def test_prereq_and_or_groups(self):
        self.assertEqual(parse_prereq_text("Either CSL304 or CS550/DSL501 and MAL403 or equivalent"),
                         [["CSL304", "CS550", "DSL501"], ["MAL403"]])
        self.assertEqual(parse_prereq_text("CSL100, CSL201, CSL202"), [["CSL100"], ["CSL201"], ["CSL202"]])
        self.assertEqual(parse_prereq_text("None"), [])

    def test_overlap(self):
        self.assertEqual(parse_overlap_text("MAL403 (35%), DSL201 (60%)"), [("MAL403", 35), ("DSL201", 60)])
        self.assertEqual(parse_overlap_text("NA"), [])


class TestPipeline(unittest.TestCase):
    def test_sample_runs_and_exports(self):
        with tempfile.TemporaryDirectory() as out:
            rc = main(["--raw", str(FIX / "sample" / "raw"), "--out", out])
            self.assertEqual(rc, 0)
            chunks = [json.loads(l) for l in open(Path(out) / "chunks.jsonl", encoding="utf-8")]
            self.assertTrue(chunks)
            for c in chunks:                       # every chunk is traceable and filterable
                self.assertTrue(c["parent_id"] and c["chunk_type"] and c["metadata"]["source_url"])

    def test_broken_fails_loudly(self):
        raw = FIX / "broken" / "raw"
        data = parse.run(raw, raw.parent / "interim")
        caught = {i["check"] for i in validate.validate(data) if i["severity"] == "error"}
        for check in ("missing_prerequisite_course", "prerequisite_cycle", "non_numeric_credits",
                      "duplicate_id", "missing_source_url"):
            self.assertIn(check, caught)
        with tempfile.TemporaryDirectory() as out:
            self.assertEqual(main(["--raw", str(raw), "--out", out]), 1)


if __name__ == "__main__":
    unittest.main()
