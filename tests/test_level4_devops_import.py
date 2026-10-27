"""Offline DevOps extraction, privacy boundary, and provisional score contract tests."""

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def load_module(filename):
    spec = importlib.util.spec_from_file_location(filename, ROOT / "scripts" / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


importer = load_module("import_level4_devops.py")
scorer = load_module("interview_assessment_scoring.py")

NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def synthetic_docx(path, paragraphs):
    payload = "".join(
        f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paragraphs
    )
    xml = f'<w:document xmlns:w="{NS}"><w:body>{payload}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)


def questions_fixture():
    result = []
    for section, numbers in (
        ("A", range(1, 3)), ("B", range(3, 5)), ("C", range(5, 15))
    ):
        result.append(f"SECTION {section} – test")
        for number in numbers:
            if number < 5:
                result.extend([
                    f"Question {number} – Code/Scenario [{15} marks]",
                    "Describe a robust, evidence-backed solution.",
                    "Requirements",
                    "Discuss failures and complexity.",
                ])
            else:
                result.extend([
                    f"Question {number} [4 marks]",
                    f"What is the correct engineering choice for Q{number}?",
                    *[f"{c}. option {c}" for c in "ABCD"],
                ])
    result.append("End of paper: submit")
    return result


def guide_fixture():
    result = ["SECTION C – DEVOPS MCQ ANSWER KEY"]
    for number in range(5, 15):
        result.extend([
            f"Question {number}",
            "Correct answer: B. correct implementation",
        ])
    result.append("INTERVIEWER DECISION GUIDE")
    result.append("Sensitive interviewer guidance")
    return result


class DevOpsImportTests(unittest.TestCase):
    def test_ten_complete_private_assessment_pairs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number in range(1, 11):
                synthetic_docx(
                    root / importer.CANDIDATE.format(n=number), questions_fixture()
                )
                synthetic_docx(
                    root / importer.INTERVIEWER.format(n=number), guide_fixture()
                )
            target = root / "private_staging"
            catalog = importer.ingest(root, target)
            self.assertEqual(sum(s["question_count"] for s in catalog["sets"]), 140)
            for number in range(1, 11):
                name = f"set-{number:02d}.json"
                visible = (target / "candidate_review_only" / name).read_text()
                private = (target / "private_interviewer_only" / name).read_text()
                self.assertNotIn("mcq_answers", visible)
                self.assertNotIn("Sensitive interviewer guidance", visible)
                self.assertIn('"publication_state": "review_required"', visible)
                self.assertIn('"mcq_answers"', private)
                self.assertIn('"visibility": "interviewer_only"', private)

    def test_invalid_question_set_and_answer_keys_fail_closed(self):
        with self.assertRaises(ValueError):
            importer.parse_candidate(["SECTION C – DEVOPS MCQ", "Question 5 [4 marks]"], 1)
        with self.assertRaises(ValueError):
            importer.parse_interviewer_key(["SECTION C – DEVOPS MCQ ANSWER KEY"], 1)

    def test_private_output_location_is_required(self):
        with self.assertRaises(ValueError):
            importer.ingest(Path("/tmp/input"), Path("/tmp/apps/web/public/source"))

    def test_devops_provisional_scoring_requires_human_review(self):
        questions = [
            {"number": n, "marks": 15 if n < 5 else 4} for n in range(1, 15)
        ]
        key = {str(n): "B" for n in range(5, 15)}
        result = scorer.score_assessment(
            questions, {"1": "Correct code", "5": "B", "6": "A"}, key,
            profile="devops",
        )
        self.assertEqual(result["automatically_scored_marks"], 4)
        self.assertEqual(result["remaining_human_review_maximum"], 60)
        self.assertIsNone(result["hiring_decision"])
        self.assertEqual(result["state"], "pending_human_review")
        with self.assertRaises(ValueError):
            scorer.score_assessment(
                questions, {"5": "B"}, {str(n): "B" for n in range(5, 14)},
                profile="devops",
            )
        with self.assertRaises(ValueError):
            tampered = [dict(q) for q in questions]
            tampered[4]["marks"] = 100
            scorer.score_assessment(tampered, {}, key, profile="devops")


if __name__ == "__main__":
    unittest.main()
