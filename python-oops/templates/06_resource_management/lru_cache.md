# 06 — LRU Cache

## What is this problem testing?

This problem tests your ability to design a data structure that gives you O(1) read and write with an automatic eviction rule. Interviewers are watching for whether you know *why* a doubly linked list and a hashmap together solve what neither can solve alone, and whether you can express the eviction policy as a swappable strategy instead of hardcoding it.

The four skill areas being assessed:

- **Data structure design** — combining a doubly linked list with a hashmap to achieve O(1) for every operation
- **Eviction policy** — understanding LRU (least recently used) and LFU (least frequently used) and when each one makes sense
- **OOP encapsulation** — hiding the doubly linked list inside the cache so the caller never touches it directly
- **Strategy pattern** — making the eviction algorithm pluggable so you can swap LRU for LFU without rewriting the cache

---

## Requirements

- The cache has a **fixed capacity** set at construction time
- `get(key)` returns the stored value, or `-1` if the key is not in the cache; accessing a key marks it as "recently used"
- `put(key, value)` inserts the key-value pair; if the key already exists it updates the value; if adding the new entry would exceed capacity, the **least recently used** entry is evicted first
- Both `get` and `put` must run in **O(1)** time
- The eviction policy must be **pluggable** — the cache should work with LRU or LFU without structural changes

---

## Clarifying questions to ask in interview

1. **What should `get` return for a missing key?** — The LeetCode convention is `-1`, but in a real system you might raise `KeyError` or return `None`. Worth confirming.
2. **Does `get` count as a "use"?** — Yes for LRU; but for LFU it also increments the frequency counter. Confirm which semantics the interviewer wants.
3. **What happens when capacity is 0?** — Should every `put` be a no-op, or is 0 capacity an illegal argument we should reject at construction?
4. **Is thread safety required?** — If multiple threads share the cache, every `get` and `put` needs to be wrapped in a lock.
5. **Should evicted entries be returned or silently dropped?** — Some designs expose an eviction callback so the caller can flush evicted data to disk. Worth asking.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| The cache itself | `LRUCache` / `Cache` |
| A single cached item | `Node` (key, value, prev pointer, next pointer) |
| The ordered container that tracks recency | `DoublyLinkedList` |
| The algorithm that decides what to remove | `EvictionPolicy` |
| LRU variant of the algorithm | `LRUPolicy` |
| LFU variant of the algorithm | `LFUPolicy` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Look up a value | `get(key) -> int` | `LRUCache` / `Cache` |
| Insert or update | `put(key, value)` | `LRUCache` / `Cache` |
| Mark a node as most recently used | `move_to_end(node)` or `add_to_end(node)` | `DoublyLinkedList` |
| Remove an arbitrary node | `remove(node)` | `DoublyLinkedList` |
| Evict the least recently used entry | `remove_first() -> Node` | `DoublyLinkedList` |
| Choose which entry to remove | `evict(cache_map) -> key` | `EvictionPolicy` |

---

## Relationships

```
LRUCache
 ├── capacity: int
 ├── _map: Dict[key → Node]     ← O(1) lookup by key (the "hashmap" half)
 └── _list: DoublyLinkedList    ← O(1) insert/remove anywhere (the "order" half)
      │
      │   dummy_head ←→ [LRU node] ←→ ... ←→ [MRU node] ←→ dummy_tail
      │       (oldest, evicted first)              (newest, kept longest)
      │
      └── Node
           ├── key: int
           ├── value: int
           ├── prev: Node
           └── next: Node

EvictionPolicy  <<abstract>>
    ├── LRUPolicy   (tracks recency — evict the node accessed least recently)
    └── LFUPolicy   (tracks frequency — evict the node accessed fewest times)

Cache  ──── HAS-ONE ────► EvictionPolicy   (injected at construction)
```

> Think of the doubly linked list as a queue of people waiting for a bus. The person at the very front has been waiting the longest — they are the LRU entry. Every time someone gets served (accessed), they go to the back of the line. The hashmap is a separate name-to-person directory so you can instantly jump to any person without walking the whole queue.

---

## Why this is a Resource Management problem

A cache is a **limited resource**: it can only hold `capacity` items at any one time. When a new item arrives and the cache is full, a slot must be **reclaimed** — this is resource eviction. The cache is making a policy decision: "which piece of data is least valuable to keep?" LRU answers "the one I have not touched in the longest time." LFU answers "the one I have touched the fewest times overall."

Every real-world system with bounded memory uses this pattern:
- CPU L1/L2/L3 caches evict cache lines using variants of LRU
- Web browsers cache pages and evict old ones when storage fills up
- Database buffer pools keep frequently queried pages in memory and evict cold pages
- CDN edge nodes cache content and evict stale or unpopular responses

The cache is the traffic police of memory: it decides who gets to stay, who gets bumped, and enforces the capacity limit on every write.

---

## Design decisions

### 1. Why a doubly linked list and a hashmap — not just one of them?

This is the single most important question an interviewer will ask. Here is what each data structure gives you alone:

| Data structure | O(1) lookup? | O(1) remove any node? | Tracks order? |
|---|---|---|---|
| Plain `dict` | Yes | No (have to scan to find LRU) | No (no `move_to_end`) |
| Doubly linked list | No (have to walk from head) | Yes (with a pointer to the node) | Yes |
| `dict` + doubly linked list | Yes | Yes (dict gives you the node pointer directly) | Yes |

The trick: the dict maps `key → Node object`. Because you have a direct pointer to the node, you can call `list.remove(node)` in O(1) without scanning. Neither structure alone gives you all three properties.

### 2. Why dummy head and tail nodes?

Without dummy nodes, `add_to_end` and `remove_first` need special-case `if` checks for an empty list (no head or no tail yet). Dummy nodes are permanent sentinels that are never removed, so the real nodes always have neighbours. This means every insert and remove looks identical regardless of whether the list has 0 or 1000 real nodes — no edge-case branches in the code.

```
dummy_head ←→ [real node A] ←→ [real node B] ←→ dummy_tail
```

### 3. Why call `move_to_end` on `get` AND on an existing key in `put`?

- On `get`: reading a key makes it "recently used". If you forget this, a frequently read key can still be evicted just because it was inserted a long time ago.
- On `put` when the key exists: you are updating a value, which is also a "use". If you skip `move_to_end` here, the key stays in its old position in the recency order. The eviction order becomes wrong even though the value is correct.

Both are easy to forget under interview pressure. The rule of thumb: *any time you touch a key, move it to the end*.

### 4. How does `collections.OrderedDict` give us this for free?

Python's `OrderedDict` is internally implemented as exactly this — a dict plus a doubly linked list. It exposes `move_to_end(key)` and `popitem(last=False)`. This means you can write a complete, correct LRU cache in about 10 lines. Use this in an interview when you want a clean solution fast; fall back to the manual implementation only when asked to "do it from scratch" or "without built-in ordered containers".

### 5. LRU vs LFU — when would you use each?

| | LRU | LFU |
|---|---|---|
| **Evicts** | The entry accessed least recently | The entry accessed least often |
| **Good for** | Workloads where recent access predicts future access (browsing history, session data) | Workloads where popular data stays popular long-term (viral content, reference data) |
| **Bad for** | One-time sequential scans (they pollute the cache by evicting actually-popular items) | New items that have not had time to build up frequency (they get evicted immediately) |
| **Implementation complexity** | Simple — one ordered structure | Higher — needs a frequency counter per key and a separate ordered structure per frequency level |

> LRU is like asking "who did you speak to most recently?" LFU is like asking "who do you speak to most often?" A new acquaintance you met yesterday (LRU: high recency, LFU: low frequency) versus your best friend who was on holiday last week (LRU: low recency, LFU: high frequency).

---

## Complete Code

### Implementation 1: Using `OrderedDict` (interview-friendly, clean)

`collections.OrderedDict` maintains insertion order and gives you `move_to_end()` and `popitem(last=False)` — exactly the two operations an LRU cache needs. This is the fastest correct solution to write in an interview.

```python
from collections import OrderedDict


class LRUCache:
    """
    Least Recently Used Cache backed by collections.OrderedDict.

    Convention:
      - FRONT of the OrderedDict  = Least Recently Used  (evicted first)
      - BACK  of the OrderedDict  = Most  Recently Used  (kept longest)

    Both get() and put() run in O(1).
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        self.capacity = capacity
        self._cache: OrderedDict = OrderedDict()   # key → value

    def get(self, key: int) -> int:
        # Cache miss — key is not present
        if key not in self._cache:
            return -1

        # Cache hit — accessing the key makes it "most recently used"
        # move_to_end moves the key to the back (MRU end) in O(1)
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self._cache:
            # Key already exists — update its position before overwriting the value
            # If we skip this, the key stays in its old (possibly LRU) position
            self._cache.move_to_end(key)

        # Insert or overwrite the value
        self._cache[key] = value

        # If we have exceeded capacity, remove the LRU entry from the front
        if len(self._cache) > self.capacity:
            # popitem(last=False) removes and returns the FRONT item — the LRU entry
            evicted_key, evicted_val = self._cache.popitem(last=False)
            # Uncomment to observe evictions during debugging:
            # print(f"[EVICT] key={evicted_key}, value={evicted_val}")
```

**What just happened?** `move_to_end(key)` is the secret weapon here. It re-positions a key at the back of the internal doubly linked list in O(1). `popitem(last=False)` removes from the front — the position no key has moved to in the longest time. The dict part handles O(1) lookup; the linked list part handles O(1) ordering.

---

### Implementation 2: From scratch with `DoublyLinkedList` (shows deeper understanding)

Use this when an interviewer says "implement it without built-in ordered containers" or "show me the underlying data structure". This version makes the mechanics explicit.

```python
from typing import Optional, Dict


# ── Node ───────────────────────────────────────────────────────────────────────
# A single slot in the cache.
# Storing the key inside the node is essential: when we evict the LRU node
# from the front of the list, we need its key to delete it from the dict too.

class Node:
    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev: Optional["Node"] = None   # points to the less-recently-used neighbour
        self.next: Optional["Node"] = None   # points to the more-recently-used neighbour

    def __repr__(self) -> str:
        return f"Node(key={self.key}, value={self.value})"


# ── DoublyLinkedList ───────────────────────────────────────────────────────────
# Maintains the recency order of cache entries.
# Dummy head and tail nodes are permanent sentinels — they are never evicted.
# This removes all edge-case null checks from add_to_end and remove_first.

class DoublyLinkedList:
    def __init__(self):
        # Create two permanent dummy nodes that bookend the real nodes
        self._head = Node(0, 0)   # dummy head — left of the LRU end
        self._tail = Node(0, 0)   # dummy tail — right of the MRU end
        self._head.next = self._tail
        self._tail.prev = self._head

    def add_to_end(self, node: Node) -> None:
        """Insert node just before the dummy tail — marking it as MRU."""
        # Find the current last real node
        prev_node = self._tail.prev

        # Stitch the new node between prev_node and dummy_tail
        prev_node.next = node
        node.prev = prev_node
        node.next = self._tail
        self._tail.prev = node

    def remove(self, node: Node) -> None:
        """Unlink node from wherever it currently sits in the list — O(1)."""
        prev_node = node.prev
        next_node = node.next

        # Bridge the gap: make prev and next point to each other, skipping node
        prev_node.next = next_node
        next_node.prev = prev_node

        # Detach the node (good practice to prevent accidental reuse)
        node.prev = None
        node.next = None

    def remove_first(self) -> Optional[Node]:
        """Remove and return the node just after dummy head — the LRU entry."""
        # If the list is empty (head points directly to tail), nothing to evict
        if self._head.next is self._tail:
            return None

        lru_node = self._head.next
        self.remove(lru_node)
        return lru_node

    def move_to_end(self, node: Node) -> None:
        """Reposition an existing node as MRU — used by get() and put()."""
        self.remove(node)
        self.add_to_end(node)


# ── LRUCache ───────────────────────────────────────────────────────────────────
# Uses the dict for O(1) lookup and the DoublyLinkedList for O(1) ordering.
# The dict maps key → Node so we can jump directly to the node in the list.

class LRUCache:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        self.capacity = capacity
        self._map: Dict[int, Node] = {}       # key → Node (O(1) lookup)
        self._list = DoublyLinkedList()        # tracks recency order

    def get(self, key: int) -> int:
        if key not in self._map:
            return -1   # cache miss

        node = self._map[key]
        self._list.move_to_end(node)   # accessing a key refreshes its recency
        return node.value

    def put(self, key: int, value: int) -> None:
        if key in self._map:
            # Key exists — update value and refresh recency
            node = self._map[key]
            node.value = value
            self._list.move_to_end(node)
        else:
            # New key — create a node and add it to both structures
            node = Node(key, value)
            self._map[key] = node
            self._list.add_to_end(node)

            # If over capacity, evict the LRU entry
            if len(self._map) > self.capacity:
                lru_node = self._list.remove_first()   # remove from list
                if lru_node:
                    del self._map[lru_node.key]        # remove from dict using the stored key
```

**What just happened?** The `Node` stores both key and value precisely so that when `remove_first()` hands back the LRU node, we know which key to delete from `_map`. Without `node.key`, we would have to scan the dict to find the evicted entry — turning an O(1) eviction into O(n).

---

### Implementation 3 (bonus): Pluggable eviction policy

Use this version if the interviewer asks "make the cache support both LRU and LFU" or "make the eviction policy swappable". This applies the Strategy pattern.

```python
from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict
from typing import Any, Dict


# ── EvictionPolicy (Strategy interface) ───────────────────────────────────────
# Every eviction strategy exposes the same three hooks:
#   on_access  — called when a key is read (get) or written (put, existing key)
#   on_insert  — called when a brand new key is added
#   evict      — called when the cache is over capacity; returns the key to remove

class EvictionPolicy(ABC):
    @abstractmethod
    def on_access(self, key: Any) -> None:
        """Called after a successful get() or after updating an existing key in put()."""
        ...

    @abstractmethod
    def on_insert(self, key: Any) -> None:
        """Called after a brand new key is added in put()."""
        ...

    @abstractmethod
    def evict(self) -> Any:
        """Return the key that should be evicted. The Cache will delete it."""
        ...


# ── LRUPolicy ──────────────────────────────────────────────────────────────────
# Evicts the key that was accessed least recently.
# Uses OrderedDict as its internal ordered set of keys.

class LRUPolicy(EvictionPolicy):
    def __init__(self):
        self._order: OrderedDict = OrderedDict()   # key → None (only order matters)

    def on_access(self, key: Any) -> None:
        # Move the accessed key to the back (MRU end)
        if key in self._order:
            self._order.move_to_end(key)

    def on_insert(self, key: Any) -> None:
        # New keys start at the back (they are the most recently used)
        self._order[key] = None

    def evict(self) -> Any:
        # Front = least recently used
        key, _ = self._order.popitem(last=False)
        return key


# ── LFUPolicy ─────────────────────────────────────────────────────────────────
# Evicts the key that has been accessed the fewest times overall.
# Ties are broken by recency (LRU within the same frequency bucket).

class LFUPolicy(EvictionPolicy):
    def __init__(self):
        self._freq: Dict[Any, int] = {}                      # key → access count
        self._freq_buckets: Dict[int, OrderedDict] = defaultdict(OrderedDict)  # freq → ordered set of keys
        self._min_freq: int = 0                               # track the bucket to evict from

    def _increment(self, key: Any) -> None:
        """Move key from its current frequency bucket to the next one up."""
        f = self._freq[key]
        del self._freq_buckets[f][key]   # remove from old bucket

        self._freq[key] = f + 1
        self._freq_buckets[f + 1][key] = None   # add to new bucket (at the back = most recent)

        # Update min_freq if the old bucket is now empty
        if not self._freq_buckets[self._min_freq]:
            self._min_freq += 1

    def on_access(self, key: Any) -> None:
        self._increment(key)

    def on_insert(self, key: Any) -> None:
        self._freq[key] = 1
        self._freq_buckets[1][key] = None
        self._min_freq = 1   # a new key starts with frequency 1, which is always the minimum

    def evict(self) -> Any:
        # Evict from the minimum-frequency bucket; within that bucket, evict LRU (front)
        bucket = self._freq_buckets[self._min_freq]
        key, _ = bucket.popitem(last=False)
        del self._freq[key]
        return key


# ── Cache (uses an injected EvictionPolicy) ───────────────────────────────────
# The Cache itself is policy-agnostic — it delegates all eviction decisions
# to whichever EvictionPolicy was injected at construction time.

class Cache:
    def __init__(self, capacity: int, policy: EvictionPolicy):
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        self.capacity = capacity
        self._store: Dict[Any, Any] = {}   # the actual key-value storage
        self._policy = policy              # injected strategy — swappable

    def get(self, key: Any) -> Any:
        if key not in self._store:
            return -1
        self._policy.on_access(key)        # tell the policy this key was accessed
        return self._store[key]

    def put(self, key: Any, value: Any) -> None:
        if key in self._store:
            self._store[key] = value
            self._policy.on_access(key)    # existing key — counts as an access
        else:
            if len(self._store) >= self.capacity:
                evict_key = self._policy.evict()   # ask the policy what to remove
                del self._store[evict_key]
            self._store[key] = value
            self._policy.on_insert(key)    # brand new key — notify the policy


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== LRU Cache (OrderedDict) ===")
    from collections import OrderedDict

    lru = LRUCache(capacity=3)
    lru.put(1, 1)
    lru.put(2, 2)
    lru.put(3, 3)
    print(lru.get(1))    # 1  — key 1 moves to MRU
    lru.put(4, 4)        # evicts key 2 (LRU after key 1 was accessed)
    print(lru.get(2))    # -1 — key 2 was evicted
    print(lru.get(3))    # 3  — key 3 is still present
    print(lru.get(4))    # 4  — key 4 is still present

    print("\n=== Pluggable Policy Cache ===")
    lfu_cache = Cache(capacity=2, policy=LFUPolicy())
    lfu_cache.put(1, 1)
    lfu_cache.put(2, 2)
    print(lfu_cache.get(1))   # 1  — key 1 now has frequency 2
    lfu_cache.put(3, 3)       # evicts key 2 (frequency 1, less than key 1's frequency 2)
    print(lfu_cache.get(2))   # -1 — key 2 was evicted
    print(lfu_cache.get(3))   # 3  — key 3 is present
```

**What just happened?** `Cache` knows nothing about LRU or LFU. It only knows that its policy has `on_access`, `on_insert`, and `evict`. To add a new eviction strategy (say, random eviction, or FIFO), you write one new class and inject it — zero changes to `Cache`. This is the Open/Closed principle: open for extension, closed for modification.

---

## Step-by-step walkthrough

Let us trace the `OrderedDict` implementation with `capacity = 3`. After each operation the full cache state is shown with the LRU end on the left and the MRU end on the right.

```python
cache = LRUCache(capacity=3)
```

Cache: `{}` — empty, capacity 3.

```python
cache.put(1, 1)
```

Key 1 is new. Insert at the back (MRU).
Cache: `[1] `
Front (LRU) = 1, Back (MRU) = 1.

```python
cache.put(2, 2)
```

Key 2 is new. Insert at the back.
Cache: `[1] ←→ [2]`
Front (LRU) = 1.

```python
cache.put(3, 3)
```

Key 3 is new. Insert at the back. Cache is now full.
Cache: `[1] ←→ [2] ←→ [3]`
Front (LRU) = 1, Back (MRU) = 3.

```python
cache.get(1)   # returns 1
```

Key 1 is found. `move_to_end(1)` promotes it to the MRU end.
Cache: `[2] ←→ [3] ←→ [1]`
Key 2 is now the LRU. Key 1 is the MRU.

> This is the critical step beginners miss. Reading key 1 "refreshes" it. Without `move_to_end`, key 1 would still sit at the front and be the next to get evicted — even though it was just used.

```python
cache.put(4, 4)
```

Key 4 is new. Insert at back. `len == 4 > capacity 3`, so evict the front.
Front = key 2. Evict key 2.
Cache: `[3] ←→ [1] ←→ [4]`

**What just happened?** Key 2 was evicted because it sat at the LRU end — it had not been accessed since `put(2, 2)`, while key 1 was refreshed by the `get`. Key 4 enters as MRU.

```python
cache.get(2)   # returns -1
```

Key 2 is gone — it was evicted. Cache miss.

```python
cache.get(3)   # returns 3
```

Key 3 is found and promoted.
Cache: `[1] ←→ [4] ←→ [3]`

Final state: keys 1, 4, 3 in LRU → MRU order. Key 1 is the next to be evicted if a new key arrives.

---

## Common interview mistakes

1. **Using a plain `dict` instead of `OrderedDict`**
   A regular `dict` in Python 3.7+ preserves *insertion* order but gives you no `move_to_end()`. You would need to `del cache[key]; cache[key] = value` to simulate it — which works but is easy to forget and harder to read. More importantly, it does not communicate intent to the reader.

2. **Forgetting to call `move_to_end` in `get`**
   If you skip `move_to_end` inside `get`, reading a key does not update its recency. A hot key that is read constantly but never written will eventually drift to the LRU end and get evicted — silently returning incorrect results for the next read.

3. **Forgetting to call `move_to_end` when updating an existing key in `put`**
   If you do `self._cache[key] = value` without first calling `move_to_end(key)`, the key gets the new value but stays in its old position in the recency order. The cache will evict it based on when it was *originally inserted*, not when it was last *written*. This is a subtle bug that only shows up in specific access patterns.

4. **Not handling the "key already exists" case in `put`**
   Some candidates write `put` as if it is always an insertion. If the key exists and you do not call `move_to_end` first, you end up with duplicates in the internal ordering (in a from-scratch implementation) or wrong eviction order (in the `OrderedDict` version).

5. **O(n) eviction — iterating to find the LRU**
   A common first instinct is to keep timestamps in the values and scan the whole dict to find the smallest timestamp. This is O(n) on every `put` when the cache is full. The entire point of the data structure is to avoid this by keeping the order implicit in the linked list. Always point out this distinction when walking through your solution.

---

## Key patterns used

- **Strategy** — `EvictionPolicy` is an abstract interface; `LRUPolicy` and `LFUPolicy` are concrete strategies injected into `Cache`. Swapping eviction algorithm requires zero changes to `Cache` itself.
- **Decorator** (conceptual) — `OrderedDict` adds LRU behaviour to a plain dict without subclassing it. The `move_to_end` and `popitem` wrappers decorate the underlying dict with recency tracking.
- **Encapsulation** — `DoublyLinkedList` hides pointer manipulation. `LRUCache` exposes only `get` and `put`; the caller never sees `Node`, `prev`, `next`, or dummy sentinels.
- **Single Responsibility** — `DoublyLinkedList` handles ordering, `dict` handles lookup, `LRUCache` coordinates them. Each class has one reason to change.


---

[← Back to Resource Management Template](template.md)
