from reference import shortest_dependency_path

CASES = [({'graph': {'a': ['c', 'b'], 'b': ['d'], 'c': ['d'], 'd': []}, 'start': 'a', 'target': 'd'}, ['a', 'b', 'd']), ({'graph': {'a': [], 'b': []}, 'start': 'a', 'target': 'b'}, []), ({'graph': {'a': []}, 'start': 'a', 'target': 'a'}, ['a']), ({'graph': {'a': ['b'], 'b': ['c'], 'c': []}, 'start': 'a', 'target': 'c'}, ['a', 'b', 'c'])]

def test_reference_cases():
    for payload, expected in CASES:
        assert shortest_dependency_path(**payload) == expected
