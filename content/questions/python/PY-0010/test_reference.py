from reference import deduplicate_tasks

CASES = [({'tasks': [{'key': 'a', 'version': 1, 'value': 'old'}, {'key': 'a', 'version': 2, 'value': 'new'}]}, [{'key': 'a', 'version': 2, 'value': 'new'}]), ({'tasks': [{'key': 'b', 'version': 1}, {'key': 'a', 'version': 3}, {'key': 'b', 'version': 2}]}, [{'key': 'b', 'version': 2}, {'key': 'a', 'version': 3}]), ({'tasks': []}, []), ({'tasks': [{'key': 'a', 'version': 2, 'value': 1}, {'key': 'a', 'version': 2, 'value': 2}]}, [{'key': 'a', 'version': 2, 'value': 1}])]

def test_reference_cases():
    for payload, expected in CASES:
        assert deduplicate_tasks(**payload) == expected
