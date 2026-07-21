def retry_schedule(attempts, base_delay, maximum_delay):
    values = (attempts, base_delay, maximum_delay)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError("all arguments must be integers")
    if attempts < 0 or base_delay <= 0 or maximum_delay <= 0 or base_delay > maximum_delay:
        raise ValueError("invalid retry configuration")
    result = []
    delay = base_delay
    for _ in range(attempts):
        result.append(delay)
        delay = min(maximum_delay, delay * 2)
    return result
