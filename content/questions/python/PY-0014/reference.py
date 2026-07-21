import heapq

def plugin_load_order(plugins):
    indegree = {name: 0 for name in plugins}
    dependents = {name: [] for name in plugins}
    for name, dependencies in plugins.items():
        for dependency in set(dependencies):
            if dependency not in plugins or dependency == name:
                raise ValueError("invalid dependency")
            indegree[name] += 1
            dependents[dependency].append(name)
    ready = [name for name, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    output = []
    while ready:
        name = heapq.heappop(ready)
        output.append(name)
        for dependent in dependents[name]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(ready, dependent)
    if len(output) != len(plugins):
        raise ValueError("plugin dependency cycle")
    return output
