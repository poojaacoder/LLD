# 06 — Resource Management Template

## What is this template?

A **Resource Management** system controls access to something that is **limited and shared**. It hands out resources to callers when they ask, takes them back when the caller is done, and enforces rules about capacity, fairness, and what to throw away when things fill up.

Think of it as the traffic police of your system — it decides who gets through, in what order, and what gets bumped when the road is full.

> Imagine a library with 5 study rooms. You walk in, ask for a room, use it, and give it back. If all 5 are taken, the librarian either tells you to wait, puts you in a queue, or kicks out whoever has been sitting there longest (eviction). That is resource management in a nutshell.

---

## How to recognise this template

When you see any of these words in an interview problem, you are almost certainly looking at a resource management problem:

| Signal word | What it implies |
|---|---|
| **capacity**, **limit**, **quota** | There is an upper bound to enforce |
| **cache**, **pool** | Resources are reused, not created fresh each time |
| **evict**, **LRU**, **LFU** | Something must be removed when at capacity |
| **throttle**, **rate limit** | Access frequency must be controlled |
| **log**, **buffer** | Writes are collected and managed before they go somewhere |

---

## Real-world examples

- **LRU Cache** — store the N most recently used items, evict the oldest
- **LFU Cache** — store the N most frequently used items, evict the least popular
- **Rate Limiter** — allow at most K requests per user per second
- **Connection Pool** — maintain a fixed set of DB connections; hand them out and reclaim them
- **Thread Pool** — manage a fixed number of worker threads
- **Logging System** — collect messages, filter by severity, route to multiple destinations
- **File System** — enforce read/write permissions per user/process
- **Memory Allocator** — hand out chunks of memory, reclaim on free

---

## Core building blocks

Every resource management system is built from the same six pieces. Learn these and you can reason about any flavour.

| Building block | What it is | Analogy |
|---|---|---|
| **Resource** | The limited thing being managed | A study room, a DB connection, a cache slot |
| **Capacity** | The fixed upper bound | "Only 5 rooms available" |
| **Allocation policy** | Who gets the resource and in what order (FIFO, LRU, LFU, token bucket) | "First come, first served" or "VIP members first" |
| **Eviction policy** | What to remove when at capacity | "The person who has been sitting longest gets asked to leave" |
| **Access control** | Who is allowed to read or write | File system permissions, log level filtering |
| **Usage tracking** | How recently / how often was a resource used | Timestamps, access counters |

> These six pieces are like the knobs on a mixing board. Different problems turn different knobs all the way up. A cache cares most about eviction policy. A rate limiter cares most about allocation policy. A logging system cares most about access control.

---

## Two flavours with diagrams

### Flavour A: Cache (LRU)

The cache stores key-value pairs up to a capacity. On overflow, it evicts the **least recently used** entry.

```
LRUCache
 ├── capacity: int
 ├── _cache: OrderedDict (key → value)
 │       (maintains insertion/access order — front = oldest, back = newest)
 └── EvictionPolicy <<interface>>
         ├── LRUPolicy   (evict from front)
         └── LFUPolicy   (evict lowest frequency counter)

get(key)        → move key to end (mark as most recently used); return value
put(key, value) → insert at end; if len > capacity, pop from front (evict LRU)
```

> Think of the OrderedDict as a queue of people at a deli counter. When someone is served (accessed), they go to the back of the line. The person at the very front has been waiting the longest without being called — they are the LRU entry, first to be evicted.

---

### Flavour B: Rate Limiter

The rate limiter decides whether to allow or deny a request based on how many requests a user has already made in a time window.

```
RateLimiter
 ├── RateLimitStrategy <<interface>>
 │       ├── TokenBucket        (tokens refill at a fixed rate; allow if tokens > 0)
 │       └── SlidingWindowCounter (count requests in the last N seconds)
 └── allow(user_id) → bool      (True = request is allowed, False = throttled)
```

> Token Bucket is like a parking meter that adds one coin every second up to a maximum. You can park (make a request) as long as there are coins left. Sliding Window is like a bouncer who counts how many times you have entered in the last hour — if it is too many, you wait outside.

---

### Flavour C: Logging System

The logger collects messages, filters them by severity, and fans them out to multiple output destinations.

```
Logger (Singleton)
 ├── LogLevel enum (DEBUG < INFO < WARNING < ERROR)
 ├── List[LogHandler] <<observer>>
 │       ├── ConsoleHandler  (prints to stdout)
 │       └── FileHandler     (writes to a file)
 └── log(level, message)
     → Chain of Responsibility: each handler processes the message
       only if its own minimum level ≤ the message's level
```

> Singleton ensures there is exactly one logger in the whole application — every module sends messages to the same place. Observer means you can add or remove handlers at runtime without changing the Logger itself.

---

## Generic skeleton code

Here is a reusable skeleton that captures the pattern. You will never submit this directly, but it trains your eye to spot the structure in any new problem.

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional

T = TypeVar("T")   # T represents the type of resource being managed


# ── Resource (abstract) ────────────────────────────────────────────────────────
# Every managed resource has an ID and knows whether it is currently in use.

class Resource(ABC):
    def __init__(self, resource_id: str):
        self.resource_id = resource_id
        self.in_use: bool = False   # False = available, True = checked out

    def __repr__(self) -> str:
        status = "in-use" if self.in_use else "available"
        return f"{self.__class__.__name__}({self.resource_id!r}, {status})"


# ── EvictionPolicy (abstract) ──────────────────────────────────────────────────
# Decides which resource to remove when the pool is full.
# Subclasses implement different eviction strategies (LRU, LFU, random, etc.)

class EvictionPolicy(ABC):
    @abstractmethod
    def evict(self, pool: "ResourcePool") -> Optional[Resource]:
        """Choose and remove one resource from the pool. Return the evicted resource."""
        ...


# ── ResourcePool ───────────────────────────────────────────────────────────────
# The central manager.
# - _available: resources not currently checked out
# - _in_use:    resources that have been acquired and not yet released

class ResourcePool:
    def __init__(self, capacity: int, eviction_policy: EvictionPolicy):
        self.capacity = capacity                    # hard upper bound
        self._available: List[Resource] = []        # free resources
        self._in_use: List[Resource] = []           # checked-out resources
        self._policy = eviction_policy              # injected — swappable

    def acquire(self) -> Optional[Resource]:
        """Hand out a resource to a caller. Returns None if none are available."""
        if self._available:
            resource = self._available.pop(0)       # FIFO: take from front
            resource.in_use = True
            self._in_use.append(resource)
            return resource

        # Pool is empty — try to evict something if we have not hit capacity yet
        if len(self._in_use) < self.capacity:
            return None   # nothing to evict; pool simply has no free resources

        evicted = self._policy.evict(self)          # ask the policy what to remove
        if evicted:
            evicted.in_use = False
            print(f"[EVICT] {evicted}")
        return None

    def release(self, resource: Resource) -> None:
        """Return a resource to the pool so another caller can use it."""
        if resource not in self._in_use:
            raise ValueError(f"{resource} was not checked out from this pool")
        self._in_use.remove(resource)
        resource.in_use = False
        self._available.append(resource)

    @property
    def utilisation(self) -> str:
        total = len(self._available) + len(self._in_use)
        return f"{len(self._in_use)}/{total} in use"
```

**What just happened?** `ResourcePool` does not know anything about *what* the resources are or *how* to choose which one to evict. Those decisions live in `Resource` subclasses and `EvictionPolicy` subclasses respectively. Adding a new eviction strategy means writing one new class — no changes to `ResourcePool`.

---

Now here is the concrete `LRUCache` built on `collections.OrderedDict`:

```python
from collections import OrderedDict

class LRUCache:
    """
    Least Recently Used Cache.

    Internally uses an OrderedDict where:
      - The FRONT (first key) is the LEAST recently used.
      - The BACK  (last key)  is the MOST  recently used.

    get() and put() are both O(1).
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache: OrderedDict = OrderedDict()   # key → value

    def get(self, key: int) -> int:
        if key not in self._cache:
            return -1                              # cache miss — conventional return value
        self._cache.move_to_end(key)               # mark as most recently used
        return self._cache[key]

    def put(self, key: int, value: int) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)           # update position even on overwrite
        self._cache[key] = value                   # insert or update the value
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)        # evict the LEAST recently used (front)
```

**What just happened?** `move_to_end(key)` is the secret sauce. It makes both `get` and `put` update the "recency" order in O(1). `popitem(last=False)` removes the front item — the one that has been untouched the longest.

---

## Design patterns used

| Pattern | Where it appears | Why |
|---|---|---|
| **Singleton** | `Logger` | The whole application must share one logger; prevents duplicate log files and inconsistent state |
| **Strategy** | `EvictionPolicy` (LRU, LFU), `RateLimitStrategy` (token bucket, sliding window) | Lets you swap eviction or rate-limiting algorithms without touching the cache or rate-limiter class |
| **Observer** | `Logger` → `List[LogHandler]` | Handlers subscribe to the logger; adding a new output (e.g., Slack alerts) requires zero changes to `Logger` itself |
| **Chain of Responsibility** | Log level filtering: each `LogHandler` decides whether to process a message | Decouples the sender from the receiver; each handler independently enforces its own threshold |

---

## Key design decisions for interview

### 1. Why `OrderedDict` for LRU?

A plain `dict` in Python 3.7+ preserves insertion order, but it has no `move_to_end()` method. You would have to delete and re-insert the key on every access — which is still O(1) but messier and error-prone. `OrderedDict.move_to_end()` expresses intent clearly and keeps the code readable.

### 2. Singleton for Logger — thread safety

A naive Singleton is not thread-safe. If two threads call `Logger.get_instance()` at the same moment and the instance does not yet exist, both might create a new instance. Fix: use `threading.Lock` around the creation check, or use Python's module-level singleton (just put `logger = Logger()` at module level — Python imports are singletons by default).

### 3. Strategy vs hardcoded eviction policy

Hardcoding LRU inside `LRUCache` is fine for interview if you are asked for LRU specifically. But if asked "make the eviction policy pluggable", extract it into a `Strategy`. The rule: if the interviewer says "support multiple X", that is a signal to reach for Strategy.

### 4. Making the cache thread-safe

Add a `threading.Lock` as an instance variable and wrap every `get` and `put` call with `with self._lock:`. This serialises access. For higher throughput, you could use a `threading.RLock` (reentrant) or shard the cache into N buckets with independent locks.

### 5. Token bucket vs sliding window for rate limiting

| | Token Bucket | Sliding Window |
|---|---|---|
| **Memory** | O(1) per user | O(requests in window) per user |
| **Burst handling** | Allows bursts up to bucket size | Strictly limits rate in any window |
| **Implementation** | Simple counter + timestamp | List/deque of timestamps |
| **Use when** | You want to allow occasional bursts | You want a hard cap on requests per second |

---

## LRU Cache — full working implementation

This is the most commonly asked resource management problem in interviews. Here is the complete, annotated implementation followed by a step-by-step walkthrough.

```python
from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity: int):
        # capacity is the maximum number of key-value pairs we can hold
        self.capacity = capacity
        # OrderedDict remembers insertion order.
        # We treat the FRONT as LRU and the BACK as MRU.
        self._cache: OrderedDict = OrderedDict()

    def get(self, key: int) -> int:
        # Step 1: check if the key exists
        if key not in self._cache:
            return -1   # cache miss; -1 is the LeetCode convention

        # Step 2: accessing a key makes it "recently used" — move it to the back
        self._cache.move_to_end(key)   # O(1)

        # Step 3: return the value
        return self._cache[key]

    def put(self, key: int, value: int) -> None:
        # Step 1: if the key already exists, move it to the back (it is now MRU)
        if key in self._cache:
            self._cache.move_to_end(key)   # O(1)

        # Step 2: insert or overwrite the value
        self._cache[key] = value

        # Step 3: if we have exceeded capacity, evict the LRU entry (the front)
        if len(self._cache) > self.capacity:
            evicted_key, evicted_val = self._cache.popitem(last=False)   # O(1)
            # Uncomment to debug:
            # print(f"[EVICT] key={evicted_key}, value={evicted_val}")
```

### Step-by-step walkthrough

Let us trace through a concrete sequence with `capacity = 3`:

```python
cache = LRUCache(capacity=3)

cache.put(1, "a")   # cache: {1: "a"}                       ← 1 is MRU
cache.put(2, "b")   # cache: {1: "a", 2: "b"}               ← 2 is MRU
cache.put(3, "c")   # cache: {1: "a", 2: "b", 3: "c"}       ← 3 is MRU, full
```

The cache is now at capacity. Front = key 1 (LRU), back = key 3 (MRU).

```python
cache.get(1)        # returns "a"
                    # cache: {2: "b", 3: "c", 1: "a"}       ← 1 moved to back (MRU)
```

Accessing key 1 promotes it. Now key 2 is the new LRU.

```python
cache.put(4, "d")   # cache is full → evict LRU (key 2)
                    # cache: {3: "c", 1: "a", 4: "d"}       ← 4 is MRU
```

Key 2 is gone. Key 3 is the new LRU.

```python
cache.get(2)        # returns -1  ← key 2 was evicted; cache miss
cache.get(3)        # returns "c"
                    # cache: {1: "a", 4: "d", 3: "c"}       ← 3 moved to back
```

**What just happened?** Every access (get or put) either moves an existing key to the back or adds a new key at the back. The front always holds the entry that was touched least recently. When capacity overflows, `popitem(last=False)` removes exactly that entry in O(1).

---

## Common mistakes

1. **Using a plain `dict` instead of `OrderedDict`**
   A `dict` does preserve insertion order in Python 3.7+, but it has no `move_to_end()` method. You would need to do `del cache[key]; cache[key] = value` on every access, which is equivalent but more verbose and easy to get wrong.

2. **O(n) eviction — scanning the whole cache to find the LRU**
   Some candidates loop through all keys to find the one with the smallest timestamp. `OrderedDict` makes this unnecessary — the LRU is always at the front. O(n) eviction will fail large-input tests.

3. **Not handling the "key already exists" case in `put`**
   If you skip `move_to_end(key)` when overwriting an existing key, the key sits in its old position in the order. A subsequent access looks correct, but the eviction order is wrong. Always move-to-end on overwrite.

4. **Not moving on `get`**
   Forgetting `move_to_end(key)` inside `get` means reading a key does not update its recency. The cache will evict a "recently read but old" key instead of a truly stale one.

5. **Forgetting thread safety**
   In a multi-threaded environment, two threads can interleave their `get` and `put` calls and corrupt the OrderedDict. Wrap the body of both methods with `with self._lock:` where `self._lock = threading.Lock()`.

---

## Problems that use this template

The following interview problems are all variations of the resource management template:

- [LRU Cache](lru_cache.md) — the canonical form; eviction policy + OrderedDict, 3 implementations
- [Rate Limiter](rate_limiter.md) — Token Bucket, Fixed Window, Sliding Window with thread safety
- [Logging System](logging_system.md) — Singleton + Chain of Responsibility + Observer for handlers
- File System *(coming soon)* — access control, disk quota, hierarchical organisation
