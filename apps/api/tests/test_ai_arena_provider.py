import json

from rigor_api.ai_arena_provider import _public_generation_context


def test_generation_context_excludes_hidden_test_bodies() -> None:
    question = {
        "title": "Public challenge",
        "structured_content": {
            "question_type": "python_coding",
            "problem_statement": "Return the doubled value.",
            "candidate_instructions": ["Keep the public function signature."],
            "constraints": ["Input is an integer."],
            "public_examples": [{"input": 2, "output": 4}],
            "mode_specification": {
                "runtime": "python3.13",
                "entrypoint": "solve",
                "starter_code": "def solve(value: int) -> int:\n    raise NotImplementedError\n",
                "tests": [
                    {
                        "id": "public-1",
                        "visibility": "public",
                        "input": {"value": 2},
                        "expected_output": 4,
                    },
                    {
                        "id": "hidden-secret",
                        "visibility": "hidden",
                        "input": {"value": 99173, "sentinel": "TOP_SECRET_INPUT"},
                        "expected_output": "TOP_SECRET_OUTPUT",
                    },
                ],
            },
        },
    }

    serialized = _public_generation_context(question, "Use arithmetic.")
    payload = json.loads(serialized)

    assert payload["candidate_prompt"] == "Use arithmetic."
    assert [test["id"] for test in payload["public_tests"]] == ["public-1"]
    assert "hidden-secret" not in serialized
    assert "TOP_SECRET_INPUT" not in serialized
    assert "TOP_SECRET_OUTPUT" not in serialized
