def parse_chunked_records(chunks):
    if any(not isinstance(chunk, str) for chunk in chunks):
        raise ValueError("chunks must be strings")
    buffer = ""
    output = []
    for chunk in chunks:
        buffer += chunk
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if not line:
                continue
            if line.count("=") != 1:
                raise ValueError("malformed record")
            key, value = line.split("=", 1)
            if not key:
                raise ValueError("empty key")
            output.append({"key": key, "value": value})
    if buffer:
        raise ValueError("unterminated record")
    return output
