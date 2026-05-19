# 02 — ATM Machine

## What is this problem testing?

This problem tests your ability to model a system that has a strict lifecycle — an ATM is never "idle and also processing a transaction" at the same time. Interviewers are watching for whether you reach for a state machine to enforce valid sequences of operations, whether you keep security concerns (PIN hashing, card blocking) inside the right classes, and whether you use the Facade pattern so callers never have to think about internal state transitions directly.

---

## Requirements

- Insert card → validate PIN → choose transaction (withdraw / deposit / check balance) → eject card
- Lock the card permanently after 3 wrong PIN attempts
- Reject withdrawals when account balance is insufficient
- Auto-eject the card on session timeout (card auto-ejected after 30 seconds of inactivity)
- Maintain a full transaction history on the account

---

## Clarifying questions to ask in interview

1. **Is there a physical cash limit on the ATM?** — Does the machine track how much cash it holds, or do we only validate the account balance?
2. **Can a blocked card ever be unblocked?** — Is blocking permanent, or does it reset after a call to the bank? This affects whether `BLOCKED` is a terminal state.
3. **What is the session timeout duration, and what triggers the clock?** — Does the timer start when the card is inserted, or only after a successful PIN?
4. **Can multiple accounts be linked to one card?** — Clarifies whether `Card` has a one-to-one or one-to-many relationship with `Account`.
5. **Do we need concurrent access safety?** — Can two threads (or two ATMs sharing a backend) try to withdraw from the same account simultaneously? This affects whether we need locking around balance updates.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| ATM | `ATM` |
| Card | `Card` |
| Account | `Account` |
| Transaction | `Transaction` |
| Cash dispenser | `CashDispenser` |
| ATM state (lifecycle stage) | `ATMState` (enum: `IDLE`, `CARD_INSERTED`, `AUTHENTICATED`, `TRANSACTION`, `BLOCKED`) |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Insert card | `insert_card(card)` | `ATM` |
| Enter PIN | `enter_pin(pin)` | `ATM` |
| Withdraw cash | `withdraw(amount)` | `ATM`, `Account` |
| Deposit cash | `deposit(amount)` | `ATM`, `Account` |
| Check balance | `check_balance()` | `ATM`, `Account` |
| Eject card | `eject_card()` | `ATM` |
| Transition between states | `_transition_to(new_state)` | `ATM` |
| Dispense physical cash | `dispense(amount)` | `CashDispenser` |
| Record transaction | `add_transaction(txn)` | `Account` |
| Hash and compare PIN | `verify_pin(pin)` | `Card` |
| Block card | `block()` | `Card` |

---

## Relationships

```
ATM ──────── HAS-ONE ──────► ATMState       (current lifecycle stage)
ATM ──────── HAS-ONE ──────► CashDispenser  (physical cash mechanism)
ATM ──────── HAS-ONE ──────► Card           (the card currently inserted, or None)
ATM ──────── HAS-ONE ──────► Account        (linked to the inserted card)

Card ──────── HAS-ONE ──────► Account       (each card maps to an account)

Account ───── HAS-MANY ─────► Transaction   (full history of deposits / withdrawals)
```

> Think of the ATM like a bouncer at a venue. The bouncer (ATM) has a strict list of rules about who can do what and when. You first show your card (insert_card), then prove your identity (enter_pin), then you are allowed inside to do things (transaction). If you fail the identity check three times, you are banned (card blocked). The bouncer always knows which stage they are in and refuses to skip steps.

---

## Why this is a State Machine problem

The ATM is a textbook state machine because:

- It is **always in exactly one state** — you cannot be authenticated and idle at the same time.
- **Operations are only valid in certain states** — you cannot withdraw without being authenticated first.
- **Transitions are triggered by user actions** — inserting a card, entering a PIN, completing a transaction.
- **Invalid transitions must be caught and rejected** — trying to withdraw before entering a PIN should fail loudly, not silently.

Here is the full state diagram:

```
[Idle] ──insert_card──► [CardInserted] ──enter_pin (correct)──► [Authenticated] ──select_transaction──► [Transaction]
                                |                                                                               |
                         enter_pin (wrong × 3)                                                            complete
                                |                                                                               |
                          [CardBlocked]                                                                    [Idle] ◄─────── eject_card ◄──── [Authenticated]
```

Simplified left-to-right:

```
[Idle]
  │
  │  insert_card()
  ▼
[CardInserted]
  │                        ╔══════════════════╗
  │  enter_pin() ──wrong ×3─►  [CardBlocked]  ║  (terminal — no exit)
  │  (correct)             ╚══════════════════╝
  ▼
[Authenticated]
  │  withdraw() / deposit() / check_balance()
  ▼
[Transaction]
  │  complete
  ▼
[Idle]   ◄──── eject_card() also returns from [Authenticated] directly
```

> **What just happened?** Drawing this diagram before writing any code forces you to enumerate every state and every allowed move. Anything not in this diagram is an invalid operation — and `_transition_to()` will raise an error if someone tries it.

---

## Design decisions

### 1. Why State pattern (Enum + transition dict) instead of if-else chains?

**Decision:** Store the ATM's current state as an `ATMState` enum. Validate every state change against a `VALID_TRANSITIONS` dictionary.

**Why:** Without a state machine, every method becomes a wall of conditionals: `if self.state == "idle": raise Error`. This is fragile — it is easy to add a new method and forget to add the guard. With a central `_transition_to()` gatekeeper, all state validation lives in one place. Adding a new state means adding one entry to the dict, not hunting through every method.

**Alternative considered:** Using a long `if/elif` chain in each method. Rejected because the transition rules would be scattered, inconsistent, and untestable.

### 2. Why separate `CashDispenser` from `ATM`?

**Decision:** Physical cash dispensing lives in its own `CashDispenser` class, injected into `ATM`.

**Why:** The ATM logic (state management, account validation) and the hardware mechanism (do we have enough notes?) are different concerns. `CashDispenser` tracks physical cash availability; `Account` tracks the account balance. Both must be satisfied for a withdrawal to succeed. Separating them means you can test account logic without needing a real dispenser, and you can swap in a different dispenser (e.g., for a different currency) without touching `ATM`.

**Alternative considered:** Putting cash tracking directly on `ATM`. Rejected — mixes hardware concern with business logic.

### 3. How to handle concurrent ATM access?

**Decision:** Not implemented here (interview scope), but worth discussing.

**Why it matters:** Two people withdrawing from the same account simultaneously could both pass the balance check and both succeed — leaving the account in a negative state. In production, you would wrap the balance check and deduction in a database transaction with a row-level lock, or use an optimistic concurrency check (read balance, compare-and-swap). In an interview, say: "I'd add a threading lock around the withdraw method, or delegate to a transaction service that handles atomicity."

### 4. Why is transaction history on `Account`, not on `ATM`?

**Decision:** `Account` owns its `transaction_history` list.

**Why:** A transaction is a permanent record of something that happened to an account. An ATM is just a machine you happened to use — you might also transact via mobile banking or a teller. The account should be the single source of truth for its own history, regardless of how the transaction was initiated.

---

## Complete Code

First, let's set up all the types we need. Every class that follows builds on these foundations.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Set
import hashlib


# ── Transaction types ──────────────────────────────────────────────────────────
# An enum keeps all valid transaction types in one named, discoverable place.
# Using auto() avoids having to manually assign integer values.

class TransactionType(Enum):
    WITHDRAW      = auto()
    DEPOSIT       = auto()
    CHECK_BALANCE = auto()


# ── ATM state lifecycle ────────────────────────────────────────────────────────
# These are the only stages the ATM can be in.
# BLOCKED is a special terminal state — a blocked card can never be re-used.

class ATMState(Enum):
    IDLE          = auto()   # no card inserted
    CARD_INSERTED = auto()   # card is in, waiting for PIN
    AUTHENTICATED = auto()   # PIN accepted, ready to transact
    TRANSACTION   = auto()   # transaction in progress
    BLOCKED       = auto()   # card locked after too many wrong PINs (terminal)


# ── Transition rulebook ────────────────────────────────────────────────────────
# Key   = current state
# Value = set of states you are allowed to transition to from here
# If a target state is not in the set, _transition_to() will raise an error.

VALID_TRANSITIONS: Dict[ATMState, Set[ATMState]] = {
    ATMState.IDLE:          {ATMState.CARD_INSERTED},
    ATMState.CARD_INSERTED: {ATMState.AUTHENTICATED, ATMState.BLOCKED, ATMState.IDLE},
    ATMState.AUTHENTICATED: {ATMState.TRANSACTION,   ATMState.IDLE},
    ATMState.TRANSACTION:   {ATMState.AUTHENTICATED, ATMState.IDLE},
    ATMState.BLOCKED:       set(),   # terminal — nothing leaves this state
}
```

> **What just happened?** We have defined every legal move on a single lookup table. `_transition_to()` will consult this table before every state change. If the move is not listed here, it is forbidden — full stop.

Now the data classes:

```python
# ── Transaction ────────────────────────────────────────────────────────────────
# A Transaction is an immutable record of one ATM operation.
# @dataclass generates __init__, __repr__, and __eq__ automatically.

@dataclass
class Transaction:
    txn_type:  TransactionType
    amount:    float
    timestamp: datetime = field(default_factory=datetime.now)
    status:    str      = "SUCCESS"   # "SUCCESS" or "FAILED"

    def __repr__(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S")
        return f"[{ts}] {self.txn_type.name:<14} ₹{self.amount:>8.2f}  {self.status}"
```

Now the core domain classes:

```python
# ── Account ────────────────────────────────────────────────────────────────────
# An Account tracks a balance and a permanent history of every transaction.
# It owns withdrawal/deposit logic — the ATM delegates to it, not the reverse.

class Account:
    def __init__(self, account_id: str, balance: float = 0.0):
        self.account_id       = account_id
        self._balance         = balance
        self.transaction_history: List[Transaction] = []

    @property
    def balance(self) -> float:
        return self._balance

    def deposit(self, amount: float) -> Transaction:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self._balance += amount
        txn = Transaction(TransactionType.DEPOSIT, amount)
        self.transaction_history.append(txn)
        return txn

    def withdraw(self, amount: float) -> Transaction:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self._balance:
            # Record the failed attempt before raising — the history should be complete
            txn = Transaction(TransactionType.WITHDRAW, amount, status="FAILED")
            self.transaction_history.append(txn)
            raise ValueError(f"Insufficient funds: balance ₹{self._balance:.2f}, requested ₹{amount:.2f}")
        self._balance -= amount
        txn = Transaction(TransactionType.WITHDRAW, amount)
        self.transaction_history.append(txn)
        return txn

    def check_balance(self) -> Transaction:
        txn = Transaction(TransactionType.CHECK_BALANCE, 0.0)
        self.transaction_history.append(txn)
        return txn

    def print_history(self) -> None:
        print(f"\n── Transaction history for {self.account_id} ──")
        if not self.transaction_history:
            print("  (no transactions yet)")
        for txn in self.transaction_history:
            print(f"  {txn}")
        print(f"  Current balance: ₹{self._balance:.2f}\n")


# ── Card ───────────────────────────────────────────────────────────────────────
# A Card stores the card number, a hashed PIN (never the plain PIN),
# and tracks failed PIN attempts.
# After MAX_WRONG_ATTEMPTS failures, the card blocks itself.

class Card:
    MAX_WRONG_ATTEMPTS = 3

    def __init__(self, card_number: str, pin: str, account: Account):
        self.card_number    = card_number
        self._pin_hash      = self._hash_pin(pin)   # never store plain text
        self.account        = account
        self.is_blocked     = False
        self.wrong_attempts = 0

    @staticmethod
    def _hash_pin(pin: str) -> str:
        # SHA-256 is used here for clarity; production systems use bcrypt or Argon2
        return hashlib.sha256(pin.encode()).hexdigest()

    def verify_pin(self, pin: str) -> bool:
        """
        Returns True if the PIN is correct.
        Increments wrong_attempts on failure.
        Blocks the card when MAX_WRONG_ATTEMPTS is reached.
        Resets wrong_attempts to 0 on success.
        """
        if self.is_blocked:
            raise PermissionError("Card is blocked. Please contact your bank.")

        if self._hash_pin(pin) == self._pin_hash:
            self.wrong_attempts = 0   # reset counter on success — common mistake to forget this
            return True

        self.wrong_attempts += 1
        if self.wrong_attempts >= self.MAX_WRONG_ATTEMPTS:
            self.block()
        return False

    def block(self) -> None:
        self.is_blocked = True
        print(f"[SECURITY] Card {self.card_number} has been blocked after {self.MAX_WRONG_ATTEMPTS} wrong PIN attempts.")

    def __repr__(self) -> str:
        status = "BLOCKED" if self.is_blocked else "active"
        return f"Card({self.card_number!r}, {status})"


# ── CashDispenser ──────────────────────────────────────────────────────────────
# Tracks the physical cash in the machine.
# Separated from ATM because hardware availability and account balance are
# two independent constraints that must both be satisfied for a withdrawal.

class CashDispenser:
    def __init__(self, cash_available: float):
        self._cash_available = cash_available

    @property
    def cash_available(self) -> float:
        return self._cash_available

    def dispense(self, amount: float) -> None:
        if amount > self._cash_available:
            raise RuntimeError(
                f"ATM has insufficient cash: available ₹{self._cash_available:.2f}, requested ₹{amount:.2f}"
            )
        self._cash_available -= amount
        print(f"[DISPENSER] Dispensing ₹{amount:.2f}. Remaining in machine: ₹{self._cash_available:.2f}")
```

Finally, the `ATM` class — the facade that orchestrates everything:

```python
# ── ATM (Facade) ───────────────────────────────────────────────────────────────
# ATM is the single public interface. Callers never touch Card, Account,
# or CashDispenser directly. All state transitions flow through _transition_to().

class ATM:
    def __init__(self, atm_id: str, dispenser: CashDispenser):
        self.atm_id       = atm_id
        self._dispenser   = dispenser
        self._state       = ATMState.IDLE     # always start with an explicit state
        self._current_card: Optional[Card]    = None
        self._current_account: Optional[Account] = None

    # ── State gatekeeper ───────────────────────────────────────────────────────
    def _transition_to(self, new_state: ATMState) -> None:
        """
        The single gatekeeper for all state changes.
        Checks the VALID_TRANSITIONS rulebook before every move.
        No other code sets self._state directly.
        """
        if new_state not in VALID_TRANSITIONS[self._state]:
            raise ValueError(
                f"[{self.atm_id}] Invalid transition: {self._state.name} → {new_state.name}"
            )
        old_state    = self._state
        self._state  = new_state
        print(f"[ATM {self.atm_id}] State: {old_state.name} → {new_state.name}")

    # ── Public operations ──────────────────────────────────────────────────────

    def insert_card(self, card: Card) -> None:
        """Step 1: Insert your card. ATM must be idle."""
        self._transition_to(ATMState.CARD_INSERTED)   # raises if not in IDLE
        if card.is_blocked:
            print(f"[ATM] Card {card.card_number} is blocked. Ejecting.")
            self._transition_to(ATMState.IDLE)
            return
        self._current_card    = card
        self._current_account = card.account
        print(f"[ATM] Card {card.card_number} accepted. Please enter your PIN.")

    def enter_pin(self, pin: str) -> None:
        """Step 2: Enter PIN. Card must be inserted (state = CARD_INSERTED)."""
        if self._state != ATMState.CARD_INSERTED:
            raise ValueError("Please insert your card first.")

        card = self._current_card
        try:
            if card.verify_pin(pin):
                self._transition_to(ATMState.AUTHENTICATED)
                print("[ATM] PIN accepted. Please select a transaction.")
            else:
                remaining = Card.MAX_WRONG_ATTEMPTS - card.wrong_attempts
                print(f"[ATM] Wrong PIN. {remaining} attempt(s) remaining.")
        except PermissionError:
            # Card got blocked on this attempt — move to BLOCKED state
            self._transition_to(ATMState.BLOCKED)
            self._cleanup_session()

    def withdraw(self, amount: float) -> None:
        """Withdraw cash. ATM must be authenticated."""
        if self._state != ATMState.AUTHENTICATED:
            raise ValueError("Please authenticate first.")

        self._transition_to(ATMState.TRANSACTION)
        try:
            # Both constraints must pass: account balance AND machine cash
            self._dispenser.dispense(amount)       # raises if machine is short
            txn = self._current_account.withdraw(amount)   # raises if balance is short
            print(f"[ATM] Withdrawal successful. {txn}")
        except (RuntimeError, ValueError) as e:
            print(f"[ATM] Withdrawal failed: {e}")
        finally:
            # Always return to AUTHENTICATED so the user can try another transaction
            self._transition_to(ATMState.AUTHENTICATED)

    def deposit(self, amount: float) -> None:
        """Deposit cash. ATM must be authenticated."""
        if self._state != ATMState.AUTHENTICATED:
            raise ValueError("Please authenticate first.")

        self._transition_to(ATMState.TRANSACTION)
        txn = self._current_account.deposit(amount)
        print(f"[ATM] Deposit successful. {txn}")
        self._transition_to(ATMState.AUTHENTICATED)

    def check_balance(self) -> float:
        """Check balance. ATM must be authenticated."""
        if self._state != ATMState.AUTHENTICATED:
            raise ValueError("Please authenticate first.")

        self._transition_to(ATMState.TRANSACTION)
        txn = self._current_account.check_balance()
        print(f"[ATM] Balance: ₹{self._current_account.balance:.2f}  {txn}")
        self._transition_to(ATMState.AUTHENTICATED)
        return self._current_account.balance

    def eject_card(self) -> None:
        """End the session and return the card. Works from AUTHENTICATED or CARD_INSERTED."""
        print(f"[ATM] Ejecting card {self._current_card.card_number if self._current_card else '(none)'}.")
        self._transition_to(ATMState.IDLE)
        self._cleanup_session()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _cleanup_session(self) -> None:
        """Clear card and account references after a session ends."""
        self._current_card    = None
        self._current_account = None

    @property
    def current_state(self) -> ATMState:
        return self._state
```

> **What just happened?** `ATM` is a pure facade. It accepts user commands (`insert_card`, `enter_pin`, `withdraw`, etc.), validates the current state, delegates to the right class (`CashDispenser`, `Account`, `Card`), and transitions the state machine. No business logic leaks into the caller.

Usage example:

```python
if __name__ == "__main__":
    # Set up an account and card
    alice_account = Account("ACC-001", balance=5000.0)
    alice_card    = Card("4111-1111-1111-1111", pin="1234", account=alice_account)

    # Set up ATM with ₹20,000 in the machine
    dispenser = CashDispenser(cash_available=20_000.0)
    atm       = ATM("ATM-MAIN", dispenser)

    # ── Happy path: full session ───────────────────────────────────────────────
    atm.insert_card(alice_card)
    atm.enter_pin("1234")           # correct PIN
    atm.check_balance()
    atm.withdraw(1500.0)
    atm.deposit(500.0)
    atm.eject_card()

    alice_account.print_history()

    # ── Wrong PIN path ─────────────────────────────────────────────────────────
    bob_account = Account("ACC-002", balance=2000.0)
    bob_card    = Card("4222-2222-2222-2222", pin="9999", account=bob_account)
    atm.insert_card(bob_card)
    atm.enter_pin("0000")   # wrong
    atm.enter_pin("0001")   # wrong
    atm.enter_pin("0002")   # wrong — card blocked on this attempt

    # ── Insufficient funds ─────────────────────────────────────────────────────
    carol_account = Account("ACC-003", balance=100.0)
    carol_card    = Card("4333-3333-3333-3333", pin="5678", account=carol_account)
    atm.insert_card(carol_card)
    atm.enter_pin("5678")
    atm.withdraw(9999.0)    # fails — insufficient funds, stays AUTHENTICATED
    atm.eject_card()
```

---

## Step-by-step walkthrough

Let's trace the happy-path session from `insert_card` to `eject_card`.

```python
alice_account = Account("ACC-001", balance=5000.0)
alice_card    = Card("4111-1111-1111-1111", pin="1234", account=alice_account)
dispenser     = CashDispenser(cash_available=20_000.0)
atm           = ATM("ATM-MAIN", dispenser)
```
Three domain objects are created. `alice_card._pin_hash` stores the SHA-256 hash of `"1234"` — the plain text PIN is never kept. ATM starts in `IDLE`.

```python
atm.insert_card(alice_card)
```
- `_transition_to(CARD_INSERTED)` is called. `IDLE → CARD_INSERTED` is in `VALID_TRANSITIONS[IDLE]`, so it succeeds.
- `alice_card.is_blocked` is `False`, so the session continues.
- `self._current_card` and `self._current_account` are set.

**What just happened?** The ATM moved from IDLE to CARD_INSERTED and stored a reference to the card and its linked account. No PIN has been checked yet.

```python
atm.enter_pin("1234")
```
- `card.verify_pin("1234")` hashes `"1234"` and compares to `card._pin_hash`. They match.
- `card.wrong_attempts` resets to `0`.
- `_transition_to(AUTHENTICATED)` succeeds: `CARD_INSERTED → AUTHENTICATED` is allowed.

**What just happened?** The card is verified. The ATM moved to AUTHENTICATED. The user can now transact.

```python
atm.withdraw(1500.0)
```
- `_transition_to(TRANSACTION)` — `AUTHENTICATED → TRANSACTION` is allowed.
- `dispenser.dispense(1500.0)`: machine has ₹20,000, so `_cash_available` drops to ₹18,500.
- `alice_account.withdraw(1500.0)`: balance is ₹5,000 ≥ ₹1,500, so `_balance` drops to ₹3,500. A `Transaction(WITHDRAW, 1500)` is appended to `transaction_history`.
- `_transition_to(AUTHENTICATED)` in the `finally` block — back to ready state.

**What just happened?** Both constraints passed (machine cash and account balance). The money is dispensed and the account balance is updated. The ATM returns to AUTHENTICATED so the user can do more.

```python
atm.eject_card()
```
- `_transition_to(IDLE)` — `AUTHENTICATED → IDLE` is allowed.
- `_cleanup_session()` sets `_current_card` and `_current_account` to `None`.

**What just happened?** The session is fully torn down. The ATM is back in IDLE, ready for the next customer. No references to Alice's card or account remain on the ATM.

---

## Common interview mistakes

1. **Putting all logic in one `ATM` class with no state enum** — Writing `if self.card_inserted and self.pin_verified: ...` in every method. This works for 2 states but collapses at 5. Use an enum and a transition dict from the start.

2. **Not validating state before every operation** — Forgetting the guard `if self._state != ATMState.AUTHENTICATED: raise ValueError(...)` means a caller can call `withdraw()` before inserting a card, and Python will happily crash on `self._current_account.withdraw(...)` with an `AttributeError` instead of a clear business error.

3. **Storing the plain PIN** — Writing `self.pin = pin` instead of `self._pin_hash = hash(pin)`. This is an instant red flag in any security-sensitive interview. Always store the hash, never the secret.

4. **Not handling card blocking** — Forgetting to transition to `BLOCKED` state when `Card.is_blocked` becomes `True`. The card object may be blocked, but if the ATM stays in `CARD_INSERTED` state, nothing stops the user from calling `enter_pin()` again.

5. **Forgetting to reset `wrong_attempts` on success** — `Card.verify_pin()` must set `wrong_attempts = 0` when the PIN is correct. Without this, a user who enters the wrong PIN twice, then the right PIN once, then the wrong PIN once more would be blocked — because `wrong_attempts` silently carried over from the earlier session.

---

## Key patterns used

- **State (Enum + transition dict)** — `ATMState` enum plus `VALID_TRANSITIONS` dict enforce the lifecycle; `_transition_to()` is the single gatekeeper
- **Facade** — `ATM` is the single public entry point; callers never touch `Card`, `Account`, or `CashDispenser` directly
- **Command (transaction history)** — Each `Transaction` dataclass is an immutable record of an operation, stored on `Account` — this is the Command pattern's "log of executed commands"
