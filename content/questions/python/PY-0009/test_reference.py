from reference import growth_windows

CASES = [({'samples': [3, 4, 8, 7, 9], 'window_size': 3, 'minimum_growth': 4}, [[0, 2]]), ({'samples': [1, 1, 1], 'window_size': 2, 'minimum_growth': 0}, [[0, 1], [1, 2]]), ({'samples': [5], 'window_size': 2, 'minimum_growth': 1}, []), ({'samples': [1, 2, 4, 7], 'window_size': 3, 'minimum_growth': 3}, [[0, 2], [1, 3]])]

def test_reference_cases():
    for payload, expected in CASES:
        assert growth_windows(**payload) == expected
