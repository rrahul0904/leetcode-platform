def compensation_plan(steps, failed_index):
    if not isinstance(failed_index, int) or isinstance(failed_index, bool) or not 0 <= failed_index < len(steps):
        raise ValueError("failed_index is out of range")
    names = [step.get("name") for step in steps]
    if any(not isinstance(name, str) or not name for name in names) or len(names) != len(set(names)):
        raise ValueError("step names must be unique")
    return [step["compensation"] for step in reversed(steps[:failed_index]) if step.get("compensation") is not None]
