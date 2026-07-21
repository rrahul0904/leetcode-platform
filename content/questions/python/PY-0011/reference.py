from collections import deque

def shortest_dependency_path(graph, start, target):
    if start not in graph or target not in graph:
        raise ValueError("start and target must exist")
    for neighbors in graph.values():
        if any(node not in graph for node in neighbors):
            raise ValueError("all referenced nodes must exist")
    queue = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == target:
            return path
        for neighbor in sorted(set(graph[node])):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])
    return []
