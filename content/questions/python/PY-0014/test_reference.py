from reference import plugin_load_order

CASES = [({'plugins': {'api': ['core'], 'core': [], 'ui': ['core']}}, ['core', 'api', 'ui']), ({'plugins': {'b': [], 'a': []}}, ['a', 'b']), ({'plugins': {}}, []), ({'plugins': {'metrics': ['core'], 'core': [], 'alerts': ['metrics']}}, ['core', 'metrics', 'alerts'])]

def test_reference_cases():
    for payload, expected in CASES:
        assert plugin_load_order(**payload) == expected
