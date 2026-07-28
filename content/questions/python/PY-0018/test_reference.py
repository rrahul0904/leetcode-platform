from reference import health_breach_intervals

CASES = [({'samples': [[1, 0.1], [2, 0.8], [3, 0.9], [4, 0.2]], 'threshold': 0.7, 'minimum_consecutive': 2}, [[2, 3]]), ({'samples': [[1, 0.8], [2, 0.1], [3, 0.9]], 'threshold': 0.7, 'minimum_consecutive': 2}, []), ({'samples': [], 'threshold': 0.5, 'minimum_consecutive': 1}, []), ({'samples': [[1, 1.0], [2, 1.0], [3, 1.0]], 'threshold': 1.0, 'minimum_consecutive': 1}, [[1, 3]])]

def test_reference_cases():
    for payload, expected in CASES:
        assert health_breach_intervals(**payload) == expected
