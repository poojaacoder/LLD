# 02 — Hotel Management System

## What is this problem testing?

This problem tests your ability to handle **date-range availability** (not just "is it free right now?" but "is it free for these specific dates?"), multi-type resources with different pricing, and a lifecycle that spans multiple state transitions: reserved → occupied → available. Interviewers also watch whether you model cancellation policy as a pluggable strategy rather than a hardcoded `if/else` block.

---

## Requirements

- The hotel has rooms of three types: Single, Double, Suite — each with its own nightly rate
- Each room type can include amenities: WiFi, Breakfast, Pool access, Parking
- Guests can search available rooms by type, date range, and price range
- Booking a room creates a Reservation with a check-in date and a check-out date
- On check-in the room is marked OCCUPIED; on check-out it returns to AVAILABLE and a Bill is generated
- Cancellation policy: full refund if cancelled more than 24 hours before check-in; 50% refund otherwise
- A room cannot be double-booked: the system must verify no overlapping reservation exists for the requested dates

---

## Clarifying questions to ask in an interview

1. **Can the same room be booked by two different guests on consecutive nights with no gap?** — Clarifies whether check-out date is exclusive (guest leaves by noon, next guest arrives same evening).
2. **What happens to a reservation if the guest never checks in?** — Do we auto-cancel, charge a no-show fee, or keep it open indefinitely?
3. **Is early checkout supported?** — Can a guest leave before their check-out date, and if so, do we recalculate the bill for actual nights stayed?
4. **Can a guest book multiple rooms in a single reservation?** — Determines whether `Reservation` holds one room or a list of rooms.
5. **Do amenities add per-night charges or is it a flat add-on?** — Affects how `Bill` is calculated.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Hotel | `Hotel` |
| Room | `Room` |
| Room type (Single/Double/Suite) | `RoomType` enum |
| Amenity (WiFi, Breakfast, etc.) | `Amenity` enum |
| Guest | `Guest` dataclass |
| Reservation | `Reservation` |
| Bill | `Bill` dataclass |
| Cancellation policy | `CancellationPolicy` (abstract) |
| Hotel service (entry point) | `HotelService` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Search available rooms | `search_available_rooms(check_in, check_out, room_type)` | `HotelService` |
| Check if a room is free for dates | `is_available_for(check_in, check_out, reservations)` | `Room` |
| Book a room | `book_room(guest, room, check_in, check_out) -> Reservation` | `HotelService` |
| Check in | `check_in(reservation_id)` | `HotelService` / `Reservation` |
| Check out | `check_out(reservation_id) -> Bill` | `HotelService` / `Reservation` |
| Cancel a reservation | `cancel_reservation(reservation_id) -> float` | `HotelService` |
| Calculate refund | `calculate_refund(reservation) -> float` | `CancellationPolicy` |
| Generate bill | `check_out() -> Bill` | `Reservation` |

---

## Relationships

```
HotelService (facade — single entry point for all operations)
 │
 ├── Hotel ──HAS-MANY──► Room
 │                          └── HAS-ONE── RoomType  (SINGLE / DOUBLE / SUITE)
 │                          └── HAS-MANY─ Amenity
 │                          └── RoomStatus: AVAILABLE → RESERVED → OCCUPIED → CLEANING → AVAILABLE
 │
 ├── Reservation ──HAS-ONE──► Room
 │               ──HAS-ONE──► Guest
 │               └── ReservationStatus: CONFIRMED → CHECKED_IN → CHECKED_OUT / CANCELLED
 │
 ├── Bill ──HAS-ONE──► Reservation  (room charges + amenity charges)
 │
 └── CancellationPolicy <<abstract interface>>
         ├── FreeCancellationPolicy   (>24h before check-in → 100% refund)
         └── PartialRefundPolicy      (≤24h before check-in → 50% refund)
```

> Think of it like a real hotel front desk. The front desk (`HotelService`) is the only window you interact with. Behind it are the physical rooms (`Room`), a booking ledger (`Reservation`), a billing printer (`Bill`), and a laminated cancellation policy card (`CancellationPolicy`) that can be swapped out by management whenever they like.

---

## Design decisions

### 1. Date-range overlap check lives on `Room`

**Decision:** `Room.is_available_for(check_in, check_out, existing_reservations)` receives the list of reservations for that room and checks whether any of them overlap with the requested dates.

**Why:** The room is the resource — it is the most natural place to ask "can I use you during these dates?" Without this method, the availability check logic would bleed into `HotelService`, making it harder to test in isolation.

**How to detect overlap:** Two date ranges [A, B) and [C, D) overlap when `A < D and C < B`. If this condition is false, the ranges are adjacent or non-overlapping. This single boolean expression is the core of the entire availability check.

**Alternative considered:** Querying all reservations from a central store in `HotelService`. Rejected — it mixes search policy with resource state, making `HotelService` too large.

### 2. Two separate status enums — `RoomStatus` and `ReservationStatus`

**Decision:** `RoomStatus` tracks the physical state of the room (is it physically ready to receive a guest?). `ReservationStatus` tracks the lifecycle of the booking transaction (has the guest shown up, paid, left?).

**Why:** They move independently. A room can be CLEANING even after a reservation is CHECKED_OUT. A reservation can be CANCELLED while the room is still AVAILABLE. Conflating them into one status would require an explosion of combined states like `ROOM_AVAILABLE_RESERVATION_CANCELLED`.

### 3. Strategy pattern for cancellation policy

**Decision:** `CancellationPolicy` is an abstract class injected into `HotelService`.

**Why:** Hotels change cancellation terms for different room types, seasons, or promotions. If the refund formula is hardcoded, every policy change requires editing `HotelService` directly. With injection, you write a new policy class and swap it in.

### 4. `Bill` is generated by `Reservation.check_out()`, not by `Room`

**Decision:** The bill calculation — `nightly_rate × nights + amenity charges` — lives in `Reservation`, not in `Room`.

**Why:** `Room` knows its rate. `Reservation` knows how many nights were actually stayed and which amenities apply. The bill is a fact about the booking event, not about the physical room.

---

## Complete Code

The code below builds the full system from enums up to the facade. Read each section's comment before reading the code beneath it.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional
import uuid


# ── Enums ──────────────────────────────────────────────────────────────────────
# Enums make invalid states unrepresentable. You can never accidentally write
# room.type = "dubble" if the type must be a RoomType enum member.

class RoomType(Enum):
    SINGLE = auto()
    DOUBLE = auto()
    SUITE  = auto()

class RoomStatus(Enum):
    AVAILABLE = auto()   # ready to be booked
    RESERVED  = auto()   # booking confirmed, guest not yet arrived
    OCCUPIED  = auto()   # guest is currently in the room
    CLEANING  = auto()   # between guests; not bookable yet

class ReservationStatus(Enum):
    CONFIRMED   = auto()   # booking exists, guest hasn't arrived
    CHECKED_IN  = auto()   # guest has arrived
    CHECKED_OUT = auto()   # guest has left, bill produced
    CANCELLED   = auto()   # reservation was cancelled

class Amenity(Enum):
    WIFI      = auto()
    BREAKFAST = auto()
    POOL      = auto()
    PARKING   = auto()


# ── Nightly rates and amenity surcharges ───────────────────────────────────────
# Keeping rates in one place means a pricing change is a one-line edit,
# not a search-and-replace across the codebase.

NIGHTLY_RATES: Dict[RoomType, float] = {
    RoomType.SINGLE: 3_000.0,   # ₹3,000/night
    RoomType.DOUBLE: 5_000.0,
    RoomType.SUITE:  12_000.0,
}

AMENITY_RATES: Dict[Amenity, float] = {
    Amenity.WIFI:      200.0,    # per night
    Amenity.BREAKFAST: 500.0,
    Amenity.POOL:      300.0,
    Amenity.PARKING:   400.0,
}


# ── Guest ──────────────────────────────────────────────────────────────────────
# A dataclass is perfect here: Guest is just a named collection of fields
# with no behaviour of its own.

@dataclass
class Guest:
    guest_id:  str
    name:      str
    email:     str
    phone:     str


# ── Room ───────────────────────────────────────────────────────────────────────
# Room is the bookable resource. It knows its own physical properties and
# can answer whether it is available for a requested date range.

class Room:
    def __init__(
        self,
        room_number: str,
        room_type:   RoomType,
        floor:       int,
        amenities:   Optional[List[Amenity]] = None,
    ):
        self.room_number = room_number
        self.room_type   = room_type
        self.floor       = floor
        self.amenities   = amenities or []
        self.status      = RoomStatus.AVAILABLE

    @property
    def nightly_rate(self) -> float:
        # Delegates to the rates table — Room doesn't hardcode its own price.
        return NIGHTLY_RATES[self.room_type]

    def is_available_for(
        self,
        check_in:  date,
        check_out: date,
        existing_reservations: List["Reservation"],
    ) -> bool:
        """
        Return True only if no existing reservation for this room overlaps
        with the requested [check_in, check_out) window.

        Overlap condition:  A < D  and  C < B
          where [A, B) is the new request and [C, D) is an existing booking.
        If this is False, the ranges don't overlap (one ends before the other starts).
        """
        if self.status not in (RoomStatus.AVAILABLE, RoomStatus.RESERVED):
            # A room being cleaned or occupied right now cannot accept new bookings
            # unless we allow future reservations — here we keep it simple.
            return False

        for res in existing_reservations:
            if res.room.room_number != self.room_number:
                continue   # not our room — skip
            if res.status in (ReservationStatus.CANCELLED, ReservationStatus.CHECKED_OUT):
                continue   # cancelled/completed reservations don't block dates
            # The two ranges overlap if neither one ends before the other starts
            if check_in < res.check_out_date and res.check_in_date < check_out:
                return False   # overlap found — room is not available
        return True

    def __repr__(self) -> str:
        return f"Room({self.room_number}, {self.room_type.name}, {self.status.name})"


# ── Bill ───────────────────────────────────────────────────────────────────────
# Bill is a pure data record. It is produced at check-out time and never mutated.

@dataclass
class Bill:
    reservation:        "Reservation"
    room_charges:       float   # nightly_rate × nights
    amenity_charges:    float   # sum of per-night amenity costs × nights
    total:              float   # room_charges + amenity_charges

    def __str__(self) -> str:
        res = self.reservation
        return (
            f"\n{'='*45}\n"
            f"  BILL — Reservation {res.reservation_id[:8]}\n"
            f"  Guest:         {res.guest.name}\n"
            f"  Room:          {res.room.room_number} ({res.room.room_type.name})\n"
            f"  Dates:         {res.check_in_date} → {res.check_out_date}\n"
            f"  Nights:        {res.nights}\n"
            f"  Room charges:  ₹{self.room_charges:,.0f}\n"
            f"  Amenities:     ₹{self.amenity_charges:,.0f}\n"
            f"  ─────────────────────────────────────────\n"
            f"  TOTAL:         ₹{self.total:,.0f}\n"
            f"{'='*45}"
        )


# ── Reservation ────────────────────────────────────────────────────────────────
# Reservation is the transaction record. It links a guest to a room for a date
# range and manages its own state transitions (check-in, check-out).

class Reservation:
    def __init__(
        self,
        guest:          Guest,
        room:           Room,
        check_in_date:  date,
        check_out_date: date,
    ):
        self.reservation_id  = str(uuid.uuid4())
        self.guest           = guest
        self.room            = room
        self.check_in_date   = check_in_date
        self.check_out_date  = check_out_date
        self.status          = ReservationStatus.CONFIRMED
        self.created_at      = datetime.now()

    @property
    def nights(self) -> int:
        # check_out is the day the guest leaves — they don't pay for that night
        return (self.check_out_date - self.check_in_date).days

    @property
    def total_amount(self) -> float:
        # Room cost + per-night amenity surcharges
        amenity_total = sum(AMENITY_RATES[a] for a in self.room.amenities)
        return (self.room.nightly_rate + amenity_total) * self.nights

    def check_in(self) -> None:
        """Guest has arrived. Move both the reservation and the room forward."""
        if self.status != ReservationStatus.CONFIRMED:
            raise ValueError(
                f"Cannot check in: reservation status is {self.status.name}"
            )
        self.status      = ReservationStatus.CHECKED_IN
        self.room.status = RoomStatus.OCCUPIED   # physical room is now occupied

    def check_out(self) -> Bill:
        """
        Guest is leaving. Move statuses forward and produce the Bill.
        The room goes to CLEANING — a real system would have housekeeping mark it
        AVAILABLE once cleaned; here we go straight to AVAILABLE for simplicity.
        """
        if self.status != ReservationStatus.CHECKED_IN:
            raise ValueError(
                f"Cannot check out: reservation status is {self.status.name}"
            )
        self.status      = ReservationStatus.CHECKED_OUT
        self.room.status = RoomStatus.AVAILABLE   # simplified: skip CLEANING

        room_charges    = self.room.nightly_rate * self.nights
        amenity_charges = sum(AMENITY_RATES[a] for a in self.room.amenities) * self.nights
        return Bill(
            reservation     = self,
            room_charges    = room_charges,
            amenity_charges = amenity_charges,
            total           = room_charges + amenity_charges,
        )

    def __repr__(self) -> str:
        return (
            f"Reservation({self.reservation_id[:8]}, "
            f"{self.guest.name}, {self.room.room_number}, "
            f"{self.check_in_date}→{self.check_out_date}, "
            f"{self.status.name})"
        )


# ── CancellationPolicy (Strategy pattern) ─────────────────────────────────────
# Swapping the policy object changes refund behaviour with zero edits to
# HotelService. This is the Strategy pattern in practice.

class CancellationPolicy(ABC):
    @abstractmethod
    def calculate_refund(self, reservation: Reservation) -> float:
        """Return the refund amount for cancelling this reservation."""
        ...

class FreeCancellationPolicy(CancellationPolicy):
    """100% refund if cancelled more than 24 hours before check-in."""

    def calculate_refund(self, reservation: Reservation) -> float:
        hours_until_checkin = (
            datetime.combine(reservation.check_in_date, datetime.min.time())
            - datetime.now()
        ).total_seconds() / 3600

        if hours_until_checkin > 24:
            return reservation.total_amount   # full refund
        # Fall back to 50% if within 24 hours
        return reservation.total_amount * 0.5

class PartialRefundPolicy(CancellationPolicy):
    """Always 50% refund regardless of timing."""

    def calculate_refund(self, reservation: Reservation) -> float:
        return reservation.total_amount * 0.5


# ── Hotel ──────────────────────────────────────────────────────────────────────
# Hotel is a simple container for Room objects. It is separate from HotelService
# so the service can potentially manage multiple hotels in the future.

class Hotel:
    def __init__(self, name: str, address: str):
        self.name    = name
        self.address = address
        self._rooms: Dict[str, Room] = {}   # room_number → Room

    def add_room(self, room: Room) -> None:
        self._rooms[room.room_number] = room

    @property
    def rooms(self) -> List[Room]:
        return list(self._rooms.values())

    def get_room(self, room_number: str) -> Room:
        room = self._rooms.get(room_number)
        if not room:
            raise KeyError(f"Room {room_number!r} not found in {self.name}")
        return room


# ── HotelService (facade) ─────────────────────────────────────────────────────
# The only class external code should ever call.
# It owns: search → book → check-in → check-out → cancel.
# All the state choreography (updating Room status, generating Bills) happens
# here so callers never have to remember the right order of operations.

class HotelService:
    def __init__(self, hotel: Hotel, cancellation_policy: CancellationPolicy):
        self._hotel               = hotel
        self._cancellation_policy = cancellation_policy   # injected — swappable
        self._reservations: Dict[str, Reservation] = {}   # reservation_id → Reservation

    # ── Search ──────────────────────────────────────────────────────────────────

    def search_available_rooms(
        self,
        check_in:   date,
        check_out:  date,
        room_type:  Optional[RoomType] = None,
        max_price:  Optional[float]    = None,
    ) -> List[Room]:
        """
        Return every room that is free for the entire [check_in, check_out) window.
        Optionally filter by room type and nightly price ceiling.
        """
        all_reservations = list(self._reservations.values())
        results = []

        for room in self._hotel.rooms:
            if room_type and room.room_type != room_type:
                continue
            if max_price and room.nightly_rate > max_price:
                continue
            if room.is_available_for(check_in, check_out, all_reservations):
                results.append(room)

        return results

    # ── Book ────────────────────────────────────────────────────────────────────

    def book_room(
        self,
        guest:          Guest,
        room:           Room,
        check_in_date:  date,
        check_out_date: date,
    ) -> Reservation:
        """
        Create a confirmed Reservation for the guest.
        Validates availability one final time to guard against races.
        """
        if check_out_date <= check_in_date:
            raise ValueError("Check-out must be after check-in.")

        all_reservations = list(self._reservations.values())
        if not room.is_available_for(check_in_date, check_out_date, all_reservations):
            raise ValueError(
                f"Room {room.room_number} is not available for "
                f"{check_in_date} → {check_out_date}"
            )

        reservation = Reservation(guest, room, check_in_date, check_out_date)
        room.status  = RoomStatus.RESERVED   # physical room is now reserved
        self._reservations[reservation.reservation_id] = reservation

        print(
            f"[BOOKED] {guest.name} → Room {room.room_number} "
            f"({check_in_date} → {check_out_date})  "
            f"Reservation: {reservation.reservation_id[:8]}  "
            f"Total: ₹{reservation.total_amount:,.0f}"
        )
        return reservation

    # ── Check-in ────────────────────────────────────────────────────────────────

    def check_in(self, reservation_id: str) -> None:
        """Guest has arrived at the hotel."""
        reservation = self._get_reservation(reservation_id)
        reservation.check_in()   # Reservation handles its own state transition
        print(
            f"[CHECK-IN]  {reservation.guest.name} → "
            f"Room {reservation.room.room_number}"
        )

    # ── Check-out ───────────────────────────────────────────────────────────────

    def check_out(self, reservation_id: str) -> Bill:
        """Guest is leaving. Returns the final Bill."""
        reservation = self._get_reservation(reservation_id)
        bill = reservation.check_out()   # Reservation generates the Bill
        print(f"[CHECK-OUT] {reservation.guest.name}")
        print(bill)
        return bill

    # ── Cancel ──────────────────────────────────────────────────────────────────

    def cancel_reservation(self, reservation_id: str) -> float:
        """
        Cancel the reservation and return the refund amount.
        The cancellation policy decides how much to refund.
        """
        reservation = self._get_reservation(reservation_id)

        if reservation.status in (
            ReservationStatus.CHECKED_OUT,
            ReservationStatus.CANCELLED,
        ):
            raise ValueError(
                f"Reservation {reservation_id[:8]} cannot be cancelled "
                f"(status: {reservation.status.name})"
            )

        refund = self._cancellation_policy.calculate_refund(reservation)
        reservation.status      = ReservationStatus.CANCELLED
        reservation.room.status = RoomStatus.AVAILABLE   # free the room

        print(
            f"[CANCELLED] Reservation {reservation_id[:8]}  "
            f"Refund: ₹{refund:,.0f}"
        )
        return refund

    # ── Private helper ──────────────────────────────────────────────────────────

    def _get_reservation(self, reservation_id: str) -> Reservation:
        reservation = self._reservations.get(reservation_id)
        if not reservation:
            raise KeyError(f"No reservation found with id: {reservation_id}")
        return reservation


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 1. Build the hotel with a few rooms
    hotel = Hotel("The Grand Bengaluru", "MG Road, Bengaluru")
    hotel.add_room(Room("101", RoomType.SINGLE, floor=1, amenities=[Amenity.WIFI]))
    hotel.add_room(Room("201", RoomType.DOUBLE, floor=2, amenities=[Amenity.WIFI, Amenity.BREAKFAST]))
    hotel.add_room(Room("301", RoomType.SUITE,  floor=3, amenities=[Amenity.WIFI, Amenity.BREAKFAST, Amenity.POOL]))

    # 2. Start the service with the free-cancellation policy
    service = HotelService(hotel, FreeCancellationPolicy())

    # 3. Alice searches for a Double room for 3 nights
    check_in  = date(2026, 6, 10)
    check_out = date(2026, 6, 13)   # 3 nights

    available = service.search_available_rooms(check_in, check_out, room_type=RoomType.DOUBLE)
    print(f"\nAvailable Double rooms: {[r.room_number for r in available]}")

    # 4. Alice books room 201
    alice = Guest("G001", "Alice Sharma", "alice@example.com", "+91-9876543210")
    reservation = service.book_room(alice, available[0], check_in, check_out)

    # 5. The same dates are now blocked — Bob can't book room 201
    blocked = service.search_available_rooms(check_in, check_out, room_type=RoomType.DOUBLE)
    print(f"\nDouble rooms still available after Alice's booking: {[r.room_number for r in blocked]}")

    # 6. Alice checks in
    service.check_in(reservation.reservation_id)

    # 7. Alice checks out — bill is generated
    bill = service.check_out(reservation.reservation_id)
```

---

## Step-by-step walkthrough

```python
hotel = Hotel("The Grand Bengaluru", "MG Road, Bengaluru")
hotel.add_room(Room("201", RoomType.DOUBLE, floor=2, amenities=[Amenity.WIFI, Amenity.BREAKFAST]))
```
A `Hotel` is created and a Double room is added. Room `"201"` starts with `status = RoomStatus.AVAILABLE`. Its `nightly_rate` property will return `₹5,000` by looking up `NIGHTLY_RATES[RoomType.DOUBLE]`.

```python
available = service.search_available_rooms(date(2026, 6, 10), date(2026, 6, 13), room_type=RoomType.DOUBLE)
```
`HotelService.search_available_rooms()` loops over every room. For room `"201"`, it calls `room.is_available_for(June 10, June 13, [])`. The reservations list is empty, so no overlap is possible — returns `True`. Room `"201"` is included in results.

```python
reservation = service.book_room(alice, available[0], check_in, check_out)
```
- `is_available_for` is checked one final time (guards against races between search and book).
- A `Reservation` object is created linking Alice, room `"201"`, and the two dates.
- Room status changes: `AVAILABLE → RESERVED`.
- The reservation is stored in `HotelService._reservations`.
- `reservation.total_amount` = `(5_000 + 200 + 500) × 3 nights = ₹16,500`.

**What just happened?** Alice's reservation is the only thing preventing Bob from getting the same room. The next `search_available_rooms` call for the same dates will reach `is_available_for`, find Alice's reservation in the list, detect overlap (`June 10 < June 13` and `June 10 < June 13`), and return `False`.

```python
service.check_in(reservation.reservation_id)
```
`HotelService` calls `reservation.check_in()`. The reservation status moves `CONFIRMED → CHECKED_IN`. The room status moves `RESERVED → OCCUPIED`.

```python
bill = service.check_out(reservation.reservation_id)
```
`HotelService` calls `reservation.check_out()`. The reservation status moves `CHECKED_IN → CHECKED_OUT`. The room returns to `AVAILABLE`. A `Bill` object is created:
- `room_charges = 5_000 × 3 = ₹15,000`
- `amenity_charges = (200 + 500) × 3 = ₹2,100`
- `total = ₹17,100`

---

## Common interview mistakes

1. **Checking only `RoomStatus` for availability, not existing reservations.** A room has `status = AVAILABLE` between bookings, but it may already have a confirmed future reservation. The overlap check against `existing_reservations` is what catches this. Without it you allow double-bookings.

2. **Conflating `RoomStatus` with `ReservationStatus`.** Adding a fifth value like `RESERVATION_CONFIRMED` to `RoomStatus` means the room and its booking history are entangled. One room can have many historical reservations. Separate the physical state from the transaction state.

3. **Hardcoding the cancellation formula in `HotelService.cancel_reservation()`.** Hotels change policies constantly. A hardcoded `if hours > 24: refund = full` block inside the service must be edited every time policy changes. Inject a `CancellationPolicy` object instead.

4. **Putting bill calculation logic on `Room` instead of `Reservation`.** `Room` doesn't know how many nights were booked — that's `Reservation`'s data. The Bill needs both the rate (from `Room`) and the duration (from `Reservation`). `Reservation.check_out()` has access to both.

5. **Not validating availability again at booking time.** Searching and booking are two separate operations. Another guest could book the room between the moment you call `search_available_rooms` and the moment you call `book_room`. Always re-check inside `book_room` before creating the `Reservation`.

---

## Key patterns used

- **Strategy** — `CancellationPolicy` and its subclasses allow refund rules to be swapped without touching `HotelService`
- **Facade** — `HotelService` is the single public interface; `Hotel`, `Room`, and `Reservation` internals are hidden
- **State** — `RoomStatus` and `ReservationStatus` enums enforce valid transitions; invalid transitions raise errors immediately
- **Single Responsibility** — `Room` handles physical availability, `Reservation` handles the booking lifecycle, `Bill` is a pure data record
- **Open/Closed Principle** — add new cancellation policies by subclassing `CancellationPolicy`; no existing class changes
