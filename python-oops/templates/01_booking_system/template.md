# Booking System — LLD Template

---

## 1. What is the Booking System template?

A booking system is any problem where users reserve a limited resource for a period of time. The core challenge is managing scarcity: only one person can hold a seat, room, or parking spot at a time. Every booking system, no matter how different the domain, shares the same fundamental mechanics — check if something is free, hold it, then confirm or release it.

---

## 2. How to recognise this template in an interview

Look for these words or ideas in the problem statement:

- **"reserve" / "book" / "allocate"** — a user is claiming something
- **"available" / "occupied" / "free"** — there is a limited supply
- **"cancel" / "release" / "refund"** — resources go back into the pool
- **"hold" / "lock" / "block"** — temporary reservation before payment
- **"ticket" / "slot" / "seat" / "spot" / "room"** — the unit being reserved
- **"capacity" / "limit"** — there are only N of something
- **"time window" / "duration" / "check-in / check-out"** — the reservation has a start and end
- **"double-booking" / "overlap"** — the interviewer is hinting at a concurrency problem

If you see two or more of these signals together, reach for this template.

---

## 3. Real-world examples

| Domain | Resource being booked |
|---|---|
| Parking Lot | Parking spot |
| Library Management | Book copy |
| Hotel | Room |
| Movie Ticket Booking | Cinema seat |
| Flight Booking | Airline seat |
| Doctor Appointments | Time slot |
| Restaurant Reservation | Table |
| Sports Court Booking | Court / lane |

---

## 4. The core skeleton (always present)

Every booking system is built from five building blocks. Understand these and you can adapt to any domain.

---

### Resource

The physical or logical thing being booked. A parking spot, a hotel room, a seat in a cinema. There is always a **type** (ParkingSpot, Room, Seat) and individual **instances** of that type.

> **Analogy:** Think of "Room" as the blueprint and "Room 204" as the actual thing someone sleeps in. You book a specific instance, not the blueprint.

---

### Availability Check

Before doing anything, the system checks whether a specific resource instance is free for the requested time window.

> **Analogy:** Asking the hotel receptionist "Is room 204 free from Friday to Sunday?" — no commitment yet, just a question.

---

### Hold / Block

A temporary lock placed on a resource after a user selects it but before they finish paying. This prevents another user from grabbing the same resource mid-checkout.

> **Analogy:** Adding an item to your online shopping cart. It doesn't mean you own it yet, but it's held for you for a few minutes while you decide.

---

### Confirm / Cancel

**Confirm** finalises the booking — the resource is now permanently assigned. **Cancel** releases the resource back into the available pool, whether before or after confirmation.

> **Analogy:** Clicking "Place Order" is Confirm. Clicking "Remove from cart" is Cancel. Both end the hold, but in opposite directions.

---

### Pricing Strategy

The rule for calculating how much the booking costs. This rule often changes: per-hour vs. flat-rate, weekday vs. weekend, member discount vs. standard. Keeping it separate means you can swap pricing rules without touching the rest of the system.

> **Analogy:** A taxi meter is one pricing strategy (per km). A fixed airport transfer is another. The car and driver don't change — only the billing rule does.

---

## 5. Class relationship diagram

```
BookingService  (facade — the single entry point callers use)
    |
    ├── Resource  ──has many──  ResourceItem  (one individual unit)
    |       |                        └── status: AVAILABLE → BLOCKED → BOOKED
    |       └── (e.g. ParkingLot has many ParkingSpot instances)
    |
    ├── Booking  (transaction record — what was booked, by whom, for how long)
    |       ├── user_id
    |       ├── items: List[ResourceItem]
    |       ├── total_amount
    |       └── status: INITIATED → CONFIRMED → CANCELLED
    |
    └── PricingStrategy  <<abstract interface>>
            ├── HourlyPricing
            └── FlatRatePricing
```

**Reading this diagram:**
- `BookingService` is the only class the outside world talks to.
- `Resource` groups similar items (e.g., all spots on floor 2). `ResourceItem` is one bookable unit.
- `Booking` is the paper trail — it records what happened and links a user to the item(s) they reserved.
- `PricingStrategy` is pluggable — swap it out without changing anything else.

---

## 6. Generic skeleton code

Read through this code top-to-bottom. Every section has a comment explaining the *why*, not just the *what*.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional
import uuid


# ---------------------------------------------------------------------------
# Enums — define the allowed states up front so the rest of the code can't
# invent new states by accident.
# ---------------------------------------------------------------------------

class ResourceStatus(Enum):
    """Tracks the lifecycle of a single bookable unit (e.g. one seat)."""
    AVAILABLE  = auto()   # free to be picked by anyone
    BLOCKED    = auto()   # temporarily held — someone is mid-checkout
    BOOKED     = auto()   # confirmed and paid for
    CANCELLED  = auto()   # was booked but is now released


class BookingStatus(Enum):
    """Tracks the lifecycle of the booking transaction itself."""
    INITIATED  = auto()   # user has selected items, payment not yet done
    CONFIRMED  = auto()   # payment succeeded, booking is live
    CANCELLED  = auto()   # booking was cancelled (items go back to AVAILABLE)


# ---------------------------------------------------------------------------
# ResourceItem — one individual unit that can be reserved.
# E.g. ParkingSpot, HotelRoom, CinemaSeat.
# Subclass this and add domain-specific fields (floor, screen, bed-type, etc.)
# ---------------------------------------------------------------------------

class ResourceItem(ABC):
    """
    A single bookable unit.

    Each item tracks its own status so the system always has a single source
    of truth about whether that specific unit is free.
    """

    def __init__(self, item_id: str):
        self.item_id: str = item_id
        self.status: ResourceStatus = ResourceStatus.AVAILABLE  # starts free

    def block(self) -> None:
        """
        Temporarily lock this item while the user completes checkout.
        Raises if the item is not currently available (guard against races).
        """
        if self.status != ResourceStatus.AVAILABLE:
            raise ValueError(
                f"Cannot block item {self.item_id}: "
                f"current status is {self.status.name}"
            )
        self.status = ResourceStatus.BLOCKED

    def confirm(self) -> None:
        """
        Finalise the reservation. Only valid after block() has been called.
        This separation (block → confirm) is what prevents double-bookings.
        """
        if self.status != ResourceStatus.BLOCKED:
            raise ValueError(
                f"Cannot confirm item {self.item_id}: "
                f"must be BLOCKED first, not {self.status.name}"
            )
        self.status = ResourceStatus.BOOKED

    def release(self) -> None:
        """
        Return the item to the available pool.
        Called on cancel (from BLOCKED or BOOKED) or on hold timeout.
        """
        self.status = ResourceStatus.AVAILABLE

    def is_available(self) -> bool:
        """Convenience helper used by availability-check logic."""
        return self.status == ResourceStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Booking — the transaction record.
# Think of it as the receipt that says "User X has Item Y from time A to B."
# ---------------------------------------------------------------------------

@dataclass
class Booking:
    """
    A single booking transaction.

    Storing a separate Booking object (rather than just marking items)
    lets us keep history, attach pricing, and support cancellations cleanly.
    """
    booking_id: str                         = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str                            = ""
    items: List[ResourceItem]               = field(default_factory=list)
    start_time: Optional[datetime]          = None
    end_time: Optional[datetime]            = None
    total_amount: float                     = 0.0
    status: BookingStatus                   = BookingStatus.INITIATED
    created_at: datetime                    = field(default_factory=datetime.now)

    def duration_hours(self) -> float:
        """How many hours does this booking span? Used by hourly pricing."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() / 3600
        return 0.0


# ---------------------------------------------------------------------------
# PricingStrategy — the strategy pattern for calculating cost.
# Adding a new pricing model = adding a new subclass. Nothing else changes.
# ---------------------------------------------------------------------------

class PricingStrategy(ABC):
    """
    Abstract base for all pricing rules.

    Why an interface here?  The booking flow (block → price → confirm) should
    not care *how* the price is calculated.  Swap strategies at runtime or per
    resource type without touching BookingService.
    """

    @abstractmethod
    def calculate(self, booking: Booking) -> float:
        """Return the total price for this booking."""
        ...


class HourlyPricing(PricingStrategy):
    """Charge a fixed rate per hour of the booking duration."""

    def __init__(self, rate_per_hour: float):
        self.rate_per_hour = rate_per_hour  # e.g. 5.0 = £5/hr

    def calculate(self, booking: Booking) -> float:
        return booking.duration_hours() * self.rate_per_hour


class FlatRatePricing(PricingStrategy):
    """Charge a single fixed fee regardless of duration."""

    def __init__(self, flat_fee: float):
        self.flat_fee = flat_fee

    def calculate(self, booking: Booking) -> float:
        return self.flat_fee


# ---------------------------------------------------------------------------
# BookingService — the facade.
# This is the ONLY class callers interact with.  It orchestrates all the
# steps so callers don't have to know the order of operations.
# ---------------------------------------------------------------------------

class BookingService:
    """
    Facade that hides the complexity of the booking flow.

    Responsibilities:
      1. Find available items.
      2. Initiate a booking (block items, price them).
      3. Confirm or cancel that booking.

    Why a facade?  Without it, every caller would need to know: "first call
    block(), then calculate price, then call confirm() — and remember to
    release() if anything goes wrong."  That's error-prone.  One service
    owns that choreography.
    """

    def __init__(self, pricing_strategy: PricingStrategy):
        # Inject the strategy — don't hardcode it.
        # This makes it easy to change pricing without editing this class.
        self.pricing_strategy = pricing_strategy
        self._bookings: dict[str, Booking] = {}  # booking_id → Booking

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def initiate_booking(
        self,
        user_id: str,
        items: List[ResourceItem],
        start_time: datetime,
        end_time: datetime,
    ) -> Booking:
        """
        Step 1 — User selects items and starts the checkout flow.

        Blocks each item so no one else can grab them during payment.
        Calculates the price so it can be shown to the user before they pay.
        Returns a Booking in INITIATED state.
        """
        # Guard: all items must be available right now
        for item in items:
            if not item.is_available():
                raise ValueError(
                    f"Item {item.item_id} is not available "
                    f"(status: {item.status.name})"
                )

        # Block every item atomically before doing anything else.
        # If this fails halfway, we release the ones already blocked.
        blocked = []
        try:
            for item in items:
                item.block()        # AVAILABLE → BLOCKED
                blocked.append(item)
        except ValueError:
            # Rollback: release any items we already blocked
            for b in blocked:
                b.release()
            raise

        # Build the booking record
        booking = Booking(
            user_id=user_id,
            items=items,
            start_time=start_time,
            end_time=end_time,
        )

        # Price it now so the user sees the total before confirming
        booking.total_amount = self.pricing_strategy.calculate(booking)

        self._bookings[booking.booking_id] = booking
        return booking

    def confirm_booking(self, booking_id: str) -> Booking:
        """
        Step 2 — Payment succeeded; make the booking permanent.

        Moves all items from BLOCKED → BOOKED and the booking to CONFIRMED.
        """
        booking = self._get_booking(booking_id)

        if booking.status != BookingStatus.INITIATED:
            raise ValueError(
                f"Booking {booking_id} cannot be confirmed "
                f"(status: {booking.status.name})"
            )

        for item in booking.items:
            item.confirm()      # BLOCKED → BOOKED

        booking.status = BookingStatus.CONFIRMED
        return booking

    def cancel_booking(self, booking_id: str) -> Booking:
        """
        Step 3 (alternate path) — User cancels or payment fails.

        Releases all items back to AVAILABLE so others can book them.
        """
        booking = self._get_booking(booking_id)

        if booking.status == BookingStatus.CANCELLED:
            raise ValueError(f"Booking {booking_id} is already cancelled.")

        for item in booking.items:
            item.release()      # BLOCKED or BOOKED → AVAILABLE

        booking.status = BookingStatus.CANCELLED
        return booking

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_booking(self, booking_id: str) -> Booking:
        """Retrieve a booking or raise a clear error."""
        booking = self._bookings.get(booking_id)
        if not booking:
            raise KeyError(f"No booking found with id: {booking_id}")
        return booking
```

> **What just happened?**
> You now have a complete, working skeleton. `BookingService.initiate_booking()` blocks items and prices them. `confirm_booking()` makes it permanent. `cancel_booking()` cleans everything up. None of these methods know *what* the resource is (parking spot, cinema seat, hotel room) — they only talk to `ResourceItem` through its `block()`, `confirm()`, and `release()` interface. That is the power of abstraction.

---

## 7. State transition diagram

### ResourceItem states

```
          select item
AVAILABLE ──────────────► BLOCKED
    ▲                        │
    │    cancel / timeout     │  payment succeeds
    └────────────────────────┘
                             │
                             ▼
                           BOOKED
                             │
                             │  refund / cancellation
                             ▼
                         AVAILABLE  (or CANCELLED if you want a terminal state)
```

### Booking states

```
INITIATED ──► CONFIRMED ──► CANCELLED
    │                            ▲
    └────────────────────────────┘
         (cancel before confirming)
```

### Why does BLOCKED exist?

Without the BLOCKED state, this scenario is possible:

1. Alice checks availability — spot 42 is free.
2. Bob checks availability — spot 42 is free (same moment).
3. Alice starts paying.
4. Bob also starts paying.
5. Both confirm. **Double booking.**

BLOCKED acts as a mutex: the moment Alice selects spot 42, it becomes BLOCKED. When Bob's system checks availability a millisecond later, it sees BLOCKED and skips it. This is the only thing standing between you and angry customers who both show up for the same seat.

> **Analogy:** It is the difference between a shop putting a "Reserved" sign on a fitting room versus just hoping two people don't walk in at once.

---

## 8. Design patterns used

| Pattern | Where it is used | Why |
|---|---|---|
| **Strategy** | `PricingStrategy` and its subclasses | Lets you swap pricing rules (hourly, flat, seasonal) at runtime without modifying `BookingService` |
| **Facade** | `BookingService` | Hides the multi-step booking flow (block → price → confirm) behind a simple API; callers do not need to know the internal sequence |
| **Template Method** | `ResourceItem.block()` / `confirm()` / `release()` in the base class | Defines the valid state transitions once; subclasses add domain fields but cannot accidentally bypass the state machine |
| **State** | `ResourceStatus` enum + guards in `block()` / `confirm()` | Each item enforces which transitions are legal; invalid transitions raise errors immediately |
| **Repository (light)** | `_bookings` dict in `BookingService` | Centralises booking storage; easy to swap for a real database later |

---

## 9. Key design decisions to explain in an interview

Interviewers do not just want working code — they want to see that you can justify your choices. Be ready to answer these five questions out loud.

- **Why separate `Resource` (the type) from `ResourceItem` (the instance)?**
  Because you need to talk about two different things: "we have 3-bed rooms" (the type, with its properties) and "room 204 specifically is available tonight" (the instance, with its status). Mixing them means you cannot easily check individual availability or extend one without affecting the other.

- **Why have a BLOCKED state before BOOKED?**
  To prevent double-booking during the payment window. Without it, two users could both see an item as available, both initiate payment, and both succeed. The BLOCKED state is a temporary lock that lasts only while the user is completing checkout (typically 5–10 minutes).

- **Why inject `PricingStrategy` instead of hardcoding the formula?**
  Pricing rules change constantly — promotions, peak pricing, membership tiers. If the formula is hardcoded inside `BookingService`, every pricing change requires editing the service and re-testing it. With injection, you write a new strategy class and swap it in. The service is never touched.

- **Why a facade service instead of letting the caller manage everything?**
  The block → price → confirm sequence must happen in the right order, with rollback if any step fails. If callers are responsible for this, one mistake in any part of the codebase causes subtle bugs (e.g., blocking an item but forgetting to release it on error). One service owns the sequence and gets it right everywhere.

- **How would you handle concurrent bookings?**
  At the application level, the BLOCKED state provides optimistic locking — only the first request to call `block()` succeeds. In production you would back this with a database-level row lock or a distributed lock (e.g., Redis `SET NX` with a TTL). You should also add a background job to release BLOCKED items that have not been confirmed within the hold window (typically 5–10 minutes).

---

## 10. Problems using this template

Practice applying the skeleton above to these three real interview problems:

- [Parking Lot](parking_lot.md)
- [Library Management System](library_management.md)
- [Movie Ticket Booking](bookmyshow.md)

Each problem file shows which parts of this template stay the same and which parts you customise for the domain.

---

## 11. Common mistakes beginners make

1. **Skipping the BLOCKED state and going straight to BOOKED.**
   This seems simpler but it means your system has no protection against double-booking during the payment window. Always include a temporary hold state.

2. **Putting availability logic inside the `Booking` class.**
   `Booking` is a transaction record — it should not know whether a spot is free. Availability belongs on `ResourceItem`. Mixing them makes both classes harder to understand and test.

3. **Hardcoding the pricing formula inside `BookingService`.**
   Pricing changes often. The moment you hardcode it, you create a class that needs to change for business reasons unrelated to booking flow. Use the Strategy pattern from the start.

4. **Forgetting to release items when a booking fails mid-flow.**
   If `block()` succeeds on item 1 but raises on item 2, item 1 stays BLOCKED forever. Always wrap multi-item blocking in a try/except that releases already-blocked items before re-raising the error.

5. **Treating `Resource` and `ResourceItem` as the same thing.**
   Beginners often create one `ParkingSpot` class that holds both "what type of spot is this?" and "is this specific spot free right now?". This works for tiny examples but breaks down when you need to query all available spots of a given type, or add properties to the type without affecting individual instances.
