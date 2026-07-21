def select_worker_batch(tasks, max_cost):
    if not isinstance(max_cost, int) or isinstance(max_cost, bool) or max_cost <= 0:
        raise ValueError("max_cost must be positive")
    seen = set()
    normalized = []
    for task in tasks:
        task_id = task.get("id")
        cost = task.get("cost")
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            raise ValueError("task IDs must be unique non-empty strings")
        if not isinstance(cost, int) or isinstance(cost, bool) or cost <= 0:
            raise ValueError("task cost must be positive")
        seen.add(task_id)
        normalized.append(task)
    remaining = max_cost
    selected = []
    for task in sorted(normalized, key=lambda item: (-item["priority"], item["enqueued_at"], item["id"])):
        if task["cost"] <= remaining:
            selected.append(task["id"])
            remaining -= task["cost"]
    return selected
