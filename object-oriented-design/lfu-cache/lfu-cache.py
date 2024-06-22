from collections import OrderedDict, defaultdict
class LFU:
    def __init__(self, capacity):
        self.key_to_freq = defaultdict()
        self.freq_to_key = defaultdict(OrderedDict)
        self.min_freq = 0
        self.capacity = capacity
    
    def get(self, key):
        # 1. check if key present
            #  if yes fetch prev freq, and value and inc freq and pop it from prev index and store in new
            #  check if it there are other elements in the same old freq if not del index
            #  check if it was min and there are no ele then inc min
        #  if not then return no key found
        if key in self.key_to_freq:
            old_freq = self.key_to_freq[key]
            value = self.freq_to_key[old_freq].pop(key)
            if not self.freq_to_key[old_freq]:
                del self.freq_to_key[old_freq]
                if old_freq == self.min_freq:
                    self.min_freq +=1
            self.key_to_freq[key]+=1
            self.freq_to_key[old_freq+1][key]= value
            return value
        else:
            return 'Key not found'
        

    def put(self, key, value):
        # check if its present
            # if yes then inc the freq to key_to_freq and pop from  freq_to_key and enter again to freq_to_key
            # if no 
                # check if cache full then remove min one
                # add new one
        if key in self.key_to_freq:
            old_freq = self.key_to_freq[key]
            old_value = self.freq_to_key[old_freq].pop(key)
            self.key_to_freq[key] +=1
            self.freq_to_key[old_freq +1][key] = value
        else:
            if len(self.key_to_freq) == self.capacity:
                key, value = self.freq_to_key[self.min_freq].popitem(last=False)
                del self.key_to_freq[key]
            self.key_to_freq[key] = 1
            self.freq_to_key[1][key] = value
            self.min_freq = 1 





