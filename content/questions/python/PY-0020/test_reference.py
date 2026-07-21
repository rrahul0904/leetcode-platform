from reference import trace_root_errors

CASES = [({'events': [{'trace': 't1', 'service': 'api', 'timestamp': 3, 'level': 'error'}, {'trace': 't1', 'service': 'db', 'timestamp': 2, 'level': 'error'}]}, [{'trace': 't1', 'service': 'db', 'timestamp': 2, 'level': 'error'}]), ({'events': [{'trace': 't2', 'service': 'api', 'timestamp': 1, 'level': 'info'}]}, []), ({'events': []}, []), ({'events': [{'trace': 'b', 'service': 'worker', 'timestamp': 1, 'level': 'error'}, {'trace': 'a', 'service': 'queue', 'timestamp': 4, 'level': 'error'}]}, [{'trace': 'a', 'service': 'queue', 'timestamp': 4, 'level': 'error'}, {'trace': 'b', 'service': 'worker', 'timestamp': 1, 'level': 'error'}])]

def test_reference_cases():
    for payload, expected in CASES:
        assert trace_root_errors(**payload) == expected
