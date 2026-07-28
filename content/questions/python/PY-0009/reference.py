def growth_windows(samples, window_size, minimum_growth):
    if not isinstance(window_size, int) or isinstance(window_size, bool) or window_size < 2:
        raise ValueError("window_size must be at least two")
    if not isinstance(minimum_growth, (int, float)) or isinstance(minimum_growth, bool) or minimum_growth < 0:
        raise ValueError("minimum_growth must be non-negative")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in samples):
        raise ValueError("samples must be numeric")
    matches = []
    for start in range(len(samples) - window_size + 1):
        window = samples[start:start + window_size]
        if all(left <= right for left, right in zip(window, window[1:])) and window[-1] - window[0] >= minimum_growth:
            matches.append([start, start + window_size - 1])
    return matches
