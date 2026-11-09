# Stable build order with explicit invalid-graph errors

`buildplan.planner.plan(graph)` accepts a dict mapping string node names to
lists of dependency names. Return each node exactly once, dependencies before
dependants. Use stable Kahn ordering: at each step choose the currently ready
node that appears earliest in the original graph's insertion order. Duplicate
edges count only once. Empty graphs return []. Do not mutate input lists.

`buildplan.graph.validate(graph)` must reject a dependency absent from the
graph, non-string nodes or dependencies, and non-list dependency collections
with ValueError. plan must call validation and reject every cycle (including
a self-loop or a disconnected cycle) with ValueError. Cycle messages must
contain "cycle" and missing-dependency messages must contain the missing
name. Preserve ordinary valid chain behavior.

## Submission scope

You may change exactly these implementation files:

- `src/buildplan/graph.py`
- `src/buildplan/planner.py`

You may also add or edit `tests/*.py` as evidence of your own verification.
The evaluator restores the original public tests before grading and runs
separate acceptance tests. Authored test changes cannot alter the score.
Keep all other files unchanged; do not create additional source modules.
