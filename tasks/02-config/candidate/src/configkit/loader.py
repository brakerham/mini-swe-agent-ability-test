from .merge import deep_merge

def load_config(base, override, environ):
    result = deep_merge(base, override)
    for key, value in result.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            result[key] = environ[value[2:-1]]
    return result
