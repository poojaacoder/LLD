# 13. LLD Interview Patterns

## What is this?

This file is your practical toolkit for tackling Low-Level Design interviews. It covers a repeatable step-by-step process for modeling any problem, Python tools that come up constantly in LLD (enums, dependency injection, template method), and a cheatsheet you can study before an interview.

---

## The 5-Step Modeling Checklist

Before writing a single line of code in an LLD interview, walk through this checklist. Interviewers reward structured thinking over rushing to code.

> Think of designing a system like building a house. An architect doesn't start swinging a hammer — they draw a blueprint first. This checklist is your blueprint process.

### Step 1: Identify Entities (Nouns → Classes)

Read the problem statement and circle every noun. Each meaningful noun is likely a class.

**Example — "Design a Parking Lot":**
- Parking Lot, Floor, Spot, Vehicle, Car, Motorcycle, Truck, Ticket, Payment

Each of those becomes a class. Don't worry about perfecting them — you'll refine as you go.

### Step 2: Identify Behaviors (Verbs → Methods)

Now look at verbs and actions. What does each entity *do* or *have done to it*?

**Example:**
- Parking Lot: `park(vehicle)`, `exit(ticket)`, `display_availability()`
- Spot: `park(vehicle)`, `vacate()`, `can_fit(vehicle)`
- Ticket: `close()`, compute `duration_hours`

These become methods on their respective classes.

### Step 3: Identify Relationships (IS-A vs HAS-A)

This step decides whether you use **inheritance** or **composition**.

| Relationship type | Question to ask | Use |
|---|---|---|
| IS-A | Is a Car always a Vehicle? | Inheritance |
| HAS-A | Does a ParkingLot have Floors? | Composition |
| IS-A (interface) | Does a Car need to support `park()`? | Abstract class / Protocol |

**Red flag:** If your "IS-A" relationship is really just "sometimes acts like", use composition instead.

### Step 4: Define Interfaces First

Before writing concrete classes, ask: "What can this entity DO?" Write abstract methods first. This forces you to think about contracts before implementations — and makes your code swappable.

```python
# Define what a pricing calculator must do — before deciding HOW
from abc import ABC, abstractmethod

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, ticket) -> float: ...
```

This means the `ParkingLot` can be written and tested before you've decided on hourly vs flat-rate pricing.

### Step 5: Apply SOLID — Especially SRP and DIP

Before writing code, quickly check:
- **SRP:** Does each class have ONE clear reason to exist? If a class does data storage AND sends emails AND generates reports, split it.
- **DIP:** Do high-level classes depend on abstractions (protocols/ABCs), not concrete classes? If `ParkingLot` directly creates a `MySQLDatabase`, that's a problem — inject it instead.

### Step 6: Add Enums for States

Any time your objects can be in different "states" (pending, confirmed, cancelled), use an Enum. This prevents bugs from magic strings like `if status == "cancled":` (typo!).

```python
from enum import Enum, auto

class OrderStatus(Enum):
    PENDING = auto()
    CONFIRMED = auto()
    CANCELLED = auto()
```

---

## Enums for State Machines

A state machine is a model where an object moves through a fixed set of states, and only specific transitions between states are valid. Enums make state machines clean and safe.

> Think of a package delivery. A package can go: Order Placed → Shipped → Out for Delivery → Delivered. It should never jump from "Order Placed" directly to "Delivered", and a "Delivered" package can't become "Shipped" again. Enforcing these rules is what a state machine does.

The `VALID_TRANSITIONS` dictionary is the heart of this pattern. It's a map from "current state" to "the set of states I'm allowed to move to."

```python
from enum import Enum, auto

class OrderStatus(Enum):
    PENDING   = auto()
    CONFIRMED = auto()
    SHIPPED   = auto()
    DELIVERED = auto()
    CANCELLED = auto()

class Order:
    # Single source of truth for what transitions are allowed
    VALID_TRANSITIONS = {
        OrderStatus.PENDING:   {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
        OrderStatus.CONFIRMED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
        OrderStatus.SHIPPED:   {OrderStatus.DELIVERED},
        OrderStatus.DELIVERED: set(),   # terminal state — no further transitions
        OrderStatus.CANCELLED: set(),   # terminal state
    }

    def __init__(self, order_id: str):
        self.order_id = order_id
        self.status = OrderStatus.PENDING  # all orders start here

    def transition_to(self, new_status: OrderStatus) -> None:
        allowed = self.VALID_TRANSITIONS[self.status]
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {self.status.name} to {new_status.name}"
            )
        self.status = new_status
        print(f"Order {self.order_id}: {self.status.name}")


order = Order("ORD-001")
order.transition_to(OrderStatus.CONFIRMED)   # OK
order.transition_to(OrderStatus.SHIPPED)     # OK

try:
    order.transition_to(OrderStatus.PENDING) # Error! Can't go back
except ValueError as e:
    print(e)  # Cannot transition from SHIPPED to PENDING
```

### Valid Transitions Table (for reference)

| From | Can go to |
|---|---|
| PENDING | CONFIRMED, CANCELLED |
| CONFIRMED | SHIPPED, CANCELLED |
| SHIPPED | DELIVERED |
| DELIVERED | (nothing — final state) |
| CANCELLED | (nothing — final state) |

> **Key takeaway:** The `VALID_TRANSITIONS` dict lives in ONE place. If business rules change ("actually, confirmed orders can be refunded and go back to pending"), you update one dict, not scattered `if` statements across the codebase.

---

## Dependency Injection Container

Dependency Injection (DI) means: instead of a class creating its own dependencies, those dependencies are provided (injected) from the outside. This makes classes independently testable and swappable.

> Think of a restaurant kitchen. Instead of each cook buying their own ingredients, the restaurant has a pantry. Cooks ask the pantry for what they need. Swapping the pantry supplier (from local farm to wholesale) doesn't change how any cook works.

A **DI container** is that pantry. It knows how to create everything and hands it out on request.

```python
class Container:
    def __init__(self):
        self._factories: dict = {}    # how to create each thing
        self._singletons: dict = {}   # cache for singleton instances

    def register(self, interface, factory, singleton: bool = False) -> None:
        """
        Register a factory function for an interface.
        - interface: the key (usually a class or string)
        - factory: a callable that creates the instance (lambda or function)
        - singleton: if True, only create it once and reuse
        """
        self._factories[interface] = (factory, singleton)

    def resolve(self, interface):
        """Ask the container for an instance of the given interface."""
        if interface not in self._factories:
            raise KeyError(f"No registration for {interface}")
        factory, is_singleton = self._factories[interface]
        if is_singleton:
            # Create it once, then cache it
            if interface not in self._singletons:
                self._singletons[interface] = factory()
            return self._singletons[interface]
        # Non-singleton: create a fresh instance every time
        return factory()


# Example: wiring up a user service with a database
class InMemoryDB:
    def query(self, sql: str) -> list: return []
    def execute(self, sql: str) -> None: pass

class UserService:
    def __init__(self, db):
        self.db = db
    def get_users(self) -> list:
        return self.db.query("SELECT * FROM users")


container = Container()

# Register the DB as a singleton — same connection shared everywhere
container.register("db", lambda: InMemoryDB(), singleton=True)

# Register UserService — gets the DB injected automatically
container.register(
    "user_service",
    lambda: UserService(container.resolve("db"))
)

# Usage — callers never call InMemoryDB() directly
svc = container.resolve("user_service")
print(svc.get_users())   # []

# The DB is a singleton — you get the same object each time
db1 = container.resolve("db")
db2 = container.resolve("db")
print(db1 is db2)   # True
```

> **Key takeaway:** With a container, swapping the database for a real MySQL implementation means changing ONE registration line — not hunting through all the code that creates `UserService`.

---

## Template Method Pattern

The Template Method pattern defines the **skeleton** of an algorithm in a base class, leaving specific steps to be filled in by subclasses. The overall order of steps is fixed; only the details change.

> Think of a recipe for making a sandwich. The steps are always the same: get bread, add filling, close the sandwich. The base "recipe" doesn't change. What changes is the filling — ham for one person, cheese for another. Each person "fills in" the filling step differently.

```python
from abc import ABC, abstractmethod

class DataProcessor(ABC):
    """
    Template method: process() defines the fixed algorithm skeleton.
    Subclasses implement the individual steps.
    """

    # The template method — callers use this
    def process(self, data: list) -> list:
        data = self.read(data)       # step 1: read
        data = self.transform(data)  # step 2: transform
        data = self.validate(data)   # step 3: validate (has a default)
        self.save(data)              # step 4: save
        return data

    @abstractmethod
    def read(self, data: list) -> list: ...

    @abstractmethod
    def transform(self, data: list) -> list: ...

    # This step has a default implementation — subclasses can override it
    def validate(self, data: list) -> list:
        # Default: filter out None values
        return [d for d in data if d is not None]

    @abstractmethod
    def save(self, data: list) -> None: ...


# A CSV-specific processor — fills in the missing steps
class CSVProcessor(DataProcessor):
    def read(self, data: list) -> list:
        print("Reading CSV data")
        return data

    def transform(self, data: list) -> list:
        # Convert everything to uppercase strings
        return [str(d).upper() for d in data]

    def save(self, data: list) -> None:
        print(f"Saving {len(data)} rows to CSV file")


# A JSON-specific processor — same skeleton, different details
class JSONProcessor(DataProcessor):
    def read(self, data: list) -> list:
        print("Parsing JSON data")
        return data

    def transform(self, data: list) -> list:
        return [{"value": d} for d in data]

    def validate(self, data: list) -> list:
        # Override the default: also filter out empty dicts
        return [d for d in data if d and d.get("value") is not None]

    def save(self, data: list) -> None:
        print(f"Writing {len(data)} objects to JSON file")


csv = CSVProcessor()
csv.process(["hello", None, "world"])
# Reading CSV data
# Saving 2 rows to CSV file  (None was filtered out)
```

> **Key takeaway:** The ORDER of steps is fixed in the base class. Subclasses can't accidentally reorder them. This is different from Strategy — in Strategy, the whole algorithm is swapped; in Template Method, only specific steps are overridden.

---

## The LLD Problem-Solving Template

Use this skeleton at the start of every LLD interview. Copy it mentally, then fill in the specific classes for the problem at hand.

```python
from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import uuid


# ── 1. Enums for all states and types ─────────────────────────────────────────
# Use enums whenever there are fixed categories or states
class Status(Enum):
    PENDING   = auto()
    ACTIVE    = auto()
    COMPLETED = auto()
    CANCELLED = auto()


# ── 2. Value Objects — simple, immutable data holders ─────────────────────────
# Use frozen dataclasses for things like addresses, coordinates, money
@dataclass(frozen=True)
class Address:
    street: str
    city: str
    country: str


# ── 3. Core Entities — mutable, own their business rules ──────────────────────
class Entity:
    def __init__(self, name: str):
        self.id = uuid.uuid4().hex[:8]   # always auto-generate IDs
        self.name = name
        self.status = Status.PENDING
        self.created_at = datetime.now()

    def some_action(self) -> None:
        # Pattern: validate → mutate → (optionally notify observers)
        if self.status != Status.PENDING:
            raise ValueError("Can only act on PENDING entities")
        self.status = Status.ACTIVE


# ── 4. Interfaces / Abstract Base Classes ─────────────────────────────────────
# Define WHAT a thing can do before deciding HOW
class Repository(ABC):
    @abstractmethod
    def save(self, entity: Entity) -> None: ...

    @abstractmethod
    def find_by_id(self, entity_id: str) -> Optional[Entity]: ...

    @abstractmethod
    def find_all(self) -> List[Entity]: ...


# ── 5. Pluggable Strategies / Policies ────────────────────────────────────────
# Any behavior that might change: pricing, sorting, routing, validation
class PricingPolicy(ABC):
    @abstractmethod
    def calculate(self, entity: Entity) -> float: ...


class StandardPricing(PricingPolicy):
    def calculate(self, entity: Entity) -> float:
        return 100.0  # placeholder


# ── 6. Service / Facade — the use-case orchestrator ───────────────────────────
# High-level class that coordinates entities using injected dependencies
class DomainService:
    def __init__(self, repo: Repository, policy: PricingPolicy):
        self._repo = repo      # injected — not created here
        self._policy = policy  # injected — swappable

    def create(self, name: str) -> Entity:
        # Standard pattern: validate → create → persist → return
        entity = Entity(name)
        self._repo.save(entity)
        return entity

    def process(self, entity_id: str) -> float:
        entity = self._repo.find_by_id(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id!r} not found")
        entity.some_action()
        fee = self._policy.calculate(entity)
        self._repo.save(entity)
        return fee
```

### How to use this template

1. Start with Step 1 (enums) — fills in the `Status` class
2. Ask yourself: what are the "value objects" (things that are never mutated, just compared)? Those become `@dataclass(frozen=True)`
3. What are the entities (things that change state over their lifetime)? Those become core classes with methods
4. For each entity, ask: "what must it be able to do?" → that's your abstract interface
5. For any behavior that might change per requirement (pricing, routing, sorting) → make it a `Strategy`
6. Write a `Service` class at the end that orchestrates everything and takes dependencies via `__init__`

---

## Class Relationships Cheatsheet

Understanding how classes relate to each other is critical for LLD. There are four main types of relationship.

### Association — "uses"

One class uses another, but neither owns nor is responsible for the other's lifetime. They're just connected.

> Two coworkers collaborate on a project. When the project ends, they both continue to exist independently.

```python
class Driver:
    def __init__(self, name: str):
        self.name = name

    def drive(self, car: "Car") -> str:
        # Driver uses a Car, but doesn't own it
        return f"{self.name} driving {car.model}"

class Car:
    def __init__(self, model: str):
        self.model = model

# Both exist independently; driver.drive() just receives a car temporarily
driver = Driver("Alice")
car = Car("Tesla")
driver.drive(car)
```

**Python representation:** Car passed as a parameter to a method.

---

### Aggregation — "has a" (weak ownership)

One class has a reference to another, but the contained object can exist independently. If the container is destroyed, the contained object lives on.

> A university HAS departments. If the university closes, the professors still exist — they just work somewhere else.

```python
class Engine:
    def __init__(self, horsepower: int):
        self.horsepower = horsepower
    def start(self) -> str:
        return f"Engine ({self.horsepower}hp) started"

class Car:
    def __init__(self, model: str, engine: "Engine"):
        self.model = model
        self.engine = engine   # Car HAS an engine, but engine was created outside

    def start(self) -> str:
        return self.engine.start()

# Engine exists independently — it can be swapped into another car
engine = Engine(200)
car = Car("Tesla", engine)

# If car is deleted, engine still exists
del car
print(engine.start())   # Engine (200hp) started — engine lives on
```

**Python representation:** Object passed in via `__init__` and stored as an attribute.

---

### Composition — "owns" (strong ownership)

One class creates and owns another. The contained object's lifetime is tied to the container. If the container is destroyed, the contained objects are too.

> A House OWNS its Rooms. You can't take Room 101 out of the building and put it in a different house — it exists as part of this specific house and only this house.

```python
class Room:
    def __init__(self, name: str):
        self.name = name

class House:
    def __init__(self, address: str, num_rooms: int):
        self.address = address
        # House CREATES and OWNS its rooms — they exist only as part of this house
        self.rooms = [Room(f"Room {i+1}") for i in range(num_rooms)]

    def describe(self) -> str:
        return f"House at {self.address} with {len(self.rooms)} rooms"

house = House("123 Main St", 3)
# The rooms were created inside House.__init__
# If house is deleted, the rooms have no independent existence
```

**Python representation:** Object created **inside** `__init__`, not passed in from outside.

---

### Dependency — "temporarily depends on"

One class depends on another only for the duration of a method call. The dependent object is not stored as an attribute.

> A Chef DEPENDS on a knife to cut vegetables. The chef uses the knife briefly and puts it back. The knife is not "part of" the chef.

```python
class EmailService:
    def send(self, address: str, message: str) -> None:
        print(f"Sending '{message}' to {address}")

class UserRegistration:
    def register(self, email: str, email_service: "EmailService") -> None:
        # Creates the user, then USES email_service briefly
        # email_service is NOT stored — just used here
        print(f"User {email} registered")
        email_service.send(email, "Welcome!")
```

**Python representation:** Object passed as a **method parameter** (not stored in `self`).

---

### Summary: Which relationship to use?

| Relationship | Key question | Example |
|---|---|---|
| Association | Do they interact temporarily? | Driver uses Car in `drive()` method |
| Aggregation | Does A hold B, but B can live without A? | Car has Engine (engine can be swapped) |
| Composition | Does A create and own B? | House creates its Rooms |
| Dependency | Does A use B only within one method? | UserRegistration uses EmailService in `register()` |

---

## Quick Reference: Python OOP Cheatsheet

```
Class definition           class Foo(Base): ...
Instantiation              obj = Foo(args)
Constructor                def __init__(self, ...): ...
String representation      def __repr__(self): ...  /  def __str__(self): ...

Equality                   def __eq__(self, other): ...
Comparison                 def __lt__(self, other): ...  (+ @total_ordering)
Hashing                    def __hash__(self): ...
Length                     def __len__(self): ...
Iteration                  def __iter__(self): ...  /  def __next__(self): ...
Subscript                  def __getitem__(self, key): ...
Callable                   def __call__(self, ...): ...
Context manager            def __enter__(self): ...  /  def __exit__(self, ...): ...

Arithmetic                 def __add__, __sub__, __mul__, __truediv__
Reverse arithmetic         def __radd__, __rmul__, ...  (e.g., 3 * MyObj)
In-place arithmetic        def __iadd__, __imul__, ...  (+=, *=)

Property                   @property  /  @x.setter  /  @x.deleter
Class method               @classmethod  def f(cls, ...)
Static method              @staticmethod  def f(...)
Abstract method            @abstractmethod  (requires ABC base class)
Abstract property          @property + @abstractmethod

Inheritance                class Child(Parent): ...
Multiple inheritance       class Child(A, B, C): ...
MRO inspection             ClassName.__mro__  or  ClassName.mro()
Cooperative super()        super().method(...)
Check inheritance          isinstance(obj, Class)  /  issubclass(Child, Parent)

Dataclass                  @dataclass  (auto __init__, __repr__, __eq__)
Immutable dataclass        @dataclass(frozen=True)
Sortable dataclass         @dataclass(order=True)
Mutable default field      field(default_factory=list)
Post-init validation       def __post_init__(self): ...
Class variable             ClassVar[int]
Convert to dict            asdict(obj)
Convert to tuple           astuple(obj)

Enum                       class Status(Enum): ACTIVE = auto()
State machine              VALID_TRANSITIONS = {State.A: {State.B, State.C}, ...}
```

---

## Common Mistakes

**Not using enums for states:**
```python
# BAD — typos and string comparisons everywhere
if order.status == "cancled":   # silent bug

# GOOD — typos caught at definition time, not runtime
if order.status == OrderStatus.CANCELLED:
```

**Injecting concrete classes instead of abstractions:**
```python
# BAD — UserService is now impossible to test without a real MySQL DB
class UserService:
    def __init__(self):
        self.db = MySQLDatabase()   # hard-wired dependency

# GOOD — pass in anything that satisfies the Database interface
class UserService:
    def __init__(self, db: Database):
        self.db = db
```

**Confusion between Template Method and Strategy:**
- **Template Method:** the SKELETON (order of steps) is fixed; subclasses fill in individual steps
- **Strategy:** the ENTIRE algorithm is swapped out; the context doesn't know which strategy it's running

**Putting all logic in the Service class:**
Business rules belong in the entity, not the service. `Order.can_be_cancelled()` should live in `Order`, not in `OrderService.cancel()`. Services orchestrate; entities enforce their own invariants.

**Giant `__init__` methods:**
If your `__init__` is doing network calls, database reads, or heavy computation, move that work into a `@classmethod` factory or a `Service.create()` method. `__init__` should only set attributes.

**Skipping the "define interfaces first" step:**
In a rush, it's tempting to write concrete classes directly. But writing the abstract interface first forces you to think about what the class needs to DO — and often reveals that you need to split a class into two.

---

## Quick Summary

- **5-step checklist:** Entities → Behaviors → Relationships → Interfaces first → SOLID + Enums
- **Enums + state machines:** `VALID_TRANSITIONS` dict makes all allowed state changes visible in one place
- **DI Container:** registers factories and resolves them — makes swapping implementations trivial
- **Template Method:** base class fixes the algorithm skeleton; subclasses fill in the details
- **Class relationships:** Association (uses), Aggregation (has, but separate), Composition (owns and creates), Dependency (uses briefly in a method)
- **LLD template:** Enums → Value Objects → Entities → Interfaces → Strategies → Service/Facade
