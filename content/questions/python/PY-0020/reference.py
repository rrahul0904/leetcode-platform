def trace_root_errors(events):
    seen = set()
    roots = {}
    for event in events:
        identity = (event.get("trace"), event.get("service"), event.get("timestamp"))
        if identity in seen:
            raise ValueError("duplicate trace event")
        seen.add(identity)
        if event.get("level") == "error":
            candidate = dict(event)
            current = roots.get(event["trace"])
            if current is None or (candidate["timestamp"], candidate["service"]) < (current["timestamp"], current["service"]):
                roots[event["trace"]] = candidate
    return [roots[trace] for trace in sorted(roots)]
