def allocate_resource_windows(requests, capacity):
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
        raise ValueError("capacity must be positive")
    seen = set()
    accepted = []
    for request in sorted(requests, key=lambda item: (item["start"], item["end"], item["id"])):
        request_id = request.get("id")
        start, end, units = request.get("start"), request.get("end"), request.get("units")
        if request_id in seen or not isinstance(request_id, str) or not request_id:
            raise ValueError("duplicate or invalid request ID")
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in (start, end, units)) or start >= end or units <= 0:
            raise ValueError("invalid resource interval")
        seen.add(request_id)
        boundaries = sorted({start, end, *(value for item in accepted for value in (item["start"], item["end"]))})
        safe = True
        for point in boundaries:
            if start <= point < end:
                used = sum(item["units"] for item in accepted if item["start"] <= point < item["end"])
                if used + units > capacity:
                    safe = False
                    break
        if safe:
            accepted.append(request)
    return [item["id"] for item in accepted]
