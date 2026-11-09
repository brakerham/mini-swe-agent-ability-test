class Cache:
    def __init__(self, capacity, ttl, clock):
        self.capacity, self.ttl, self.clock = capacity, ttl, clock
        self.data = {}

    def set(self, key, value):
        self.data[key] = (value, self.clock()+self.ttl)
        if len(self.data)>self.capacity:
            del self.data[next(iter(self.data))]

    def get(self, key, default=None):
        if key not in self.data:
            return default
        value, deadline = self.data[key]
        if self.clock()>deadline:
            del self.data[key]
            return default
        return value

    def keys(self):
        return list(self.data)
