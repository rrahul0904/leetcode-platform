from reference import rate_limit_decisions

CASES = [({'events': [[0, 'a'], [1, 'a'], [2, 'a']], 'limit': 2, 'window_seconds': 10}, [True, True, False]), ({'events': [[0, 'a'], [1, 'b'], [2, 'a']], 'limit': 1, 'window_seconds': 2}, [True, True, True]), ({'events': [], 'limit': 1, 'window_seconds': 1}, []), ({'events': [[0, 'a'], [5, 'a'], [5, 'a']], 'limit': 1, 'window_seconds': 5}, [True, True, False])]

def test_reference_cases():
    for payload, expected in CASES:
        assert rate_limit_decisions(**payload) == expected
