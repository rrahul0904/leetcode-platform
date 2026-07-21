def diff_snapshots(before, after):
    before_keys, after_keys = set(before), set(after)
    changed = [{"key": key, "before": before[key], "after": after[key]} for key in sorted(before_keys & after_keys) if before[key] != after[key]]
    return {"added": sorted(after_keys - before_keys), "removed": sorted(before_keys - after_keys), "changed": changed}
