from reference import collect_api_pages

CASES = [({'pages': [{'token': None, 'next_token': 'p2', 'items': [{'id': 'a'}]}, {'token': 'p2', 'next_token': None, 'items': [{'id': 'b'}]}]}, [{'id': 'a'}, {'id': 'b'}]), ({'pages': [{'token': None, 'next_token': None, 'items': []}]}, []), ({'pages': []}, []), ({'pages': [{'token': None, 'next_token': None, 'items': [{'id': 'x', 'value': 3}]}]}, [{'id': 'x', 'value': 3}])]

def test_reference_cases():
    for payload, expected in CASES:
        assert collect_api_pages(**payload) == expected
