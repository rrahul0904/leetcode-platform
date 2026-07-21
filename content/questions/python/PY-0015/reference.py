from collections import defaultdict, deque

def rate_limit_decisions(events, limit, window_seconds):
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0 or not isinstance(window_seconds, int) or isinstance(window_seconds, bool) or window_seconds <= 0:
        raise ValueError("limits must be positive integers")
    queues = defaultdict(deque)
    output = []
    previous = None
    for timestamp, tenant in events:
        if previous is not None and timestamp < previous:
            raise ValueError("events must be ordered")
        previous = timestamp
        queue = queues[tenant]
        while queue and queue[0] <= timestamp - window_seconds:
            queue.popleft()
        allowed = len(queue) < limit
        output.append(allowed)
        if allowed:
            queue.append(timestamp)
    return output
