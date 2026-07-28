def collect_api_pages(pages):
    expected_token = None
    seen_tokens = set()
    seen_items = set()
    output = []
    for page in pages:
        token = page.get("token")
        if token != expected_token or (token is not None and token in seen_tokens):
            raise ValueError("broken pagination token chain")
        if token is not None:
            seen_tokens.add(token)
        for item in page.get("items", []):
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id or item_id in seen_items:
                raise ValueError("item IDs must be unique")
            seen_items.add(item_id)
            output.append(item)
        expected_token = page.get("next_token")
    if expected_token is not None:
        raise ValueError("page chain is incomplete")
    return output
