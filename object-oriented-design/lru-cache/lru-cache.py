from collections import OrderedDict
class LRU:
    def __init__(self, capacity):
        self.cache = OrderedDict()
        self.capacity = capacity
        
    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return 'Key not found'
    
    def put(self, key, value):
        if len(self.cache) == self.capacity:
            self.cache.popitem(last= False)
        self.cache[key] = value
        self.cache.move_to_end(key)