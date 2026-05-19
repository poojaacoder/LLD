# 03 — Splitwise

## What is this problem testing?

This problem tests your ability to model a **two-sided financial marketplace** — where one person lends money and others owe it back — and then design clean logic to track, simplify, and settle those debts. Interviewers are watching for how you apply the Strategy pattern to split types, how you build a balance map correctly (direction matters!), and whether you can articulate the greedy algorithm for debt simplification. It also tests whether you keep split logic out of the `Expense` class and in a dedicated strategy instead.

---

## Requirements

- Users can create groups (e.g. "Trip to Goa", "Flat mates")
- Any group member can add an expense (paid by one person, split among some or all members)
- Three split strategies: **Equal** (divide evenly), **Exact** (each person owes a specified amount), **Percentage** (each person owes a percentage)
- View balances: who owes whom, and how much
- Debt simplification: minimise the number of transactions needed to settle all debts
- Settle up: record a direct payment from one user to another

---

## Clarifying questions to ask in interview

1. **Can a user belong to multiple groups?** — Yes, and their balances are tracked per group, not globally.
2. **Does ExactSplit need to validate that amounts sum to the total?** — Yes, otherwise money appears or disappears.
3. **Is settle-up a real payment or just a record?** — For this design, it is a recorded transaction that reduces the balance.
4. **Can someone pay for a partial subset of the group?** — Yes, the payer specifies which members are included in the split.
5. **Do we need user authentication or just data modelling?** — Data modelling only for an interview setting.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| User | `User` |
| Group of users | `Group` |
| A shared expense | `Expense` |
| One user's share of an expense | `ExpenseSplit` |
| How an expense is divided | `SplitStrategy` |
| Net balance tracker | computed inside `Group.get_balances()` |
| Entry point / coordinator | `SplitwiseService` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Create a group | `create_group(name, members)` | `SplitwiseService` |
| Add an expense | `add_expense(desc, amount, paid_by, strategy, **kwargs)` | `Group` |
| Divide the bill | `calculate(total, members, **kwargs)` | `SplitStrategy` subclass |
| View balances | `get_balances()` | `Group` |
| Simplify debts | `simplify(balances)` | `DebtSimplifier` |
| Settle a debt | `settle_up(payer, payee, amount)` | `Group` |

---

## Relationships

```
SplitwiseService  (facade — single entry point)
 │
 ├── Group
 │    ├── HAS-MANY ──► User  (members)
 │    └── HAS-MANY ──► Expense
 │
 ├── Expense
 │    ├── HAS-ONE  ──► User  (paid_by)
 │    └── HAS-MANY ──► ExpenseSplit
 │
 ├── ExpenseSplit
 │    └── HAS-ONE  ──► User  (who owes this share)
 │
 └── SplitStrategy  <<abstract>>
          ├── EqualSplit
          ├── ExactSplit
          └── PercentageSplit
```

> Think of it like splitting a restaurant bill. The waiter brings one bill (the `Expense`). The `SplitStrategy` is your table's agreed rule — "let's go halves", "pay what you ordered", or "split by salary percentage". The receipt each person mentally carries home is their `ExpenseSplit`. The app (the `Group`) just keeps track of all those mental notes so nobody has to remember.

---

## Design decisions

### 1. Strategy pattern for split types

**Decision:** `SplitStrategy` is an abstract class. `EqualSplit`, `ExactSplit`, and `PercentageSplit` are concrete subclasses. `Expense` receives a strategy object and calls `strategy.calculate(...)`.

**Why:** New split types (e.g. "split by shares", "split by room size") can be added without touching `Expense` at all. Open/Closed principle — open to extension, closed to modification.

**Alternative considered:** A big `if split_type == "equal" / "exact" / "percentage"` block inside `Expense.add()`. Rejected — every new split type means editing `Expense`, which risks breaking existing splits.

### 2. Balance map direction matters

**Decision:** `get_balances()` returns `Dict[User, float]` where a **positive** value means "this user is owed money" and a **negative** value means "this user owes money".

**Why:** Direction is everything in a debt graph. If you flip the sign, Bob appears to owe Alice when it is actually the reverse. Always define the convention explicitly and comment it.

**How it is built:** For each `Expense`, the payer gets a `+amount` credit and each `ExpenseSplit.user` gets a `-amount_owed` debit. Sum these across all expenses.

### 3. Debt simplification with a greedy algorithm

**Decision:** `DebtSimplifier.simplify()` uses a greedy max-creditor vs max-debtor approach.

**Why:** Naively showing raw balances (Alice owes Bob ₹100, Bob owes Charlie ₹100) requires two payments. Simplification collapses this to one (Alice pays Charlie ₹100 directly). The greedy algorithm achieves this in `O(n log n)` using heaps.

**Algorithm in plain English:** While there are unsettled users, take the person who is owed the most (max creditor) and the person who owes the most (max debtor). Match them for `min(credit, debt)`. Reduce both by that amount. If either hits zero, remove them from the list.

### 4. `ExpenseSplit` as a Value Object

**Decision:** `ExpenseSplit` is a `dataclass` — immutable-ish, no methods of its own.

**Why:** It is pure data: a (user, amount) pair. Giving it behaviour would violate Single Responsibility. The `Expense` that owns it does all the work.

### 5. Settle-up as a zero-description expense

**Decision:** `settle_up(payer, payee, amount)` records a payment by creating an `Expense` where `paid_by = payer`, and the only split is a single `ExpenseSplit(user=payee, amount_owed=amount)`.

**Why:** Re-using `Expense` for settlements means `get_balances()` needs zero extra logic — a settlement is just another expense that happens to reduce debt rather than create it. No separate data structure needed.

---

## Complete Code

Plain-English summary before you read the code: we build the enums and data classes first (small, no dependencies), then the strategies, then `Expense` and `Group`, and finally the `DebtSimplifier` and `SplitwiseService` facade.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple
import uuid
import heapq


# ── Enums ──────────────────────────────────────────────────────────────────────

class SplitType(Enum):
    EQUAL      = auto()   # divide total evenly among members
    EXACT      = auto()   # caller specifies each person's exact share
    PERCENTAGE = auto()   # caller specifies each person's percentage


# ── Core Data Classes ──────────────────────────────────────────────────────────
# These are plain containers. They hold data and nothing else.

@dataclass
class User:
    user_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""

    def __hash__(self) -> int:
        # We need Users to be hashable so they can be dict keys
        return hash(self.user_id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and self.user_id == other.user_id

    def __repr__(self) -> str:
        return f"User({self.name!r})"


@dataclass
class ExpenseSplit:
    """One user's share of a single expense."""
    user: User
    amount_owed: float  # always positive; represents what this user owes the payer


# ── Split Strategies (Strategy pattern) ───────────────────────────────────────
# Each strategy answers the same question differently:
# "Given a total and a list of members, how much does each person owe?"

class SplitStrategy(ABC):
    @abstractmethod
    def calculate(
        self,
        total: float,
        members: List[User],
        **kwargs,
    ) -> List[ExpenseSplit]:
        """Return one ExpenseSplit per member. Amounts must sum to total."""
        ...


class EqualSplit(SplitStrategy):
    """Divide the total evenly. If ₹300 among 3 people → ₹100 each."""

    def calculate(self, total: float, members: List[User], **kwargs) -> List[ExpenseSplit]:
        if not members:
            raise ValueError("Need at least one member to split among.")
        share = round(total / len(members), 2)
        # Adjust the last split to absorb rounding difference (e.g. ₹100.01 due to float)
        splits = [ExpenseSplit(user=m, amount_owed=share) for m in members]
        diff = round(total - sum(s.amount_owed for s in splits), 2)
        splits[-1].amount_owed = round(splits[-1].amount_owed + diff, 2)
        return splits


class ExactSplit(SplitStrategy):
    """
    Caller provides a dict mapping each User to their exact share.
    Example: Alice owes ₹120, Bob owes ₹80, Charlie owes ₹100 (total ₹300).
    """

    def calculate(
        self,
        total: float,
        members: List[User],
        exact_amounts: Optional[Dict[User, float]] = None,
        **kwargs,
    ) -> List[ExpenseSplit]:
        if exact_amounts is None:
            raise ValueError("ExactSplit requires 'exact_amounts' dict.")

        provided_total = round(sum(exact_amounts.values()), 2)
        if abs(provided_total - total) > 0.01:
            raise ValueError(
                f"ExactSplit amounts sum to {provided_total}, but expense total is {total}."
            )

        return [
            ExpenseSplit(user=user, amount_owed=amount)
            for user, amount in exact_amounts.items()
        ]


class PercentageSplit(SplitStrategy):
    """
    Caller provides a dict mapping each User to their percentage share.
    Percentages must sum to 100.
    Example: Alice 50%, Bob 30%, Charlie 20%.
    """

    def calculate(
        self,
        total: float,
        members: List[User],
        percentages: Optional[Dict[User, float]] = None,
        **kwargs,
    ) -> List[ExpenseSplit]:
        if percentages is None:
            raise ValueError("PercentageSplit requires 'percentages' dict.")

        total_pct = round(sum(percentages.values()), 2)
        if abs(total_pct - 100.0) > 0.01:
            raise ValueError(
                f"Percentages must sum to 100, but got {total_pct}."
            )

        splits = []
        for user, pct in percentages.items():
            amount = round((pct / 100) * total, 2)
            splits.append(ExpenseSplit(user=user, amount_owed=amount))

        # Fix any rounding drift on the last split
        diff = round(total - sum(s.amount_owed for s in splits), 2)
        splits[-1].amount_owed = round(splits[-1].amount_owed + diff, 2)
        return splits


# ── Expense ────────────────────────────────────────────────────────────────────
# An Expense records what was spent, who paid, and how it was divided.
# It does NOT calculate splits — it delegates to a SplitStrategy.

class Expense:
    def __init__(
        self,
        description: str,
        total_amount: float,
        paid_by: User,
        strategy: SplitStrategy,
        members: List[User],
        **kwargs,
    ):
        self.expense_id = str(uuid.uuid4())
        self.description = description
        self.total_amount = total_amount
        self.paid_by = paid_by
        # Delegate split calculation to the injected strategy
        self.splits: List[ExpenseSplit] = strategy.calculate(total_amount, members, **kwargs)

    def __repr__(self) -> str:
        return f"Expense({self.description!r}, ₹{self.total_amount}, paid by {self.paid_by.name})"


# ── Group ──────────────────────────────────────────────────────────────────────
# A Group manages members and their shared expenses.
# It is the core domain object — most operations happen here.

class Group:
    def __init__(self, name: str, members: Optional[List[User]] = None):
        self.group_id = str(uuid.uuid4())
        self.name = name
        self._members: List[User] = members or []
        self._expenses: List[Expense] = []

    def add_member(self, user: User) -> None:
        if user not in self._members:
            self._members.append(user)

    def remove_member(self, user: User) -> None:
        self._members.remove(user)

    def add_expense(
        self,
        description: str,
        amount: float,
        paid_by: User,
        strategy: SplitStrategy,
        members: Optional[List[User]] = None,
        **kwargs,
    ) -> Expense:
        """
        Add a shared expense.
        'members' defaults to all group members if not specified.
        '**kwargs' are passed through to the strategy (e.g. exact_amounts, percentages).
        """
        split_among = members or self._members
        expense = Expense(description, amount, paid_by, strategy, split_among, **kwargs)
        self._expenses.append(expense)
        print(f"[{self.name}] Added: {expense}")
        return expense

    def get_balances(self) -> Dict[User, float]:
        """
        Compute net balance for every member.

        Convention:
          positive → this user is owed money (creditor)
          negative → this user owes money (debtor)

        Algorithm:
          For each expense:
            - The payer GAINS credit equal to the full amount (+total)
            - Each split user LOSES credit equal to their share (-amount_owed)
        """
        balances: Dict[User, float] = {m: 0.0 for m in self._members}

        for expense in self._expenses:
            # Payer is credited the full amount
            if expense.paid_by in balances:
                balances[expense.paid_by] += expense.total_amount
            else:
                balances[expense.paid_by] = expense.total_amount

            # Each split user is debited their share
            for split in expense.splits:
                if split.user in balances:
                    balances[split.user] -= split.amount_owed
                else:
                    balances[split.user] = -split.amount_owed

        return balances

    def settle_up(self, payer: User, payee: User, amount: float) -> None:
        """
        Record that 'payer' paid 'payee' the given amount directly.

        Trick: we model this as a special Expense where:
          - paid_by = payer  (payer gets credit for paying)
          - the only split = payee owes that amount to payer
          - after netting, payer's credit goes up and payee's debt goes down

        This means get_balances() needs zero extra logic to handle settlements.
        """
        # Use ExactSplit so the split is precisely the settled amount
        strategy = ExactSplit()
        expense = Expense(
            description=f"Settlement: {payer.name} → {payee.name}",
            total_amount=amount,
            paid_by=payer,
            strategy=strategy,
            members=[payee],
            exact_amounts={payee: amount},
        )
        self._expenses.append(expense)
        print(f"[{self.name}] Settled: {payer.name} paid {payee.name} ₹{amount:.2f}")

    def display_balances(self) -> None:
        print(f"\n── Balances in '{self.name}' ──")
        balances = self.get_balances()
        for user, amount in balances.items():
            if abs(amount) < 0.01:
                print(f"  {user.name}: settled up")
            elif amount > 0:
                print(f"  {user.name}: is owed ₹{amount:.2f}")
            else:
                print(f"  {user.name}: owes ₹{abs(amount):.2f}")


# ── DebtSimplifier ─────────────────────────────────────────────────────────────
# Takes a raw balance map and returns the minimum set of direct payments
# needed to settle all debts.

class DebtSimplifier:
    """
    Greedy algorithm:
      1. Separate users into creditors (positive balance) and debtors (negative balance).
      2. Always match the max creditor with the max debtor.
      3. The smaller of the two amounts is transacted. One of them is now settled.
      4. Repeat until everyone is at zero.

    This minimises the number of transactions.
    """

    @staticmethod
    def simplify(
        balances: Dict[User, float]
    ) -> List[Tuple[User, User, float]]:
        """
        Returns a list of (debtor, creditor, amount) tuples.
        Read as: "debtor should pay creditor that amount."
        """
        # Build two heaps:
        #   max-creditor heap: (-balance, user)  — negate for max-heap via Python's min-heap
        #   max-debtor heap:   (balance, user)   — balance is negative, so min-heap gives max debt
        creditors: List[Tuple[float, User]] = []  # max-heap via negated amounts
        debtors: List[Tuple[float, User]] = []    # min-heap (most negative = most debt)

        for user, balance in balances.items():
            if balance > 0.01:
                heapq.heappush(creditors, (-balance, user))  # negate for max-heap
            elif balance < -0.01:
                heapq.heappush(debtors, (balance, user))     # already negative

        transactions: List[Tuple[User, User, float]] = []

        while creditors and debtors:
            max_credit_neg, creditor = heapq.heappop(creditors)
            max_credit = -max_credit_neg          # undo negation
            max_debt_neg, debtor = heapq.heappop(debtors)
            max_debt = -max_debt_neg              # max_debt is positive amount owed

            # The transaction amount is the smaller of what the creditor is owed
            # and what the debtor owes
            transaction_amount = round(min(max_credit, max_debt), 2)
            transactions.append((debtor, creditor, transaction_amount))

            remaining_credit = round(max_credit - transaction_amount, 2)
            remaining_debt   = round(max_debt - transaction_amount, 2)

            # Push back whoever still has an outstanding balance
            if remaining_credit > 0.01:
                heapq.heappush(creditors, (-remaining_credit, creditor))
            if remaining_debt > 0.01:
                heapq.heappush(debtors, (-remaining_debt, debtor))

        return transactions


# ── SplitwiseService (facade) ──────────────────────────────────────────────────
# External code calls SplitwiseService. It never touches Group internals directly.

class SplitwiseService:
    def __init__(self):
        self._users: Dict[str, User] = {}
        self._groups: Dict[str, Group] = {}
        self._simplifier = DebtSimplifier()

    def add_user(self, name: str, email: str = "") -> User:
        user = User(name=name, email=email)
        self._users[user.user_id] = user
        return user

    def create_group(self, name: str, members: List[User]) -> Group:
        group = Group(name=name, members=list(members))
        self._groups[group.group_id] = group
        print(f"[SplitwiseService] Group created: '{name}' with {[m.name for m in members]}")
        return group

    def show_simplified_debts(self, group: Group) -> None:
        balances = group.get_balances()
        transactions = self._simplifier.simplify(balances)
        print(f"\n── Simplified debts for '{group.name}' ──")
        if not transactions:
            print("  Everyone is settled up!")
        for debtor, creditor, amount in transactions:
            print(f"  {debtor.name} should pay {creditor.name} ₹{amount:.2f}")


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    service = SplitwiseService()

    # Create three friends
    alice   = service.add_user("Alice",   "alice@example.com")
    bob     = service.add_user("Bob",     "bob@example.com")
    charlie = service.add_user("Charlie", "charlie@example.com")

    # Create a group for their trip
    trip = service.create_group("Trip to Goa", [alice, bob, charlie])

    # Expense 1: Alice pays ₹300 for dinner — split equally
    trip.add_expense(
        description="Dinner",
        amount=300,
        paid_by=alice,
        strategy=EqualSplit(),
    )

    # Expense 2: Bob pays ₹200 for taxi — split equally
    trip.add_expense(
        description="Taxi",
        amount=200,
        paid_by=bob,
        strategy=EqualSplit(),
    )

    # Expense 3: Charlie pays ₹150 for drinks — exact split
    trip.add_expense(
        description="Drinks",
        amount=150,
        paid_by=charlie,
        strategy=ExactSplit(),
        exact_amounts={alice: 80, bob: 40, charlie: 30},
    )

    # Show raw balances
    trip.display_balances()

    # Show simplified debt transactions
    service.show_simplified_debts(trip)

    # Bob settles up with Alice
    trip.settle_up(payer=bob, payee=alice, amount=80)
    print("\nAfter Bob settles with Alice:")
    trip.display_balances()
    service.show_simplified_debts(trip)
```

---

## Step-by-step walkthrough

```python
alice = service.add_user("Alice", "alice@example.com")
bob   = service.add_user("Bob",   "bob@example.com")
charlie = service.add_user("Charlie", "charlie@example.com")
trip = service.create_group("Trip to Goa", [alice, bob, charlie])
```
Three `User` objects are created and stored. A `Group` is created with all three as members. No balances yet — the balance map is computed on demand, not stored.

```python
trip.add_expense("Dinner", 300, paid_by=alice, strategy=EqualSplit())
```
- `EqualSplit.calculate(300, [alice, bob, charlie])` runs.
- Each person's share is `300 / 3 = ₹100`.
- Three `ExpenseSplit` objects are produced: `(alice, 100)`, `(bob, 100)`, `(charlie, 100)`.
- An `Expense` is created and appended to `trip._expenses`.

**What just happened?** Alice has paid ₹300 but only owes ₹100 of it herself, so she is owed ₹200 net from this expense. Bob and Charlie each owe ₹100.

```python
trip.add_expense("Taxi", 200, paid_by=bob, strategy=EqualSplit())
```
- Bob pays ₹200, split equally → each person owes `₹66.67` (with rounding adjustment).
- After this expense, Bob is owed back some of the ₹200 he laid out.

```python
trip.add_expense("Drinks", 150, paid_by=charlie, strategy=ExactSplit(),
                 exact_amounts={alice: 80, bob: 40, charlie: 30})
```
- `ExactSplit.calculate(150, ..., exact_amounts=...)` verifies `80 + 40 + 30 = 150`. Passes.
- Three splits are created with exact amounts.

**What just happened?** Three expenses are recorded. `get_balances()` now has enough data to compute a net position for each person.

```python
trip.display_balances()
```
Calls `get_balances()`, which walks every expense and builds a running total:

| Step | Alice | Bob | Charlie |
|---|---|---|---|
| Dinner: Alice pays ₹300 | +300 | 0 | 0 |
| Dinner splits (₹100 each) | -100 | -100 | -100 |
| Taxi: Bob pays ₹200 | 0 | +200 | 0 |
| Taxi splits (~₹66.67 each) | -66.67 | -66.67 | -66.67 |
| Drinks: Charlie pays ₹150 | 0 | 0 | +150 |
| Drinks splits (80/40/30) | -80 | -40 | -30 |
| **Net** | **+53.33** | **-6.67** | **-46.67** |

Alice is owed ₹53.33. Bob owes ₹6.67. Charlie owes ₹46.67.

```python
service.show_simplified_debts(trip)
```
The simplifier runs the greedy algorithm: match max creditor (Alice, +53.33) with max debtor (Charlie, -46.67). Charlie pays Alice ₹46.67. Charlie is settled. Alice's remaining credit is ₹6.67. Now match Alice (+6.67) with Bob (-6.67). Bob pays Alice ₹6.67. Done. **Two transactions instead of potentially three.**

---

## Common interview mistakes

1. **Not validating ExactSplit sums** — If `exact_amounts` adds up to ₹290 on a ₹300 expense, ₹10 silently vanishes. Always check and raise a `ValueError`.

2. **Getting the balance direction wrong** — The most common bug. The payer should receive a **credit** (positive). The split users incur a **debit** (negative). Reversing either one means your balance map is wrong in both direction and sign.

3. **Embedding split logic inside `Expense.__init__`** — A big `if split_type == EQUAL / EXACT / PERCENTAGE` block inside `Expense` means every new split type requires editing `Expense`. Strategy pattern keeps this extensible.

4. **No debt simplification** — Showing raw balances is correct but wasteful. If Alice owes Bob ₹100 and Bob owes Charlie ₹100, that is two payments. Simplified, Alice just pays Charlie ₹100. Interviewers expect you to know this.

5. **Treating settle-up as a special case** — Building a separate `settlements` list and adding extra logic to `get_balances()` to handle it. Instead, model a settlement as a regular expense (as shown above) and the balance logic stays clean and unified.

---

## Key patterns used

- **Strategy** — `SplitStrategy` lets you add new split types without touching `Expense`
- **Facade** — `SplitwiseService` is the single public entry point; callers never touch `Group` internals
- **Value Object** — `ExpenseSplit` is a pure data container (no behaviour), making it easy to reason about
- **Single Responsibility** — `Expense` stores what was spent, `SplitStrategy` calculates shares, `Group` tracks balances, `DebtSimplifier` minimises transactions
- **Open/Closed Principle** — add `ShareBasedSplit` by subclassing `SplitStrategy`; zero changes to existing classes


---

[← Back to Marketplace / Matching Template](template.md)
