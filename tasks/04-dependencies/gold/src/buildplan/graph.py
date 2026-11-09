def validate(graph):
    if not isinstance(graph, dict):
        raise ValueError("graph must be a dict")
    for name, dependencies in graph.items():
        if not isinstance(name, str) or not isinstance(dependencies, list):
            raise ValueError("nodes must be strings and dependencies lists")
        for dependency in dependencies:
            if not isinstance(dependency, str):
                raise ValueError("dependencies must be strings")
            if dependency not in graph:
                raise ValueError(f"missing dependency: {dependency}")
