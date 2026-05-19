# 10 — SOLID Principles

## What is this?

SOLID is a set of five design principles that make code easier to understand, change, and extend. Each letter stands for one principle. Learning them will help you spot problems in your own code — and they come up in almost every LLD interview.

---

## Overview

| Letter | Principle | One-line rule |
|---|---|---|
| S | Single Responsibility | Each class should have exactly one reason to change |
| O | Open/Closed | Open for extension, closed for modification |
| L | Liskov Substitution | Subclasses must be drop-in replacements for their parent |
| I | Interface Segregation | Don't force classes to implement methods they don't need |
| D | Dependency Inversion | Depend on abstractions, not concrete implementations |

---

## S — Single Responsibility Principle

**One-line rule:** A class should have one job. If it needs to change, there should be only one reason why.

> Analogy: A Swiss army knife is handy in a survival kit, but you would not use it in a professional kitchen. A chef uses specialised tools — a knife for cutting, a pan for cooking, a thermometer for temperature. Each tool does one thing and does it well. The same applies to classes.

### The problem: one class doing too many jobs

Here is a `UserManager` class that handles users, emails, the database, and reporting all at once:

```python
# BAD — this class has four separate reasons to change:
# 1. The user creation logic changes
# 2. The email template changes
# 3. The database schema changes
# 4. The reporting format changes
class UserManager:
    def create_user(self, data):
        # ... user creation logic
        pass

    def send_welcome_email(self, user):
        # ... email sending logic (email concern mixed in here)
        pass

    def save_to_db(self, user):
        # ... SQL queries (persistence concern mixed in here)
        pass

    def generate_report(self):
        # ... CSV/PDF generation (reporting concern mixed in here)
        pass
```

If the email provider changes, you must edit `UserManager`. If the database schema changes, you must edit `UserManager`. Every change risks breaking the other features accidentally.

### The fix: one class, one responsibility

Split each concern into its own class. Now each class changes for exactly one reason:

```python
# GOOD — each class has one job and one reason to change

class UserRepository:
    """Only responsible for persistence."""
    def save(self, user):
        print(f"Saving {user} to database")

    def find_by_id(self, user_id):
        return None  # database lookup here


class EmailService:
    """Only responsible for sending emails."""
    def send_welcome(self, user):
        print(f"Sending welcome email to {user}")


class UserService:
    """Orchestrates the other services — but doesn't DO their jobs."""
    def __init__(self, repo: UserRepository, email: EmailService):
        self.repo = repo
        self.email = email

    def register(self, data: dict):
        user = data  # simplified — normally creates a User object
        self.repo.save(user)
        self.email.send_welcome(user)
        return user


# Each piece can change independently
repo  = UserRepository()
email = EmailService()
service = UserService(repo, email)
service.register({"name": "Alice", "email": "alice@example.com"})
```

> **What just happened?**
> Now if the email provider changes, you only touch `EmailService`. If the database engine changes, you only touch `UserRepository`. `UserService` never needs to change for either reason. Each class has exactly one reason to change.

---

## O — Open/Closed Principle

**One-line rule:** You should be able to add new features by writing new code, not by editing existing code.

> Analogy: Think of a wall socket. The socket was designed once and never needs to be modified. When a new device is invented (laptop, phone, vacuum cleaner), you just build a new plug. The socket is *closed* for modification but *open* for new plugs. Well-designed classes work the same way.

### The problem: adding a feature means editing existing code

Here is an `Order` class that calculates discounts with if/elif:

```python
# BAD — every new discount type requires editing this existing class
class Order:
    def __init__(self, price: float, discount_type: str):
        self.price = price
        self.discount_type = discount_type

    def total(self) -> float:
        if self.discount_type == "none":
            return self.price
        elif self.discount_type == "percentage":
            return self.price * 0.9    # hardcoded 10%
        elif self.discount_type == "bogo":
            return self.price / 2
        # To add a new discount, you must edit this method — risky!
```

Every time marketing invents a new discount, a developer must open this class and edit it. This is error-prone and violates the principle.

### The fix: new discounts are new classes, not edits

Define a `DiscountStrategy` abstraction. Each discount is a separate class. The `Order` class never needs to change when a new discount is added:

```python
from abc import ABC, abstractmethod

class DiscountStrategy(ABC):
    """The abstraction — each discount type implements this."""
    @abstractmethod
    def apply(self, price: float) -> float: ...


class NoDiscount(DiscountStrategy):
    def apply(self, price: float) -> float:
        return price


class PercentageDiscount(DiscountStrategy):
    def __init__(self, percent: float):
        self.percent = percent

    def apply(self, price: float) -> float:
        return price * (1 - self.percent / 100)


class BuyOneGetOneFree(DiscountStrategy):
    def apply(self, price: float) -> float:
        return price / 2


class Order:
    def __init__(self, price: float, discount: DiscountStrategy):
        self.price = price
        self.discount = discount

    def total(self) -> float:
        return self.discount.apply(self.price)


# Adding a new "flash sale" discount = new class, zero edits to Order
class FlashSaleDiscount(DiscountStrategy):
    def apply(self, price: float) -> float:
        return price * 0.5   # 50% off

order1 = Order(100, PercentageDiscount(10))
order2 = Order(100, BuyOneGetOneFree())
order3 = Order(100, FlashSaleDiscount())

print(order1.total())   # 90.0
print(order2.total())   # 50.0
print(order3.total())   # 50.0
```

> **Key takeaway:** When you find yourself adding another `elif` to a method every time a new variant is added, that's a sign the Open/Closed Principle is being violated. Each variant should be its own class.

---

## L — Liskov Substitution Principle

**One-line rule:** If `S` is a subclass of `T`, you should be able to use `S` anywhere `T` is expected, and the program should still behave correctly.

> Analogy: If you hire an employee and later promote them to manager, the rest of the team should still be able to ask them to attend meetings, write reports, and do code reviews. A Manager should be able to do everything an Employee does. If a promotion breaks the team's workflow — if suddenly meetings can no longer happen because the manager objects to them — that's a Liskov violation.

### The classic example: Rectangle and Square

In mathematics, a square IS a rectangle. This makes it tempting to write `class Square(Rectangle)`. But it creates a subtle and nasty bug:

```python
# BAD — Square inherits from Rectangle but breaks its expectations
class Rectangle:
    def __init__(self, w: float, h: float):
        self.w = w
        self.h = h

    def area(self) -> float:
        return self.w * self.h


class Square(Rectangle):
    def __init__(self, side: float):
        super().__init__(side, side)

    # The problem: if someone independently sets width and height,
    # the square stops being a square.
    # Any code that does rect.w = 5; rect.h = 10 breaks for a Square.


def scale_and_print(rect: Rectangle) -> None:
    rect.w = 10
    rect.h = 5
    # A programmer expects area = 50 for any Rectangle
    print(rect.area())   # Prints 50 for Rectangle — but a Square would be broken

r = Rectangle(2, 3)
s = Square(4)
scale_and_print(r)   # 50 — correct
scale_and_print(s)   # 50 — only by accident; the Square's invariant (w==h) was violated
```

The square cannot truly replace the rectangle because they have different constraints. Passing width and height independently makes sense for a rectangle but breaks the meaning of a square.

### The fix: share a common abstraction, not an inheritance chain

Give both `Rectangle` and `Square` a common parent (`Shape`), but keep them as siblings rather than parent-and-child:

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...


class Rectangle(Shape):
    def __init__(self, w: float, h: float):
        self.w = w
        self.h = h

    def area(self) -> float:
        return self.w * self.h


class Square(Shape):
    def __init__(self, side: float):
        self.side = side

    def area(self) -> float:
        return self.side ** 2


# Now any code that works with Shape works correctly for both
shapes = [Rectangle(4, 5), Square(4)]
for s in shapes:
    print(s.area())   # 20, 16 — both correct and predictable
```

> **What just happened?**
> By making `Rectangle` and `Square` siblings under `Shape`, code that uses `Shape` works correctly for both — no surprises. Neither class promises to support something it can't deliver.

### A quick Liskov test

Before making `B` a subclass of `A`, ask:
1. Does `B` support everything `A` supports?
2. Does `B` add constraints that would surprise code written for `A`?
3. Can you replace every `A` in the codebase with `B` without breaking anything?

If any answer is "no", use composition or a sibling relationship instead.

---

## I — Interface Segregation Principle

**One-line rule:** Don't force a class to implement methods it will never use.

> Analogy: Imagine a TV remote with 80 buttons. Most people use 5 of them. A robot that controls the TV only needs volume and channel — but it has to deal with the DVD, streaming, and parrot-training buttons anyway. A better design would be separate, focused remotes for each function. Fat interfaces force implementors to carry dead weight.

### The problem: a fat interface forces useless implementations

Here is a `Worker` abstract class that assumes all workers eat and sleep:

```python
from abc import ABC, abstractmethod

# BAD — forces RobotWorker to implement eat() and sleep(), which make no sense
class Worker(ABC):
    @abstractmethod
    def work(self): ...

    @abstractmethod
    def eat(self): ...

    @abstractmethod
    def sleep(self): ...


class HumanWorker(Worker):
    def work(self):  print("Human working")
    def eat(self):   print("Human eating")
    def sleep(self): print("Human sleeping")


class RobotWorker(Worker):
    def work(self):  print("Robot working")

    def eat(self):
        raise NotImplementedError("Robots don't eat")   # forced, useless, misleading

    def sleep(self):
        raise NotImplementedError("Robots don't sleep")  # same problem
```

Every time someone calls `eat()` on a `Worker` reference and gets a `RobotWorker`, they get an unexpected error. The interface promised something the class cannot deliver.

### The fix: split into small, focused interfaces

Use `Protocol` (or separate ABCs) to define small, specific capabilities:

```python
from typing import Protocol

class Workable(Protocol):
    def work(self) -> None: ...

class Eatable(Protocol):
    def eat(self) -> None: ...

class Sleepable(Protocol):
    def sleep(self) -> None: ...


class HumanWorker:
    def work(self)  -> None: print("Human working")
    def eat(self)   -> None: print("Human eating")
    def sleep(self) -> None: print("Human sleeping")


class RobotWorker:
    def work(self) -> None: print("Robot working")
    # No eat() or sleep() needed — not in the Workable protocol


# Functions only ask for what they actually need
def start_shift(worker: Workable) -> None:
    worker.work()

def lunch_break(human: Eatable) -> None:
    human.eat()


robot = RobotWorker()
human = HumanWorker()

start_shift(robot)   # Robot working — no problem, robot satisfies Workable
start_shift(human)   # Human working
lunch_break(human)   # Human eating
# lunch_break(robot) — type checker catches this! Robot is not Eatable
```

> **What just happened?**
> Each function only asks for the capability it actually uses. `RobotWorker` is not forced to pretend it eats. The interfaces are small and precise. This also makes code much easier to test — you can pass in a minimal fake object that only implements the one method you need.

---

## D — Dependency Inversion Principle

**One-line rule:** High-level code should depend on abstractions (interfaces), not on concrete, low-level implementations.

> Analogy: Your laptop charger has a standard plug — it doesn't care whether the electricity in the wall comes from a coal plant, a solar farm, or a nuclear reactor. The laptop (high-level) depends on the socket standard (abstraction), not on the specific power source (concrete implementation). This means you can plug in anywhere in the world.

### The problem: high-level code is hardwired to low-level code

Here is a `UserService` that creates a `MySQLDatabase` internally. It is welded to MySQL:

```python
# BAD — UserService is hardwired to MySQL; impossible to test or swap
class MySQLDatabase:
    def query(self, sql: str) -> list:
        print(f"MySQL: {sql}")
        return []

    def execute(self, sql: str) -> None:
        print(f"MySQL execute: {sql}")


class UserService:
    def __init__(self):
        self.db = MySQLDatabase()   # hard dependency — created internally

    def get_users(self) -> list:
        return self.db.query("SELECT * FROM users")
```

To test `UserService`, you would need a real MySQL database running. To switch to PostgreSQL, you must edit `UserService` itself. The high-level logic is locked to a low-level detail.

### The fix: inject the abstraction

Define an interface (Protocol or ABC) for the database. `UserService` only knows about the abstraction — any concrete implementation that matches the interface will work:

```python
from typing import Protocol

# The abstraction — what any database must be able to do
class Database(Protocol):
    def query(self, sql: str) -> list: ...
    def execute(self, sql: str) -> None: ...


# The real implementations (low-level)
class MySQLDatabase:
    def query(self, sql: str) -> list:
        print(f"MySQL query: {sql}")
        return [{"id": 1, "name": "Alice"}]

    def execute(self, sql: str) -> None:
        print(f"MySQL execute: {sql}")


class PostgreSQLDatabase:
    def query(self, sql: str) -> list:
        print(f"PostgreSQL query: {sql}")
        return []

    def execute(self, sql: str) -> None:
        print(f"PostgreSQL execute: {sql}")


class InMemoryDatabase:
    """Lightweight fake — perfect for unit tests."""
    def query(self, sql: str) -> list:
        return [{"id": 1, "name": "TestUser"}]

    def execute(self, sql: str) -> None:
        pass


# The high-level service — depends on the abstraction, not any concrete DB
class UserService:
    def __init__(self, db: Database):   # injected from outside
        self.db = db

    def get_users(self) -> list:
        return self.db.query("SELECT * FROM users")


# In production:
production_service = UserService(MySQLDatabase())

# In tests — no database needed at all:
test_service = UserService(InMemoryDatabase())
users = test_service.get_users()
print(users)   # [{'id': 1, 'name': 'TestUser'}]

# Switching database = one line change at the wiring point, nowhere else:
pg_service = UserService(PostgreSQLDatabase())
```

> **What just happened?**
> `UserService` is now completely independent of MySQL, PostgreSQL, or any specific database. You can test it with an in-memory fake, deploy it against MySQL, and switch to PostgreSQL — all without changing a single line inside `UserService`. The high-level logic and the low-level details are decoupled.

---

## All five principles in one example

Here is a short sketch showing all five principles applied together:

```python
from abc import ABC, abstractmethod
from typing import Protocol

# S — each class has one job
class OrderValidator:
    def validate(self, order: dict) -> bool:
        return bool(order.get("items"))

class OrderRepository:
    def save(self, order: dict) -> None:
        print(f"Saved order: {order}")

# O — new discounts are new classes, not edits to existing code
class DiscountStrategy(ABC):
    @abstractmethod
    def apply(self, price: float) -> float: ...

class TenPercentOff(DiscountStrategy):
    def apply(self, price: float) -> float:
        return price * 0.9

# L — any DiscountStrategy subclass can replace any other
class NoDiscount(DiscountStrategy):
    def apply(self, price: float) -> float:
        return price

# I — small, focused notification interface
class Notifiable(Protocol):
    def notify(self, message: str) -> None: ...

class EmailNotifier:
    def notify(self, message: str) -> None:
        print(f"Email: {message}")

# D — OrderService depends on abstractions, not concrete classes
class OrderService:
    def __init__(
        self,
        validator: OrderValidator,
        repo: OrderRepository,
        discount: DiscountStrategy,
        notifier: Notifiable,
    ):
        self._validator = validator
        self._repo = repo
        self._discount = discount
        self._notifier = notifier

    def place_order(self, order: dict, price: float) -> float:
        if not self._validator.validate(order):
            raise ValueError("Invalid order")
        final_price = self._discount.apply(price)
        self._repo.save(order)
        self._notifier.notify(f"Order placed! Total: ${final_price:.2f}")
        return final_price


service = OrderService(
    validator=OrderValidator(),
    repo=OrderRepository(),
    discount=TenPercentOff(),
    notifier=EmailNotifier(),
)
service.place_order({"items": ["book"]}, 50.0)
# Saved order: {'items': ['book']}
# Email: Order placed! Total: $45.00
```

---

## Common mistakes

**S — Combining too many concerns in one class**

The most common symptom: a class with a long list of methods that span multiple topics (user logic + email + database + reporting). Split them. If you cannot describe a class's job in one short sentence, it is doing too much.

**O — Using if/elif to add variants**

Every time you add a new `elif` for a new type of discount, payment, export format, or notification channel, you are modifying existing code and risking regressions. Use the strategy pattern (new class for each variant) instead.

**L — Making a subclass that throws `NotImplementedError`**

If a subclass inherits a method and then raises `NotImplementedError`, that is a Liskov violation. Code that calls the parent's method expects it to work — not to explode. If you can't implement the method meaningfully, you should not be inheriting it.

**I — Inheriting a giant ABC and leaving half the methods as stubs**

If you find yourself implementing abstract methods with `pass` or `return None` just to satisfy an ABC, the interface is too fat. Split it.

**D — Creating dependencies with `new` / constructor calls inside the class**

```python
# SMELL — hard dependency created internally
class Service:
    def __init__(self):
        self.db = MySQLDatabase()   # impossible to swap or test
```

The rule of thumb: if you need to `import` a concrete class inside another class's constructor, consider injecting it instead.

---

## Quick summary table

| Principle | One-line rule | Interview red flag |
|---|---|---|
| S — Single Responsibility | One class, one reason to change | Class named `Manager`, `Handler`, or `Util` doing 5 different things |
| O — Open/Closed | Add features by adding code, not editing it | Long `if/elif` chain that grows with every new variant |
| L — Liskov Substitution | Subclasses must not surprise code written for the parent | Subclass raises `NotImplementedError` on an inherited method |
| I — Interface Segregation | Only require methods you actually use | Class forced to implement a method with `pass` or `raise NotImplementedError` |
| D — Dependency Inversion | Depend on abstractions, not concrete classes | `self.db = MySQLDatabase()` hardwired inside a constructor |

**The one-sentence rule:** SOLID principles all point at the same goal — write code where each piece can change independently without breaking everything else.
