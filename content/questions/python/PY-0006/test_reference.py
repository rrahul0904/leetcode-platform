from reference import retry_schedule

CASES = [({'attempts': 4, 'base_delay': 2, 'maximum_delay': 20}, [2, 4, 8, 16]), ({'attempts': 6, 'base_delay': 3, 'maximum_delay': 10}, [3, 6, 10, 10, 10, 10]), ({'attempts': 0, 'base_delay': 1, 'maximum_delay': 1}, []), ({'attempts': 3, 'base_delay': 5, 'maximum_delay': 5}, [5, 5, 5])]

def test_reference_cases():
    for payload, expected in CASES:
        assert retry_schedule(**payload) == expected
