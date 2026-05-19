# 02 — Vending Machine

## What is this problem testing?

This problem tests whether you can model an object whose behaviour depends entirely on what stage it is currently in. A vending machine can only dispense a snack after you have selected one *and* inserted enough money — not before, not out of order. Interviewers are watching for whether you use a proper state machine (with an explicit transition rulebook) rather than a tangle of `if/elif` checks, whether you separate inventory management from payment logic, and whether you handle edge cases like insufficient funds, out-of-stock items, and change calculation.

---

## Requirements

- Display available items with their prices and stock levels
- Accept coins and notes of multiple denominations
- Let the customer select an item; if enough money has been inserted, dispense the item and return change
- Allow the customer to request a full refund of inserted money at any time
- Admin can restock items and collect accumulated cash from the machine
- Handle out-of-stock items gracefully (inform the customer, do not change state)
- Handle insufficient funds gracefully (inform the customer, wait for more money)

---

## Clarifying questions to ask in interview

1. **What denominations are accepted?** — Are we dealing with rupees, cents, or a generic currency? Does the machine accept notes as well as coins?
2. **Is change always guaranteed?** — Does the machine carry a cash float, or does it only give change from the money the customer inserted?
3. **What happens if the machine cannot make exact change?** — Reject the transaction and refund, or dispense anyway and accept a small loss?
4. **Can the customer select a different item after selecting one?** — i.e., is re-selection allowed before inserting money, or must they cancel first?
5. **Do we need concurrent access?** — Can two customers interact with the machine simultaneously, or is this a single-threaded simulation?

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Vending machine | `VendingMachine` |
| Item (snack, drink) | `Item` |
| Inventory | `Inventory` |
| Coin or note | `Coin` (enum) |
| Payment handler | `PaymentHandler` |
| Machine state | `VendingMachineState` (enum) |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Display items | `display_items()` | `VendingMachine` |
| Select an item | `select_item(item_id)` | `VendingMachine` |
| Insert money | `insert_money(coin)` | `VendingMachine` |
| Dispense item | `dispense()` | `VendingMachine` (internal) |
| Refund inserted money | `refund()` | `VendingMachine`, `PaymentHandler` |
| Calculate change | `calculate_change(price)` | `PaymentHandler` |
| Restock an item | `restock(item_id, qty)` | `VendingMachine`, `Inventory` |
| Collect cash | `collect_cash()` | `VendingMachine`, `PaymentHandler` |
| Transition state | `_transition_to(state)` | `VendingMachine` |
| Check item availability | `is_available(item_id)` | `Inventory` |

---

## Relationships

```
VendingMachine ─── HAS-ONE ────► Inventory
VendingMachine ─── HAS-ONE ────► PaymentHandler
VendingMachine ─── HAS-ONE ────► VendingMachineState  (current state)

Inventory ──────── HAS-MANY ───► Item

PaymentHandler ─── HAS-ONE ────► Coin[] (inserted so far)

Coin  <<enum>>
    └── values: 1, 2, 5, 10, 20

VendingMachineState <<enum>>
    └── IDLE, ITEM_SELECTED, HAS_MONEY, DISPENSING
```

> Think of it like a real snack machine in a school corridor. The machine itself is `VendingMachine` — the outer shell everyone interacts with. The shelf inside holding all the packets is `Inventory`. The coin slot and change tray together are `PaymentHandler`. The little light that shows "SELECT ITEM", "INSERT COINS", or "DISPENSING" is the `VendingMachineState`. Each of these things has one job and one job only.

---

## Why this is a State Machine problem

The machine behaves **completely differently** depending on which stage it is in:
- In `IDLE`: button presses do nothing useful.
- In `ITEM_SELECTED`: the machine knows what you want, but is waiting for money.
- In `HAS_MONEY`: the machine has some money and may be waiting for more, or ready to dispense.
- In `DISPENSING`: the machine is delivering the item and returning change.

You **cannot** jump from `IDLE` straight to `DISPENSING` — you would be skipping required steps. The state machine enforces this ordering.

```
[IDLE] ──select_item──► [ITEM_SELECTED] ──insert_money──► [HAS_MONEY]
                                                               │
                                              enough money? ───┤
                                                               │
                                              yes ──────────► [DISPENSING] ──► [IDLE]
                                                               │
                                              no ──────────► [HAS_MONEY]
                                                          (keep inserting)

[ITEM_SELECTED] ──refund──► [IDLE]
[HAS_MONEY]     ──refund──► [IDLE]
```

Every arrow in this diagram becomes an entry in `VALID_TRANSITIONS`. Every arrow that is *missing* (like `IDLE → DISPENSING`) is a bug you have prevented by design.

---

## Design decisions

### 1. Why separate `Inventory` from `VendingMachine`?

**Decision:** `Inventory` is its own class with methods `add_item`, `get_item`, `is_available`, and `restock`.

**Why:** `VendingMachine` is already responsible for state management and user interaction. If it also manages stock counts, it has two reasons to change (state changes *and* inventory rule changes) — a violation of the Single Responsibility Principle. A separate `Inventory` class is also independently testable: you can verify that restocking and deducting stock works correctly without spinning up the full machine.

**Alternative considered:** Store items in a plain dict on `VendingMachine`. Rejected — every inventory operation would be scattered as loose logic on the facade.

### 2. Why `PaymentHandler` as a separate class?

**Decision:** All coin tracking, refund logic, and change calculation live in `PaymentHandler`.

**Why:** Payment logic is genuinely complex (greedy change algorithm, tracking inserted coins, admin cash collection). Mixing it into `VendingMachine` would make that class enormous. `PaymentHandler` can be unit-tested on its own — "given these inserted coins and a price of ₹15, what change is returned?"

**Alternative considered:** Just keep a running `total` integer on `VendingMachine`. Rejected — this loses denomination information needed for change calculation and makes admin cash collection impossible.

### 3. How to calculate change optimally — greedy coin change

**Decision:** Sort available denominations largest-first and greedily subtract each from the remaining change amount.

**Why:** The greedy algorithm works correctly when denominations are "nice" (1, 2, 5, 10, 20) because each larger coin is a multiple of smaller ones. It is O(d) where d is the number of denominations — fast enough for any realistic vending machine.

**Caveat to mention in interview:** If denominations were arbitrary (e.g., 1, 3, 4), the greedy algorithm can fail to find the optimal answer. In that case you would use dynamic programming. For the standard coin set here, greedy is correct and simpler.

### 4. Why use the State pattern (Enum + transition dict) vs. simple `if/elif`?

**Decision:** Use `VALID_TRANSITIONS` dict and a single `_transition_to()` gatekeeper.

**Why:** With `if/elif`, every method (`select_item`, `insert_money`, `dispense`, `refund`) would need its own guard conditions, and it is easy to miss one. The transition dict is the **single source of truth** — add a new state by adding one line to the dict, not by hunting through five methods. The gatekeeper method (`_transition_to`) ensures nothing bypasses the rules, even future code you haven't written yet.

---

## Complete Code

The full implementation follows. Read the inline comments — they explain *why* each decision was made, not just *what* the code does.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional


# ── 1. States ──────────────────────────────────────────────────────────────────
# The machine is always in exactly one of these four states.
# auto() assigns integer values automatically — we never need to care what they are.

class VendingMachineState(Enum):
    IDLE          = auto()   # waiting for a customer to do something
    ITEM_SELECTED = auto()   # customer has chosen an item, no money yet
    HAS_MONEY     = auto()   # customer has inserted some money
    DISPENSING    = auto()   # machine is delivering the item (brief transient state)


# ── 2. Transition rulebook ─────────────────────────────────────────────────────
# Key   = current state
# Value = set of states that are valid next moves from here
#
# Anything NOT in the set is forbidden. The gatekeeper (_transition_to) enforces this.

VALID_TRANSITIONS: Dict[VendingMachineState, set] = {
    VendingMachineState.IDLE:          {VendingMachineState.ITEM_SELECTED},
    VendingMachineState.ITEM_SELECTED: {VendingMachineState.HAS_MONEY,
                                        VendingMachineState.IDLE},          # refund path
    VendingMachineState.HAS_MONEY:     {VendingMachineState.DISPENSING,
                                        VendingMachineState.HAS_MONEY,      # more coins
                                        VendingMachineState.IDLE},          # refund path
    VendingMachineState.DISPENSING:    {VendingMachineState.IDLE},          # always back to idle
}


# ── 3. Coin denominations ──────────────────────────────────────────────────────
# Using an Enum with explicit integer values (instead of auto()) because
# the *value* of the coin is what matters for arithmetic.

class Coin(Enum):
    ONE      = 1
    TWO      = 2
    FIVE     = 5
    TEN      = 10
    TWENTY   = 20


# ── 4. Item ────────────────────────────────────────────────────────────────────
# A dataclass is perfect here: it is pure data with no behaviour of its own.
# @dataclass writes __init__, __repr__, and __eq__ for us automatically.

@dataclass
class Item:
    item_id:  str
    name:     str
    price:    int    # in the smallest currency unit (paise / cents) — avoids float rounding
    quantity: int = 0


# ── 5. Inventory ───────────────────────────────────────────────────────────────
# Owns all the items. Responsible only for stock counts.
# VendingMachine delegates all inventory questions here.

class Inventory:
    def __init__(self) -> None:
        self._items: Dict[str, Item] = {}   # item_id → Item

    def add_item(self, item: Item) -> None:
        """Add a new item type to the machine (used during initial setup)."""
        self._items[item.item_id] = item

    def get_item(self, item_id: str) -> Optional[Item]:
        """Return the Item object, or None if the ID is unknown."""
        return self._items.get(item_id)

    def is_available(self, item_id: str) -> bool:
        """True only if the item exists AND has stock remaining."""
        item = self.get_item(item_id)
        return item is not None and item.quantity > 0

    def deduct(self, item_id: str) -> None:
        """Reduce stock by 1 when an item is dispensed. Raises if stock is zero."""
        item = self.get_item(item_id)
        if not item or item.quantity <= 0:
            raise ValueError(f"Item '{item_id}' is out of stock")
        item.quantity -= 1

    def restock(self, item_id: str, qty: int) -> None:
        """Admin method: add more units to an existing item."""
        item = self.get_item(item_id)
        if not item:
            raise ValueError(f"Unknown item_id '{item_id}'. Use add_item() first.")
        item.quantity += qty
        print(f"[ADMIN] Restocked '{item.name}' by {qty}. New stock: {item.quantity}")

    def display(self) -> None:
        """Print the current menu with prices and stock levels."""
        print("\n── Available Items ────────────────")
        for item in self._items.values():
            status = f"{item.quantity} left" if item.quantity > 0 else "OUT OF STOCK"
            print(f"  [{item.item_id}]  {item.name:<20}  ₹{item.price}   ({status})")
        print("────────────────────────────────────\n")


# ── 6. PaymentHandler ──────────────────────────────────────────────────────────
# Owns all money that has passed through the machine.
# Tracks what the current customer has inserted (session coins) separately
# from the machine's total cash reserve (for admin collection).

class PaymentHandler:
    def __init__(self) -> None:
        # Coins the current customer has inserted this session
        self._session_coins: List[int] = []
        # All coins ever inserted (persists across sessions) — for admin cash collection
        self._total_coins: List[int] = []

    def insert(self, coin: Coin) -> None:
        """Accept a single coin or note from the customer."""
        self._session_coins.append(coin.value)
        self._total_coins.append(coin.value)
        print(f"  Inserted: ₹{coin.value}  |  Total so far: ₹{self.total_inserted}")

    @property
    def total_inserted(self) -> int:
        """How much money the current customer has inserted this session."""
        return sum(self._session_coins)

    def calculate_change(self, price: int) -> List[int]:
        """
        Greedy change calculation.
        Given the price of the selected item, figure out which coins to return.

        Works correctly for standard denominations (1, 2, 5, 10, 20) because
        each denomination divides evenly into larger ones.

        Returns a list of coin values (e.g. [10, 5, 2, 2] for ₹19 change).
        Raises ValueError if exact change cannot be made (shouldn't happen with ₹1 coin).
        """
        change_due = self.total_inserted - price
        if change_due < 0:
            raise ValueError("Insufficient funds — cannot calculate change")

        denominations = sorted([c.value for c in Coin], reverse=True)  # [20, 10, 5, 2, 1]
        change_coins: List[int] = []
        remaining = change_due

        for denom in denominations:
            while remaining >= denom:
                change_coins.append(denom)
                remaining -= denom

        if remaining != 0:
            # This should never happen with a ₹1 coin in the set
            raise ValueError(f"Cannot make exact change for ₹{change_due}")

        return change_coins

    def refund(self) -> int:
        """
        Return all coins the customer inserted this session.
        Clears the session but does NOT touch the total reserve
        (we already added these to total; we need to remove them on refund).
        """
        amount = self.total_inserted
        # Remove session coins from the total reserve too
        for coin_val in self._session_coins:
            self._total_coins.remove(coin_val)
        self._session_coins.clear()
        return amount

    def finalise_payment(self, price: int) -> List[int]:
        """
        Called after a successful dispense.
        Deducts the item price from session coins, returns change coin list,
        and clears the session. The price amount stays in the total reserve.
        """
        change_coins = self.calculate_change(price)
        # Remove change coins from the total reserve (we're physically returning them)
        for coin_val in change_coins:
            self._total_coins.remove(coin_val)
        self._session_coins.clear()
        return change_coins

    def collect(self) -> int:
        """Admin method: empty the machine's cash reserve. Returns total collected."""
        total = sum(self._total_coins)
        self._total_coins.clear()
        return total


# ── 7. VendingMachine (facade) ─────────────────────────────────────────────────
# The single entry point for all customer and admin interactions.
# Orchestrates state transitions, delegates to Inventory and PaymentHandler.
# External code never needs to touch Inventory or PaymentHandler directly.

class VendingMachine:
    def __init__(self) -> None:
        self._state           = VendingMachineState.IDLE   # always start IDLE
        self._inventory       = Inventory()
        self._payment_handler = PaymentHandler()
        self._selected_item:  Optional[Item] = None        # tracks chosen item

    # ── State management ───────────────────────────────────────────────────────

    def _transition_to(self, new_state: VendingMachineState) -> None:
        """
        The single gatekeeper for all state changes.
        No other method sets self._state directly — everything goes through here.
        Raises ValueError if the transition is not in the rulebook.
        """
        if new_state not in VALID_TRANSITIONS[self._state]:
            raise ValueError(
                f"Invalid transition: {self._state.name} → {new_state.name}"
            )
        print(f"  [State] {self._state.name} → {new_state.name}")
        self._state = new_state

    @property
    def state(self) -> VendingMachineState:
        """Read-only access to the current state for inspection/testing."""
        return self._state

    # ── Customer interface ─────────────────────────────────────────────────────

    def display_items(self) -> None:
        """Show the menu. Available from any state."""
        self._inventory.display()

    def select_item(self, item_id: str) -> None:
        """
        Customer selects an item by ID.
        Only valid from IDLE. Rejects out-of-stock items without changing state.
        """
        if self._state != VendingMachineState.IDLE:
            print(f"  Cannot select item in state {self._state.name}. "
                  f"Finish or cancel the current session first.")
            return

        item = self._inventory.get_item(item_id)
        if not item:
            print(f"  Unknown item '{item_id}'. Please check the display.")
            return

        if not self._inventory.is_available(item_id):
            print(f"  Sorry, '{item.name}' is out of stock.")
            return   # state stays IDLE — customer can pick a different item

        self._selected_item = item
        self._transition_to(VendingMachineState.ITEM_SELECTED)
        print(f"  Selected: {item.name}  |  Price: ₹{item.price}  |  "
              f"Please insert money.")

    def insert_money(self, coin: Coin) -> None:
        """
        Customer inserts a coin or note.
        Valid from ITEM_SELECTED or HAS_MONEY.
        Automatically triggers dispense if enough money has been inserted.
        """
        if self._state not in (VendingMachineState.ITEM_SELECTED,
                                VendingMachineState.HAS_MONEY):
            print(f"  Please select an item before inserting money.")
            return

        # Record the coin and move to HAS_MONEY if not already there
        self._payment_handler.insert(coin)
        self._transition_to(VendingMachineState.HAS_MONEY)

        # Check if we have enough to dispense
        if self._payment_handler.total_inserted >= self._selected_item.price:
            self._dispense()
        else:
            remaining = self._selected_item.price - self._payment_handler.total_inserted
            print(f"  Need ₹{remaining} more to buy {self._selected_item.name}.")

    def _dispense(self) -> None:
        """
        Internal method — called automatically when enough money is inserted.
        Transitions through DISPENSING and back to IDLE.
        Deducts stock, calculates change, resets session.
        """
        self._transition_to(VendingMachineState.DISPENSING)

        item = self._selected_item
        self._inventory.deduct(item.item_id)

        change_coins = self._payment_handler.finalise_payment(item.price)

        print(f"\n  *** Dispensing: {item.name} ***")
        if change_coins:
            print(f"  Change returned: ₹{sum(change_coins)}  "
                  f"(coins: {change_coins})")
        else:
            print(f"  No change. Exact amount inserted.")

        # Clean up session state
        self._selected_item = None
        self._transition_to(VendingMachineState.IDLE)

    def refund(self) -> None:
        """
        Customer requests a full refund of inserted money.
        Valid from ITEM_SELECTED or HAS_MONEY. Resets to IDLE.
        """
        if self._state not in (VendingMachineState.ITEM_SELECTED,
                                VendingMachineState.HAS_MONEY):
            print(f"  Nothing to refund in state {self._state.name}.")
            return

        amount = self._payment_handler.refund()
        self._selected_item = None
        self._transition_to(VendingMachineState.IDLE)
        print(f"  Refunded: ₹{amount}")

    # ── Admin interface ────────────────────────────────────────────────────────

    def add_item(self, item: Item) -> None:
        """Admin: register a new item type. Usually called at setup time."""
        self._inventory.add_item(item)

    def restock(self, item_id: str, qty: int) -> None:
        """Admin: add more units to an existing item."""
        self._inventory.restock(item_id, qty)

    def collect_cash(self) -> None:
        """Admin: empty the cash reserve and print the total collected."""
        total = self._payment_handler.collect()
        print(f"[ADMIN] Cash collected: ₹{total}")


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── Set up the machine ─────────────────────────────────────────────────────
    vm = VendingMachine()
    vm.add_item(Item("A1", "Lays Classic",   price=20, quantity=5))
    vm.add_item(Item("A2", "Kurkure",        price=10, quantity=3))
    vm.add_item(Item("B1", "Frooti",         price=20, quantity=0))  # out of stock
    vm.add_item(Item("B2", "Sprite 250ml",   price=30, quantity=2))

    # ── Normal happy path ──────────────────────────────────────────────────────
    print("=" * 50)
    print("SCENARIO 1: Buy Lays (₹20) — insert ₹10 then ₹20, get ₹10 change")
    print("=" * 50)

    vm.display_items()
    vm.select_item("A1")          # IDLE → ITEM_SELECTED
    vm.insert_money(Coin.TEN)     # ITEM_SELECTED → HAS_MONEY  (₹10 inserted, need ₹10 more)
    vm.insert_money(Coin.TWENTY)  # HAS_MONEY → DISPENSING → IDLE  (₹30 inserted, ₹10 change)

    # ── Out-of-stock item ──────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("SCENARIO 2: Try to buy Frooti — out of stock")
    print("=" * 50)

    vm.select_item("B1")   # stays IDLE — item is out of stock

    # ── Refund scenario ────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("SCENARIO 3: Select item, insert money, then refund")
    print("=" * 50)

    vm.select_item("B2")          # IDLE → ITEM_SELECTED  (Sprite ₹30)
    vm.insert_money(Coin.TWENTY)  # ITEM_SELECTED → HAS_MONEY  (₹20, need ₹10 more)
    vm.refund()                   # HAS_MONEY → IDLE  (₹20 returned)

    # ── Invalid transition attempt ─────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("SCENARIO 4: Try to insert money without selecting item first")
    print("=" * 50)

    vm.insert_money(Coin.TEN)   # Politely rejected — machine is in IDLE state

    # ── Exact change scenario ──────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("SCENARIO 5: Buy Kurkure (₹10) — insert exact ₹10")
    print("=" * 50)

    vm.select_item("A2")       # IDLE → ITEM_SELECTED
    vm.insert_money(Coin.TEN)  # Exact amount — dispense immediately, no change

    # ── Admin operations ───────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("SCENARIO 6: Admin restocks Frooti and collects cash")
    print("=" * 50)

    vm.restock("B1", qty=10)
    vm.collect_cash()
    vm.display_items()
```

> **What just happened?**
> The machine went through five real-world scenarios: a normal purchase with change, an out-of-stock rejection, a mid-session refund, an attempted shortcut (inserting money without selecting), and an exact-change purchase. In every case, `_transition_to()` was the gatekeeper — it either approved the move or blocked it before any state was mutated.

---

## Step-by-step walkthrough

Trace: select Lays (₹20) → insert ₹10 → insert ₹20 → dispense → get ₹10 change

```python
vm.select_item("A1")
```
- `_state` is `IDLE`. The guard passes.
- `Inventory.get_item("A1")` returns the `Item("A1", "Lays Classic", price=20, quantity=5)` object.
- `Inventory.is_available("A1")` returns `True` (quantity > 0).
- `self._selected_item` is set to the Lays item.
- `_transition_to(ITEM_SELECTED)`: checked against `VALID_TRANSITIONS[IDLE]` → `{ITEM_SELECTED}` — allowed. State becomes `ITEM_SELECTED`.
- Prints: `Selected: Lays Classic | Price: ₹20 | Please insert money.`

**What just happened?** The machine now knows what the customer wants. It is holding that selection in `_selected_item` and waiting for payment.

```python
vm.insert_money(Coin.TEN)
```
- `_state` is `ITEM_SELECTED`. The guard passes.
- `PaymentHandler.insert(Coin.TEN)`: appends `10` to `_session_coins` and `_total_coins`. `total_inserted` is now `10`.
- `_transition_to(HAS_MONEY)`: checked against `VALID_TRANSITIONS[ITEM_SELECTED]` → `{HAS_MONEY, IDLE}` — allowed.
- `total_inserted (10) < price (20)` → not enough. Prints: `Need ₹10 more to buy Lays Classic.`

**What just happened?** The machine accepted the coin and updated its running total. It stayed in `HAS_MONEY` and told the customer how much more is needed.

```python
vm.insert_money(Coin.TWENTY)
```
- `_state` is `HAS_MONEY`. The guard passes.
- `PaymentHandler.insert(Coin.TWENTY)`: appends `20`. `total_inserted` is now `30`.
- `_transition_to(HAS_MONEY)`: checked against `VALID_TRANSITIONS[HAS_MONEY]` → includes `HAS_MONEY` — allowed (self-loop for additional coins).
- `total_inserted (30) >= price (20)` → enough! Calls `_dispense()`.

Inside `_dispense()`:

- `_transition_to(DISPENSING)`: `HAS_MONEY → DISPENSING` — allowed.
- `Inventory.deduct("A1")`: quantity drops from `5` to `4`.
- `PaymentHandler.finalise_payment(20)`:
  - `change_due = 30 - 20 = 10`.
  - Greedy: `20 > 10` skip, `10 <= 10` → add `10`, `remaining = 0`.
  - Removes the `10` coin from `_total_coins` (physically returning it).
  - Clears `_session_coins`.
  - Returns `[10]`.
- Prints: `*** Dispensing: Lays Classic ***` and `Change returned: ₹10  (coins: [10])`.
- `_selected_item` is reset to `None`.
- `_transition_to(IDLE)`: `DISPENSING → IDLE` — allowed.

**What just happened?** The machine dispensed the snack, calculated ₹10 change using the greedy algorithm, physically returned that coin (removed from the reserve), cleared the session, and returned to idle — ready for the next customer.

---

## Common interview mistakes

1. **No state validation — dispense without selecting an item.** Writing `dispense()` as a public method with no guard means a caller can invoke it directly from `IDLE` and get a free snack. All state-changing methods must check the current state first.

2. **Not handling change calculation — keeping only a running total.** If you track only `total_inserted: int`, you have no information about which denominations were inserted. You cannot compute change. Use a list of coin values so you can run the greedy algorithm.

3. **Inventory embedded in `VendingMachine` — SRP violation.** Putting `self._stock: Dict[str, int]` directly on `VendingMachine` and writing stock-manipulation logic inside its methods means `VendingMachine` has two jobs. Every inventory rule change forces you to edit the state machine class.

4. **Not handling refund.** Many candidates implement the happy path and forget that customers can change their minds. The `HAS_MONEY → IDLE` transition via `refund()` is a core requirement, and forgetting it means inserted money is lost forever.

5. **Forgetting to reset state after dispensing.** Returning from `_dispense()` without calling `_transition_to(IDLE)` leaves the machine in `DISPENSING` forever. The next customer cannot select an item because `VALID_TRANSITIONS[DISPENSING]` only allows `→ IDLE`. Always reset to a clean state at the end of a successful transaction.

---

## Key patterns used

- **State** — `VendingMachineState` enum + `VALID_TRANSITIONS` dict + `_transition_to()` gatekeeper enforce that the machine can only do what makes sense in its current stage
- **Facade** — `VendingMachine` is the single public interface; customers and admins never touch `Inventory` or `PaymentHandler` directly
- **Strategy** — Change calculation in `PaymentHandler.calculate_change()` uses the greedy algorithm, which could be swapped for dynamic programming without changing any other class
