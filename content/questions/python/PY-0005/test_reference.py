from reference import select_worker_batch

CASES = [({'tasks': [{'id': 'b', 'cost': 2, 'priority': 2, 'enqueued_at': 2}, {'id': 'a', 'cost': 3, 'priority': 2, 'enqueued_at': 1}], 'max_cost': 4}, ['a']), ({'tasks': [{'id': 'low', 'cost': 1, 'priority': 1, 'enqueued_at': 0}, {'id': 'high', 'cost': 2, 'priority': 4, 'enqueued_at': 9}], 'max_cost': 3}, ['high', 'low']), ({'tasks': [], 'max_cost': 5}, []), ({'tasks': [{'id': 'large', 'cost': 9, 'priority': 9, 'enqueued_at': 0}, {'id': 'fit', 'cost': 2, 'priority': 1, 'enqueued_at': 0}], 'max_cost': 2}, ['fit'])]

def test_reference_cases():
    for payload, expected in CASES:
        assert select_worker_batch(**payload) == expected
