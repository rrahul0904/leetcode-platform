from reference import crawl_frontier

CASES = [({'graph': {'a': ['c', 'b'], 'b': ['d'], 'c': [], 'd': []}, 'start': 'a', 'maximum_depth': 1}, ['a', 'b', 'c']), ({'graph': {'a': ['b'], 'b': ['a']}, 'start': 'a', 'maximum_depth': 5}, ['a', 'b']), ({'graph': {'a': []}, 'start': 'a', 'maximum_depth': 0}, ['a']), ({'graph': {'a': ['b'], 'b': ['c'], 'c': []}, 'start': 'a', 'maximum_depth': 2}, ['a', 'b', 'c'])]

def test_reference_cases():
    for payload, expected in CASES:
        assert crawl_frontier(**payload) == expected
