import heapq

def merge_pipeline_batches(batches):
    for batch in batches:
        if any(left > right for left, right in zip(batch, batch[1:])):
            raise ValueError("each batch must be sorted")
    heap = []
    for batch_index, batch in enumerate(batches):
        if batch:
            heapq.heappush(heap, (batch[0], batch_index, 0))
    output = []
    while heap:
        value, batch_index, position = heapq.heappop(heap)
        if not output or value != output[-1]:
            output.append(value)
        next_position = position + 1
        if next_position < len(batches[batch_index]):
            heapq.heappush(heap, (batches[batch_index][next_position], batch_index, next_position))
    return output
