def health_breach_intervals(samples, threshold, minimum_consecutive):
    if not isinstance(minimum_consecutive, int) or isinstance(minimum_consecutive, bool) or minimum_consecutive <= 0:
        raise ValueError("minimum_consecutive must be positive")
    if any(samples[index][0] >= samples[index + 1][0] for index in range(len(samples) - 1)):
        raise ValueError("timestamps must increase")
    output = []
    start = None
    count = 0
    previous_timestamp = None
    for timestamp, value in samples + [[None, None]]:
        if timestamp is not None and value >= threshold:
            if start is None:
                start = timestamp
            previous_timestamp = timestamp
            count += 1
        else:
            if start is not None and count >= minimum_consecutive:
                output.append([start, previous_timestamp])
            start, count, previous_timestamp = None, 0, None
    return output
