def deduplicate_tasks(tasks):
    best = {}
    first_position = {}
    for position, task in enumerate(tasks):
        key, version = task.get("key"), task.get("version")
        if not isinstance(key, str) or not key or not isinstance(version, int) or isinstance(version, bool):
            raise ValueError("invalid task identity")
        first_position.setdefault(key, position)
        if key not in best or version > best[key]["version"]:
            best[key] = dict(task)
    return [best[key] for key in sorted(best, key=first_position.get)]
