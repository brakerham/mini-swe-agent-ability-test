import re
from .merge import deep_merge

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

def load_config(base, override, environ):
    def expand(value):
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, str):
            match = _PLACEHOLDER.fullmatch(value)
            if match:
                return environ[match.group(1)]
        return value
    return expand(deep_merge(base, override))
