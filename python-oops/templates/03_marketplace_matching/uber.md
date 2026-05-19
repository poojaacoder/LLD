# 03 — Uber / Ride Sharing

## What is this problem testing?

This problem tests your ability to model a **two-sided real-time marketplace** where a consumer (rider) is matched to a provider (driver) and both sides move through a well-defined lifecycle. Interviewers are watching for: whether you separate the matching algorithm from the service, whether pricing is a pluggable strategy rather than hardcoded logic, whether the trip follows a proper state machine, and whether driver availability is correctly updated at every stage.

---

## Requirements

- Riders can request a ride from their current location to a destination
- The system matches the rider to the nearest available driver
- Drivers can accept or reject a matched ride
- A trip moves through a fixed lifecycle: `REQUESTED → MATCHED → ACCEPTED → IN_PROGRESS → COMPLETED / CANCELLED`
- Dynamic pricing: base fare during normal hours, surge multiplier during peak hours
- Rating system: a rider can rate a driver after a completed trip
- Both rider and driver maintain a history of their trips

---

## Clarifying questions to ask in interview

1. **What happens if no driver is available?** — Return `None` immediately, or queue the request and notify when a driver comes free?
2. **What happens if a driver rejects a ride?** — Re-match with the next best driver, or notify the rider that no match was found?
3. **Is location real-time (GPS stream) or static?** — For this design, location is a simple coordinate updated when needed.
4. **How is surge pricing triggered?** — By time of day, by demand-supply ratio, or manually? For this design, it is injected at service construction time.
5. **Can a rider cancel after a driver is matched but before they accept?** — Yes, any non-terminal state can transition to `CANCELLED`.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Rider | `Rider` |
| Driver | `Driver` |
| A geographic point | `Location` |
| A ride request and its lifecycle | `Trip` |
| Current state of a trip | `TripStatus` (enum) |
| Algorithm for picking a driver | `MatchingStrategy` |
| Rules for calculating fare | `PricingStrategy` |
| A star rating with a comment | `Rating` |
| Entry point / coordinator | `UberService` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Register a driver | `register_driver(driver)` | `UberService` |
| Register a rider | `register_rider(rider)` | `UberService` |
| Request a ride | `request_ride(rider, destination)` | `UberService` |
| Find best driver | `find_match(rider, drivers)` | `MatchingStrategy` |
| Accept a ride | `accept_ride(driver, trip)` | `UberService` |
| Start a trip | `start_trip(trip)` | `UberService` |
| Complete a trip | `complete_trip(trip)` | `UberService` |
| Cancel a trip | `cancel_trip(trip, reason)` | `UberService` |
| Calculate fare | `calculate(trip)` | `PricingStrategy` |
| Rate a driver | `rate_driver(trip, score, comment)` | `UberService` |
| Advance trip state | `transition_to(new_status)` | `Trip` |

---

## Relationships

```
UberService  (facade — single entry point)
 │
 ├── MatchingStrategy  <<abstract>>
 │       ├── NearestDriverStrategy
 │       └── HighestRatedStrategy
 │
 ├── PricingStrategy  <<abstract>>
 │       ├── BasePricing
 │       └── SurgePricing
 │
 ├── Rider
 │     └── trip_history: List[Trip]
 │
 ├── Driver
 │     ├── location: Location
 │     ├── is_available: bool
 │     ├── rating: float
 │     └── trip_history: List[Trip]
 │
 └── Trip  (the join entity — links Rider + Driver)
       ├── TripStatus (state machine)
       ├── start_location, destination: Location
       ├── fare: float
       └── rating: Optional[Rating]
```

> Think of it like a taxi dispatch centre. The dispatcher (`UberService`) receives a call from a passenger (`Rider`). The dispatcher's rulebook (`MatchingStrategy`) picks the best cab. A job sheet (`Trip`) is created and handed to the driver (`Driver`). The job sheet tracks everything — where, when, how much — and its status changes as the journey progresses.

---

## Trip lifecycle — State Machine

Every `Trip` moves through exactly these states. Drawing this on the whiteboard early shows you have thought about edge cases.

```
[REQUESTED] ──► match found ──► [MATCHED] ──► driver accepts ──► [ACCEPTED]
                                     │                                │
                              driver rejects                    trip starts
                            (re-match or fail)                       │
                                                               [IN_PROGRESS]
                                                                     │
                                              ┌──────────────────────┤
                                         success                  cancel
                                              │                       │
                                        [COMPLETED]            [CANCELLED]

Any state except COMPLETED/CANCELLED can go to CANCELLED.
```

---

## Design decisions

### 1. `MatchingStrategy` separate from `PricingStrategy`

**Decision:** Two independent abstract classes, injected separately into `UberService`.

**Why:** They change for completely different reasons. Matching logic might change from "nearest" to "highest rated" based on a product decision. Pricing might change from base to surge based on real-time demand. If they were in one class, changing one would risk breaking the other — violating Single Responsibility.

### 2. Trip as the join entity

**Decision:** `Trip` is a first-class object that holds references to both `Rider` and `Driver`, plus the full lifecycle state.

**Why:** The relationship between rider and driver only exists during a trip. A `Trip` is the formal contract that captures that moment — who, where, when, how much. Without `Trip` as an object, you would be scattering fare, status, and timestamps across `Rider` and `Driver` — and they would need to know about each other directly.

### 3. State machine with `transition_to()`

**Decision:** `Trip` owns a `transition_to()` method that validates the transition before applying it.

**Why:** Without validation, a bug in `UberService` could call `complete_trip()` on a trip that was never started, corrupting the fare and history. The state machine makes illegal transitions explicit errors. This is the State pattern.

### 4. Driver availability as a flag

**Decision:** `Driver.is_available` is set to `False` when matched and back to `True` when the trip completes or is cancelled.

**Why:** If you forget to reset this, the driver disappears from the marketplace permanently — a silent bug that is hard to trace. The flag is the simplest representation; for production you would use a proper availability service.

### 5. Pricing injected, not embedded in `Trip`

**Decision:** `PricingStrategy.calculate(trip)` computes the fare outside `Trip`. The result is stored on `trip.fare` at completion time.

**Why:** `Trip` stores facts (start time, end time, distance). `PricingStrategy` applies a policy to those facts. Separating the two makes it trivial to change from base to surge pricing, or add a discount strategy, without touching `Trip`.

---

## Complete Code

The code below follows the same top-down order as the entity table: enums first, then data classes, then strategies, then core entities, then the facade.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional
import math
import uuid


# ── Enums ──────────────────────────────────────────────────────────────────────

class TripStatus(Enum):
    REQUESTED   = auto()   # rider has asked for a ride; no driver yet
    MATCHED     = auto()   # system has found a candidate driver
    ACCEPTED    = auto()   # driver has confirmed
    IN_PROGRESS = auto()   # trip is underway
    COMPLETED   = auto()   # trip finished, fare settled — terminal state
    CANCELLED   = auto()   # someone cancelled — terminal state


# ── Value Objects ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Location:
    """
    An immutable (lat, lng) pair. Frozen so it cannot be accidentally mutated.
    Use simple Euclidean distance — perfectly valid for interviews.
    """
    lat: float
    lng: float

    def distance_to(self, other: Location) -> float:
        return math.sqrt((self.lat - other.lat) ** 2 + (self.lng - other.lng) ** 2)


@dataclass
class Rating:
    """A star rating with an optional comment. 1 = worst, 5 = best."""
    score: int        # 1–5
    comment: str = ""

    def __post_init__(self) -> None:
        if not 1 <= self.score <= 5:
            raise ValueError(f"Rating score must be between 1 and 5, got {self.score}.")


# ── Core Entities ──────────────────────────────────────────────────────────────

class Rider:
    def __init__(self, name: str, location: Location):
        self.rider_id = str(uuid.uuid4())
        self.name = name
        self.location = location
        self.trip_history: List[Trip] = []

    def __hash__(self) -> int:
        return hash(self.rider_id)

    def __repr__(self) -> str:
        return f"Rider({self.name!r})"


class Driver:
    def __init__(self, name: str, location: Location):
        self.driver_id = str(uuid.uuid4())
        self.name = name
        self.location = location           # updated as the driver moves
        self.is_available: bool = True     # False while on a trip
        self.rating: float = 5.0           # running average, updated after trips
        self._rating_count: int = 0
        self.trip_history: List[Trip] = []

    def update_rating(self, new_score: int) -> None:
        """Incremental average: no need to store all past scores."""
        self._rating_count += 1
        self.rating = round(
            ((self.rating * (self._rating_count - 1)) + new_score) / self._rating_count,
            2,
        )

    def __hash__(self) -> int:
        return hash(self.driver_id)

    def __repr__(self) -> str:
        return f"Driver({self.name!r}, rating={self.rating})"


# ── Trip (the join entity + state machine) ─────────────────────────────────────

# Valid transitions: maps each state to the set of states it may advance to.
# Having this in one place makes it easy to audit and extend.
_VALID_TRANSITIONS: Dict[TripStatus, set] = {
    TripStatus.REQUESTED:   {TripStatus.MATCHED,      TripStatus.CANCELLED},
    TripStatus.MATCHED:     {TripStatus.ACCEPTED,     TripStatus.CANCELLED},
    TripStatus.ACCEPTED:    {TripStatus.IN_PROGRESS,  TripStatus.CANCELLED},
    TripStatus.IN_PROGRESS: {TripStatus.COMPLETED,    TripStatus.CANCELLED},
    TripStatus.COMPLETED:   set(),   # terminal
    TripStatus.CANCELLED:   set(),   # terminal
}


class Trip:
    def __init__(
        self,
        rider: Rider,
        start_location: Location,
        destination: Location,
    ):
        self.trip_id = str(uuid.uuid4())
        self.rider = rider
        self.driver: Optional[Driver] = None         # assigned when matched
        self.start_location = start_location
        self.destination = destination
        self.status: TripStatus = TripStatus.REQUESTED
        self.start_time: Optional[datetime] = None   # set when IN_PROGRESS
        self.end_time:   Optional[datetime] = None   # set when COMPLETED
        self.fare: float = 0.0                       # set when COMPLETED
        self.rating: Optional[Rating] = None         # set after completion
        self.cancellation_reason: str = ""

    def transition_to(self, new_status: TripStatus) -> None:
        """
        Move the trip to a new state.
        Raises ValueError if the transition is not allowed.
        This is the guard at every state change — the heart of the state machine.
        """
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {self.status.name} to {new_status.name}."
            )
        print(f"[Trip {self.trip_id[:8]}] {self.status.name} → {new_status.name}")
        self.status = new_status

    @property
    def distance_km(self) -> float:
        """Straight-line distance between start and destination."""
        return self.start_location.distance_to(self.destination)

    @property
    def duration_minutes(self) -> float:
        """Duration in minutes. Returns 0 if the trip has not ended yet."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return 0.0

    def __repr__(self) -> str:
        return (
            f"Trip({self.rider.name!r} → {self.driver.name!r if self.driver else 'unassigned'}, "
            f"{self.status.name})"
        )


# ── Matching Strategies ────────────────────────────────────────────────────────

class MatchingStrategy(ABC):
    @abstractmethod
    def find_match(
        self, rider: Rider, available_drivers: List[Driver]
    ) -> Optional[Driver]:
        """Return the best driver for this rider, or None if no one is available."""
        ...


class NearestDriverStrategy(MatchingStrategy):
    """Pick the driver whose current location is closest to the rider."""

    def find_match(
        self, rider: Rider, available_drivers: List[Driver]
    ) -> Optional[Driver]:
        if not available_drivers:
            return None
        return min(
            available_drivers,
            key=lambda d: rider.location.distance_to(d.location),
        )


class HighestRatedStrategy(MatchingStrategy):
    """Pick the available driver with the highest rating."""

    def find_match(
        self, rider: Rider, available_drivers: List[Driver]
    ) -> Optional[Driver]:
        if not available_drivers:
            return None
        return max(available_drivers, key=lambda d: d.rating)


# ── Pricing Strategies ─────────────────────────────────────────────────────────

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, trip: Trip) -> float:
        """Return the fare for a completed trip."""
        ...


class BasePricing(PricingStrategy):
    """
    Simple fare: base amount + per-km rate.
    Example: ₹50 base + ₹15/km.
    """

    def __init__(self, base_fare: float = 50.0, per_km_rate: float = 15.0):
        self._base_fare = base_fare
        self._per_km_rate = per_km_rate

    def calculate(self, trip: Trip) -> float:
        return round(self._base_fare + self._per_km_rate * trip.distance_km, 2)


class SurgePricing(PricingStrategy):
    """
    Apply a surge multiplier on top of the base fare.
    Surge factor of 2.0 means the rider pays double during peak hours.
    """

    def __init__(
        self,
        base_fare: float = 50.0,
        per_km_rate: float = 15.0,
        surge_multiplier: float = 2.0,
    ):
        self._base_fare = base_fare
        self._per_km_rate = per_km_rate
        self._surge_multiplier = surge_multiplier

    def calculate(self, trip: Trip) -> float:
        base = self._base_fare + self._per_km_rate * trip.distance_km
        return round(base * self._surge_multiplier, 2)


# ── UberService (facade) ───────────────────────────────────────────────────────
# All operations go through UberService.
# Riders and drivers never interact with each other's objects directly.

class UberService:
    def __init__(
        self,
        matching_strategy: MatchingStrategy,
        pricing_strategy: PricingStrategy,
    ):
        self._matching_strategy = matching_strategy
        self._pricing_strategy  = pricing_strategy
        self._drivers: Dict[str, Driver] = {}
        self._riders:  Dict[str, Rider]  = {}
        self._trips:   Dict[str, Trip]   = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register_driver(self, driver: Driver) -> None:
        self._drivers[driver.driver_id] = driver
        print(f"[Uber] Driver registered: {driver.name}")

    def register_rider(self, rider: Rider) -> None:
        self._riders[rider.rider_id] = rider
        print(f"[Uber] Rider registered: {rider.name}")

    # ── Ride request ──────────────────────────────────────────────────────────

    def request_ride(self, rider: Rider, destination: Location) -> Optional[Trip]:
        """
        Rider asks for a ride.
        1. Create a Trip in REQUESTED state.
        2. Find available drivers using the matching strategy.
        3. If found, assign the driver and move trip to MATCHED.
        4. If not found, cancel the trip and return None.
        """
        trip = Trip(rider=rider, start_location=rider.location, destination=destination)
        self._trips[trip.trip_id] = trip
        print(f"\n[Uber] Ride requested by {rider.name}")

        available = [d for d in self._drivers.values() if d.is_available]
        matched_driver = self._matching_strategy.find_match(rider, available)

        if not matched_driver:
            print(f"[Uber] No available driver found for {rider.name}.")
            trip.transition_to(TripStatus.CANCELLED)
            trip.cancellation_reason = "No driver available"
            return None

        # Assign driver and advance state
        trip.driver = matched_driver
        matched_driver.is_available = False   # take the driver off the market
        trip.transition_to(TripStatus.MATCHED)
        print(f"[Uber] Matched {rider.name} with driver {matched_driver.name}")
        return trip

    # ── Driver response ────────────────────────────────────────────────────────

    def accept_ride(self, driver: Driver, trip: Trip) -> None:
        """Driver confirms they will pick up the rider."""
        if trip.driver is not driver:
            raise ValueError(f"{driver.name} is not the assigned driver for this trip.")
        trip.transition_to(TripStatus.ACCEPTED)

    def reject_ride(self, driver: Driver, trip: Trip) -> Optional[Trip]:
        """
        Driver declines. Free them up, then try to find the next best driver.
        This avoids the rider being stuck indefinitely.
        """
        if trip.driver is not driver:
            raise ValueError(f"{driver.name} is not the assigned driver for this trip.")

        print(f"[Uber] {driver.name} rejected the ride. Re-matching...")
        driver.is_available = True  # free the rejecting driver
        trip.driver = None

        # Move back to REQUESTED so we can match again
        trip.status = TripStatus.REQUESTED  # direct assignment to reset, not transition

        # Exclude the rejecting driver from the next round
        available = [
            d for d in self._drivers.values()
            if d.is_available and d is not driver
        ]
        next_driver = self._matching_strategy.find_match(trip.rider, available)

        if not next_driver:
            print(f"[Uber] No other driver available. Cancelling trip.")
            trip.transition_to(TripStatus.CANCELLED)
            trip.cancellation_reason = "All drivers rejected"
            return None

        trip.driver = next_driver
        next_driver.is_available = False
        trip.transition_to(TripStatus.MATCHED)
        print(f"[Uber] Re-matched with {next_driver.name}")
        return trip

    # ── Trip lifecycle ─────────────────────────────────────────────────────────

    def start_trip(self, trip: Trip) -> None:
        """Driver has picked up the rider. The meter starts."""
        trip.transition_to(TripStatus.IN_PROGRESS)
        trip.start_time = datetime.now()

    def complete_trip(self, trip: Trip) -> float:
        """
        Rider has arrived. Calculate fare, free the driver, update history.
        Returns the fare charged.
        """
        trip.end_time = datetime.now()
        trip.transition_to(TripStatus.COMPLETED)

        # Fare is calculated by the injected pricing strategy
        trip.fare = self._pricing_strategy.calculate(trip)

        # Free the driver for new rides
        if trip.driver:
            trip.driver.is_available = True
            trip.driver.trip_history.append(trip)

        trip.rider.trip_history.append(trip)

        print(
            f"[Uber] Trip completed. Distance: {trip.distance_km:.2f} units. "
            f"Fare: ₹{trip.fare:.2f}"
        )
        return trip.fare

    def cancel_trip(self, trip: Trip, reason: str = "") -> None:
        """Either side cancels. Free the driver if one was assigned."""
        trip.cancellation_reason = reason
        trip.transition_to(TripStatus.CANCELLED)

        if trip.driver:
            trip.driver.is_available = True   # never forget to free the driver

        print(f"[Uber] Trip cancelled. Reason: {reason or 'not specified'}")

    # ── Rating ─────────────────────────────────────────────────────────────────

    def rate_driver(self, trip: Trip, score: int, comment: str = "") -> None:
        """Rider rates the driver after a completed trip."""
        if trip.status is not TripStatus.COMPLETED:
            raise ValueError("Can only rate a completed trip.")
        if not trip.driver:
            raise ValueError("No driver to rate.")

        rating = Rating(score=score, comment=comment)
        trip.rating = rating
        trip.driver.update_rating(score)
        print(f"[Uber] {trip.rider.name} rated {trip.driver.name}: {score}/5 — '{comment}'")


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Build the service with nearest-driver matching and base pricing
    uber = UberService(
        matching_strategy=NearestDriverStrategy(),
        pricing_strategy=BasePricing(base_fare=50, per_km_rate=15),
    )

    # Register riders
    alice = Rider("Alice", Location(12.9, 77.6))
    uber.register_rider(alice)

    # Register drivers at different locations
    bob   = Driver("Bob",   Location(12.91, 77.61))   # close to Alice
    carol = Driver("Carol", Location(13.00, 77.80))   # farther away
    uber.register_driver(bob)
    uber.register_driver(carol)

    # Alice requests a ride to the airport
    airport = Location(13.2, 77.7)
    trip = uber.request_ride(alice, destination=airport)

    if trip:
        # Bob (nearest) was matched — he accepts
        uber.accept_ride(bob, trip)

        # Trip starts
        uber.start_trip(trip)

        # Trip completes
        fare = uber.complete_trip(trip)

        # Alice rates Bob
        uber.rate_driver(trip, score=5, comment="Great driver, very smooth ride!")

        print(f"\nBob's updated rating: {bob.rating}")
        print(f"Alice's trip history: {alice.trip_history}")
```

---

## Step-by-step walkthrough

```python
uber = UberService(
    matching_strategy=NearestDriverStrategy(),
    pricing_strategy=BasePricing(base_fare=50, per_km_rate=15),
)
```
The service is constructed with two injected strategies. `NearestDriverStrategy` and `BasePricing` are plug-in objects — you could swap them to `HighestRatedStrategy` and `SurgePricing` without touching any other code.

```python
alice = Rider("Alice", Location(12.9, 77.6))
bob   = Driver("Bob",   Location(12.91, 77.61))
carol = Driver("Carol", Location(13.00, 77.80))
```
Three objects are created. Bob is very close to Alice (distance ≈ 0.014 units). Carol is much farther away (distance ≈ 0.22 units). Both drivers start with `is_available = True`.

```python
trip = uber.request_ride(alice, destination=Location(13.2, 77.7))
```
- A `Trip` is created in `REQUESTED` state. `trip.driver` is `None`.
- `NearestDriverStrategy.find_match()` computes the distance from Alice to each available driver. Bob wins.
- Bob's `is_available` is set to `False` — he is reserved.
- `trip.driver = bob`. Trip transitions to `MATCHED`.

**What just happened?** A job sheet (`Trip`) now exists linking Alice and Bob. Bob is off the market. Carol is still free to be matched with a new rider.

```python
uber.accept_ride(bob, trip)
```
Validates that `trip.driver is bob` (guards against a different driver accepting). Trip transitions: `MATCHED → ACCEPTED`.

```python
uber.start_trip(trip)
```
Trip transitions: `ACCEPTED → IN_PROGRESS`. `trip.start_time = datetime.now()` is stamped.

```python
fare = uber.complete_trip(trip)
```
- `trip.end_time` is stamped.
- Trip transitions: `IN_PROGRESS → COMPLETED`.
- `BasePricing.calculate(trip)` computes: distance from `(12.9, 77.6)` to `(13.2, 77.7)` ≈ 0.316 units. Fare = `₹50 + 15 × 0.316 ≈ ₹54.74`.
- `trip.fare = 54.74` is stored on the trip.
- Bob's `is_available` is reset to `True`.
- Both Bob and Alice's `trip_history` are updated.

**What just happened?** The trip is finished. Bob is free for the next rider. Alice's and Bob's histories both contain this trip. The fare is recorded on the trip object for auditing.

```python
uber.rate_driver(trip, score=5, comment="Great driver!")
```
- Validates that the trip is `COMPLETED`.
- Creates a `Rating(score=5, ...)` and attaches it to `trip.rating`.
- Calls `bob.update_rating(5)` — uses incremental average formula so Bob's overall rating is updated without storing every past score.

---

## Common interview mistakes

1. **No state validation in `transition_to()`** — If `complete_trip()` can be called on a `REQUESTED` trip, the system records a fare with no start time and corrupts the driver's history. Always validate allowed transitions and raise on illegal ones.

2. **Matching logic inside `UberService`** — A hardcoded `min(drivers, key=lambda d: distance(...))` inside `request_ride()` is a common first draft. It makes the strategy impossible to change without editing the facade. Extract it into a `MatchingStrategy` immediately.

3. **Forgetting to reset `driver.is_available`** — If `is_available` stays `False` after a trip completes or is cancelled, the driver is invisible to new riders forever. This is a silent bug — the system still works but that driver is lost. Always reset in both `complete_trip()` and `cancel_trip()`.

4. **Hardcoding pricing inside `Trip`** — Putting `fare = 50 + 15 * distance` inside `Trip.complete()` means changing the pricing model requires editing the core domain object. Pricing is a policy — it belongs in a separate strategy class.

5. **No handling of driver rejection** — If `reject_ride()` is missing, a driver who is offline or busy simply never responds and the rider waits forever. Show that you have thought about re-matching and max retry limits even if you do not implement them fully.

---

## Key patterns used

- **Strategy** — `MatchingStrategy` and `PricingStrategy` are independently swappable algorithms
- **State** — `TripStatus` + `transition_to()` + `_VALID_TRANSITIONS` make the lifecycle explicit and validated
- **Facade** — `UberService` is the single public interface; `Trip`, `Driver`, and `Rider` are internal domain objects
- **Single Responsibility** — `Trip` stores trip facts, `MatchingStrategy` picks drivers, `PricingStrategy` calculates fare, `UberService` orchestrates
- **Open/Closed Principle** — add `PremiumMatchingStrategy` or `SubscriptionPricing` by subclassing; zero changes to `UberService`
- **Observer (extension point)** — to add real-time driver location updates, make `Driver` an observable subject and have `UberService` subscribe; the matching layer never needs to poll
