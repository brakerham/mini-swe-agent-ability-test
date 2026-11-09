# Add recursive configuration overrides and environment placeholders

Implement `configkit.merge.deep_merge(base, override)` and
`configkit.loader.load_config(base, override, environ)`.
Inputs are JSON-compatible mappings. Merge mappings recursively; every other
override replaces the base value, including lists and None. Keys absent from
override are preserved. The result shares no dict/list containers with either
input, even for replaced or unchanged branches.

After merging, load_config recursively expands strings that exactly match
`${NAME}`, where NAME matches [A-Za-z_][A-Za-z0-9_]*, through the supplied
environ mapping. Return its string value without recursive interpolation.
Embedded placeholders, malformed names and ordinary strings remain literal.
Missing referenced variables raise KeyError. Empty strings are valid values.
Never read os.environ; never mutate the inputs or environment mapping.

## Submission scope

You may change exactly these implementation files:

- `src/configkit/merge.py`
- `src/configkit/loader.py`

You may also add or edit `tests/*.py` as evidence of your own verification.
The evaluator restores the original public tests before grading and runs
separate acceptance tests. Authored test changes cannot alter the score.
Keep all other files unchanged; do not create additional source modules.
