# Template 03 — Marketplace / Matching System

---

## 1. What is the Marketplace / Matching Template?

In plain English: there are **two sides** to every marketplace.

- One side **offers** something (a ride, a meal, a product, a skill).
- The other side **wants** that something.
- The system's job is to **find the best match**, create a deal between them, and handle the money.

> Think of it like a matchmaker at a wedding bureau. Families (providers) register their children with a profile. Candidates (consumers) come in with their wish list. The matchmaker (matching algorithm) looks at both lists and introduces the best pair. Once they agree, the wedding (transaction) is booked.

Everything else — surge pricing, ratings, cancellations — is just detail on top of this core loop.

---

## 2. How to Recognise This Template in an Interview

When an interviewer says any of these things, your brain should immediately think "Marketplace / Matching":

| Signal phrase | Real system |
|---|---|
| "driver and rider" | Uber, Ola |
| "restaurant and customer" | Zomato, Swiggy |
| "seller and buyer" | Amazon, Flipkart |
| "match / assign / pair" | Job portals, freelancer platforms |
| "bid / quote / auction" | eBay, upwork |
| "split the bill" | Splitwise |
| "delivery partner" | Dunzo, Blinkit |

If you hear two distinct groups and the word "match", "assign", or "book" — you are in Marketplace territory.

---

## 3. Real-World Examples

| System | Provider | Consumer | What is matched |
|---|---|---|---|
| Uber / Ola | Driver | Rider | Nearest available cab |
| Swiggy / Zomato | Restaurant + Delivery partner | Customer | Food order + delivery |
| Amazon / Flipkart | Seller | Buyer | Product listing |
| LinkedIn Jobs | Employer | Job seeker | Job posting |
| Upwork / Fiverr | Freelancer | Client | Service offer |
| Splitwise | Payers | Payees | Debt settlement |

Each of these looks different on the surface, but the skeleton underneath is the same.

---

## 4. Core Building Blocks

Here are the six pieces you will need in almost every marketplace problem. Learn these six and you can sketch any marketplace.

### 4.1 Provider
The entity that **has** something to offer.

> A driver sitting idle with his cab. A restaurant with items on the menu. A seller with stock in a warehouse.

### 4.2 Consumer
The entity that **wants** something.

> A rider who needs to go somewhere. A hungry customer. A buyer who searched for a product.

### 4.3 Listing / Offer
The specific thing a provider is making available **right now**.

> Not just "I am a driver" but "I am at coordinates (12.9, 77.6), available, my cab fits 4 people, and my base rate is ₹12/km." That specific offer is a Listing.

### 4.4 Matching Algorithm
The logic that looks at all available listings and picks the best one for the consumer.

> The matchmaker's rulebook. Rule 1: nearest first. Rule 2: if tie, prefer higher-rated. Rule 3: if consumer is premium, prefer luxury cars.

This is deliberately separated from everything else so you can **swap the algorithm** without touching the rest of the system. (This is the Strategy pattern — more on that in Section 8.)

### 4.5 Transaction / Order
The formal contract created once a match is found and accepted.

> The signed wedding agreement. Once this exists, both sides are committed. It tracks status (requested → accepted → completed), the amount, timestamps, and who is involved.

### 4.6 Pricing Strategy
The rules for calculating what the consumer pays.

> Base fare + distance rate. Or: base fare × surge multiplier during peak hours. Or: flat fee for a subscription user.

Again, this is separate so pricing rules can change (or be A/B tested) without rewriting the whole system.

---

## 5. Class Relationship Diagram

```
MatchingService  (the facade — the single entry point)
       |
       ├── Provider  ──offers──►  Listing
       │
       ├── Consumer
       │
       ├── MatchingStrategy  <<abstract>>
       │       ├── NearestFirstStrategy
       │       └── CheapestFirstStrategy
       │
       ├── Transaction / Order
       │       └── TransactionStatus  (enum)
       │
       └── PricingStrategy  <<abstract>>
               ├── BasePricing
               └── SurgePricing
```

> The `MatchingService` is the receptionist at the wedding bureau. You (the consumer) walk in and talk only to the receptionist. The receptionist internally coordinates with the matchmaker, the registry, and the accountant. You never deal with them directly.

---

## 6. Generic Skeleton Code

Read through this once top to bottom before worrying about memorising it. The inline comments explain every choice.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional
import uuid
import math


# ──────────────────────────────────────────────
# ENUMS
# ──────────────────────────────────────────────

class TransactionStatus(Enum):
    REQUESTED   = auto()   # consumer asked for a match
    MATCHED     = auto()   # system found a provider
    ACCEPTED    = auto()   # provider confirmed
    IN_PROGRESS = auto()   # service is happening
    COMPLETED   = auto()   # done, payment settled
    CANCELLED   = auto()   # someone backed out


# ──────────────────────────────────────────────
# CORE ENTITIES
# ──────────────────────────────────────────────

@dataclass
class Location:
    """Simple (lat, lon) pair. Swap for a richer geo library if needed."""
    lat: float
    lon: float

    def distance_to(self, other: Location) -> float:
        """Straight-line (Euclidean) distance. Good enough for interviews."""
        return math.sqrt((self.lat - other.lat) ** 2 + (self.lon - other.lon) ** 2)


@dataclass
class Provider:
    """
    The entity that HAS something to offer.
    Examples: driver, restaurant, seller, freelancer.
    """
    provider_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    rating: float = 5.0
    location: Optional[Location] = None
    is_available: bool = True


@dataclass
class Consumer:
    """
    The entity that WANTS something.
    Examples: rider, customer, buyer.
    """
    consumer_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    location: Optional[Location] = None


@dataclass
class Listing:
    """
    What a specific provider is offering right now.
    Providers can have multiple listings (e.g. multiple products).
    """
    listing_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    provider: Optional[Provider] = None
    title: str = ""
    base_price: float = 0.0
    metadata: dict = field(default_factory=dict)  # flexible bag for extra info


@dataclass
class Transaction:
    """
    The contract created once a match is made.
    Think of this as the receipt + status tracker combined.
    """
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consumer: Optional[Consumer] = None
    provider: Optional[Provider] = None
    listing: Optional[Listing] = None
    status: TransactionStatus = TransactionStatus.REQUESTED
    amount: float = 0.0

    def transition_to(self, new_status: TransactionStatus) -> None:
        """Move the transaction to the next state."""
        # In production you'd validate allowed transitions here
        print(f"[Transaction {self.transaction_id[:8]}] {self.status.name} → {new_status.name}")
        self.status = new_status


# ──────────────────────────────────────────────
# STRATEGY: MATCHING
# ──────────────────────────────────────────────

class MatchingStrategy(ABC):
    """
    Abstract base: 'how do we pick the best provider for this consumer?'
    Concrete subclasses implement different algorithms.
    """

    @abstractmethod
    def find_match(
        self,
        consumer: Consumer,
        listings: List[Listing]
    ) -> Optional[Listing]:
        """Return the best listing, or None if no match found."""
        ...


class NearestFirstStrategy(MatchingStrategy):
    """
    Pick the provider whose location is closest to the consumer.
    Classic for ride-hailing.
    """

    def find_match(
        self,
        consumer: Consumer,
        listings: List[Listing]
    ) -> Optional[Listing]:
        available = [
            l for l in listings
            if l.provider and l.provider.is_available and l.provider.location
        ]
        if not available or not consumer.location:
            return None

        return min(
            available,
            key=lambda l: consumer.location.distance_to(l.provider.location)
        )


class CheapestFirstStrategy(MatchingStrategy):
    """
    Pick the listing with the lowest base price.
    Classic for e-commerce or budget travel.
    """

    def find_match(
        self,
        consumer: Consumer,
        listings: List[Listing]
    ) -> Optional[Listing]:
        available = [l for l in listings if l.provider and l.provider.is_available]
        if not available:
            return None
        return min(available, key=lambda l: l.base_price)


# ──────────────────────────────────────────────
# STRATEGY: PRICING
# ──────────────────────────────────────────────

class PricingStrategy(ABC):
    """Abstract base: 'how do we calculate the final price?'"""

    @abstractmethod
    def calculate(self, listing: Listing, consumer: Consumer) -> float:
        ...


class BasePricing(PricingStrategy):
    """Charge exactly the listing's base price. No extras."""

    def calculate(self, listing: Listing, consumer: Consumer) -> float:
        return listing.base_price


class SurgePricing(PricingStrategy):
    """
    Multiply base price by a surge factor.
    Surge factor > 1.0 during peak hours.
    """

    def __init__(self, surge_multiplier: float = 1.5):
        self.surge_multiplier = surge_multiplier

    def calculate(self, listing: Listing, consumer: Consumer) -> float:
        return listing.base_price * self.surge_multiplier


# ──────────────────────────────────────────────
# FACADE: MarketplaceService
# ──────────────────────────────────────────────

class MarketplaceService:
    """
    The single entry point for the entire marketplace.
    Consumers and providers never interact directly —
    everything goes through here.

    This is the Facade pattern: hide complexity behind a simple interface.
    """

    def __init__(
        self,
        matching_strategy: MatchingStrategy,
        pricing_strategy: PricingStrategy,
    ):
        self._matching_strategy = matching_strategy
        self._pricing_strategy  = pricing_strategy
        self._listings: List[Listing] = []
        self._transactions: dict[str, Transaction] = {}

    # ── Provider side ──────────────────────────

    def register_listing(self, listing: Listing) -> None:
        """Provider publishes something they want to offer."""
        self._listings.append(listing)
        print(f"[Marketplace] Listing registered: '{listing.title}' by {listing.provider.name}")

    # ── Consumer side ──────────────────────────

    def request(self, consumer: Consumer) -> Optional[Transaction]:
        """
        Consumer asks for a match.
        Returns a Transaction in MATCHED state, or None if no provider found.
        """
        matched_listing = self._matching_strategy.find_match(consumer, self._listings)

        if not matched_listing:
            print(f"[Marketplace] No match found for {consumer.name}.")
            return None

        amount = self._pricing_strategy.calculate(matched_listing, consumer)

        txn = Transaction(
            consumer=consumer,
            provider=matched_listing.provider,
            listing=matched_listing,
            amount=amount,
        )
        txn.transition_to(TransactionStatus.MATCHED)

        self._transactions[txn.transaction_id] = txn

        # Mark the provider as busy so they don't get double-matched
        matched_listing.provider.is_available = False

        return txn

    def accept(self, transaction_id: str) -> None:
        """Provider confirms they will fulfil the request."""
        txn = self._get_txn(transaction_id)
        txn.transition_to(TransactionStatus.ACCEPTED)
        txn.transition_to(TransactionStatus.IN_PROGRESS)

    def complete(self, transaction_id: str) -> None:
        """Service is done. Provider is free again."""
        txn = self._get_txn(transaction_id)
        txn.transition_to(TransactionStatus.COMPLETED)
        txn.provider.is_available = True  # provider can take new requests
        print(f"[Marketplace] Payment of ₹{txn.amount:.2f} settled.")

    def cancel(self, transaction_id: str) -> None:
        """Either side cancels. Provider is freed."""
        txn = self._get_txn(transaction_id)
        txn.transition_to(TransactionStatus.CANCELLED)
        if txn.provider:
            txn.provider.is_available = True

    # ── Internal helper ────────────────────────

    def _get_txn(self, transaction_id: str) -> Transaction:
        if transaction_id not in self._transactions:
            raise ValueError(f"Transaction {transaction_id} not found.")
        return self._transactions[transaction_id]
```

> **What just happened?**
> You now have a complete, working marketplace skeleton. Notice that `MarketplaceService` does not contain a single `if surge_pricing` or `if nearest_driver` branch. All that logic lives in swappable strategy objects. This is what interviewers want to see — clean separation of concerns.

---

## 7. Order Lifecycle — State Machine

Every transaction moves through a fixed sequence of states. Draw this on the whiteboard early in an interview — it shows you have thought about edge cases.

```
                  ┌─────────────┐
                  │  REQUESTED  │  ← consumer calls request()
                  └──────┬──────┘
                         │ system finds a provider
                  ┌──────▼──────┐
                  │   MATCHED   │  ← system has a candidate
                  └──────┬──────┘
                         │ provider calls accept()
                  ┌──────▼──────┐
                  │  ACCEPTED   │
                  └──────┬──────┘
                         │ service starts
                  ┌──────▼──────┐
                  │ IN_PROGRESS │
                  └──────┬──────┘
             ┌───────────┴────────────┐
             │ success                │ failure / cancel
      ┌──────▼──────┐         ┌───────▼──────┐
      │  COMPLETED  │         │  CANCELLED   │
      └─────────────┘         └──────────────┘
```

**Key rule:** any state except `COMPLETED` and `CANCELLED` can transition to `CANCELLED`. Add validation in `transition_to()` when you build the real thing.

---

## 8. Design Patterns Used

| Pattern | Where it appears | Why it helps |
|---|---|---|
| **Strategy** | `MatchingStrategy`, `PricingStrategy` | Swap algorithms at runtime without changing caller code |
| **Facade** | `MarketplaceService` | Single clean interface hides all internal complexity |
| **State** | `TransactionStatus` + `transition_to()` | Makes lifecycle explicit; prevents illegal state jumps |
| **Factory** | `Transaction` creation inside `request()` | Centralises object creation |
| **Observer** | Real-time location updates (see Section 9) | Push updates to interested parties without tight coupling |

---

## 9. Key Design Decisions to Explain in an Interview

When an interviewer asks "walk me through your design", these are the follow-up questions they will probe. Have an answer ready.

### Why separate `MatchingStrategy` from `PricingStrategy`?

They change for different reasons and at different times. A new pricing promotion should not require touching the matching code. Single Responsibility + Open/Closed principle. If both were in one class, every change would risk breaking the other.

### How do you handle "no provider available"?

Three options — pick based on the problem:
1. Return `None` immediately and tell the consumer to retry (simplest).
2. Put the consumer's request in a queue and notify them when a provider comes free (better UX, needs a queue + Observer).
3. Widen the search radius or relax constraints step by step (Uber's fallback logic).

Always mention the queue option — it shows you think about real-world scale.

### How do you handle provider rejection?

When a provider rejects (does not `accept()`), the transaction stays in `MATCHED` state. The service should:
1. Mark that provider unavailable for this request (not globally).
2. Call `find_match()` again on the remaining providers.
3. Set a max-retry count to avoid infinite loops.

### How would you add real-time location updates?

Use the **Observer pattern**. Providers are `Observable` subjects. `MarketplaceService` subscribes and updates the provider's `location` field whenever a new ping arrives. This decouples the GPS tracking layer from the matching layer.

```python
# Sketch — not full code
class LocationObserver:
    def on_location_update(self, provider: Provider, new_location: Location):
        provider.location = new_location
```

### How would you handle split fare or group orders?

Split fare = one `Transaction` with multiple `Consumer` objects (or a `ConsumerGroup`). The `amount` is divided by `PricingStrategy`. For Splitwise-style: a `DebtGraph` keeps track of who owes whom — that is its own sub-problem.

---

## 10. Common Beginner Mistakes

**Mistake 1: Putting matching logic inside `Consumer` or `Provider`**
These classes represent data entities. They should not know how to find each other. Put all matching logic in `MatchingStrategy`. Rule of thumb: if a class knows about the other side, something is wrong.

**Mistake 2: Making `TransactionStatus` a plain string**
Strings like `"completed"` are error-prone (`"Completed"`, `"COMPLETED"` are bugs waiting to happen). Always use an `Enum`. It gives you autocomplete, prevents typos, and makes state transitions readable.

**Mistake 3: Mixing pricing rules into the transaction**
`Transaction` stores *what was charged*. It should not *calculate* the price. Calculation belongs to `PricingStrategy`. Keeping the result separate from the calculation makes it easy to audit, log, or change the formula later.

**Mistake 4: Forgetting to free the provider after completion or cancellation**
If a provider stays `is_available = False` after a trip ends, they disappear from the marketplace forever. Always reset availability in both `complete()` and `cancel()`.

**Mistake 5: Designing a God class**
Beginners often put `register_provider`, `find_match`, `calculate_price`, `send_notification`, `process_payment` all in one class. In an interview, show that you know to split these into `MatchingService`, `PricingService`, `NotificationService`, `PaymentService`. Mention them even if you only implement one — it signals awareness of separation of concerns.

---

## 11. Problems That Use This Template

Solved problems in this folder:

- [Uber / Ride Sharing](uber.md) — nearest-driver matching, trip lifecycle, surge pricing
- [Splitwise](splitwise.md) — expense splitting strategies, debt simplification algorithm

> When you encounter a new marketplace problem, come back to this template first. Identify which parts map to Provider, Consumer, Listing, MatchingStrategy, Transaction, and PricingStrategy. The skeleton from Section 6 is your starting point — extend it, do not rewrite from scratch.

---

*Template 03 of 06 — Marketplace / Matching System*
