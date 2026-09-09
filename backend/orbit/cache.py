from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from time import monotonic


class TTLCache:
    def __init__(self, capacity=256, ttl=60):
        self.capacity, self.ttl = capacity, ttl
        self.entries = OrderedDict()
        self.lock = RLock()

    def get_or_load(self, key, loader):
        with self.lock:
            entry = self.entries.get(key)
            if entry and entry[0] > monotonic():
                self.entries.move_to_end(key)
                return deepcopy(entry[1]), True
        value = loader()
        with self.lock:
            self.entries[key] = (monotonic() + self.ttl, deepcopy(value))
            self.entries.move_to_end(key)
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
        return value, False

    def invalidate_user(self, user_id):
        with self.lock:
            for key in list(self.entries):
                if key[0] == user_id:
                    del self.entries[key]


cache = TTLCache()
