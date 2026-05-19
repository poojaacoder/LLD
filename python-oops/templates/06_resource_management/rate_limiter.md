# 06 — Rate Limiter

## What is this problem testing?

This problem tests your ability to design a system that controls **how often** a caller is allowed to do something. Interviewers are watching for whether you know the difference between time-window strategies, whether you apply the Strategy pattern to make those strategies swappable, and whether your implementation is correct under concurrent use.

The four skill areas being assessed:

- **Algorithm design** — understanding Token Bucket, Fixed Window, and Sliding Window Log and the trade-offs between them
- **Strategy pattern** — making the rate-limiting algorithm pluggable so you can swap algorithms without touching the service layer
- **Thread safety** — using `threading.Lock` to prevent race conditions when multiple threads check the same user's quota
- **Per-user resource management** — tracking and enforcing limits independently for each user or tier

---

## Requirements

- Allow at most **N requests per user per time window**
- Support three algorithms: **Token Bucket**, **Fixed Window Counter**, **Sliding Window Log**
- Support **per-user limits** — different users or subscription tiers can have different quotas
- Must be **thread-safe** — concurrent requests from the same user must not be double-counted
- Every decision returns not just `allowed: bool` but also **remaining quota** and **retry_after seconds** so callers know when to try again

---

## Clarifying questions to ask in interview

1. **Is this single-process or distributed?** — A single-process rate limiter can use in-memory dicts and locks. A distributed limiter (many servers) needs a shared store like Redis with atomic operations. Worth confirming scope.
2. **Do we need burst tolerance?** — Token Bucket allows a burst up to the bucket capacity. Fixed Window and Sliding Window are stricter. If the product wants to allow occasional bursts, that drives algorithm choice.
3. **What is the default if a user has no rule?** — Should we allow everything, deny everything, or apply a global fallback rule?
4. **How precise does the window need to be?** — Fixed Window is cheap but has an edge-case double-burst. Sliding Window is precise but uses more memory. What is the acceptable trade-off?
5. **Should exceeded limits be logged or trigger alerts?** — Rate limit violations are often security signals. Clarifying this opens a conversation about integrating with a logging system.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| The decision returned to the caller | `RateLimitResult` |
| The abstract algorithm interface | `RateLimitStrategy` |
| Token Bucket algorithm | `TokenBucketStrategy` |
| Fixed Window Counter algorithm | `FixedWindowStrategy` |
| Sliding Window Log algorithm | `SlidingWindowStrategy` |
| The top-level service that routes requests to the right strategy | `RateLimiterService` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Check if a request is allowed | `is_allowed(user_id) -> RateLimitResult` | `RateLimitStrategy` (all subclasses) |
| Register a per-user rule | `add_rule(user_id, strategy)` | `RateLimiterService` |
| Route a request to the correct per-user strategy | `is_allowed(user_id) -> RateLimitResult` | `RateLimiterService` |
| Refill tokens based on elapsed time | internal to `is_allowed` | `TokenBucketStrategy` |
| Reset the window counter when the window expires | internal to `is_allowed` | `FixedWindowStrategy` |
| Purge timestamps older than the window | internal to `is_allowed` | `SlidingWindowStrategy` |

---

## Relationships

```
RateLimiterService
 ├── _user_strategies: Dict[user_id → RateLimitStrategy]
 └── is_allowed(user_id) → RateLimitResult
          │
          ▼
     RateLimitStrategy  <<abstract>>
          ├── TokenBucketStrategy
          │       ├── capacity: int
          │       ├── refill_rate: float   (tokens / second)
          │       └── _buckets: Dict[user_id → (tokens, last_refill_time)]
          ├── FixedWindowStrategy
          │       ├── limit: int
          │       ├── window_seconds: float
          │       └── _windows: Dict[user_id → (count, window_start)]
          └── SlidingWindowStrategy
                  ├── limit: int
                  ├── window_seconds: float
                  └── _logs: Dict[user_id → deque[timestamp]]
```

> Think of `RateLimiterService` as the front desk of a nightclub. The desk does not itself decide who gets in — it looks up which bouncer (strategy) is assigned to each VIP guest (user) and hands the decision to them. Each bouncer has a different rule book. Same front desk, swappable rule books.

---

## Why this is a Resource Management problem

Requests are the **scarce resource**. Every API endpoint, database connection, or expensive computation has a cost. The rate limiter is the **allocation policy** that enforces fair use and prevents any single caller from exhausting a shared resource.

The six resource management building blocks map directly:

| Building block | Rate Limiter equivalent |
|---|---|
| **Resource** | A request slot (one "unit" of allowed traffic) |
| **Capacity** | `N` requests per window |
| **Allocation policy** | Token Bucket / Fixed Window / Sliding Window |
| **Eviction policy** | Old tokens refilled, old timestamps purged |
| **Access control** | Per-user rules, tier-based limits |
| **Usage tracking** | Token count, window counter, timestamp log |

---

## Algorithm deep-dive

### Algorithm 1: Token Bucket

**What problem does it solve?** You want to allow a steady rate of requests *and* tolerate occasional short bursts — like a user who is usually quiet but sometimes sends a flurry.

> Imagine a jar that holds at most 5 coins. Every second, one new coin is dropped in (up to the 5-coin maximum). Each request costs one coin. You can make 5 requests instantly if the jar is full. Then you must wait for coins to refill. This is Token Bucket.

**How it works step by step:**
1. Each user starts with a full bucket of `capacity` tokens.
2. When a request arrives, calculate how much time has elapsed since the last refill.
3. Add `elapsed * refill_rate` tokens to the bucket (capped at `capacity`).
4. If there is at least 1 token, subtract 1 and allow the request.
5. If the bucket is empty, deny the request and report how long until the next token arrives.

| Pros | Cons |
|---|---|
| Allows controlled bursts | Tokens can accumulate during quiet periods, enabling a large burst later |
| Smooth long-term rate | Slightly more math than Fixed Window |
| O(1) memory per user | Requires tracking last-refill timestamp per user |

---

### Algorithm 2: Fixed Window Counter

**What problem does it solve?** You want the simplest possible quota: "no more than N requests per minute." You do not care about burst patterns within the minute.

> Imagine a turnstile that resets its counter to zero at the top of every hour. You can walk through up to 10 times per hour. At 12:00:00 the counter resets. Simple and cheap. But two bursts of 10 at 11:59 and 12:01 slip through the seam.

**How it works step by step:**
1. Each user has a counter and a window start time.
2. When a request arrives, check if the current time is past `window_start + window_seconds`.
3. If yes, reset the counter to 0 and update `window_start`.
4. If the counter is below the limit, increment it and allow. Otherwise deny.

| Pros | Cons |
|---|---|
| Minimal memory (one counter + one timestamp per user) | "Double burst" at window boundary: a user can make 2× the limit in a short span by hitting just before and just after the reset |
| Easy to reason about | Rate is not smooth within a window |
| Trivial to implement | |

---

### Algorithm 3: Sliding Window Log

**What problem does it solve?** You want a precise, continuous rate limit with no boundary loophole. Every request is evaluated against the last `window_seconds` worth of actual history.

> Imagine the bouncer keeps a notepad. Every time you enter, they write down the exact time. When you want to enter again, they cross out any entries older than 1 hour and count what remains. If there are already 10 entries in the last hour, you wait. No reset trick works here.

**How it works step by step:**
1. Each user has a `deque` (double-ended queue) of request timestamps.
2. When a request arrives, remove all timestamps older than `now - window_seconds` from the front.
3. Count how many timestamps remain — this is requests in the current sliding window.
4. If the count is below the limit, append the current timestamp and allow. Otherwise deny.

| Pros | Cons |
|---|---|
| Precisely enforces rate with no boundary loophole | Memory grows with request count: O(limit) per user |
| Easy to reason about the "last N seconds" semantics | Slightly more memory than Fixed Window |
| No burst anomaly at window seams | |

---

## Design decisions

### 1. Why Strategy pattern for the algorithm?

Hardcoding one algorithm inside `RateLimiterService` means you can never change the algorithm without editing the service class. With Strategy, each algorithm is a self-contained class. You can mix algorithms: free-tier users get Fixed Window (cheap), paid users get Token Bucket (burst-tolerant), internal services get no limit. Zero changes to `RateLimiterService`.

> The rule of thumb from the template: if the interviewer says "support multiple X", reach for Strategy. Here X = rate-limiting algorithms.

### 2. How would you handle distributed rate limiting?

In a single process, an in-memory dict is fine. Across multiple servers, each server has its own dict — so a user could hit the limit on server A but appear fresh on server B.

The fix is a **shared atomic store**, typically Redis:
- Use `INCR` + `EXPIRE` for Fixed Window (atomic increment + TTL).
- Use a sorted set (`ZADD`, `ZREMRANGEBYSCORE`, `ZCARD`) for Sliding Window.
- Token Bucket can be implemented with a Lua script for atomicity.

For this interview problem, mention this trade-off and note that the in-memory version assumes a single process.

### 3. Per-user vs global rate limiting

A global limiter uses one strategy instance shared by all users — easy but unfair (one heavy user blocks everyone). Per-user limiting gives each user their own state bucket inside the strategy. This implementation uses per-user state stored in `_buckets` / `_windows` / `_logs` dicts keyed by `user_id`.

### 4. Token Bucket — burst advantage

Fixed Window lets a user make all N requests in the first millisecond of the window, then nothing for the rest. Token Bucket prevents this by spreading capacity over time: even if the bucket is full, it only holds `capacity` tokens, so the burst is bounded and then the user must wait for refill.

### 5. Thread safety with `threading.Lock`

Without a lock, two threads can both read `tokens = 1`, both decide "yes, I can allow this", and both subtract 1 — resulting in `tokens = -1` and two allowed requests when only one should have passed. The fix: acquire the lock before reading the state, release it after writing. This serialises access to the shared per-user state.

---

## Complete Code

The imports and the `RateLimitResult` dataclass come first, followed by the abstract base class, then each of the three concrete strategies, and finally the service layer.

```python
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Deque, Tuple, Optional


# ── RateLimitResult ────────────────────────────────────────────────────────────
# A value object returned on every call to is_allowed().
# Callers use .allowed to decide whether to proceed.
# Callers use .retry_after to implement backoff: "try again in X seconds".

@dataclass
class RateLimitResult:
    allowed: bool          # True  = request is permitted
    remaining: int         # how many more requests are allowed right now
    retry_after: float     # seconds to wait before the next token / window reset
                           # 0.0 when the request is allowed

    def __str__(self) -> str:
        if self.allowed:
            return f"ALLOWED  (remaining={self.remaining})"
        return f"BLOCKED  (retry_after={self.retry_after:.2f}s)"


# ── RateLimitStrategy (abstract) ───────────────────────────────────────────────
# The Strategy interface. Each subclass implements one rate-limiting algorithm.
# All state (counters, timestamps) is stored inside the strategy instance,
# keyed by user_id, so one strategy object can serve all users.

class RateLimitStrategy(ABC):
    @abstractmethod
    def is_allowed(self, user_id: str) -> RateLimitResult:
        """
        Decide whether user_id is allowed to make a request right now.
        This method MUST be thread-safe.
        """
        ...


# ── TokenBucketStrategy ────────────────────────────────────────────────────────
# Every user gets a bucket that holds up to `capacity` tokens.
# Tokens refill at `refill_rate` tokens per second (fractional tokens are allowed).
# Each request costs exactly 1 token.
# Allows bursts up to `capacity` as long as the bucket is full.

class TokenBucketStrategy(RateLimitStrategy):
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity:    Maximum tokens a bucket can hold.  Also the max burst size.
            refill_rate: Tokens added per second.  E.g., 1.0 means one token/second.
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        # Per-user state: maps user_id → (current_tokens, last_refill_timestamp)
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()   # one lock protects the entire _buckets dict

    def _get_or_create_bucket(self, user_id: str) -> Tuple[float, float]:
        """Return the (tokens, last_refill_time) for user_id, creating it if needed."""
        if user_id not in self._buckets:
            # New user starts with a full bucket
            self._buckets[user_id] = (float(self.capacity), time.monotonic())
        return self._buckets[user_id]

    def is_allowed(self, user_id: str) -> RateLimitResult:
        with self._lock:
            tokens, last_refill = self._get_or_create_bucket(user_id)
            now = time.monotonic()

            # Step 1: Refill — add tokens proportional to elapsed time
            elapsed = now - last_refill
            tokens = min(self.capacity, tokens + elapsed * self.refill_rate)

            if tokens >= 1.0:
                # Step 2: Consume one token and allow
                tokens -= 1.0
                self._buckets[user_id] = (tokens, now)
                return RateLimitResult(
                    allowed=True,
                    remaining=int(tokens),
                    retry_after=0.0
                )
            else:
                # Step 3: Not enough tokens — compute wait time
                # tokens_needed = 1.0 - tokens (the deficit)
                # time_to_wait  = deficit / refill_rate
                wait = (1.0 - tokens) / self.refill_rate
                self._buckets[user_id] = (tokens, now)
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after=round(wait, 3)
                )


# ── FixedWindowStrategy ────────────────────────────────────────────────────────
# Divides time into fixed-length windows (e.g., 0–60s, 60–120s, ...).
# Each user gets `limit` requests per window.
# At the start of each new window, the counter resets.

class FixedWindowStrategy(RateLimitStrategy):
    def __init__(self, limit: int, window_seconds: float):
        """
        Args:
            limit:          Max requests allowed per window.
            window_seconds: Length of each time window in seconds.
        """
        self.limit = limit
        self.window_seconds = window_seconds
        # Per-user state: maps user_id → (request_count, window_start_time)
        self._windows: Dict[str, Tuple[int, float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, user_id: str) -> RateLimitResult:
        with self._lock:
            now = time.monotonic()

            if user_id not in self._windows:
                # First request ever — open a new window
                self._windows[user_id] = (0, now)

            count, window_start = self._windows[user_id]

            # Step 1: Has the window expired?
            if now - window_start >= self.window_seconds:
                # Reset the counter and start a fresh window
                count = 0
                window_start = now

            if count < self.limit:
                # Step 2: Under the limit — allow and increment
                self._windows[user_id] = (count + 1, window_start)
                return RateLimitResult(
                    allowed=True,
                    remaining=self.limit - (count + 1),
                    retry_after=0.0
                )
            else:
                # Step 3: Over the limit — compute seconds until window resets
                wait = self.window_seconds - (now - window_start)
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after=round(wait, 3)
                )


# ── SlidingWindowStrategy ──────────────────────────────────────────────────────
# Keeps a log of every request's timestamp.
# On each new request, purges timestamps older than `window_seconds`.
# The number of remaining timestamps = requests in the sliding window.

class SlidingWindowStrategy(RateLimitStrategy):
    def __init__(self, limit: int, window_seconds: float):
        """
        Args:
            limit:          Max requests allowed within any window_seconds span.
            window_seconds: Width of the sliding window in seconds.
        """
        self.limit = limit
        self.window_seconds = window_seconds
        # Per-user state: maps user_id → deque of request timestamps
        # A deque is ideal: we add to the right (new requests) and
        # remove from the left (old requests) — both O(1).
        self._logs: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, user_id: str) -> RateLimitResult:
        with self._lock:
            now = time.monotonic()

            if user_id not in self._logs:
                self._logs[user_id] = deque()

            log = self._logs[user_id]
            cutoff = now - self.window_seconds

            # Step 1: Purge timestamps that have fallen outside the window
            while log and log[0] <= cutoff:
                log.popleft()

            if len(log) < self.limit:
                # Step 2: Under the limit — record this request and allow
                log.append(now)
                return RateLimitResult(
                    allowed=True,
                    remaining=self.limit - len(log),
                    retry_after=0.0
                )
            else:
                # Step 3: Over the limit — oldest entry tells us when a slot opens
                # The earliest recorded request will fall out of the window at:
                # log[0] + window_seconds
                wait = log[0] + self.window_seconds - now
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after=round(wait, 3)
                )


# ── RateLimiterService ─────────────────────────────────────────────────────────
# The front desk. Stores a per-user strategy and routes is_allowed() calls.
# Uses a fallback strategy for users with no registered rule.

class RateLimiterService:
    def __init__(self, default_strategy: Optional[RateLimitStrategy] = None):
        """
        Args:
            default_strategy: Applied to any user_id not explicitly registered.
                              If None, unknown users are always denied.
        """
        self._user_strategies: Dict[str, RateLimitStrategy] = {}
        self._default_strategy = default_strategy

    def add_rule(self, user_id: str, strategy: RateLimitStrategy) -> None:
        """Register a specific strategy for user_id (overwrites any previous rule)."""
        self._user_strategies[user_id] = strategy

    def is_allowed(self, user_id: str) -> RateLimitResult:
        """
        Route the request to the user's registered strategy.
        Falls back to default_strategy if no rule exists.
        Denies if no strategy is found at all.
        """
        strategy = self._user_strategies.get(user_id, self._default_strategy)

        if strategy is None:
            # No rule and no default — deny
            return RateLimitResult(allowed=False, remaining=0, retry_after=-1.0)

        return strategy.is_allowed(user_id)


# ── Usage example ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Token Bucket (capacity=3, refill=1/sec) ===")
    tb = TokenBucketStrategy(capacity=3, refill_rate=1.0)
    service = RateLimiterService()
    service.add_rule("alice", tb)

    # Rapid burst: 3 requests should pass, 4th should be blocked
    for i in range(4):
        result = service.is_allowed("alice")
        print(f"  request {i+1}: {result}")

    print()
    print("=== Fixed Window (limit=3, window=60s) ===")
    fw = FixedWindowStrategy(limit=3, window_seconds=60.0)
    service.add_rule("bob", fw)

    for i in range(4):
        result = service.is_allowed("bob")
        print(f"  request {i+1}: {result}")

    print()
    print("=== Sliding Window (limit=3, window=10s) ===")
    sw = SlidingWindowStrategy(limit=3, window_seconds=10.0)
    service.add_rule("carol", sw)

    for i in range(4):
        result = service.is_allowed("carol")
        print(f"  request {i+1}: {result}")

    print()
    print("=== Per-user rules: alice=Token Bucket, bob=Fixed Window ===")
    result_alice = service.is_allowed("alice")
    result_bob = service.is_allowed("bob")
    print(f"  alice: {result_alice}")
    print(f"  bob:   {result_bob}")
```

**What just happened?** `RateLimiterService` does not contain a single `if algorithm == "token_bucket"` branch. It just calls `strategy.is_allowed(user_id)` and the right class does the work. Adding a fourth algorithm — say, a Leaky Bucket — means writing one new class and injecting it. Zero changes to `RateLimiterService`.

---

## Step-by-step walkthrough

Let us trace the Token Bucket strategy with `capacity=3, refill_rate=1.0` (one token per second).

```python
tb = TokenBucketStrategy(capacity=3, refill_rate=1.0)
```

State: no users yet. Alice's bucket does not exist.

```python
tb.is_allowed("alice")   # Request 1
```

Alice is new — bucket created with `tokens=3.0`. Elapsed since last refill = 0s. Tokens after refill: `min(3, 3.0 + 0*1.0) = 3.0`. Consume 1. `tokens=2.0`. **ALLOWED. remaining=2.**

```python
tb.is_allowed("alice")   # Request 2
```

Elapsed ≈ 0s (almost instant). Tokens after refill: ≈ `3.0` is wrong — refill is `2.0 + ~0 * 1.0 ≈ 2.0`. Consume 1. `tokens=1.0`. **ALLOWED. remaining=1.**

```python
tb.is_allowed("alice")   # Request 3
```

Same: `tokens ≈ 1.0`. Consume 1. `tokens ≈ 0.0`. **ALLOWED. remaining=0.**

```python
tb.is_allowed("alice")   # Request 4
```

`tokens ≈ 0.0`. `0.0 < 1.0` so cannot consume. `wait = (1.0 - 0.0) / 1.0 = 1.0s`. **BLOCKED. retry_after=1.0s.**

> This is the burst in action. Alice fired 3 requests instantly (the bucket was full), then the 4th was blocked. The bucket holds exactly as much burst as `capacity` allows — no more.

Now wait 1 second:

```python
time.sleep(1.0)
tb.is_allowed("alice")   # Request 5
```

Elapsed = 1.0s. Tokens after refill: `min(3, 0.0 + 1.0 * 1.0) = 1.0`. Consume 1. `tokens=0.0`. **ALLOWED. remaining=0.**

**What just happened?** The refill arithmetic is the heart of Token Bucket. By tracking `last_refill_time`, the bucket grows in proportion to idle time. A user who pauses for 3 seconds earns 3 tokens back (up to `capacity`). There is no separate background thread filling the bucket — the math happens lazily on each request.

---

## Common interview mistakes

1. **Not accounting for elapsed time in token refill**
   Forgetting to compute `elapsed = now - last_refill` before adding tokens means the bucket never refills, and every request after the burst is permanently blocked. Always refill first, then check.

2. **The Fixed Window boundary double-burst**
   A user sends `limit` requests at 11:59:59 (window A, allowed) and then `limit` more at 12:00:01 (window B, also allowed). They just sent `2 × limit` requests in 2 seconds. This is the known weakness of Fixed Window. Mention it in interviews and note that Sliding Window eliminates it.

3. **Shared lock across all strategies**
   Putting a single global lock around all `is_allowed` calls means every user serialises behind every other user. The correct design is one lock per strategy instance — or, for higher throughput, one lock per user within a strategy. This implementation uses a per-strategy lock, which is a reasonable middle ground.

4. **Single global state instead of per-user state**
   Storing one counter instead of `Dict[user_id → counter]` means one heavy user's traffic is charged to everyone. Always key state by `user_id`.

5. **Not returning `retry_after`**
   Returning only `True/False` is functional but unhelpful. Without `retry_after`, callers either retry immediately (hammering the service) or guess a sleep time. Returning the exact wait time enables polite exponential-backoff and is a simple way to impress an interviewer.

---

## Key patterns used

- **Strategy** — `RateLimitStrategy` is the abstract interface; `TokenBucketStrategy`, `FixedWindowStrategy`, and `SlidingWindowStrategy` are the concrete strategies. `RateLimiterService` is the context that delegates to whichever strategy is registered for a user.
- **Factory** (extension point) — you could add a `RateLimitStrategyFactory.create(type, **params)` method that instantiates the right strategy from a config string, hiding construction details from callers.
- **Thread safety** — `threading.Lock` inside each strategy serialises all reads and writes to per-user state. The lock is acquired at the top of `is_allowed` and released when the `with` block exits, even if an exception is raised.
