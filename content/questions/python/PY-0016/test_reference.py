from reference import merge_pipeline_batches

CASES = [({'batches': [[1, 4, 7], [2, 4, 8]]}, [1, 2, 4, 7, 8]), ({'batches': [[], [1, 1], []]}, [1]), ({'batches': []}, []), ({'batches': [[-3, 0], [-2, 0, 5], [5]]}, [-3, -2, 0, 5])]

def test_reference_cases():
    for payload, expected in CASES:
        assert merge_pipeline_batches(**payload) == expected
