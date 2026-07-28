from collections import deque

def crawl_frontier(graph, start, maximum_depth):
    if start not in graph or not isinstance(maximum_depth, int) or isinstance(maximum_depth, bool) or maximum_depth < 0:
        raise ValueError("invalid crawl configuration")
    queue = deque([(start, 0)])
    seen = {start}
    output = []
    while queue:
        page, depth = queue.popleft()
        output.append(page)
        if depth == maximum_depth:
            continue
        for neighbor in sorted(set(graph.get(page, []))):
            if neighbor in graph and neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, depth + 1))
    return output
