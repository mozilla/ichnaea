def _is_true(value):
    if isinstance(value, str):
        value = value.lower() in ('true', '1')
    return value
