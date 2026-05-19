# 04 — BookMyShow (Movie Ticket Booking)

## What is this problem testing?

This problem tests your ability to model a system with a subtle but critical distinction: a physical seat in a theatre never changes (row A, seat 3 will always be row A, seat 3), but the *availability* of that seat changes for every show. Interviewers want to see whether you create a `ShowSeat` wrapper to hold per-show state, and whether you understand the **atomic blocking** pattern — seats must be temporarily locked before payment begins to prevent two users from booking the same seat simultaneously. It also tests your ability to model a multi-step booking lifecycle (PENDING → CONFIRMED / CANCELLED).

---

## Requirements

- Theatres have Screens; Screens run Shows for a Movie
- Each Show has Seats with types: Regular, Premium, VIP (with different prices)
- Users select 1 or more seats for a show; seats are **blocked** (locked) before payment
- After successful payment, the booking is **confirmed** and seats are marked `BOOKED`
- If payment fails or times out, the booking is **cancelled** and seats are released back to `AVAILABLE`
- Prevent double-booking: two users cannot book the same seat for the same show

---

## Clarifying questions to ask in interview

1. **How long can seats stay in BLOCKED state?** — In production you need a timeout (e.g., 10 minutes); seats auto-release if payment is not completed. For this problem, confirm if timeout handling is in scope.
2. **Can a user partially book?** — If a user selects 3 seats and seat 2 is taken, do we fail the whole request or proceed with the remaining 2?
3. **Is concurrency (thread safety) required?** — This determines whether `block_seats()` needs a database-level lock or an in-memory mutex.
4. **Can confirmed bookings be cancelled?** — Adds a refund flow and returns seats to `AVAILABLE`.
5. **Do seat prices vary by show time or day?** — Weekend pricing, prime-time surcharge, etc.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Theatre | `Theatre` |
| Screen | `Screen` |
| Movie | `Movie` |
| Show | `Show` |
| Physical seat | `Seat` |
| Show-specific seat state | `ShowSeat` |
| Booking | `Booking` |
| Booking service | `BookingService` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Block a seat | `block()` | `ShowSeat` |
| Confirm a seat | `confirm()` | `ShowSeat` |
| Release a seat | `release()` | `ShowSeat` |
| Block multiple seats atomically | `block_seats(seat_ids)` | `Show` |
| Confirm all seats in booking | `confirm_seats(seat_ids)` | `Show` |
| Release all seats in booking | `release_seats(seat_ids)` | `Show` |
| Start a booking (PENDING) | `initiate(user, show, seats)` | `BookingService` |
| Confirm after payment | `confirm(booking_id)` | `BookingService` |
| Cancel a booking | `cancel(booking_id)` | `BookingService` |
| Get available seats | `available_seats()` | `Show` |

---

## Relationships

```
Theatre ──────── HAS-MANY ────► Screen
Screen ───────── HAS-MANY ────► Seat       (physical, permanent)

Show ─────────── HAS-ONE  ────► Movie
Show ─────────── HAS-ONE  ────► Screen
Show ─────────── HAS-MANY ────► ShowSeat   (one per physical seat, per show)

ShowSeat ──────── WRAPS ───────► Seat
ShowSeat ─────── HAS-ONE  ────► SeatStatus (AVAILABLE / BLOCKED / BOOKED)

Booking ─────────HAS-ONE  ────► Show
Booking ─────────HAS-ONE  ────► user_id
Booking ─────────HAS-MANY ────► ShowSeat

BookingService ── HAS-MANY ────► Booking   (active bookings dict)
```

> Think of it like a concert venue. The `Seat` is the plastic chair — it does not move. Its row and number are printed on it forever. But for *tonight's show*, that chair might be `AVAILABLE`, `BLOCKED` (someone is at the payment screen right now), or `BOOKED` (confirmed purchase). That show-specific state is `ShowSeat`. If another band plays tomorrow night, all `ShowSeat` objects for that show start fresh at `AVAILABLE` — even though the chairs are the same.

---

## Design decisions

### 1. `Seat` vs `ShowSeat` — the critical split

**Decision:** `Seat` is an immutable data object (row, number, type). `ShowSeat` wraps a `Seat` and adds show-specific mutable state (status, price).

**Why:** Without this split, you would either need to reset seat status between shows (dangerous — what if you forget?) or duplicate the entire seat list for every show (wasteful). `ShowSeat` instances are created fresh when a `Show` is created, so each show starts with all seats available.

**Alternative considered:** Storing `{show_id: {seat_id: status}}` in a nested dict on `Seat`. Rejected — this mixes two separate concerns into one object and makes querying awkward.

### 2. `block_seats()` is atomic — all or nothing

**Decision:** `Show.block_seats()` iterates all requested seats and blocks each one. If *any* seat raises (already taken), the whole call fails.

**Why:** This is the core double-booking prevention mechanism. Without atomicity, two users could both check availability, both see seat A1 as free, and both successfully book it. In production you would use a database transaction; here the in-memory raise achieves the same effect within a single thread.

**Important nuance:** The current implementation has a subtle issue — if seat 1 and 2 are blocked successfully but seat 3 is already taken, seats 1 and 2 remain blocked. A production system would use a try/finally to roll back already-blocked seats. This is a great discussion point in the interview.

### 3. Booking status lifecycle (State Machine)

**Decision:** `Booking.status` transitions through `PENDING → CONFIRMED` or `PENDING → CANCELLED`. `BookingService` enforces these transitions.

**Why:** Without explicit state, you might allow confirming an already-cancelled booking or cancelling a confirmed one without a refund flow. Explicit states make illegal transitions obvious and easy to guard.

### 4. `BookingService` as the Facade

**Decision:** All booking operations go through `BookingService`. The caller never calls `show.block_seats()` or `booking.confirm()` directly.

**Why:** The service owns the booking ID generation and the booking registry. It is the right place to add cross-cutting concerns later (notifications, payment gateway calls, audit logs) without changing `Booking` or `Show`.

---

## Complete Code

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional
import uuid


# ── Enums ──────────────────────────────────────────────────────────────────────

class SeatType(Enum):
    REGULAR = auto()
    PREMIUM = auto()
    VIP     = auto()

class SeatStatus(Enum):
    AVAILABLE = auto()
    BLOCKED   = auto()   # temporarily held — payment in progress
    BOOKED    = auto()   # payment confirmed — seat is sold

class BookingStatus(Enum):
    PENDING   = auto()   # seats blocked, awaiting payment
    CONFIRMED = auto()   # payment received — seats are BOOKED
    CANCELLED = auto()   # payment failed or user cancelled — seats released


# ── Core domain objects (mostly immutable data) ────────────────────────────────
# Using @dataclass for objects that are primarily data containers.
# These do not change after creation — Movie, Seat, Screen, Theatre are stable facts.

@dataclass
class Movie:
    movie_id: str
    title: str
    duration_mins: int
    language: str = "English"

    def __repr__(self) -> str:
        return f"Movie({self.title!r})"


@dataclass
class Seat:
    """
    Physical seat in a screen. Permanent — row and number never change.
    This is NOT where availability lives. That belongs to ShowSeat.
    """
    seat_id: str
    row: str
    number: int
    seat_type: SeatType

    def __repr__(self) -> str:
        return f"{self.row}{self.number}({self.seat_type.name})"


@dataclass
class Screen:
    screen_id: str
    name: str
    seats: List[Seat] = field(default_factory=list)   # all physical seats in this screen


@dataclass
class Theatre:
    theatre_id: str
    name: str
    city: str
    screens: List[Screen] = field(default_factory=list)


# ── ShowSeat — per-show mutable seat state ─────────────────────────────────────
# This is the most important design decision in this problem.
# One ShowSeat is created per (show, physical seat) pair.
# Status transitions:
#   AVAILABLE → BLOCKED  (user starts checkout)
#   BLOCKED   → BOOKED   (payment confirmed)
#   BLOCKED   → AVAILABLE (payment failed / timeout / cancelled)

class ShowSeat:
    # Price per seat type — shared across all instances (class variable)
    PRICES: Dict[SeatType, float] = {
        SeatType.REGULAR: 150,
        SeatType.PREMIUM: 250,
        SeatType.VIP:     500,
    }

    def __init__(self, seat: Seat):
        self.seat = seat
        self.status = SeatStatus.AVAILABLE             # every show starts fresh
        self.price: float = self.PRICES[seat.seat_type]

    def block(self) -> None:
        """Reserve the seat temporarily while the user pays."""
        if self.status != SeatStatus.AVAILABLE:
            # This is the double-booking guard — only one user can block a seat
            raise ValueError(f"Seat {self.seat} is not available (status={self.status.name})")
        self.status = SeatStatus.BLOCKED

    def confirm(self) -> None:
        """Permanently mark the seat as sold — called after payment."""
        if self.status != SeatStatus.BLOCKED:
            raise ValueError(f"Seat {self.seat} must be BLOCKED before confirming")
        self.status = SeatStatus.BOOKED

    def release(self) -> None:
        """Return the seat to AVAILABLE — called on cancellation or timeout."""
        self.status = SeatStatus.AVAILABLE   # reset regardless of current status

    def __repr__(self) -> str:
        return f"ShowSeat({self.seat}, {self.status.name})"


# ── Show ───────────────────────────────────────────────────────────────────────
# A Show represents one screening of a Movie in a Screen at a specific time.
# It creates a fresh set of ShowSeats at construction — each seat starts AVAILABLE.

class Show:
    def __init__(self, show_id: str, movie: Movie, screen: Screen, start_time: datetime):
        self.show_id = show_id
        self.movie = movie
        self.screen = screen
        self.start_time = start_time
        # Create one ShowSeat for each physical seat in the screen
        # Dict keyed by seat_id for O(1) lookup by ID
        self._show_seats: Dict[str, ShowSeat] = {
            s.seat_id: ShowSeat(s) for s in screen.seats
        }

    def available_seats(self) -> List[ShowSeat]:
        """Return all ShowSeats that can still be booked."""
        return [ss for ss in self._show_seats.values() if ss.status == SeatStatus.AVAILABLE]

    def get_show_seat(self, seat_id: str) -> ShowSeat:
        ss = self._show_seats.get(seat_id)
        if not ss:
            raise ValueError(f"Seat {seat_id!r} not in this show")
        return ss

    def block_seats(self, seat_ids: List[str]) -> List[ShowSeat]:
        """
        Atomically block all requested seats.
        If any seat is unavailable, a ValueError is raised and blocking stops.
        NOTE: seats blocked before the failure remain blocked in this implementation.
        In production, wrap in a transaction or use try/finally to roll back.
        """
        show_seats = [self.get_show_seat(sid) for sid in seat_ids]
        for ss in show_seats:
            ss.block()   # raises ValueError if seat is already taken
        return show_seats

    def confirm_seats(self, seat_ids: List[str]) -> None:
        for sid in seat_ids:
            self.get_show_seat(sid).confirm()

    def release_seats(self, seat_ids: List[str]) -> None:
        for sid in seat_ids:
            self.get_show_seat(sid).release()

    def __repr__(self) -> str:
        return f"Show({self.movie.title!r}, {self.start_time.strftime('%H:%M')})"


# ── Booking ────────────────────────────────────────────────────────────────────
# A Booking ties a user, a show, and a set of ShowSeats together.
# It tracks the lifecycle (PENDING → CONFIRMED / CANCELLED) and the total cost.

class Booking:
    def __init__(self, booking_id: str, user_id: str, show: Show, show_seats: List[ShowSeat]):
        self.booking_id = booking_id
        self.user_id = user_id
        self.show = show
        self.show_seats = show_seats
        self.status = BookingStatus.PENDING
        # Sum prices at booking time — price could change in the future
        self.total_amount: float = sum(ss.price for ss in show_seats)
        self.created_at = datetime.now()

    def confirm(self) -> None:
        """Called after payment succeeds. Moves all ShowSeats to BOOKED."""
        self.show.confirm_seats([ss.seat.seat_id for ss in self.show_seats])
        self.status = BookingStatus.CONFIRMED
        print(f"[CONFIRMED] {self.booking_id}  seats={[ss.seat for ss in self.show_seats]}  ₹{self.total_amount}")

    def cancel(self) -> None:
        """Called on failure or user request. Returns seats to AVAILABLE."""
        self.show.release_seats([ss.seat.seat_id for ss in self.show_seats])
        self.status = BookingStatus.CANCELLED
        print(f"[CANCELLED] {self.booking_id}")

    def __repr__(self) -> str:
        return f"Booking({self.booking_id!r}, {self.status.name}, ₹{self.total_amount})"


# ── BookingService (facade) ────────────────────────────────────────────────────
# BookingService is the single entry point for all booking operations.
# It generates booking IDs, maintains the booking registry, and enforces
# the state machine transitions (PENDING → CONFIRMED/CANCELLED).

class BookingService:
    def __init__(self):
        self._bookings: Dict[str, Booking] = {}

    def initiate(self, user_id: str, show: Show, seat_ids: List[str]) -> Booking:
        """
        Step 1 of booking: block the seats and create a PENDING booking.
        This must succeed before the user is sent to the payment page.
        Raises ValueError if any requested seat is not available.
        """
        # block_seats is the atomic guard — raises if any seat is already taken
        show_seats = show.block_seats(seat_ids)
        booking_id = uuid.uuid4().hex[:8].upper()   # short, readable ID
        booking = Booking(booking_id, user_id, show, show_seats)
        self._bookings[booking_id] = booking
        print(f"[PENDING]  {booking_id}  {show}  seats={seat_ids}")
        return booking

    def confirm(self, booking_id: str) -> Booking:
        """
        Step 2 of booking: payment succeeded, confirm the seats.
        Only PENDING bookings can be confirmed.
        """
        booking = self._get(booking_id)
        if booking.status != BookingStatus.PENDING:
            raise ValueError("Only PENDING bookings can be confirmed")
        booking.confirm()
        return booking

    def cancel(self, booking_id: str) -> None:
        """
        Cancel a PENDING booking — releases all seats back to AVAILABLE.
        Confirmed bookings require a separate refund flow (not in scope here).
        """
        booking = self._get(booking_id)
        if booking.status == BookingStatus.CONFIRMED:
            raise ValueError("Confirmed bookings cannot be cancelled here (use refund flow)")
        booking.cancel()

    def _get(self, booking_id: str) -> Booking:
        b = self._bookings.get(booking_id)
        if not b:
            raise ValueError(f"Booking {booking_id!r} not found")
        return b


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── Set up the venue ────────────────────────────────────────────────────────
    seats = [
        Seat("S1", "A", 1, SeatType.REGULAR),
        Seat("S2", "A", 2, SeatType.REGULAR),
        Seat("S3", "B", 1, SeatType.PREMIUM),
        Seat("S4", "C", 1, SeatType.VIP),
    ]
    screen = Screen("SC1", "Screen 1", seats)
    theatre = Theatre("TH1", "PVR Cinemas", "Bangalore", [screen])
    movie = Movie("M1", "Inception", 148)

    # ── Create a show ───────────────────────────────────────────────────────────
    show = Show("SH1", movie, screen, datetime(2024, 6, 15, 18, 30))
    service = BookingService()

    # ── Alice books S1 (Regular) and S3 (Premium) ───────────────────────────────
    booking = service.initiate("user_alice", show, ["S1", "S3"])
    service.confirm(booking.booking_id)

    # ── Bob tries to book S1 — already BOOKED — should raise ───────────────────
    try:
        service.initiate("user_bob", show, ["S1"])
    except ValueError as e:
        print(f"[ERROR] {e}")

    # ── Show remaining available seats ──────────────────────────────────────────
    print(f"\nAvailable seats: {show.available_seats()}")
```

---

## Step-by-step walkthrough

```python
seats = [
    Seat("S1", "A", 1, SeatType.REGULAR),
    ...
]
screen = Screen("SC1", "Screen 1", seats)
```
Four `Seat` objects are created — permanent, immutable physical seats. `Screen` holds the list. These objects never change status; they are facts about the theatre.

```python
show = Show("SH1", movie, screen, datetime(2024, 6, 15, 18, 30))
```
The `Show` constructor iterates `screen.seats` and creates one `ShowSeat` per seat. The internal dict is now:
```
{ "S1": ShowSeat(Seat A1 REGULAR, AVAILABLE),
  "S2": ShowSeat(Seat A2 REGULAR, AVAILABLE),
  "S3": ShowSeat(Seat B1 PREMIUM, AVAILABLE),
  "S4": ShowSeat(Seat C1 VIP,     AVAILABLE) }
```
All four start as `AVAILABLE`. If a second show were created for the same screen, it would get a completely independent set of `ShowSeat` objects.

```python
booking = service.initiate("user_alice", show, ["S1", "S3"])
```
- `show.block_seats(["S1", "S3"])` is called.
- `get_show_seat("S1")` returns the `ShowSeat` for S1.
- `ss.block()` — status is `AVAILABLE`, so it transitions to `BLOCKED`.
- `get_show_seat("S3")` → `ss.block()` — same transition.
- A `Booking` is created with status `PENDING`, `total_amount = 150 + 250 = ₹400`.
- The booking is stored in `_bookings` and returned.

**What just happened?** S1 and S3 are now `BLOCKED`. No one else can block them. Alice has not paid yet — the booking is `PENDING`.

```python
service.confirm(booking.booking_id)
```
- Booking is looked up — status is `PENDING`, so confirmation is allowed.
- `booking.confirm()` is called:
  - `show.confirm_seats(["S1", "S3"])` transitions S1 and S3 from `BLOCKED` to `BOOKED`.
  - `booking.status` becomes `CONFIRMED`.
- Output: `[CONFIRMED] ABCD1234  seats=[A1(REGULAR), B1(PREMIUM)]  ₹400`

**What just happened?** S1 and S3 are permanently sold. The booking is fully completed.

```python
service.initiate("user_bob", show, ["S1"])
```
- `show.block_seats(["S1"])` is called.
- `get_show_seat("S1")` returns S1's `ShowSeat` which is `BOOKED`.
- `ss.block()` checks `if self.status != SeatStatus.AVAILABLE` — it is `BOOKED`, not `AVAILABLE`.
- Raises `ValueError: "Seat A1(REGULAR) is not available (status=BOOKED)"`.
- The `except` block catches it and prints `[ERROR] Seat A1(REGULAR) is not available (status=BOOKED)`.

**What just happened?** Bob's attempt was blocked atomically. No partial state was created.

```python
print(f"\nAvailable seats: {show.available_seats()}")
```
Returns S2 (REGULAR) and S4 (VIP) — the two seats Alice did not book.

---

## Common interview mistakes

1. **Storing seat status on `Seat` instead of `ShowSeat`** — This is the most critical mistake. If `Seat` has a `status` field, you cannot run two shows in the same screen because booking for Monday's show would affect Tuesday's show.

2. **Not using atomic blocking** — Checking availability and blocking in separate steps:
   ```python
   # WRONG: race condition between these two lines
   if seat.is_available():
       seat.book()
   ```
   The `block()` method must do both: check and transition in one step. Any thread interleaving between check and transition is a bug.

3. **Missing the PENDING state** — Going directly from AVAILABLE to BOOKED without a BLOCKED intermediate. Without PENDING, you have no way to hold a seat while the payment gateway (which can take 5–30 seconds) processes the transaction.

4. **Calculating total on confirmation instead of initiation** — If price changes between initiation and confirmation, the user could be charged a different amount than shown. Capture price at `initiate()` time.

5. **Letting callers directly manipulate `ShowSeat.status`** — Writing `show_seat.status = SeatStatus.BOOKED` outside of `ShowSeat.confirm()`. This bypasses the guard that ensures the status transitions are always valid.

---

## Key patterns used

- **State Machine** — `ShowSeat` transitions `AVAILABLE → BLOCKED → BOOKED` with explicit guards on each transition
- **Facade** — `BookingService` is the single API; callers never touch `Show.block_seats()` or `ShowSeat.block()` directly
- **Atomic Operation** — `block_seats()` is the concurrency lock that prevents double-booking
- **Separation of Immutable vs Mutable** — `Seat` is permanent data; `ShowSeat` is ephemeral show-specific state
- **Dataclass for Value Objects** — `Movie`, `Seat`, `Screen`, `Theatre` are pure data with no behavior; `@dataclass` reduces boilerplate
- **Single Responsibility** — `ShowSeat` manages seat state, `Booking` manages booking lifecycle, `BookingService` manages orchestration
- **Enumeration** — `SeatType`, `SeatStatus`, `BookingStatus` make all states explicit and exhaustive


---

[← Back to Booking System Template](template.md)
