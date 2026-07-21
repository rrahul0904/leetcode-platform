from reference import compensation_plan

CASES = [({'steps': [{'name': 'reserve', 'compensation': 'release'}, {'name': 'charge', 'compensation': 'refund'}, {'name': 'email', 'compensation': None}], 'failed_index': 2}, ['refund', 'release']), ({'steps': [{'name': 'first', 'compensation': 'undo'}], 'failed_index': 0}, []), ({'steps': [{'name': 'a', 'compensation': None}, {'name': 'b', 'compensation': 'undo-b'}], 'failed_index': 1}, []), ({'steps': [{'name': 'a', 'compensation': 'undo-a'}, {'name': 'b', 'compensation': None}, {'name': 'c', 'compensation': 'undo-c'}], 'failed_index': 2}, ['undo-a'])]

def test_reference_cases():
    for payload, expected in CASES:
        assert compensation_plan(**payload) == expected
