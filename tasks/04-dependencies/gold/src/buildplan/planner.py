from .graph import validate

def plan(graph):
    validate(graph)
    pending = {name:set(dependencies) for name, dependencies in graph.items()}
    result = []
    while pending:
        ready = next((name for name, dependencies in pending.items() if not dependencies), None)
        if ready is None:
            raise ValueError("dependency cycle detected")
        result.append(ready)
        del pending[ready]
        for dependencies in pending.values():
            dependencies.discard(ready)
    return result
