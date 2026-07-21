from reference import allocate_resource_windows

CASES = [({'requests': [{'id': 'a', 'start': 0, 'end': 5, 'units': 2}, {'id': 'b', 'start': 2, 'end': 4, 'units': 2}], 'capacity': 3}, ['a']), ({'requests': [{'id': 'b', 'start': 5, 'end': 8, 'units': 3}, {'id': 'a', 'start': 0, 'end': 5, 'units': 3}], 'capacity': 3}, ['a', 'b']), ({'requests': [], 'capacity': 2}, []), ({'requests': [{'id': 'a', 'start': 0, 'end': 10, 'units': 1}, {'id': 'b', 'start': 3, 'end': 7, 'units': 1}, {'id': 'c', 'start': 4, 'end': 5, 'units': 1}], 'capacity': 2}, ['a', 'b'])]

def test_reference_cases():
    for payload, expected in CASES:
        assert allocate_resource_windows(**payload) == expected
