from reference import parse_chunked_records

CASES = [({'chunks': ['a=1\nb=', 'two\n']}, [{'key': 'a', 'value': '1'}, {'key': 'b', 'value': 'two'}]), ({'chunks': ['\n', 'x=\n']}, [{'key': 'x', 'value': ''}]), ({'chunks': []}, []), ({'chunks': ['service=api\nregion=us-east-1\n']}, [{'key': 'service', 'value': 'api'}, {'key': 'region', 'value': 'us-east-1'}])]

def test_reference_cases():
    for payload, expected in CASES:
        assert parse_chunked_records(**payload) == expected
