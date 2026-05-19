# Template 02: State Machine

> Think of a vending machine. It can be **idle**, **waiting for money**, **dispensing a snack**, or **returning change**. It flows through these stages in a specific order — and you can't jump straight from "idle" to "dispensing" without putting money in first. That's a state machine.

---

## 1. What is the State Machine Template?

A **state machine** models an object that has a **lifecycle** — it moves through well-defined stages, and not every move between stages is allowed.

In plain English:
- The object is **always in exactly one state** at any given time.
- It can **transition** to another state, but only if that move is allowed.
- Something **triggers** the transition — a button press, a payment, a timeout, a user action.
- When a transition happens, **actions** may fire (send an email, log an event, update a database).

If you've ever tracked an online order — PENDING → CONFIRMED → SHIPPED → DELIVERED — you've used a state machine without knowing it.

---

## 2. How to Recognise This Template

Look for these **signal words** in the problem statement:

| Signal word | What it implies |
|---|---|
| "status", "state" | The object has a lifecycle |
| "transition", "flow" | Moves between stages are defined |
| "lifecycle", "stage", "process" | Ordered progression |
| "can only ... after ..." | Transition rules / guards |
| "invalid operation" | Some actions are forbidden in certain states |

**Rule of thumb:** If you find yourself drawing boxes and arrows to describe how an object behaves over time, reach for the State Machine template.

---

## 3. Real-World Examples

| System | States | Example Transition |
|---|---|---|
| ATM | IDLE → PIN_ENTRY → TRANSACTION → DISPENSING → IDLE | Card inserted triggers PIN_ENTRY |
| Vending Machine | IDLE → WAITING_PAYMENT → DISPENSING → CHANGE | Money inserted triggers WAITING_PAYMENT |
| Order Lifecycle | PENDING → CONFIRMED → SHIPPED → DELIVERED | Seller confirms order |
| Elevator | IDLE → MOVING → DOOR_OPEN → DOOR_CLOSED | Floor button pressed |
| Traffic Light | RED → GREEN → YELLOW → RED | Timer expires |
| Support Ticket | OPEN → IN_PROGRESS → RESOLVED (or CLOSED) | Agent picks up ticket |

---

## 4. Core Building Blocks

### States
> Think of floors in a building. An elevator is always on exactly one floor — it's never "between" floors from the system's perspective. States are the same: the object is always in exactly one state.

States are the **stages** your object can be in. You model them as an `Enum` so they're named, not magic strings.

```python
from enum import Enum, auto

class OrderStatus(Enum):
    PENDING   = auto()
    CONFIRMED = auto()
    SHIPPED   = auto()
    DELIVERED = auto()
    CANCELLED = auto()
```

### Transitions
> Think of one-way streets. You can drive from A to B, but not necessarily from B back to A. Transitions are the allowed one-way moves between states.

Transitions are **rules** — a map of "from this state, you may go to these states". They stop you from doing impossible things like shipping a cancelled order.

```python
VALID_TRANSITIONS = {
    OrderStatus.PENDING:   {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.SHIPPED,   OrderStatus.CANCELLED},
    OrderStatus.SHIPPED:   {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),   # terminal state — no further moves
    OrderStatus.CANCELLED: set(),   # terminal state — no further moves
}
```

### Events / Triggers
> Think of a doorbell. Ringing the bell (event) causes the door to open (transition). Without the bell, the door stays closed.

Events are **what causes a transition** — a method call, a button press, a payment received, a timer firing. In code, these often become methods on your class (`confirm()`, `ship()`, `cancel()`).

### Actions
> Think of a notification SMS. When your order ships, you get a text. That SMS is an action — a side effect that fires when entering (or exiting) a state.

Actions are **what happens during a transition** — log an event, send an email, update a timestamp, charge a card. You hook them into `on_enter()` or `on_exit()` methods.

---

## 5. Two Implementation Approaches

### Approach A: Enum + Transition Dict (Simpler — preferred for interviews)

This approach keeps everything in one class. It's easy to read, easy to explain, and fast to write under interview pressure.

The idea: store allowed transitions in a dictionary. Before every state change, look up whether the move is legal.

```python
from enum import Enum, auto

class OrderStatus(Enum):
    PENDING   = auto()
    CONFIRMED = auto()
    SHIPPED   = auto()
    DELIVERED = auto()
    CANCELLED = auto()

# The rulebook: from each state, which states can you go to?
VALID_TRANSITIONS = {
    OrderStatus.PENDING:   {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.SHIPPED,   OrderStatus.CANCELLED},
    OrderStatus.SHIPPED:   {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}

class Order:
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.status   = OrderStatus.PENDING   # always start in initial state

    def transition_to(self, new_status: OrderStatus) -> None:
        if new_status not in VALID_TRANSITIONS[self.status]:
            raise ValueError(
                f"Cannot move from {self.status.name} to {new_status.name}"
            )
        print(f"Order {self.order_id}: {self.status.name} → {new_status.name}")
        self.status = new_status
        self._on_enter(new_status)

    def _on_enter(self, status: OrderStatus) -> None:
        """Hook: runs every time we enter a new state."""
        if status == OrderStatus.SHIPPED:
            print(f"  [Action] Sending shipping notification for order {self.order_id}")
        elif status == OrderStatus.DELIVERED:
            print(f"  [Action] Order {self.order_id} marked complete. Requesting review.")

    # Convenience methods — cleaner API for callers
    def confirm(self):   self.transition_to(OrderStatus.CONFIRMED)
    def ship(self):      self.transition_to(OrderStatus.SHIPPED)
    def deliver(self):   self.transition_to(OrderStatus.DELIVERED)
    def cancel(self):    self.transition_to(OrderStatus.CANCELLED)
```

**Usage:**

```python
order = Order("ORD-001")
order.confirm()   # PENDING → CONFIRMED
order.ship()      # CONFIRMED → SHIPPED  (also fires shipping notification)
order.cancel()    # raises ValueError — can't cancel a shipped order
```

> **What just happened?**
> `transition_to()` is the gatekeeper. It checks the rulebook (`VALID_TRANSITIONS`) before allowing any move. If the move is illegal, it raises an error immediately. If the move is legal, it updates the state and fires any `on_enter` actions. Every state change goes through this one method — nothing bypasses it.

---

### Approach B: State Pattern (More OOP — better for complex per-state behaviour)

Use this when each state has **significantly different behaviour** — not just different data, but different logic. For example, an ATM in `IDLE` state ignores button presses, but in `TRANSACTION` state it processes them differently.

The idea: each state becomes its own class with a `handle()` method. The context object delegates behaviour to the current state object.

```python
from abc import ABC, abstractmethod

class TicketState(ABC):
    """Base class. Every concrete state must implement handle()."""

    @abstractmethod
    def handle(self, ticket, action: str) -> None:
        pass

    def __str__(self):
        return self.__class__.__name__


class OpenState(TicketState):
    def handle(self, ticket, action: str) -> None:
        if action == "assign":
            print("Ticket assigned. Moving to IN_PROGRESS.")
            ticket.set_state(InProgressState())
        else:
            print(f"Action '{action}' not valid in OPEN state.")


class InProgressState(TicketState):
    def handle(self, ticket, action: str) -> None:
        if action == "resolve":
            print("Ticket resolved.")
            ticket.set_state(ResolvedState())
        elif action == "reopen":
            print("Ticket reopened.")
            ticket.set_state(OpenState())
        else:
            print(f"Action '{action}' not valid in IN_PROGRESS state.")


class ResolvedState(TicketState):
    def handle(self, ticket, action: str) -> None:
        print("Ticket is resolved. No further actions allowed.")


class SupportTicket:
    """The context — holds the current state and delegates to it."""

    def __init__(self, ticket_id: str):
        self.ticket_id   = ticket_id
        self._state: TicketState = OpenState()   # initial state

    def set_state(self, state: TicketState) -> None:
        print(f"  [Transition] {self._state} → {state}")
        self._state = state

    def perform(self, action: str) -> None:
        self._state.handle(self, action)

    @property
    def current_state(self) -> str:
        return str(self._state)
```

**Usage:**

```python
ticket = SupportTicket("TKT-42")
ticket.perform("assign")    # OPEN → IN_PROGRESS
ticket.perform("resolve")   # IN_PROGRESS → RESOLVED
ticket.perform("assign")    # "No further actions allowed"
```

> **What just happened?**
> The ticket itself doesn't contain any `if/elif` logic for states. Instead, it delegates to the current state object. Adding a new state means adding a new class — you never touch the existing ones. This is the **Open/Closed Principle** in action: open for extension, closed for modification.

---

### When to choose which?

| Factor | Enum + Dict (Approach A) | State Pattern (Approach B) |
|---|---|---|
| Interview time pressure | Fast to write | Slower, more setup |
| Per-state logic | Minimal | Complex, varies a lot |
| Number of states | Any | Works best with many |
| Adding new states | Edit the dict | Add a new class |
| Readability | Very clear | More indirection |

**Default recommendation for interviews: Approach A.** Only reach for Approach B if the interviewer asks "how would you handle complex per-state behaviour?" or the problem clearly needs it.

---

## 6. Generic Skeleton Code

Copy this skeleton and adapt it for any LLD problem with a lifecycle.

```python
from enum import Enum, auto
from typing import Set, Dict

# ─── 1. Define all possible states ────────────────────────────────────────────
class State(Enum):
    INITIAL     = auto()   # starting state
    STATE_A     = auto()   # intermediate state
    STATE_B     = auto()   # intermediate state
    TERMINAL    = auto()   # end state — no transitions out

# ─── 2. Define the transition rulebook ────────────────────────────────────────
# Key   = current state
# Value = set of states you are allowed to move to from here
VALID_TRANSITIONS: Dict[State, Set[State]] = {
    State.INITIAL:  {State.STATE_A, State.TERMINAL},
    State.STATE_A:  {State.STATE_B, State.TERMINAL},
    State.STATE_B:  {State.TERMINAL},
    State.TERMINAL: set(),   # terminal — no exits
}

# ─── 3. The entity that carries the state ─────────────────────────────────────
class StatefulEntity:
    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self.state     = State.INITIAL   # always set an explicit initial state

    # ── Core method: the only way to change state ──────────────────────────────
    def transition_to(self, new_state: State) -> None:
        """
        Validates the transition, updates state, and fires on_enter hook.
        This is the single gatekeeper — no other code should set self.state directly.
        """
        if new_state not in VALID_TRANSITIONS[self.state]:
            raise ValueError(
                f"[{self.entity_id}] Invalid transition: "
                f"{self.state.name} → {new_state.name}"
            )
        old_state  = self.state
        self.state = new_state
        print(f"[{self.entity_id}] {old_state.name} → {new_state.name}")
        self.on_enter(new_state)

    # ── Hook: override this to add side effects on state entry ─────────────────
    def on_enter(self, state: State) -> None:
        """
        Called every time we enter a new state.
        Override to send notifications, log events, trigger payments, etc.
        """
        pass   # default: do nothing

    # ── Convenience methods: one per business-level event ─────────────────────
    def advance(self):  self.transition_to(State.STATE_A)
    def finish(self):   self.transition_to(State.TERMINAL)
```

> **What just happened?**
> This skeleton gives you three separation points: the **states** (enum), the **rules** (dict), and the **behaviour** (class). In an interview, fill in the enum first, draw the transitions, fill in the dict, then add business methods. You'll have a working state machine in about 5 minutes.

---

## 7. State Transition Diagram

**Always draw this before writing any code in an interview.** It forces you to enumerate all states and transitions upfront, catches missing edge cases, and shows the interviewer you think before you code.

Here is the format to use:

```
[PENDING] --confirm--> [CONFIRMED] --ship--> [SHIPPED] --deliver--> [DELIVERED]
    |                       |
  cancel                  cancel
    v                       v
[CANCELLED]            [CANCELLED]
```

For a support ticket:

```
[OPEN] --assign--> [IN_PROGRESS] --resolve--> [RESOLVED]
                        |
                      reopen
                        v
                      [OPEN]
```

**How to draw it step by step:**

1. List every state as a box `[STATE_NAME]`
2. Draw arrows for every allowed transition, label the arrow with the trigger
3. Circle or double-box terminal states (no arrows leaving them)
4. Check: is there any state with no way out except terminal? That might be a missing transition.

**Saying this out loud in an interview:**

> "Let me draw the state diagram first. We have these states: ... and these transitions: ... DELIVERED and CANCELLED are terminal states — once you're there, you can't go anywhere else. Does that match what you had in mind?"

---

## 8. Design Patterns Used

| Pattern | Where it appears | Why |
|---|---|---|
| **State Pattern** | Approach B (per-state classes) | Encapsulates state-specific behaviour, removes conditionals from the context class |
| **Template Method** | `on_enter()` hook in the skeleton | Defines the skeleton of the transition algorithm; subclasses fill in the side effects |
| **Strategy** | Each concrete state in Approach B | Each state is an interchangeable behaviour that the context delegates to |
| **Enum + Dictionary** | Approach A transition rulebook | Simple data-driven rules; easy to read and modify without touching behaviour |

---

## 9. Key Design Decisions to Explain in an Interview

### Enum + dict vs State pattern — when to choose?

> "I'd default to Enum + dict for this problem because the per-state logic is minimal — just different data, not different behaviour. If each state needed to do very different things (like an ATM where each state handles button presses differently), I'd reach for the State pattern."

### Where to put transition logic — in the entity or in a service?

- **In the entity** (`Order.transition_to()`): Simpler, self-contained. Good for most interview problems.
- **In a service** (`OrderService.transition(order, new_status)`): Better when multiple entity types share transition logic, or when you need to apply business rules that span multiple objects (e.g., check inventory before shipping).

> "I've put the logic in the entity for now to keep things simple. In a production system, I'd consider moving it to an `OrderService` so the entity stays a plain data holder and the service handles orchestration."

### How to handle invalid transitions — raise exception or return bool?

- **Raise `ValueError`**: Clear, forces the caller to handle errors explicitly. Preferred.
- **Return `False`**: Softer, but callers can silently ignore it. Avoid unless the problem specifically asks for it.

> "I'm raising a `ValueError` on invalid transitions. In a REST API, this would map to a 400 Bad Request with a clear error message."

### How to add side effects on transition (e.g., send email when order ships)?

Three options, from simple to complex:

1. **`on_enter()` hook** — put side effects directly in the hook (good for simple cases)
2. **Observer / Event Bus** — emit an event on transition, let subscribers handle it (good for many side effects or when you want decoupling)
3. **Callback list** — register callbacks per state (good for dynamic, configurable behaviour)

> "I've used the `on_enter()` hook here. In a real system, I'd emit a domain event like `OrderShippedEvent` and let separate handlers (email, analytics, inventory) react to it. That keeps the Order class unaware of notification logic."

### How to persist state in a database?

- Store the **enum value as a string** (not integer) so it's readable in the DB: `order.status = "SHIPPED"`
- On load, convert back: `OrderStatus[row["status"]]`
- Wrap the transition + DB write in a **transaction** — never update the state in memory without persisting it atomically.

> "I'd store the status as a VARCHAR in the database. When loading an order, I'd convert the string back to the enum. The `transition_to()` call would be wrapped in a DB transaction so the state in memory and in the database are always in sync."

---

## 10. Problems Using This Template

- [Elevator System](elevator_system.md)

---

## 11. Common Mistakes

### Mistake 1: Allowing direct state assignment

```python
# BAD — bypasses all validation
order.status = OrderStatus.SHIPPED

# GOOD — goes through the gatekeeper
order.transition_to(OrderStatus.SHIPPED)
```

Make `status` a private attribute (`_status`) and expose only `transition_to()`. This way, no code can bypass your rules.

### Mistake 2: Not defining valid transitions upfront

Checking transitions with a long `if/elif` chain is fragile and easy to get wrong. Define the rulebook as data (a dict) once, and let `transition_to()` consult it. Adding a new state means adding one line to the dict — not hunting through conditionals.

### Mistake 3: Forgetting terminal states

Every lifecycle has end states — DELIVERED, CANCELLED, RESOLVED, CLOSED. These states have **no valid outgoing transitions** (`set()`). If you forget to define them, you might accidentally allow transitions like DELIVERED → PENDING.

```python
# Always explicitly define terminal states
OrderStatus.DELIVERED: set(),   # nothing goes out from here
OrderStatus.CANCELLED: set(),
```

### Mistake 4: Mixing state logic with business logic in the same method

Avoid doing too much in `transition_to()`:

```python
# BAD — too much responsibility in one place
def transition_to(self, new_status):
    if new_status not in VALID_TRANSITIONS[self.status]:
        raise ValueError(...)
    self.status = new_status
    send_email(self)           # side effect crammed in here
    charge_card(self)          # another side effect
    update_inventory(self)     # and another
```

Keep `transition_to()` focused on the transition itself. Use `on_enter()` or domain events for side effects.

### Mistake 5: Not naming your initial state explicitly

Always set an explicit initial state in `__init__`. Never rely on `None` or assume the first enum value is the default. Explicit is always better than implicit, especially in an interview where clarity counts.

```python
# BAD
self.status = None

# GOOD
self.status = OrderStatus.PENDING   # clear, intentional, named
```
