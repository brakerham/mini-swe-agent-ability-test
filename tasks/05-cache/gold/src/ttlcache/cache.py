from collections import OrderedDict
import math

class Cache:
    def __init__(self, capacity, ttl, clock):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        if isinstance(ttl, bool) or not isinstance(ttl, (int,float)) or not math.isfinite(ttl) or ttl < 0:
            raise ValueError("ttl must be finite and nonnegative")
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self.data = OrderedDict()

    def _purge(self, now):
        for key in list(self.data):
            if now >= self.data[key][1]:
                del self.data[key]

    def set(self, key, value):
        now = self.clock()
        self._purge(now)
        self.data[key] = (value, now+self.ttl)
        self.data.move_to_end(key)
        if len(self.data)>self.capacity:
            self.data.popitem(last=False)

    def get(self, key, default=None):
        self._purge(self.clock())
        if key not in self.data:
            return default
        self.data.move_to_end(key)
        return self.data[key][0]

    def keys(self):
        self._purge(self.clock())
        return list(self.data)
