"""Offline importer and fail-closed provisional scoring contract tests."""

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


importer = load_script("import_level4_interviews.py")
scorer = load_script("interview_assessment_scoring.py")

NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def synthetic_docx(path, paragraphs, answer_key=False):
    parts = []
    for paragraph in paragraphs:
        parts.append(f'<w:p><w:r><w:t>{escape(paragraph)}</w:t></w:r></w:p>')
    if answer_key:
        rows = []
        for number in range(7, 17):
            cells = "".join(
                f'<w:tc><w:p><w:r><w:t>{escape(value)}</w:t></w:r></w:p></w:tc>'
                for value in (str(number), "A", "feature", "explanation")
            )
            rows.append(f"<w:tr>{cells}</w:tr>")
        parts.append("<w:tbl>" + "".join(rows) + "</w:tbl>")
    xml = (
        f'<w:document xmlns:w="{NS}"><w:body>'
        + "".join(parts)
        + "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)


def candidate_fixture():
    items = []
    for section, numbers in (("A", range(1, 3)), ("B", range(3, 6)),
                             ("C", range(6, 7)), ("D", range(7, 17))):
        items.append(f"SECTION {section} - PRACTICE")
        for number in numbers:
            if number <= 6:
                items.append(f"Question {number} - Synthetic Question [{10} marks | recommended 6 min]")
                items.extend(["Requirements", "Explain solution.", "What is being assessed: Reasoning"])
            else:
                items.append(f"{number}. Choose the correct design.")
                items.extend([f"{c}. choice {c}" for c in "ABCD"])
    items.append("End of paper: confirm your answers")
    return items


class Level4AssessmentContractTests(unittest.TestCase):
    def test_all_seven_sets_staged_and_solutions_separated(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            for number in range(3, 10):
                synthetic_docx(
                    root / importer.CANDIDATE_PATTERN.format(n=number),
                    candidate_fixture(),
                )
                synthetic_docx(
                    root / importer.GUIDE_PATTERN.format(n=number),
                    ["Reference solutions, interviewer-only."],
                    answer_key=True,
                )
            out = root / "staged"
            catalog = importer.ingest(root, out)
            self.assertEqual(len(catalog["sets"]), 7)
            self.assertEqual(sum(item["question_count"] for item in catalog["sets"]), 112)
            candidate = (out / "candidate_review_only" / "set-3.json").read_text()
            secret = (out / "private_interviewer_only" / "set-3.json").read_text()
            self.assertNotIn("mcq_answers", candidate)
            self.assertNotIn("Reference solutions", candidate)
            self.assertIn("mcq_answers", secret)
            self.assertIn('"publication_state": "review_required"', candidate)

    def test_missing_questions_and_keys_fail_closed(self):
        with self.assertRaises(ValueError):
            importer._candidate_questions(["SECTION D - SNOWFLAKE", "7. Some question"], 3)
        with self.assertRaises(ValueError):
            importer._guide_answers([], 3)

    def test_scoring_is_provisional_and_cannot_make_hiring_decision(self):
        questions = [{"number": n, "marks": importer.MARKS[n]} for n in range(1, 17)]
        key = {str(n): "A" for n in range(7, 17)}
        answers = {"1": "A detailed Python implementation", "7": "A", "8": "B"}
        result = scorer.score_level4(questions, answers, key)
        self.assertEqual(result["automatically_scored_marks"], 4)
        self.assertEqual(result["remaining_human_review_maximum"], 60)
        self.assertEqual(result["state"], "pending_human_review")
        self.assertIsNone(result["hiring_decision"])
        self.assertNotIn('"mcq_answers"', str(result))

    def test_bad_answer_fails(self):
        questions = [{"number": n, "marks": importer.MARKS[n]} for n in range(1, 17)]
        key = {str(n): "A" for n in range(7, 17)}
        with self.assertRaises(ValueError):
            scorer.score_level4(questions, {"7": "E"}, key)
        with self.assertRaises(ValueError):
            scorer.score_level4(questions, {"17": "A"}, key)


if __name__ == "__main__":
    unittest.main()
