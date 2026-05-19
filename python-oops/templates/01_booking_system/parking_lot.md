# 01 — Parking Lot

## What is this problem testing?

This problem tests your ability to model a real-world physical system with multiple entity types, size constraints, and pluggable business logic. Interviewers are watching for how you separate the "what fits where" rules from the "how much does it cost" rules, and whether you use the Strategy pattern to keep pricing swappable. It also tests whether you reach for enums to express domain states instead of raw strings or integers.

---

## Requirements

- The lot has multiple floors; each floor has parking spots
- Spots come in three sizes: Small, Medium, Large
- Vehicle types: Motorcycle, Car, Truck
  - Motorcycles fit in Small, Medium, or Large spots
  - Cars fit in Medium or Large spots
  - Trucks fit in Large spots only
- On entry, a Ticket is issued linking the vehicle to its spot
- On exit, the ticket is closed, the spot is freed, and a fee is calculated
- Pricing strategy is pluggable (hourly rates, flat rate, etc.)

---

## Clarifying questions to ask in interview

1. **Is the lot pre-built or dynamic?** — Do we need to add/remove floors and spots at runtime, or is the structure fixed at startup?
2. **What happens when the lot is full?** — Return an error, put the vehicle in a queue, or redirect to another lot?
3. **Do spots have reserved status?** — Can a spot be reserved in advance (e.g., monthly pass holders)?
4. **Is pricing per vehicle type, per spot size, or both?** — Clarifies how complex the pricing model needs to be.
5. **Do we need concurrent access safety?** — Is this a single-threaded simulation or a real multi-threaded system where two cars could race for the same spot?

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Parking lot | `ParkingLot` |
| Floor | `ParkingFloor` |
| Spot | `ParkingSpot` |
| Vehicle (motorcycle, car, truck) | `Vehicle`, `Motorcycle`, `Car`, `Truck` |
| Ticket | `Ticket` |
| Pricing rule | `PricingStrategy` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Park a vehicle | `park(vehicle)` | `ParkingSpot`, `ParkingLot` |
| Free a spot | `vacate()` | `ParkingSpot` |
| Find an available spot | `find_spot(vehicle)` | `ParkingFloor` |
| Issue a ticket | `park(vehicle) -> Ticket` | `ParkingLot` |
| Close a ticket and charge | `exit(ticket_id) -> float` | `ParkingLot` |
| Calculate fee | `calculate(ticket) -> float` | `PricingStrategy` |
| Check if spot fits a vehicle | `can_fit(vehicle) -> bool` | `ParkingSpot` |
| Show available spots | `display_availability()` | `ParkingLot` |

---

## Relationships

```
ParkingLot  ─── HAS-MANY ───► ParkingFloor
ParkingFloor ── HAS-MANY ───► ParkingSpot
ParkingSpot ─── HAS-ONE ────► Vehicle   (when occupied, else None)

Ticket ─────────HAS-ONE ────► Vehicle
Ticket ─────────HAS-ONE ────► ParkingSpot

PricingStrategy <<interface>>
    └── HourlyPricing
    └── FlatRatePricing

ParkingLot ─────HAS-ONE ────► PricingStrategy  (injected)
```

> Think of it like a shopping mall. The mall is `ParkingLot`. Each level (B1, B2, G) is a `ParkingFloor`. Each painted rectangle is a `ParkingSpot`. When you enter, the barrier gives you a slip of paper — that is your `Ticket`. The pricing board at the exit is the `PricingStrategy`.

---

## Design decisions

### 1. `_FITS` dict in `ParkingSpot` — single source of truth for size compatibility

**Decision:** Store which vehicle types fit in each spot size as a class-level dictionary inside `ParkingSpot`.

**Why:** Without this, you would scatter `if vehicle_type == MOTORCYCLE and spot_size == SMALL` conditions across `ParkingFloor.find_spot()`, `ParkingSpot.park()`, and possibly the `ParkingLot` facade. The dict keeps all compatibility rules in one place — change it once, it propagates everywhere.

**Alternative considered:** Giving each vehicle a `fits_in(spot_size)` method. Rejected because then the vehicle knows about spot sizes, which is a mixing of concerns.

### 2. Strategy pattern for pricing

**Decision:** `PricingStrategy` is an abstract class injected into `ParkingLot`.

**Why:** Different lots (airport, mall, hospital) may have completely different pricing models. The `ParkingLot` should not need to change when pricing rules change — this is the Open/Closed principle.

**Alternative considered:** Hardcoding rates inside `ParkingLot.exit()`. Rejected — this violates OCP and makes testing harder.

### 3. `ParkingLot` as a Facade

**Decision:** External code only calls `lot.park()` and `lot.exit()`. It never touches `ParkingFloor` or `ParkingSpot` directly.

**Why:** Hides complexity. If you later add a pre-booking feature or change how floors are searched, callers are unaffected.

### 4. `Ticket` owns duration logic

**Decision:** `ticket.duration_hours` is a property on `Ticket`, not computed in `PricingStrategy`.

**Why:** Duration is a fact about the parking event. Pricing is a policy applied to that fact. Separating them keeps each class focused.

---

## Complete Code

```python
from abc import ABC, abstractmethod
from enum import Enum, auto
from datetime import datetime
from typing import Optional, List, Dict
import math


# ── Enums ──────────────────────────────────────────────────────────────────────
# Enums prevent magic strings like "car" or "large" from being scattered
# throughout the codebase. They make invalid states unrepresentable.

class VehicleType(Enum):
    MOTORCYCLE = auto()   # auto() assigns integer values automatically
    CAR = auto()
    TRUCK = auto()

class SpotSize(Enum):
    SMALL = auto()
    MEDIUM = auto()
    LARGE = auto()


# ── Vehicle hierarchy ──────────────────────────────────────────────────────────
# Vehicle is abstract — you can never park a "Vehicle", only a specific kind.
# Each subclass passes its type to the parent constructor.

class Vehicle(ABC):
    def __init__(self, license_plate: str, vehicle_type: VehicleType):
        self.license_plate = license_plate
        self.vehicle_type = vehicle_type     # stored so ParkingSpot can check compatibility

    def __repr__(self) -> str:
        # __repr__ gives us useful debug output like Car('KA-01-1234')
        return f"{self.__class__.__name__}({self.license_plate!r})"

class Motorcycle(Vehicle):
    def __init__(self, plate: str):
        super().__init__(plate, VehicleType.MOTORCYCLE)   # always call super().__init__

class Car(Vehicle):
    def __init__(self, plate: str):
        super().__init__(plate, VehicleType.CAR)

class Truck(Vehicle):
    def __init__(self, plate: str):
        super().__init__(plate, VehicleType.TRUCK)


# ── ParkingSpot ────────────────────────────────────────────────────────────────
# A ParkingSpot knows: its own ID, its size, and whether it is occupied.
# The compatibility rules (_FITS) live here as a class variable — shared across
# all instances, defined once.

class ParkingSpot:
    # Class variable: which vehicle types are allowed in each spot size.
    # This is the single source of truth for all compatibility checks.
    _FITS: Dict[SpotSize, set] = {
        SpotSize.SMALL:  {VehicleType.MOTORCYCLE},
        SpotSize.MEDIUM: {VehicleType.MOTORCYCLE, VehicleType.CAR},
        SpotSize.LARGE:  {VehicleType.MOTORCYCLE, VehicleType.CAR, VehicleType.TRUCK},
    }

    def __init__(self, spot_id: str, size: SpotSize):
        self.spot_id = spot_id
        self.size = size
        self._vehicle: Optional[Vehicle] = None   # None means the spot is free

    @property
    def is_available(self) -> bool:
        # A property feels like a field to callers (spot.is_available)
        # but is computed dynamically — no need to keep a separate boolean in sync
        return self._vehicle is None

    def can_fit(self, vehicle: Vehicle) -> bool:
        # Look up compatibility using the class-level dict
        return vehicle.vehicle_type in self._FITS[self.size]

    def park(self, vehicle: Vehicle) -> None:
        # Validate before mutating state — fail fast with a clear message
        if not self.is_available:
            raise ValueError(f"Spot {self.spot_id} already occupied")
        if not self.can_fit(vehicle):
            raise ValueError(f"{vehicle} doesn't fit in {self.size.name} spot")
        self._vehicle = vehicle

    def vacate(self) -> Vehicle:
        if self.is_available:
            raise ValueError(f"Spot {self.spot_id} is empty")
        # Swap-and-return pattern: store the vehicle, clear the slot, return the vehicle
        vehicle, self._vehicle = self._vehicle, None
        return vehicle

    def __repr__(self) -> str:
        status = "free" if self.is_available else f"occupied by {self._vehicle}"
        return f"Spot({self.spot_id}, {self.size.name}, {status})"


# ── Ticket ─────────────────────────────────────────────────────────────────────
# A Ticket is the receipt for a single parking event.
# It records entry time and knows how to compute elapsed duration.

class Ticket:
    def __init__(self, ticket_id: str, vehicle: Vehicle, spot: ParkingSpot):
        self.ticket_id = ticket_id
        self.vehicle = vehicle
        self.spot = spot
        self.entry_time: datetime = datetime.now()   # captured at creation
        self.exit_time: Optional[datetime] = None    # set when the car leaves

    def close(self) -> None:
        # Called by ParkingLot.exit() — stamps the exit time
        self.exit_time = datetime.now()

    @property
    def duration_hours(self) -> float:
        # If the ticket is still open (car hasn't left), use "now" as the end time
        end = self.exit_time or datetime.now()
        return (end - self.entry_time).total_seconds() / 3600

    def __repr__(self) -> str:
        return f"Ticket({self.ticket_id!r}, {self.vehicle})"


# ── Pricing strategies (Strategy pattern) ─────────────────────────────────────
# PricingStrategy is the abstract interface.
# Concrete strategies are swapped in at ParkingLot construction time.
# Adding a new strategy requires ZERO changes to ParkingLot — Open/Closed principle.

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, ticket: Ticket) -> float: ...

class HourlyPricing(PricingStrategy):
    # Rate per hour, per vehicle type (₹)
    _RATES = {
        VehicleType.MOTORCYCLE: 20,
        VehicleType.CAR:        40,
        VehicleType.TRUCK:      80,
    }

    def calculate(self, ticket: Ticket) -> float:
        # Minimum 1 hour; round up partial hours (math.ceil)
        hours = max(1, math.ceil(ticket.duration_hours))
        return hours * self._RATES[ticket.vehicle.vehicle_type]

class FlatRatePricing(PricingStrategy):
    # Same fee regardless of vehicle type or duration
    def __init__(self, rate: float):
        self._rate = rate

    def calculate(self, ticket: Ticket) -> float:
        return self._rate


# ── ParkingFloor ───────────────────────────────────────────────────────────────
# A floor manages a list of spots and knows how to find a suitable one.
# It does NOT know about tickets or pricing — that's the lot's job.

class ParkingFloor:
    def __init__(self, floor_number: int, spots: List[ParkingSpot]):
        self.floor_number = floor_number
        self._spots = spots

    def find_spot(self, vehicle: Vehicle) -> Optional[ParkingSpot]:
        # next(..., None) is idiomatic Python: return the first match or None
        return next(
            (s for s in self._spots if s.is_available and s.can_fit(vehicle)),
            None,
        )

    def availability(self) -> Dict[SpotSize, int]:
        # Count free spots grouped by size — useful for display boards
        counts: Dict[SpotSize, int] = {s: 0 for s in SpotSize}
        for spot in self._spots:
            if spot.is_available:
                counts[spot.size] += 1
        return counts


# ── ParkingLot (facade) ────────────────────────────────────────────────────────
# ParkingLot is the single entry point for all operations.
# It orchestrates: finding a spot → issuing a ticket → collecting fees.
# External code never needs to touch ParkingFloor or ParkingSpot directly.

class ParkingLot:
    def __init__(self, name: str, floors: List[ParkingFloor], pricing: PricingStrategy):
        self.name = name
        self._floors = floors
        self._pricing = pricing                      # injected — swappable
        self._active_tickets: Dict[str, Ticket] = {}  # ticket_id → Ticket
        self._counter = 0                             # used to generate unique ticket IDs

    def _new_ticket_id(self) -> str:
        self._counter += 1
        return f"TKT-{self._counter:05d}"   # e.g. TKT-00001

    def park(self, vehicle: Vehicle) -> Ticket:
        # Walk floors in order; park on the first floor that has a matching spot
        for floor in self._floors:
            spot = floor.find_spot(vehicle)
            if spot:
                spot.park(vehicle)                              # occupy the spot
                ticket = Ticket(self._new_ticket_id(), vehicle, spot)
                self._active_tickets[ticket.ticket_id] = ticket  # remember it
                print(f"[ENTRY] {vehicle} → {spot.spot_id}  |  Ticket: {ticket.ticket_id}")
                return ticket
        raise RuntimeError("Parking lot is full")   # no floor had a free spot

    def exit(self, ticket_id: str) -> float:
        # pop() removes and returns the ticket — it is no longer "active"
        ticket = self._active_tickets.pop(ticket_id, None)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id!r} not found")
        ticket.close()             # stamp exit time
        ticket.spot.vacate()       # free the physical spot
        fee = self._pricing.calculate(ticket)   # compute fee via strategy
        print(f"[EXIT]  {ticket.vehicle}  |  Duration: {ticket.duration_hours:.2f}h  |  Fee: ₹{fee}")
        return fee

    def display_availability(self) -> None:
        print(f"\n── {self.name} availability ──")
        for floor in self._floors:
            print(f"  Floor {floor.floor_number}: {floor.availability()}")


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Build the lot: 1 floor with 4 spots of mixed sizes
    spots_f1 = [
        ParkingSpot("F1-S1", SpotSize.SMALL),
        ParkingSpot("F1-M1", SpotSize.MEDIUM),
        ParkingSpot("F1-M2", SpotSize.MEDIUM),
        ParkingSpot("F1-L1", SpotSize.LARGE),
    ]
    lot = ParkingLot("Central Park", [ParkingFloor(1, spots_f1)], HourlyPricing())

    t1 = lot.park(Car("KA-01-1234"))
    t2 = lot.park(Motorcycle("KA-02-9999"))
    lot.display_availability()
    lot.exit(t1.ticket_id)
```

---

## Step-by-step walkthrough

```python
# 1. Build four spots on floor 1
spots_f1 = [
    ParkingSpot("F1-S1", SpotSize.SMALL),   # only motorcycles
    ParkingSpot("F1-M1", SpotSize.MEDIUM),  # motorcycles + cars
    ParkingSpot("F1-M2", SpotSize.MEDIUM),
    ParkingSpot("F1-L1", SpotSize.LARGE),   # all vehicle types
]
```
Four `ParkingSpot` objects are created. Each knows its ID and size. All `_vehicle` fields start as `None` (available).

```python
lot = ParkingLot("Central Park", [ParkingFloor(1, spots_f1)], HourlyPricing())
```
One `ParkingLot` is built. It holds a list containing one floor. `HourlyPricing()` is injected — the lot delegates all fee logic to it.

```python
t1 = lot.park(Car("KA-01-1234"))
```
- A `Car` object is created with plate `"KA-01-1234"` and `vehicle_type = VehicleType.CAR`.
- `lot.park()` iterates floor 1's spots.
- `F1-S1` is checked: `can_fit(car)` returns `False` (Small only holds motorcycles). Skipped.
- `F1-M1` is checked: `can_fit(car)` returns `True` (Medium holds motorcycles and cars). `is_available` is `True`. Selected.
- `spot.park(car)` sets `spot._vehicle = car`.
- A `Ticket` is created with ID `"TKT-00001"`, a reference to the car and the spot, and `entry_time = now()`.
- The ticket is stored in `_active_tickets` and returned.

**What just happened?** The car has a ticket and its spot is now marked occupied. The lot remembers the ticket in its active dictionary so it can look it up on exit.

```python
t2 = lot.park(Motorcycle("KA-02-9999"))
```
Same process. The motorcycle checks `F1-S1` first — Small fits motorcycles, so it parks there. Ticket `"TKT-00002"` is issued.

```python
lot.display_availability()
```
Calls `floor.availability()` which counts free spots. Output shows `SMALL: 0, MEDIUM: 1, LARGE: 1` (F1-M1 is taken, F1-M2 and F1-L1 are free).

```python
lot.exit(t1.ticket_id)
```
- Looks up `"TKT-00001"` in `_active_tickets` and removes it.
- Calls `ticket.close()` — stamps `exit_time`.
- Calls `ticket.spot.vacate()` — clears `spot._vehicle = None`, freeing the spot.
- Calls `HourlyPricing.calculate(ticket)`: rounds up duration to 1 hour, returns `1 * 40 = ₹40`.
- Prints the fee and returns `40.0`.

---

## Common interview mistakes

1. **Merging `Vehicle` and spot compatibility** — Writing `if isinstance(vehicle, Truck)` directly inside `ParkingFloor.find_spot()`. This scatters business logic and makes adding a new vehicle type require changes in multiple places. Put compatibility rules in `ParkingSpot._FITS`.

2. **Not using the Strategy pattern for pricing** — Hardcoding `if vehicle_type == CAR: fee = hours * 40` inside `ParkingLot.exit()`. This violates OCP. Pricing should be injected.

3. **Skipping `Ticket` as an object** — Just storing `entry_time` in a dict keyed by license plate. This breaks when the same vehicle parks twice (two active sessions), and the duration logic leaks into `ParkingLot`.

4. **Making `ParkingLot` access `floor._spots` directly** — Bypasses encapsulation. `ParkingFloor.find_spot()` should be the only way to query spot availability from outside the floor.

5. **Not raising on a full lot** — Returning `None` silently when the lot is full is easy to miss. Raise a `RuntimeError` so the caller is forced to handle it.

---

## Key patterns used

- **Strategy** — `PricingStrategy` allows fee calculation to be swapped without changing `ParkingLot`
- **Facade** — `ParkingLot` is the single public interface; floors and spots are internal
- **Abstract Factory / Hierarchy** — `Vehicle` is abstract; `Car`, `Motorcycle`, `Truck` are concrete types
- **Enumeration** — `VehicleType`, `SpotSize` prevent magic strings and invalid states
- **Single Responsibility** — `ParkingSpot` handles occupancy, `Ticket` handles duration, `PricingStrategy` handles fees
- **Open/Closed Principle** — add new pricing by subclassing `PricingStrategy`, no changes to existing code


---

[← Back to Booking System Template](template.md)
