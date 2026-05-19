# 03 — Flight Booking System

## What is this problem testing?

This problem tests your ability to model a **seat map** (specific named seats in a 2D grid, not just a count), **group bookings** (one booking for multiple passengers), a **waitlist** (FIFO queue auto-processed when a seat is freed), and **refund policies** that depend on how far in advance the cancellation happens. Interviewers also watch whether you separate `Aircraft` (the physical plane) from `Flight` (a specific journey on a specific date) — a distinction that trips up most beginners.

---

## Requirements

- Flights can be searched by origin, destination, and date
- Each flight operates on a specific aircraft; the aircraft has a seat map
- Seats belong to fare classes: Economy, Business, or First Class
- A booking links one or more passengers to a flight and to specific seats
- Passengers have passport numbers and meal preferences
- If a fare class is full, passengers can join a waitlist; they are auto-assigned when a seat becomes available
- On cancellation, refund amount depends on fare class and time before departure
- Each booking receives a unique PNR (Passenger Name Record) number

---

## Clarifying questions to ask in an interview

1. **Can a single passenger hold more than one seat?** — Clarifies whether one booking is always one seat per passenger or could be one booking for multiple seats per passenger.
2. **Is seat selection mandatory?** — Can a passenger book a flight without choosing a seat (auto-assigned) or must they pick one?
3. **What happens if a waitlisted passenger cannot be reached when a seat opens up?** — Do we skip them and go to the next person, or hold the seat for a fixed time?
4. **Are fare class inventories independent?** — If Economy is full, can the airline sell an Economy ticket into a Business seat at a higher price?
5. **Do we need to handle connecting flights (multi-leg itineraries)?** — Determines whether `Booking` holds one flight or a list of flights.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Flight | `Flight` |
| Aircraft | `Aircraft` |
| Seat | `Seat` |
| Fare class (Economy/Business/First) | `SeatClass` enum |
| Passenger | `Passenger` dataclass |
| Booking | `Booking` |
| PNR | generated string inside `Booking` |
| Waitlist | `deque` inside `Flight` |
| Refund policy | `RefundPolicy` (abstract) |
| Flight service (entry point) | `FlightService` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Search flights | `search_flights(origin, destination, date)` | `FlightService` |
| Check available seats | `available_seats(seat_class)` | `Flight` / `Aircraft` |
| Book a flight | `book_flight(flight, passengers, seat_class) -> Booking` | `FlightService` |
| Select specific seats | `select_seats(booking, seat_ids)` | `FlightService` |
| Cancel a booking | `cancel_booking(pnr) -> float` | `FlightService` |
| Process waitlist | `_process_waitlist(flight)` | `FlightService` (private) |
| Block a seat | `block()` | `Seat` |
| Confirm a seat | `confirm()` | `Seat` |
| Release a seat | `release()` | `Seat` |
| Calculate refund | `calculate_refund(booking, now) -> float` | `RefundPolicy` |

---

## Relationships

```
FlightService (facade — single entry point for all operations)
 │
 ├── Flight ──HAS-ONE──► Aircraft
 │          ──HAS-ONE──► origin, destination, departure_time, arrival_time
 │          └── _waitlist: deque of pending BookingRequest objects
 │
 ├── Aircraft ──HAS-MANY──► Seat
 │                              └── HAS-ONE── SeatClass (ECONOMY / BUSINESS / FIRST)
 │                              └── SeatStatus: AVAILABLE → BLOCKED → BOOKED
 │
 ├── Booking ──HAS-ONE────► Flight
 │           ──HAS-MANY───► Passenger
 │           ──HAS-MANY───► Seat
 │           └── BookingStatus: CONFIRMED → CANCELLED
 │
 └── RefundPolicy <<abstract interface>>
         ├── FullRefundPolicy    (>72h before departure → 100%)
         ├── PartialRefundPolicy (24h–72h before departure → 50%)
         └── NoRefundPolicy      (<24h before departure → 0%)
```

> Think of it like a physical airport check-in counter. `FlightService` is the counter agent. The `Flight` board shows departures; each flight is an `Aircraft` full of labelled seats. When you book, the agent prints a piece of paper with a code at the top — that is your PNR (your `Booking`). If the cabin is full, the agent puts your name on a clipboard hanging on the wall — that is the `_waitlist`.

---

## Design decisions

### 1. `Aircraft` is separate from `Flight`

**Decision:** `Aircraft` holds the seat map. `Flight` holds the journey details and references an `Aircraft`.

**Why:** The same physical plane (`Aircraft("B737-001")`) can fly multiple routes on different days. If you merged them, you would need to rebuild the seat map for every flight that plane operates — and you could not share seat configuration between flights. Separating them also reflects reality: the seat count is a property of the plane, not of where it is flying today.

**Alternative considered:** One `Flight` class that directly owns a list of seats. Rejected — no reuse, and changes to seat layout require editing `Flight`.

### 2. Seat has a three-state lifecycle: AVAILABLE → BLOCKED → BOOKED

**Decision:** Mirrors the template's ResourceItem pattern. `block()` is called when a booking is being created; `confirm()` finalises it; `release()` frees it on cancellation.

**Why:** Without BLOCKED, two passengers could both see the same seat as available simultaneously and both confirm it — a classic race condition. BLOCKED acts as a short-lived lock while the booking is being assembled.

### 3. Waitlist is a `deque` inside `Flight`

**Decision:** Each `Flight` owns a `deque` of pending `WaitlistEntry` objects (passenger + seat class requested). When a seat is released, `FlightService._process_waitlist()` pops from the front and auto-books.

**Why:** A FIFO queue is the fairest and most intuitive waitlist behaviour. Storing it on `Flight` keeps the queue scoped to that specific flight; `FlightService` only processes it, not owns it.

### 4. Strategy pattern for refund policy

**Decision:** `RefundPolicy` is an abstract class; three concrete policies implement different time-window rules. The policy is injected into `FlightService`.

**Why:** Airlines have wildly different refund rules by fare class and route. Injecting the policy means you can apply different policies per route or fare class without changing `FlightService`.

### 5. PNR generation

**Decision:** A random 6-character alphanumeric string, checked for uniqueness against existing bookings before being assigned.

**Why:** PNRs must be short enough to read aloud at a check-in counter but unique enough not to collide. Six alphanumeric characters gives 36^6 ≈ 2.1 billion possible values — sufficient for our simulation.

---

## Complete Code

Read each section's comment before reading the code beneath it.

```python
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Deque, Dict, List, Optional
import random
import string


# ── Enums ──────────────────────────────────────────────────────────────────────

class SeatClass(Enum):
    ECONOMY  = auto()
    BUSINESS = auto()
    FIRST    = auto()

class SeatStatus(Enum):
    AVAILABLE = auto()   # free to be selected
    BLOCKED   = auto()   # held during checkout — prevents double-booking
    BOOKED    = auto()   # confirmed and paid for

class BookingStatus(Enum):
    CONFIRMED = auto()
    CANCELLED = auto()

class MealPreference(Enum):
    VEG     = auto()
    NON_VEG = auto()
    VEGAN   = auto()


# ── Fare prices ────────────────────────────────────────────────────────────────
# Single source of truth for seat pricing. Change this dict to update prices
# everywhere — no need to touch Seat, Aircraft, or Flight.

SEAT_PRICES: Dict[SeatClass, float] = {
    SeatClass.ECONOMY:  5_000.0,    # ₹5,000 per seat
    SeatClass.BUSINESS: 15_000.0,
    SeatClass.FIRST:    35_000.0,
}


# ── Passenger ──────────────────────────────────────────────────────────────────
# Passenger is a pure data record — no behaviour needed.

@dataclass
class Passenger:
    name:             str
    passport_number:  str
    meal_preference:  MealPreference = MealPreference.VEG


# ── Seat ───────────────────────────────────────────────────────────────────────
# Seat is a single bookable unit. Its ID (e.g. "12A") encodes row and column.
# It manages its own status transitions and raises clearly on illegal moves.

class Seat:
    def __init__(self, seat_id: str, row: int, column: str, seat_class: SeatClass):
        self.seat_id    = seat_id     # e.g. "12A"
        self.row        = row         # 12
        self.column     = column      # "A"
        self.seat_class = seat_class
        self.status     = SeatStatus.AVAILABLE

    @property
    def price(self) -> float:
        return SEAT_PRICES[self.seat_class]

    def block(self) -> None:
        """Hold this seat while the booking is being assembled."""
        if self.status != SeatStatus.AVAILABLE:
            raise ValueError(
                f"Seat {self.seat_id} cannot be blocked: "
                f"current status is {self.status.name}"
            )
        self.status = SeatStatus.BLOCKED

    def confirm(self) -> None:
        """Finalise the booking — seat is now permanently reserved."""
        if self.status != SeatStatus.BLOCKED:
            raise ValueError(
                f"Seat {self.seat_id} must be BLOCKED before confirming, "
                f"not {self.status.name}"
            )
        self.status = SeatStatus.BOOKED

    def release(self) -> None:
        """Return seat to available pool (on cancel or hold timeout)."""
        self.status = SeatStatus.AVAILABLE

    def is_available(self) -> bool:
        return self.status == SeatStatus.AVAILABLE

    def __repr__(self) -> str:
        return f"Seat({self.seat_id}, {self.seat_class.name}, {self.status.name})"


# ── Aircraft ───────────────────────────────────────────────────────────────────
# Aircraft owns the seat map. It is reusable — the same aircraft can be
# assigned to many different flights.

class Aircraft:
    def __init__(self, aircraft_id: str, model: str):
        self.aircraft_id = aircraft_id
        self.model       = model
        self._seats: Dict[str, Seat] = {}   # seat_id → Seat

    def add_seat(self, seat: Seat) -> None:
        self._seats[seat.seat_id] = seat

    def get_seat(self, seat_id: str) -> Seat:
        seat = self._seats.get(seat_id)
        if not seat:
            raise KeyError(f"Seat {seat_id!r} not found on aircraft {self.aircraft_id}")
        return seat

    def get_available_seats(self, seat_class: SeatClass) -> List[Seat]:
        """Return all seats of the given class that are currently available."""
        return [
            s for s in self._seats.values()
            if s.seat_class == seat_class and s.is_available()
        ]

    @property
    def total_seats(self) -> int:
        return len(self._seats)

    def __repr__(self) -> str:
        return f"Aircraft({self.aircraft_id}, {self.model})"


# ── WaitlistEntry ──────────────────────────────────────────────────────────────
# A lightweight record of who is waiting and what they want.
# Stored in the Flight's waitlist deque.

@dataclass
class WaitlistEntry:
    passengers: List[Passenger]
    seat_class: SeatClass
    requested_at: datetime = field(default_factory=datetime.now)


# ── Flight ─────────────────────────────────────────────────────────────────────
# Flight represents a specific journey: plane + route + time.
# It also manages the waitlist for seats that are currently full.

class Flight:
    def __init__(
        self,
        flight_number:  str,
        aircraft:       Aircraft,
        origin:         str,
        destination:    str,
        departure_time: datetime,
        arrival_time:   datetime,
    ):
        self.flight_number  = flight_number
        self.aircraft       = aircraft
        self.origin         = origin
        self.destination    = destination
        self.departure_time = departure_time
        self.arrival_time   = arrival_time
        self._waitlist: Deque[WaitlistEntry] = deque()   # FIFO queue

    def available_seats(self, seat_class: SeatClass) -> List[Seat]:
        """Delegate to the aircraft's seat map."""
        return self.aircraft.get_available_seats(seat_class)

    def is_full(self, seat_class: SeatClass) -> bool:
        return len(self.available_seats(seat_class)) == 0

    def add_to_waitlist(self, entry: WaitlistEntry) -> int:
        """Add an entry to the waitlist. Returns the queue position (1-indexed)."""
        self._waitlist.append(entry)
        return len(self._waitlist)

    def next_waitlist_entry(self) -> Optional[WaitlistEntry]:
        """Return and remove the next entry from the waitlist, or None if empty."""
        return self._waitlist.popleft() if self._waitlist else None

    def __repr__(self) -> str:
        return (
            f"Flight({self.flight_number}, "
            f"{self.origin}→{self.destination}, "
            f"{self.departure_time:%Y-%m-%d %H:%M})"
        )


# ── Booking ────────────────────────────────────────────────────────────────────
# Booking is the transaction record. One booking covers multiple passengers
# and their assigned seats on a single flight.

class Booking:
    def __init__(
        self,
        pnr:        str,
        flight:     Flight,
        passengers: List[Passenger],
        seats:      List[Seat],
    ):
        self.pnr        = pnr
        self.flight     = flight
        self.passengers = passengers
        self.seats      = seats
        self.status     = BookingStatus.CONFIRMED
        self.created_at = datetime.now()

    @property
    def total_fare(self) -> float:
        """Sum of prices of all booked seats."""
        return sum(seat.price for seat in self.seats)

    def __repr__(self) -> str:
        names = ", ".join(p.name for p in self.passengers)
        seat_ids = ", ".join(s.seat_id for s in self.seats)
        return (
            f"Booking(PNR={self.pnr}, "
            f"Flight={self.flight.flight_number}, "
            f"Passengers=[{names}], "
            f"Seats=[{seat_ids}], "
            f"Fare=₹{self.total_fare:,.0f}, "
            f"{self.status.name})"
        )


# ── RefundPolicy (Strategy pattern) ───────────────────────────────────────────
# Swap the policy to change refund behaviour without touching FlightService.

class RefundPolicy(ABC):
    @abstractmethod
    def calculate_refund(self, booking: Booking, now: datetime) -> float:
        """Return the refund amount for cancelling this booking."""
        ...

class FullRefundPolicy(RefundPolicy):
    """100% refund if cancelled more than 72 hours before departure."""

    def calculate_refund(self, booking: Booking, now: datetime) -> float:
        hours_until = (booking.flight.departure_time - now).total_seconds() / 3600
        if hours_until > 72:
            return booking.total_fare
        if hours_until > 24:
            return booking.total_fare * 0.5   # 50% for 24–72h window
        return 0.0   # no refund within 24h

class PartialRefundPolicy(RefundPolicy):
    """50% refund always, regardless of timing."""

    def calculate_refund(self, booking: Booking, now: datetime) -> float:
        return booking.total_fare * 0.5

class NoRefundPolicy(RefundPolicy):
    """No refund under any circumstances (e.g. lowest budget fares)."""

    def calculate_refund(self, booking: Booking, now: datetime) -> float:
        return 0.0


# ── PNR generator ──────────────────────────────────────────────────────────────

def _generate_pnr(existing_pnrs: set) -> str:
    """
    Generate a unique 6-character alphanumeric PNR.
    Keeps generating until it finds one not already in use.
    The collision probability is negligible for simulation-scale loads.
    """
    chars = string.ascii_uppercase + string.digits
    while True:
        pnr = "".join(random.choices(chars, k=6))
        if pnr not in existing_pnrs:
            return pnr


# ── FlightService (facade) ────────────────────────────────────────────────────
# The only class external code should ever call.
# It orchestrates: search → select seats → block → confirm → or waitlist.

class FlightService:
    def __init__(self, refund_policy: RefundPolicy):
        self._refund_policy = refund_policy     # injected — swappable
        self._flights:  Dict[str, Flight]  = {}  # flight_number → Flight
        self._bookings: Dict[str, Booking] = {}  # pnr → Booking

    # ── Fleet management ────────────────────────────────────────────────────────

    def add_flight(self, flight: Flight) -> None:
        self._flights[flight.flight_number] = flight

    # ── Search ──────────────────────────────────────────────────────────────────

    def search_flights(
        self,
        origin:      str,
        destination: str,
        travel_date: str,   # "YYYY-MM-DD"
    ) -> List[Flight]:
        """Return all flights matching origin, destination, and departure date."""
        results = []
        for flight in self._flights.values():
            if (
                flight.origin.upper()      == origin.upper()
                and flight.destination.upper() == destination.upper()
                and flight.departure_time.strftime("%Y-%m-%d") == travel_date
            ):
                results.append(flight)
        return results

    # ── Book ────────────────────────────────────────────────────────────────────

    def book_flight(
        self,
        flight:     Flight,
        passengers: List[Passenger],
        seat_class: SeatClass,
    ) -> Booking:
        """
        Book seats for all passengers in the given class.
        If there are not enough seats, adds everyone to the waitlist instead.
        Returns the confirmed Booking, or raises WaitlistError.
        """
        available = flight.available_seats(seat_class)

        if len(available) < len(passengers):
            # Not enough seats — go to waitlist
            position = flight.add_to_waitlist(
                WaitlistEntry(passengers=passengers, seat_class=seat_class)
            )
            raise WaitlistError(
                f"Flight {flight.flight_number} {seat_class.name} is full. "
                f"Added to waitlist at position {position}."
            )

        # Take exactly as many seats as we need
        chosen_seats = available[: len(passengers)]

        # Block all seats atomically — release already-blocked ones if any fail
        blocked: List[Seat] = []
        try:
            for seat in chosen_seats:
                seat.block()
                blocked.append(seat)
        except ValueError:
            for s in blocked:
                s.release()
            raise

        # Confirm all seats and create the booking record
        for seat in blocked:
            seat.confirm()

        pnr     = _generate_pnr(set(self._bookings.keys()))
        booking = Booking(pnr=pnr, flight=flight, passengers=passengers, seats=blocked)
        self._bookings[pnr] = booking

        print(
            f"[BOOKED] PNR: {pnr}  "
            f"Flight: {flight.flight_number}  "
            f"Seats: {[s.seat_id for s in blocked]}  "
            f"Total: ₹{booking.total_fare:,.0f}"
        )
        return booking

    # ── Seat selection (upgrade / change) ───────────────────────────────────────

    def select_seats(self, booking: Booking, seat_ids: List[str]) -> None:
        """
        Swap the booking's current seats for the specified seat IDs.
        The new seats must be available and must match the same fare class.
        """
        if booking.status != BookingStatus.CONFIRMED:
            raise ValueError("Cannot change seats on a cancelled booking.")
        if len(seat_ids) != len(booking.passengers):
            raise ValueError(
                f"Number of seat IDs ({len(seat_ids)}) must match "
                f"number of passengers ({len(booking.passengers)})."
            )

        aircraft = booking.flight.aircraft
        new_seats = [aircraft.get_seat(sid) for sid in seat_ids]

        # Validate all new seats are available and same class
        for seat in new_seats:
            if seat.seat_class != booking.seats[0].seat_class:
                raise ValueError(
                    f"Seat {seat.seat_id} is {seat.seat_class.name}; "
                    f"booking is for {booking.seats[0].seat_class.name}."
                )
            if not seat.is_available():
                raise ValueError(f"Seat {seat.seat_id} is not available.")

        # Release old seats, block and confirm new ones
        for old_seat in booking.seats:
            old_seat.release()
        blocked: List[Seat] = []
        try:
            for seat in new_seats:
                seat.block()
                blocked.append(seat)
            for seat in blocked:
                seat.confirm()
        except ValueError:
            for s in blocked:
                s.release()
            # Re-book original seats if possible; in production, handle more carefully
            raise

        booking.seats = new_seats
        print(f"[SEATS UPDATED] PNR: {booking.pnr}  New seats: {seat_ids}")

    # ── Cancel ──────────────────────────────────────────────────────────────────

    def cancel_booking(self, pnr: str) -> float:
        """
        Cancel a booking, release its seats, calculate the refund,
        and immediately process the waitlist to fill the freed seats.
        """
        booking = self._get_booking(pnr)

        if booking.status == BookingStatus.CANCELLED:
            raise ValueError(f"Booking {pnr} is already cancelled.")

        # Release all seats back to the available pool
        for seat in booking.seats:
            seat.release()

        booking.status = BookingStatus.CANCELLED
        refund = self._refund_policy.calculate_refund(booking, datetime.now())

        print(f"[CANCELLED] PNR: {pnr}  Refund: ₹{refund:,.0f}")

        # Give freed seats to the next person on the waitlist
        self._process_waitlist(booking.flight)

        return refund

    # ── Waitlist processing ─────────────────────────────────────────────────────

    def _process_waitlist(self, flight: Flight) -> None:
        """
        Check the front of the waitlist. If enough seats are now available,
        auto-book them and remove the entry from the queue.
        Called automatically after every cancellation.
        """
        entry = flight.next_waitlist_entry()
        if not entry:
            return   # waitlist is empty — nothing to do

        available = flight.available_seats(entry.seat_class)
        if len(available) < len(entry.passengers):
            # Still not enough seats — put the entry back at the front
            flight._waitlist.appendleft(entry)
            return

        # Enough seats are now free — auto-book without going through book_flight
        # (avoids recursion; _process_waitlist is called by cancel_booking)
        chosen_seats = available[: len(entry.passengers)]
        for seat in chosen_seats:
            seat.block()
        for seat in chosen_seats:
            seat.confirm()

        pnr     = _generate_pnr(set(self._bookings.keys()))
        booking = Booking(
            pnr        = pnr,
            flight     = flight,
            passengers = entry.passengers,
            seats      = chosen_seats,
        )
        self._bookings[pnr] = booking
        print(
            f"[WAITLIST AUTO-BOOKED] PNR: {pnr}  "
            f"Seats: {[s.seat_id for s in chosen_seats]}"
        )

    # ── Private helper ──────────────────────────────────────────────────────────

    def _get_booking(self, pnr: str) -> Booking:
        booking = self._bookings.get(pnr)
        if not booking:
            raise KeyError(f"No booking found with PNR: {pnr}")
        return booking


# ── Custom exception ───────────────────────────────────────────────────────────

class WaitlistError(Exception):
    """Raised when a flight is full and the passenger is added to the waitlist."""
    pass


# ── Helper: build a simple aircraft ───────────────────────────────────────────

def build_aircraft(aircraft_id: str, economy_rows: int, business_rows: int) -> Aircraft:
    """
    Build an aircraft with labelled seats.
    Columns A–F. Economy rows first, then Business rows.
    """
    aircraft = Aircraft(aircraft_id, "Boeing 737")
    columns  = ["A", "B", "C", "D", "E", "F"]

    for row in range(1, economy_rows + 1):
        for col in columns:
            aircraft.add_seat(Seat(f"{row}{col}", row, col, SeatClass.ECONOMY))

    for row in range(economy_rows + 1, economy_rows + business_rows + 1):
        for col in columns[:4]:   # Business: 4 seats per row (A–D)
            aircraft.add_seat(Seat(f"{row}{col}", row, col, SeatClass.BUSINESS))

    return aircraft


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 1. Build an aircraft: 3 economy rows (rows 1-3), 1 business row (row 4)
    aircraft = build_aircraft("AC-001", economy_rows=3, business_rows=1)

    # 2. Create a flight
    flight = Flight(
        flight_number  = "AI-204",
        aircraft       = aircraft,
        origin         = "BLR",
        destination    = "DEL",
        departure_time = datetime(2026, 6, 15, 6, 30),
        arrival_time   = datetime(2026, 6, 15, 9, 0),
    )

    # 3. Start the service
    service = FlightService(FullRefundPolicy())
    service.add_flight(flight)

    # 4. Search for the flight
    results = service.search_flights("BLR", "DEL", "2026-06-15")
    print(f"\nFlights found: {results}")

    # 5. Book 2 economy passengers
    ravi  = Passenger("Ravi Kumar",  "P1234567", MealPreference.VEG)
    priya = Passenger("Priya Singh", "P9876543", MealPreference.NON_VEG)

    booking = service.book_flight(results[0], [ravi, priya], SeatClass.ECONOMY)
    print(f"\nBooking details: {booking}")

    # 6. Change seats
    service.select_seats(booking, ["2A", "2B"])
    print(f"\nAfter seat change: {booking}")

    # 7. Cancel and observe refund (flight is >72h away from now in our simulation)
    refund = service.cancel_booking(booking.pnr)
    print(f"\nRefund received: ₹{refund:,.0f}")
```

---

## Step-by-step walkthrough

```python
aircraft = build_aircraft("AC-001", economy_rows=3, business_rows=1)
```
`build_aircraft` creates 3 × 6 = 18 Economy seats (rows 1–3, columns A–F) and 1 × 4 = 4 Business seats (row 4, columns A–D). Each `Seat` starts with `status = SeatStatus.AVAILABLE`.

```python
flight = Flight("AI-204", aircraft, "BLR", "DEL", departure_time, arrival_time)
service.add_flight(flight)
```
A `Flight` is created pointing at the aircraft. The `_waitlist` deque inside `Flight` starts empty. `FlightService` stores the flight in its `_flights` dict keyed by `"AI-204"`.

```python
results = service.search_flights("BLR", "DEL", "2026-06-15")
```
`FlightService` loops over all flights and checks origin, destination, and date string. Finds `"AI-204"` and returns it in a list.

```python
booking = service.book_flight(results[0], [ravi, priya], SeatClass.ECONOMY)
```
- `flight.available_seats(ECONOMY)` returns all 18 Economy seats (all AVAILABLE).
- Two seats are taken from the front of that list: `"1A"` and `"1B"`.
- `seat.block()` is called on both: status moves `AVAILABLE → BLOCKED`.
- `seat.confirm()` is called on both: status moves `BLOCKED → BOOKED`.
- A PNR is generated (e.g. `"X7KP2Q"`).
- A `Booking` object is created and stored in `_bookings`.

**What just happened?** Ravi and Priya each have a confirmed seat. If a third passenger had tried to book seat `"1A"` at the same moment between `block()` and `confirm()`, they would have found it BLOCKED and been refused. That is the double-booking protection.

```python
service.select_seats(booking, ["2A", "2B"])
```
- Old seats `"1A"` and `"1B"` are released (`BOOKED → AVAILABLE`).
- New seats `"2A"` and `"2B"` are blocked then confirmed.
- `booking.seats` is updated to the new list.

```python
refund = service.cancel_booking(booking.pnr)
```
- Seats `"2A"` and `"2B"` are released back to AVAILABLE.
- `booking.status = BookingStatus.CANCELLED`.
- `FullRefundPolicy.calculate_refund()` checks hours until departure. Since the departure is far in the future (> 72h), it returns the full `₹10,000` fare.
- `_process_waitlist(flight)` is called. The waitlist is empty, so nothing else happens.

---

## Common interview mistakes

1. **Not separating `Aircraft` from `Flight`.** If you put the seat list directly on `Flight`, every flight that uses the same plane needs its own copy of the seat map. You also cannot re-use seat configuration across routes. Separate them: Aircraft holds the map, Flight holds the route.

2. **No atomicity when blocking multiple seats.** If you block seat 1 and seat 2 one by one, and seat 2 is already taken, seat 1 stays BLOCKED forever. Always wrap multi-seat blocking in a try/except that releases already-blocked seats before re-raising the error.

3. **Forgetting the waitlist when a booking is cancelled.** The freed seats sit idle while the next person on the waitlist is still waiting. Always call `_process_waitlist()` immediately after releasing seats.

4. **Hardcoding the refund formula inside `Booking.cancel()`.** Fare classes, routes, and promotions all have different refund rules. Keep the formula in a `RefundPolicy` object that is injected into the service.

5. **PNR collision.** Generating a PNR with `random.choices` without checking uniqueness can produce duplicates (birthday problem). Always check against existing PNRs and regenerate if there is a collision.

---

## Key patterns used

- **Strategy** — `RefundPolicy` and its subclasses allow refund rules to be swapped without changing `FlightService`
- **Facade** — `FlightService` is the single public interface; `Aircraft`, `Seat`, and `Flight` internals are hidden
- **State** — `SeatStatus` and `BookingStatus` enums enforce valid transitions; `block()` and `confirm()` guard against illegal moves
- **Factory** — `_generate_pnr()` encapsulates unique-ID creation; `build_aircraft()` encapsulates seat-map construction
- **Single Responsibility** — `Aircraft` holds the seat map, `Flight` holds the journey + waitlist, `Booking` is the transaction record
- **Open/Closed Principle** — add new refund policies by subclassing `RefundPolicy`; no existing class changes


---

[← Back to Booking System Template](template.md)
