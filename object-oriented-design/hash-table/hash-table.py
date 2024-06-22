class Item(object):
    def __init__(self, key, value):
        self.key = key
        self.value = value

class Hash(object):
    def __init__(self, size):
        self.size = size
        self.table = [ [] for _ in range(self.size)] 
    
    def hash_function(self, key):
        return key % self.size
    
    def set(self, key, value):
        hash_ind = self.hash_function(key)
        for item in self.table[hash_ind]:
            if item.key == key:
                item.value = value
                return
        self.table[hash_ind][key] = value


    def get(self,key):
        hash_ind = self.hash_function(key)
        if self.table[hash_ind] and key in self.table[hash_ind]:
            return self.table[hash_ind][key]
        return 'Key not found'

    def remove(self, key):
        hash_ind = self.hash_function(key)
        if self.table[hash_ind] and key in self.table[hash_ind]:
            del self.table[hash_ind][key]
            return
        return 'does not exist'
