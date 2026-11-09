# Expired cache entries and updates break LRU eviction

Repair `ttlcache.cache.Cache(capacity, ttl, clock)`. clock is a supplied
zero-argument monotonic seconds function. capacity must be a positive int
(bool rejected); ttl must be a finite nonnegative int/float (bool rejected).
Invalid constructor arguments raise ValueError. No real-time sleeps.

`set(key,value)` purges expired entries first, inserts or updates the key,
resets its deadline to clock()+ttl, marks it most recently used and evicts
the least recently used LIVE entry if capacity is exceeded. ttl=0 means
immediate expiration. `get(key, default=None)` returns default when absent
or expired; a hit marks the key most recently used WITHOUT extending TTL.
Storing None is valid. At now == deadline the entry is expired.
`keys()` returns a list of live keys ordered least to most recently used,
without changing recency. Expiration applies independently to every key.
Preserve object identity of stored values. The clock never moves backwards.

## Submission scope

You may change exactly these implementation files:

- `src/ttlcache/cache.py`

You may also add or edit `tests/*.py` as evidence of your own verification.
The evaluator restores the original public tests before grading and runs
separate acceptance tests. Authored test changes cannot alter the score.
Keep all other files unchanged; do not create additional source modules.
