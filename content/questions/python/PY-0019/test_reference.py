from reference import diff_snapshots

CASES = [({'before': {'a': 1, 'b': 2}, 'after': {'b': 3, 'c': 4}}, {'added': ['c'], 'removed': ['a'], 'changed': [{'key': 'b', 'before': 2, 'after': 3}]}), ({'before': {}, 'after': {}}, {'added': [], 'removed': [], 'changed': []}), ({'before': {'x': [1]}, 'after': {'x': [1]}}, {'added': [], 'removed': [], 'changed': []}), ({'before': {'z': 0, 'a': False}, 'after': {'z': 1, 'a': True}}, {'added': [], 'removed': [], 'changed': [{'key': 'a', 'before': False, 'after': True}, {'key': 'z', 'before': 0, 'after': 1}]})]

def test_reference_cases():
    for payload, expected in CASES:
        assert diff_snapshots(**payload) == expected
