# 03 — Elevator System

## What is this problem testing?

This problem tests your ability to model a concurrent, event-driven system and select an appropriate scheduling algorithm. Interviewers want to see whether you know the SCAN algorithm (also called the "elevator algorithm"), whether you understand how to implement ascending and descending priority queues using Python's `heapq`, and whether you separate the *dispatching* concern (which elevator should answer a call?) from the *movement* concern (where does the elevator go next?). The simulation loop (`step()`) is also a signal of testable, incremental design.

---

## Requirements

- The system manages N elevators across M floors
- **External requests**: a person on a floor presses UP or DOWN
- **Internal requests**: a passenger inside an elevator presses a destination floor button
- Elevators use the **SCAN algorithm** — continue in the current direction, servicing all stops along the way; reverse when no more stops exist in that direction
- The dispatcher assigns an incoming call to the elevator with the lowest cost (minimum floors to travel)
- Status of all elevators can be queried at any time

---

## Clarifying questions to ask in interview

1. **How many floors and elevators?** — Affects whether simple linear search is fast enough for dispatch, or if you need something more sophisticated.
2. **Do we simulate movement tick-by-tick, or jump directly to the next stop?** — Tick-by-tick is more realistic and testable; jump-to-stop is simpler to implement.
3. **What happens if all elevators are busy?** — Does the request queue up, or does it always get assigned immediately?
4. **Are there weight limits or capacity limits?** — Not required for a basic LLD, but worth asking.
5. **Should we handle priority for emergency floors?** — Some real systems have dedicated priority queues for fire alarms.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Elevator system | `ElevatorSystem` |
| Elevator | `Elevator` |
| Floor request | Value (floor number + direction) |
| Direction | `Direction` (enum) |
| Door status | `DoorStatus` (enum) |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Call an elevator to a floor | `call_elevator(floor, direction)` | `ElevatorSystem` |
| Select a destination from inside | `select_floor(elevator_id, floor)` | `ElevatorSystem` |
| Add a stop to the queue | `add_stop(floor)` | `Elevator` |
| Move one floor toward next stop | `step()` | `Elevator` |
| Decide next target (SCAN logic) | `_next_target()` | `Elevator` |
| Pick the cheapest elevator | `_dispatch(floor)` | `ElevatorSystem` |
| Estimate travel cost | `cost_to_serve(floor)` | `Elevator` |

---

## Relationships

```
ElevatorSystem ── HAS-MANY ────► Elevator
ElevatorSystem    IS             Dispatcher  (owns _dispatch logic)

Elevator ─────── HAS ──────────► up_stops   (min-heap: floors above current)
Elevator ─────── HAS ──────────► down_stops (max-heap: floors below current)

Direction  <<enum>>: UP | DOWN | IDLE
DoorStatus <<enum>>: OPEN | CLOSED
```

> Think of it like a supermarket scanner. The SCAN algorithm works the same way an elevator does in real life — it goes up, picks up everyone going up, reaches the top, then comes back down picking up everyone going down. It does not jump around randomly. The two heaps are its "to-do lists" for each direction.

---

## Design decisions

### 1. SCAN algorithm with two heaps

**Decision:** Use a min-heap for upward stops and a max-heap (simulated via negation) for downward stops.

**Why:** SCAN is fairer than FCFS (first-come, first-served) because requests in the current direction of travel are never starved. A single min-heap would require sorting every time direction changes, which is inefficient. Two heaps allow O(log n) insertions and O(1) peek at the next stop in either direction.

**The negation trick for max-heap:**
Python's `heapq` is a min-heap only. To get a max-heap (largest first), negate the values. Pushing `-7` and `-3` onto a min-heap will pop `-7` first, which represents floor 7 — the highest.

**Alternative considered:** A sorted list scanned linearly. Works but is O(n) per operation, which matters at scale.

### 2. `step()` moves one floor at a time

**Decision:** Each call to `step()` moves the elevator exactly one floor.

**Why:** This makes the simulation deterministic and testable. You can assert the elevator's position after exactly K steps. A "jump to destination" model is harder to test and harder to extend (e.g., adding delays, weight sensors).

### 3. `cost_to_serve()` is a pluggable heuristic

**Decision:** The dispatch cost is computed by a method on `Elevator`, not hardcoded in `ElevatorSystem._dispatch()`.

**Why:** The simplest heuristic is absolute distance (`abs(current - floor)`). A smarter heuristic would also consider direction alignment (an elevator already moving toward the requested floor should be cheaper). By putting the heuristic on `Elevator`, you can subclass and override it without touching `ElevatorSystem`.

### 4. External vs internal requests use the same `add_stop()` method

**Decision:** Both hall calls (`call_elevator`) and cabin button presses (`select_floor`) funnel through `Elevator.add_stop()`.

**Why:** From the elevator's perspective, a stop is a stop — it does not matter who requested it. This avoids duplicating the heap insertion logic.

---

## Complete Code

```python
from enum import Enum, auto
from typing import List, Optional
import heapq


# ── Enums ──────────────────────────────────────────────────────────────────────

class Direction(Enum):
    UP   = auto()
    DOWN = auto()
    IDLE = auto()   # no pending stops — elevator is waiting

class DoorStatus(Enum):
    OPEN   = auto()
    CLOSED = auto()


# ── Elevator ───────────────────────────────────────────────────────────────────
# Each elevator manages its own two queues and knows how to move itself.
# It does NOT know about other elevators or how it was dispatched.

class Elevator:
    def __init__(self, elevator_id: int):
        self.elevator_id = elevator_id
        self.current_floor = 0              # all elevators start at ground
        self.direction = Direction.IDLE
        self.door = DoorStatus.CLOSED
        self._up_stops: list = []           # min-heap: smallest floor number first
        self._down_stops: list = []         # max-heap via negation: largest floor first

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_stop(self, floor: int) -> None:
        """Queue a floor stop — routes to the correct heap based on direction."""
        if floor > self.current_floor:
            # Going up: push onto the min-heap (serves lowest floor first)
            heapq.heappush(self._up_stops, floor)
        elif floor < self.current_floor:
            # Going down: push negated value onto min-heap to simulate max-heap
            # Example: push -7 for floor 7. When we pop -7, we negate it back to 7.
            heapq.heappush(self._down_stops, -floor)
        else:
            # Already on this floor — just open doors
            self._open_doors()

    def step(self) -> None:
        """Advance one floor toward the next stop (SCAN algorithm)."""
        target = self._next_target()
        if target is None:
            self.direction = Direction.IDLE
            return

        # Set direction based on where we need to go
        self.direction = Direction.UP if target > self.current_floor else Direction.DOWN
        # Move exactly one floor
        self.current_floor += 1 if self.direction == Direction.UP else -1

        # If we reached a stop, open and close doors, then remove it from the queue
        if self.current_floor == target:
            self._open_doors()
            self._close_doors()

    def cost_to_serve(self, floor: int) -> int:
        """
        Heuristic used by the dispatcher: how many floors must this elevator
        travel before it can realistically serve `floor`?
        Simple version: absolute distance. Override for smarter dispatch.
        """
        return abs(self.current_floor - floor)

    # ── Internals ──────────────────────────────────────────────────────────────

    def _next_target(self) -> Optional[int]:
        """
        SCAN logic: continue in the current direction if stops remain.
        When the current direction is exhausted, check the other direction.
        """
        if self.direction in (Direction.UP, Direction.IDLE):
            if self._up_stops:
                return self._up_stops[0]        # peek at next upward stop (no pop)
            if self._down_stops:
                return -self._down_stops[0]     # negate back to get the actual floor
        else:  # Direction.DOWN
            if self._down_stops:
                return -self._down_stops[0]
            if self._up_stops:
                return self._up_stops[0]
        return None   # no stops in either direction — elevator is truly idle

    def _consume_target(self, floor: int) -> None:
        """Remove the floor we just reached from whichever heap it was in."""
        if self.direction in (Direction.UP, Direction.IDLE):
            if self._up_stops and self._up_stops[0] == floor:
                heapq.heappop(self._up_stops)
        elif self._down_stops and -self._down_stops[0] == floor:
            heapq.heappop(self._down_stops)

    def _open_doors(self) -> None:
        self.door = DoorStatus.OPEN
        print(f"  Elevator {self.elevator_id} ── doors OPEN  at floor {self.current_floor}")

    def _close_doors(self) -> None:
        self.door = DoorStatus.CLOSED
        self._consume_target(self.current_floor)   # remove this floor from the queue
        print(f"  Elevator {self.elevator_id} ── doors CLOSED at floor {self.current_floor}")

    def __repr__(self) -> str:
        return f"Elevator({self.elevator_id}, floor={self.current_floor}, {self.direction.name})"


# ── ElevatorSystem (dispatcher + facade) ──────────────────────────────────────
# ElevatorSystem is the single public interface.
# It handles both external (hall) and internal (cabin) requests.
# The _dispatch() method picks the best elevator for an incoming call.

class ElevatorSystem:
    def __init__(self, num_elevators: int, num_floors: int):
        self.num_floors = num_floors
        self.elevators: List[Elevator] = [Elevator(i) for i in range(num_elevators)]

    def call_elevator(self, floor: int, direction: Direction) -> Elevator:
        """External request — someone on floor `floor` pressed UP or DOWN."""
        if not (0 <= floor < self.num_floors):
            raise ValueError(f"Floor {floor} out of range [0, {self.num_floors - 1}]")
        elevator = self._dispatch(floor)            # pick the best elevator
        elevator.add_stop(floor)                    # add the stop to its queue
        print(f"[DISPATCH] Floor {floor} ({direction.name}) → Elevator {elevator.elevator_id}")
        return elevator

    def select_floor(self, elevator_id: int, floor: int) -> None:
        """Internal request — passenger inside elevator presses a floor button."""
        self.elevators[elevator_id].add_stop(floor)
        print(f"[SELECT]   Elevator {elevator_id} → Floor {floor}")

    def step_all(self) -> None:
        """Advance the simulation by one tick — each elevator moves one floor."""
        for e in self.elevators:
            e.step()

    def status(self) -> None:
        """Print the current state of all elevators."""
        for e in self.elevators:
            print(f"  {e}")

    def _dispatch(self, floor: int) -> Elevator:
        """
        Pick the elevator with the lowest cost to serve this floor.
        Uses min() with cost_to_serve() as the key — simple and swappable.
        """
        return min(self.elevators, key=lambda e: e.cost_to_serve(floor))


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    system = ElevatorSystem(num_elevators=2, num_floors=10)

    # Someone on floor 5 wants to go up; the elevator is also told to go to floor 8
    e = system.call_elevator(floor=5, direction=Direction.UP)
    system.select_floor(e.elevator_id, floor=8)

    print("\nSimulating movement:")
    for _ in range(10):
        system.step_all()

    system.status()
```

---

## Step-by-step walkthrough

```python
system = ElevatorSystem(num_elevators=2, num_floors=10)
```
Two `Elevator` objects are created, IDs 0 and 1. Both start on floor 0, `IDLE`, doors `CLOSED`, both heaps empty.

```python
e = system.call_elevator(floor=5, direction=Direction.UP)
```
- `_dispatch(5)` is called. It runs `min([Elevator(0), Elevator(1)], key=lambda e: e.cost_to_serve(5))`.
- Elevator 0: `abs(0 - 5) = 5`. Elevator 1: `abs(0 - 5) = 5`. Tie — Python's `min` picks the first one (Elevator 0).
- `elevator.add_stop(5)` is called. `5 > 0` (current floor), so `heapq.heappush(up_stops, 5)`. Up-heap is now `[5]`.
- The elevator object is returned so the caller can use its ID for the next step.

**What just happened?** Elevator 0 now has one stop queued: floor 5. Its heap looks like `_up_stops = [5]`.

```python
system.select_floor(e.elevator_id, floor=8)
```
- `elevator.add_stop(8)`. `8 > 0`, so push 8 onto up-heap. `_up_stops = [5, 8]` (heap order).

```python
for _ in range(10):
    system.step_all()
```
Each iteration calls `step()` on both elevators. Let's trace Elevator 0:

- **Tick 1:** `_next_target()` returns `5` (IDLE defaults to UP direction, checks `_up_stops`). Direction is set to `UP`. Floor advances: `0 → 1`. Not at target yet.
- **Tick 2 to 4:** Floor advances `2 → 3 → 4`.
- **Tick 5:** Floor reaches `5`. Doors open, then close. `_consume_target(5)` pops 5 from the heap. `_up_stops = [8]`.
- **Ticks 6–8:** Floor advances `6 → 7 → 8`.
- **Tick 9:** Floor reaches `8`. Doors open, then close. `_consume_target(8)` pops 8. `_up_stops = []`.
- **Tick 10:** `_next_target()` returns `None`. Direction set to `IDLE`. No movement.

**What just happened?** The elevator visited floors 5 and 8 in order (SCAN: smallest first while going up). After serving both stops it went IDLE.

---

## Common interview mistakes

1. **Using FCFS (first-come, first-served) instead of SCAN** — FCFS can lead to starvation (a request on floor 9 waits forever while everyone keeps pressing 2 and 3). SCAN is a minimal requirement for any real elevator system. Name the algorithm explicitly in your interview.

2. **Using a single sorted list instead of two heaps** — A single list requires O(n) scan on every `step()` to find the next stop in the current direction. Two heaps give O(log n) insert and O(1) peek.

3. **Forgetting the negation trick for the down-heap** — Python's `heapq` is always a min-heap. For descending order (service highest floor first while going down), negate values on push and negate back on pop. Forgetting this means the elevator services downward stops in the wrong order.

4. **Jumping directly to the destination** — Setting `current_floor = target` in one step. This skips all intermediate floors and breaks the SCAN guarantee that floors along the way get served.

5. **Putting SCAN logic in `ElevatorSystem`** — The elevator should move itself. `ElevatorSystem` should only dispatch and coordinate. If SCAN logic is in the system, you cannot test an individual elevator in isolation.

---

## Key patterns used

- **Strategy (pluggable)** — `cost_to_serve()` is a method that can be overridden in a subclass to implement smarter dispatching without changing `ElevatorSystem`
- **Facade** — `ElevatorSystem` is the single API; callers never touch heap internals
- **Simulation loop** — `step()` advances state one unit at a time, making the system deterministically testable
- **Two-heap pattern** — Asymmetric priority queues for ascending vs descending traversal
- **Enumeration** — `Direction` and `DoorStatus` make state transitions readable and exhaustive
- **Single Responsibility** — `Elevator` moves itself; `ElevatorSystem` dispatches and coordinates


---

[← Back to State Machine Template](template.md)
