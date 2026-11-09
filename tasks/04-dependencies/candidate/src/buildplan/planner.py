from .graph import validate

def plan(graph):
    validate(graph)
    seen, result = set(), []
    def visit(name):
        if name in seen:
            return
        seen.add(name)
        for dependency in graph.get(name, []):
            visit(dependency)
        result.append(name)
    for name in sorted(graph):
        visit(name)
    return result
