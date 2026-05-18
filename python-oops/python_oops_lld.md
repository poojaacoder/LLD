# Python OOP for LLD Interviews

## Table of Contents
1. [Core Building Blocks](#1-core-building-blocks)
2. [Four Pillars](#2-four-pillars)
3. [Magic / Dunder Methods](#3-magic--dunder-methods)
4. [Properties and Descriptors](#4-properties-and-descriptors)
5. [Class vs Static vs Instance](#5-class-vs-static-vs-instance)
6. [Inheritance Deep Dive](#6-inheritance-deep-dive)
7. [Abstract Classes and Interfaces](#7-abstract-classes-and-interfaces)
8. [Protocols (Structural Subtyping)](#8-protocols-structural-subtyping)
9. [Composition over Inheritance](#9-composition-over-inheritance)
10. [SOLID Principles](#10-solid-principles)
11. [Design Patterns](#11-design-patterns)
12. [Dataclasses](#12-dataclasses)
13. [LLD Interview Patterns](#13-lld-interview-patterns)
14. [Worked LLD Problems](#14-worked-lld-problems)
    - [14.1 Parking Lot](#141-parking-lot)
    - [14.2 Library Management System](#142-library-management-system)
    - [14.3 Elevator System](#143-elevator-system)
    - [14.4 Movie Ticket Booking (BookMyShow)](#144-movie-ticket-booking-bookmyshow)

---

## 1. Core Building Blocks

### Classes and Objects

```python
class BankAccount:
    # Class variable — shared across all instances
    interest_rate = 0.05

    def __init__(self, owner: str, balance: float = 0.0):
        # Instance variables — unique per object
        self.owner = owner
        self._balance = balance          # "protected" by convention
        self.__account_id = id(self)     # "private" — name-mangled to _BankAccount__account_id

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self._balance += amount

    def __repr__(self) -> str:
        return f"BankAccount(owner={self.owner!r}, balance={self._balance})"

    def __str__(self) -> str:
        return f"{self.owner}'s account: ${self._balance:.2f}"


acc = BankAccount("Alice", 1000)
print(acc)           # Alice's account: $1000.00
print(repr(acc))     # BankAccount(owner='Alice', balance=1000.0)
```

**Key rules:**
- `__repr__` → unambiguous, for developers (used in REPL, logs)
- `__str__` → readable, for end users (`print()` calls this)
- Single underscore `_x` → convention "don't touch from outside"
- Double underscore `__x` → name mangling, harder to access accidentally

---

## 2. Four Pillars

### 2.1 Encapsulation

Bundle data + behavior; control access via properties.

```python
class Temperature:
    def __init__(self, celsius: float):
        self._celsius = celsius

    @property
    def celsius(self) -> float:
        return self._celsius

    @celsius.setter
    def celsius(self, value: float) -> None:
        if value < -273.15:
            raise ValueError("Temperature below absolute zero")
        self._celsius = value

    @property
    def fahrenheit(self) -> float:
        return self._celsius * 9 / 5 + 32
```

### 2.2 Inheritance

```python
class Vehicle:
    def __init__(self, make: str, model: str):
        self.make = make
        self.model = model

    def start(self) -> str:
        return "Vehicle started"

    def describe(self) -> str:
        return f"{self.make} {self.model}"


class ElectricCar(Vehicle):
    def __init__(self, make: str, model: str, battery_kwh: float):
        super().__init__(make, model)      # always call super().__init__
        self.battery_kwh = battery_kwh

    def start(self) -> str:               # method override
        return f"{self.describe()} silently starts (battery: {self.battery_kwh}kWh)"

    def charge(self) -> str:
        return "Charging..."


car = ElectricCar("Tesla", "Model 3", 82)
print(car.start())   # Tesla Model 3 silently starts (battery: 82kWh)
print(isinstance(car, Vehicle))   # True
```

### 2.3 Polymorphism

Same interface, different behavior — two flavors:

```python
# 1. Method overriding (runtime polymorphism)
class Shape:
    def area(self) -> float:
        raise NotImplementedError

class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = radius
    def area(self) -> float:
        import math
        return math.pi * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, w: float, h: float):
        self.w, self.h = w, h
    def area(self) -> float:
        return self.w * self.h

shapes = [Circle(5), Rectangle(4, 6)]
for s in shapes:
    print(s.area())   # each calls its own area()


# 2. Duck typing (Python's idiomatic polymorphism)
class Duck:
    def quack(self): return "Quack!"

class Person:
    def quack(self): return "I'm quacking like a duck!"

def make_it_quack(obj):
    print(obj.quack())   # doesn't care about type, only capability

make_it_quack(Duck())    # Quack!
make_it_quack(Person())  # I'm quacking like a duck!
```

### 2.4 Abstraction

Hide implementation details, expose only what matters.

```python
from abc import ABC, abstractmethod

class PaymentProcessor(ABC):
    @abstractmethod
    def process_payment(self, amount: float) -> bool: ...

    @abstractmethod
    def refund(self, transaction_id: str) -> bool: ...

    def validate_amount(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")

class StripeProcessor(PaymentProcessor):
    def process_payment(self, amount: float) -> bool:
        self.validate_amount(amount)
        print(f"Processing ${amount} via Stripe")
        return True

    def refund(self, transaction_id: str) -> bool:
        print(f"Refunding {transaction_id} via Stripe")
        return True

# PaymentProcessor()  # TypeError: Can't instantiate abstract class
```

---

## 3. Magic / Dunder Methods

Essential for making your objects behave like built-in types.

### Comparison and Hashing

```python
from functools import total_ordering

@total_ordering   # implement __eq__ + one of __lt__/__gt__/__le__/__ge__, rest auto-generated
class Employee:
    def __init__(self, name: str, salary: float):
        self.name = name
        self.salary = salary

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Employee):
            return NotImplemented
        return self.salary == other.salary

    def __lt__(self, other: "Employee") -> bool:
        return self.salary < other.salary

    def __hash__(self) -> int:
        return hash(self.name)   # needed if __eq__ is defined

    def __repr__(self) -> str:
        return f"Employee({self.name!r}, {self.salary})"

employees = [Employee("Bob", 90000), Employee("Alice", 70000)]
print(sorted(employees))   # [Employee('Alice', 70000), Employee('Bob', 90000)]
```

### Container Protocol

```python
class Stack:
    def __init__(self):
        self._items: list = []

    def push(self, item) -> None:
        self._items.append(item)

    def pop(self):
        return self._items.pop()

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item) -> bool:
        return item in self._items

    def __iter__(self):
        return iter(reversed(self._items))   # top to bottom

    def __bool__(self) -> bool:
        return len(self._items) > 0

    def __repr__(self) -> str:
        return f"Stack({self._items})"

s = Stack()
s.push(1); s.push(2); s.push(3)
print(len(s))        # 3
print(2 in s)        # True
print(list(s))       # [3, 2, 1]
print(bool(s))       # True
```

### Context Manager Protocol

```python
class DatabaseConnection:
    def __init__(self, url: str):
        self.url = url
        self.connection = None

    def __enter__(self):
        print(f"Connecting to {self.url}")
        self.connection = {"connected": True}   # simulate
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        print("Closing connection")
        self.connection = None
        if exc_type is ValueError:
            print(f"Suppressing ValueError: {exc_val}")
            return True    # suppress the exception
        return False       # re-raise other exceptions

with DatabaseConnection("postgres://localhost/db") as conn:
    print(conn)   # {'connected': True}
# Closing connection
```

### Callable Objects

```python
class Multiplier:
    def __init__(self, factor: float):
        self.factor = factor

    def __call__(self, value: float) -> float:
        return value * self.factor

double = Multiplier(2)
triple = Multiplier(3)
print(double(5))   # 10
print(triple(5))   # 15
print(callable(double))   # True
```

### Arithmetic Operators

```python
class Vector:
    def __init__(self, x: float, y: float):
        self.x, self.y = x, y

    def __add__(self, other: "Vector") -> "Vector":
        return Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector") -> "Vector":
        return Vector(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector":
        return Vector(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> "Vector":
        return self.__mul__(scalar)   # handles: 3 * Vector(...)

    def __abs__(self) -> float:
        return (self.x**2 + self.y**2) ** 0.5

    def __repr__(self) -> str:
        return f"Vector({self.x}, {self.y})"

v1 = Vector(1, 2)
v2 = Vector(3, 4)
print(v1 + v2)   # Vector(4, 6)
print(3 * v1)    # Vector(3, 6)
print(abs(v2))   # 5.0
```

---

## 4. Properties and Descriptors

### @property

```python
class Circle:
    def __init__(self, radius: float):
        self._radius = radius

    @property
    def radius(self) -> float:
        return self._radius

    @radius.setter
    def radius(self, value: float) -> None:
        if value < 0:
            raise ValueError("Radius cannot be negative")
        self._radius = value

    @radius.deleter
    def radius(self) -> None:
        del self._radius

    @property
    def area(self) -> float:   # computed property — no setter needed
        import math
        return math.pi * self._radius ** 2
```

### Descriptors (advanced — for frameworks/ORMs)

```python
class PositiveNumber:
    """A descriptor that enforces positive values."""

    def __set_name__(self, owner, name: str) -> None:
        self.name = name
        self.private_name = f"_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self   # accessed on class, not instance
        return getattr(obj, self.private_name, None)

    def __set__(self, obj, value: float) -> None:
        if value <= 0:
            raise ValueError(f"{self.name} must be positive, got {value}")
        setattr(obj, self.private_name, value)


class Product:
    price = PositiveNumber()
    quantity = PositiveNumber()

    def __init__(self, name: str, price: float, quantity: int):
        self.name = name
        self.price = price          # triggers PositiveNumber.__set__
        self.quantity = quantity

p = Product("Widget", 9.99, 10)
# p.price = -1   # ValueError: price must be positive, got -1
```

---

## 5. Class vs Static vs Instance

```python
class Counter:
    _count = 0   # class variable

    def __init__(self, name: str):
        Counter._count += 1
        self.name = name
        self.id = Counter._count

    # Instance method — has access to self (instance) and cls indirectly
    def describe(self) -> str:
        return f"Counter #{self.id}: {self.name}"

    # Class method — operates on the class, not a specific instance
    @classmethod
    def get_count(cls) -> int:
        return cls._count

    @classmethod
    def reset(cls) -> None:
        cls._count = 0

    # Static method — utility; no access to instance or class state
    @staticmethod
    def validate_name(name: str) -> bool:
        return isinstance(name, str) and len(name) > 0


c1 = Counter("A")
c2 = Counter("B")
print(Counter.get_count())           # 2
print(Counter.validate_name("A"))    # True
print(c1.describe())                 # Counter #1: A
```

**When to use each:**

| Method type | Access to | Use when |
|---|---|---|
| Instance `def f(self)` | instance + class | behavior depends on object state |
| Class `@classmethod` | class only | alternative constructors, factory methods |
| Static `@staticmethod` | neither | pure utility logic related to the class |

### Alternative Constructors (common LLD pattern)

```python
class Date:
    def __init__(self, year: int, month: int, day: int):
        self.year, self.month, self.day = year, month, day

    @classmethod
    def from_string(cls, date_str: str) -> "Date":
        year, month, day = map(int, date_str.split("-"))
        return cls(year, month, day)

    @classmethod
    def today(cls) -> "Date":
        from datetime import date
        d = date.today()
        return cls(d.year, d.month, d.day)

    def __repr__(self) -> str:
        return f"Date({self.year}, {self.month}, {self.day})"

d = Date.from_string("2024-01-15")
print(d)   # Date(2024, 1, 15)
```

---

## 6. Inheritance Deep Dive

### MRO (Method Resolution Order) — C3 Linearization

```python
class A:
    def hello(self): return "A"

class B(A):
    def hello(self): return "B"

class C(A):
    def hello(self): return "C"

class D(B, C):   # Diamond inheritance
    pass

d = D()
print(d.hello())     # "B" — follows MRO
print(D.__mro__)     # (<class 'D'>, <class 'B'>, <class 'C'>, <class 'A'>, <class 'object'>)
```

### Cooperative Multiple Inheritance with super()

```python
class LogMixin:
    def save(self) -> str:
        print("LogMixin: logging before save")
        return super().save()   # cooperatively calls next in MRO

class ValidationMixin:
    def save(self) -> str:
        print("ValidationMixin: validating before save")
        return super().save()

class Base:
    def save(self) -> str:
        print("Base: saving")
        return "saved"

class Model(LogMixin, ValidationMixin, Base):
    pass

m = Model()
m.save()
# LogMixin: logging before save
# ValidationMixin: validating before save
# Base: saving
```

### Mixin Pattern (common in LLD)

```python
class SerializableMixin:
    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict):
        obj = cls.__new__(cls)
        obj.__dict__.update(data)
        return obj

class TimestampMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from datetime import datetime
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

class User(SerializableMixin, TimestampMixin):
    def __init__(self, name: str, email: str):
        super().__init__()
        self.name = name
        self.email = email

u = User("Alice", "alice@example.com")
print(u.to_dict())   # {'name': 'Alice', 'email': '...', 'created_at': '...', 'updated_at': '...'}
```

---

## 7. Abstract Classes and Interfaces

```python
from abc import ABC, abstractmethod
from typing import List

class Notification(ABC):
    """Abstract base — cannot be instantiated directly."""

    @abstractmethod
    def send(self, recipient: str, message: str) -> bool:
        """Send notification. Return True on success."""
        ...

    @abstractmethod
    def get_channel(self) -> str: ...

    # Concrete method in ABC — shared default behavior
    def send_bulk(self, recipients: List[str], message: str) -> dict:
        return {r: self.send(r, message) for r in recipients}


class EmailNotification(Notification):
    def send(self, recipient: str, message: str) -> bool:
        print(f"Email to {recipient}: {message}")
        return True

    def get_channel(self) -> str:
        return "email"


class SMSNotification(Notification):
    def send(self, recipient: str, message: str) -> bool:
        print(f"SMS to {recipient}: {message}")
        return True

    def get_channel(self) -> str:
        return "sms"
```

### Abstract Properties

```python
class Shape(ABC):
    @property
    @abstractmethod
    def area(self) -> float: ...

    @property
    @abstractmethod
    def perimeter(self) -> float: ...

    def describe(self) -> str:
        return f"Area: {self.area:.2f}, Perimeter: {self.perimeter:.2f}"

class Square(Shape):
    def __init__(self, side: float):
        self.side = side

    @property
    def area(self) -> float:
        return self.side ** 2

    @property
    def perimeter(self) -> float:
        return 4 * self.side
```

---

## 8. Protocols (Structural Subtyping)

Python's duck-typing made explicit — no inheritance required.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Drawable(Protocol):
    def draw(self) -> None: ...
    def resize(self, factor: float) -> None: ...

class Circle:
    def draw(self) -> None:
        print("Drawing circle")
    def resize(self, factor: float) -> None:
        self.radius *= factor

class Square:
    def draw(self) -> None:
        print("Drawing square")
    def resize(self, factor: float) -> None:
        self.side *= factor

# Neither inherits from Drawable — but both satisfy the protocol
def render(shape: Drawable) -> None:
    shape.draw()

c = Circle()
render(c)   # works — Circle structurally matches Drawable

print(isinstance(c, Drawable))   # True (runtime_checkable)
```

**Protocol vs ABC:**
- `ABC` → nominal subtyping (must explicitly inherit)
- `Protocol` → structural subtyping (just needs matching methods)
- Use `Protocol` for interop with third-party types you can't modify

---

## 9. Composition over Inheritance

Prefer composing objects over deep inheritance hierarchies.

```python
# BAD: deep inheritance — tight coupling, fragile base class problem
class Animal: ...
class FlyingAnimal(Animal): ...
class SwimmingAnimal(Animal): ...
# What about a duck? Multiple inheritance gets messy.


# GOOD: composition
class FlyBehavior:
    def fly(self) -> str:
        return "Flying with wings"

class NoFlyBehavior:
    def fly(self) -> str:
        return "Can't fly"

class SwimBehavior:
    def swim(self) -> str:
        return "Swimming"

class NoSwimBehavior:
    def swim(self) -> str:
        return "Can't swim"


class Animal:
    def __init__(self, name: str, fly_behavior, swim_behavior):
        self.name = name
        self._fly = fly_behavior
        self._swim = swim_behavior

    def fly(self) -> str:
        return self._fly.fly()

    def swim(self) -> str:
        return self._swim.swim()


duck = Animal("Duck", FlyBehavior(), SwimBehavior())
penguin = Animal("Penguin", NoFlyBehavior(), SwimBehavior())

print(duck.fly())      # Flying with wings
print(penguin.fly())   # Can't fly
print(penguin.swim())  # Swimming
```

---

## 10. SOLID Principles

### S — Single Responsibility

```python
# BAD: one class doing too much
class UserManager:
    def create_user(self, data): ...
    def send_welcome_email(self, user): ...   # email concern
    def save_to_db(self, user): ...           # persistence concern
    def generate_report(self): ...            # reporting concern

# GOOD: each class has one reason to change
class UserRepository:
    def save(self, user): ...
    def find_by_id(self, user_id): ...

class EmailService:
    def send_welcome(self, user): ...

class UserService:
    def __init__(self, repo: UserRepository, email: EmailService):
        self.repo = repo
        self.email = email

    def register(self, data: dict):
        user = User(**data)
        self.repo.save(user)
        self.email.send_welcome(user)
        return user
```

### O — Open/Closed

```python
from abc import ABC, abstractmethod

# Open for extension, closed for modification
class DiscountStrategy(ABC):
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

# Adding new discounts requires NO changes to Order
```

### L — Liskov Substitution

```python
# BAD: Square "is-a" Rectangle but violates LSP
class Rectangle:
    def __init__(self, w: float, h: float):
        self.w, self.h = w, h
    def area(self) -> float:
        return self.w * self.h

class Square(Rectangle):
    def __init__(self, side: float):
        super().__init__(side, side)
    # If we override setters to keep w==h, area() contracts break

# GOOD: separate hierarchy; both implement Shape
class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...

class Rectangle(Shape):
    def __init__(self, w: float, h: float):
        self.w, self.h = w, h
    def area(self) -> float:
        return self.w * self.h

class Square(Shape):
    def __init__(self, side: float):
        self.side = side
    def area(self) -> float:
        return self.side ** 2
```

### I — Interface Segregation

```python
# BAD: fat interface
class Worker(ABC):
    @abstractmethod
    def work(self): ...
    @abstractmethod
    def eat(self): ...
    @abstractmethod
    def sleep(self): ...
    # RobotWorker doesn't eat/sleep — forced to implement useless methods

# GOOD: segregated interfaces
class Workable(Protocol):
    def work(self) -> None: ...

class Eatable(Protocol):
    def eat(self) -> None: ...

class HumanWorker:
    def work(self) -> None: print("Human working")
    def eat(self) -> None: print("Human eating")

class RobotWorker:
    def work(self) -> None: print("Robot working")
    # No eat() needed — not in the Workable protocol
```

### D — Dependency Inversion

```python
# BAD: high-level module depends on low-level concrete class
class MySQLDatabase:
    def query(self, sql: str): ...

class UserService:
    def __init__(self):
        self.db = MySQLDatabase()   # hard dependency — impossible to swap/test


# GOOD: depend on abstraction
class Database(Protocol):
    def query(self, sql: str) -> list: ...
    def execute(self, sql: str) -> None: ...

class UserService:
    def __init__(self, db: Database):   # injected — any DB works
        self.db = db

    def get_users(self) -> list:
        return self.db.query("SELECT * FROM users")

class InMemoryDB:
    def query(self, sql: str) -> list: return []
    def execute(self, sql: str) -> None: pass

service = UserService(InMemoryDB())   # easy to test/swap
```

---

## 11. Design Patterns

### Creational

#### Singleton

```python
class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, value: int = 0):
        # Guard against re-init on subsequent calls
        if not hasattr(self, "_initialized"):
            self.value = value
            self._initialized = True


s1 = Singleton(10)
s2 = Singleton(20)
print(s1 is s2)       # True
print(s1.value)       # 10 — not 20, init only ran once


# Thread-safe Singleton
import threading

class ThreadSafeSingleton:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:   # double-checked locking
                    cls._instance = super().__new__(cls)
        return cls._instance
```

#### Factory Method

```python
from abc import ABC, abstractmethod

class Notification(ABC):
    @abstractmethod
    def send(self, message: str) -> None: ...

class EmailNotification(Notification):
    def send(self, message: str) -> None:
        print(f"Email: {message}")

class PushNotification(Notification):
    def send(self, message: str) -> None:
        print(f"Push: {message}")

class SMSNotification(Notification):
    def send(self, message: str) -> None:
        print(f"SMS: {message}")


class NotificationFactory:
    _registry: dict = {
        "email": EmailNotification,
        "push": PushNotification,
        "sms": SMSNotification,
    }

    @classmethod
    def create(cls, channel: str) -> Notification:
        klass = cls._registry.get(channel.lower())
        if not klass:
            raise ValueError(f"Unknown channel: {channel}")
        return klass()

    @classmethod
    def register(cls, channel: str, klass: type) -> None:
        cls._registry[channel] = klass


n = NotificationFactory.create("email")
n.send("Hello!")   # Email: Hello!
```

#### Builder

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Pizza:
    size: str
    crust: str
    toppings: List[str] = field(default_factory=list)
    extra_cheese: bool = False
    sauce: str = "tomato"

class PizzaBuilder:
    def __init__(self, size: str):
        self._size = size
        self._crust = "thin"
        self._toppings: List[str] = []
        self._extra_cheese = False
        self._sauce = "tomato"

    def crust(self, crust: str) -> "PizzaBuilder":
        self._crust = crust
        return self   # fluent interface — method chaining

    def add_topping(self, topping: str) -> "PizzaBuilder":
        self._toppings.append(topping)
        return self

    def extra_cheese(self) -> "PizzaBuilder":
        self._extra_cheese = True
        return self

    def sauce(self, sauce: str) -> "PizzaBuilder":
        self._sauce = sauce
        return self

    def build(self) -> Pizza:
        return Pizza(
            size=self._size,
            crust=self._crust,
            toppings=self._toppings,
            extra_cheese=self._extra_cheese,
            sauce=self._sauce,
        )


pizza = (
    PizzaBuilder("large")
    .crust("thick")
    .add_topping("mushrooms")
    .add_topping("peppers")
    .extra_cheese()
    .build()
)
print(pizza)
```

### Structural

#### Decorator Pattern (not @decorator syntax)

```python
from abc import ABC, abstractmethod

class Coffee(ABC):
    @abstractmethod
    def cost(self) -> float: ...
    @abstractmethod
    def description(self) -> str: ...

class SimpleCoffee(Coffee):
    def cost(self) -> float: return 1.0
    def description(self) -> str: return "Simple coffee"

class CoffeeDecorator(Coffee, ABC):
    def __init__(self, coffee: Coffee):
        self._coffee = coffee

    def cost(self) -> float:
        return self._coffee.cost()

    def description(self) -> str:
        return self._coffee.description()

class Milk(CoffeeDecorator):
    def cost(self) -> float:
        return self._coffee.cost() + 0.25
    def description(self) -> str:
        return self._coffee.description() + ", milk"

class Sugar(CoffeeDecorator):
    def cost(self) -> float:
        return self._coffee.cost() + 0.10
    def description(self) -> str:
        return self._coffee.description() + ", sugar"

coffee = Sugar(Milk(SimpleCoffee()))
print(coffee.description())   # Simple coffee, milk, sugar
print(coffee.cost())          # 1.35
```

#### Adapter

```python
# Existing interface clients expect
class EUSocket:
    def plug_in(self, eu_plug) -> str:
        return f"EU plug connected"

# New/third-party class with incompatible interface
class USPlug:
    def connect(self) -> str:
        return "US plug connected"

# Adapter makes USPlug work where EUSocket is expected
class USToEUAdapter:
    def __init__(self, us_plug: USPlug):
        self._us_plug = us_plug

    def plug_in(self, eu_plug=None) -> str:
        return self._us_plug.connect()   # delegates, translating the interface

socket = EUSocket()
us_plug = USPlug()
adapter = USToEUAdapter(us_plug)
print(socket.plug_in(None))     # EU plug connected
print(adapter.plug_in(None))    # US plug connected
```

### Behavioral

#### Observer

```python
from abc import ABC, abstractmethod
from typing import List

class Observer(ABC):
    @abstractmethod
    def update(self, event: str, data) -> None: ...

class Subject:
    def __init__(self):
        self._observers: List[Observer] = []
        self._state = None

    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)

    def notify(self, event: str) -> None:
        for obs in self._observers:
            obs.update(event, self._state)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value) -> None:
        self._state = value
        self.notify("state_changed")


class Logger(Observer):
    def update(self, event: str, data) -> None:
        print(f"[LOG] {event}: {data}")

class AlertService(Observer):
    def update(self, event: str, data) -> None:
        if data and data.get("critical"):
            print(f"[ALERT] Critical state: {data}")


store = Subject()
store.attach(Logger())
store.attach(AlertService())
store.state = {"status": "ok"}
store.state = {"status": "down", "critical": True}
```

#### Strategy

```python
from abc import ABC, abstractmethod
from typing import List

class SortStrategy(ABC):
    @abstractmethod
    def sort(self, data: List[int]) -> List[int]: ...

class BubbleSort(SortStrategy):
    def sort(self, data: List[int]) -> List[int]:
        arr = data[:]
        for i in range(len(arr)):
            for j in range(len(arr) - i - 1):
                if arr[j] > arr[j+1]:
                    arr[j], arr[j+1] = arr[j+1], arr[j]
        return arr

class QuickSort(SortStrategy):
    def sort(self, data: List[int]) -> List[int]:
        if len(data) <= 1:
            return data
        pivot = data[len(data) // 2]
        left = [x for x in data if x < pivot]
        mid = [x for x in data if x == pivot]
        right = [x for x in data if x > pivot]
        return self.sort(left) + mid + self.sort(right)

class Sorter:
    def __init__(self, strategy: SortStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: SortStrategy) -> None:
        self._strategy = strategy

    def sort(self, data: List[int]) -> List[int]:
        return self._strategy.sort(data)

sorter = Sorter(QuickSort())
print(sorter.sort([3, 1, 4, 1, 5]))   # [1, 1, 3, 4, 5]
sorter.set_strategy(BubbleSort())
print(sorter.sort([3, 1, 4, 1, 5]))   # [1, 1, 3, 4, 5]
```

#### Command

```python
from abc import ABC, abstractmethod
from typing import List

class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...
    @abstractmethod
    def undo(self) -> None: ...

class TextEditor:
    def __init__(self):
        self.text = ""

    def insert(self, text: str) -> None:
        self.text += text

    def delete(self, n: int) -> None:
        self.text = self.text[:-n]

class InsertCommand(Command):
    def __init__(self, editor: TextEditor, text: str):
        self.editor = editor
        self.text = text

    def execute(self) -> None:
        self.editor.insert(self.text)

    def undo(self) -> None:
        self.editor.delete(len(self.text))

class CommandHistory:
    def __init__(self):
        self._history: List[Command] = []

    def execute(self, command: Command) -> None:
        command.execute()
        self._history.append(command)

    def undo(self) -> None:
        if self._history:
            self._history.pop().undo()

editor = TextEditor()
history = CommandHistory()

history.execute(InsertCommand(editor, "Hello"))
history.execute(InsertCommand(editor, " World"))
print(editor.text)   # Hello World
history.undo()
print(editor.text)   # Hello
```

---

## 12. Dataclasses

Reduce boilerplate for data-holding classes.

```python
from dataclasses import dataclass, field, asdict, astuple
from typing import List, ClassVar

@dataclass
class Point:
    x: float
    y: float

    def distance_from_origin(self) -> float:
        return (self.x**2 + self.y**2) ** 0.5

@dataclass(order=True, frozen=True)   # frozen = immutable (hashable)
class Version:
    major: int
    minor: int
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080
    tags: List[str] = field(default_factory=list)       # mutable default
    _instance_count: ClassVar[int] = 0                   # not a field

    def __post_init__(self):
        Config._instance_count += 1
        if self.port < 0 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")

v1 = Version(1, 2, 3)
v2 = Version(1, 3, 0)
print(v1 < v2)        # True — order=True uses field order for comparison
print({v1, v2})       # set works — frozen=True makes it hashable

cfg = Config(tags=["prod", "us-east"])
print(asdict(cfg))    # {'host': 'localhost', 'port': 8080, 'tags': ['prod', 'us-east']}
```

---

## 13. LLD Interview Patterns

### Modeling Checklist

1. **Identify entities** → nouns in the problem statement → classes
2. **Identify behaviors** → verbs → methods
3. **Identify relationships** → IS-A (inheritance) vs HAS-A (composition)
4. **Define interfaces first** → what can each entity do?
5. **Apply SOLID** → especially SRP and DIP
6. **Add enums for states** → prevents magic strings

### Enums for State Machines

```python
from enum import Enum, auto

class OrderStatus(Enum):
    PENDING = auto()
    CONFIRMED = auto()
    SHIPPED = auto()
    DELIVERED = auto()
    CANCELLED = auto()

class Order:
    VALID_TRANSITIONS = {
        OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
        OrderStatus.CONFIRMED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
        OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
        OrderStatus.DELIVERED: set(),
        OrderStatus.CANCELLED: set(),
    }

    def __init__(self, order_id: str):
        self.order_id = order_id
        self.status = OrderStatus.PENDING

    def transition_to(self, new_status: OrderStatus) -> None:
        allowed = self.VALID_TRANSITIONS[self.status]
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from {self.status.name} to {new_status.name}"
            )
        self.status = new_status
```

### Dependency Injection Container (simple)

```python
class Container:
    def __init__(self):
        self._factories: dict = {}
        self._singletons: dict = {}

    def register(self, interface, factory, singleton: bool = False) -> None:
        self._factories[interface] = (factory, singleton)

    def resolve(self, interface):
        if interface not in self._factories:
            raise KeyError(f"No registration for {interface}")
        factory, is_singleton = self._factories[interface]
        if is_singleton:
            if interface not in self._singletons:
                self._singletons[interface] = factory()
            return self._singletons[interface]
        return factory()


container = Container()
container.register("db", lambda: InMemoryDB(), singleton=True)
container.register("user_service", lambda: UserService(container.resolve("db")))
```

### Template Method Pattern

```python
class DataProcessor(ABC):
    """Template method defines the skeleton; subclasses fill in steps."""

    def process(self, data: list) -> list:
        data = self.read(data)
        data = self.transform(data)
        data = self.validate(data)
        self.save(data)
        return data

    @abstractmethod
    def read(self, data: list) -> list: ...

    @abstractmethod
    def transform(self, data: list) -> list: ...

    def validate(self, data: list) -> list:
        return [d for d in data if d is not None]   # default implementation

    @abstractmethod
    def save(self, data: list) -> None: ...

class CSVProcessor(DataProcessor):
    def read(self, data: list) -> list:
        print("Reading CSV"); return data

    def transform(self, data: list) -> list:
        return [str(d).upper() for d in data]

    def save(self, data: list) -> None:
        print(f"Saving {len(data)} rows to CSV")
```

### Quick Reference: Python OOP Cheatsheet

```
Class definition         class Foo(Base): ...
Instantiation           obj = Foo(args)
Constructor             def __init__(self, ...): ...
String representation   def __repr__(self): ...  /  def __str__(self): ...
Equality                def __eq__(self, other): ...
Comparison              def __lt__(self, other): ...  (+@total_ordering)
Hashing                 def __hash__(self): ...
Length                  def __len__(self): ...
Iteration               def __iter__(self): ...  /  def __next__(self): ...
Subscript               def __getitem__(self, key): ...
Callable                def __call__(self, ...): ...
Context manager         def __enter__(self): ...  /  def __exit__(self, ...): ...
Arithmetic              def __add__, __sub__, __mul__, __truediv__
Reverse arithmetic      def __radd__, __rmul__, ...  (e.g., 3 * MyObj)
In-place arithmetic     def __iadd__, __imul__, ...  (+=, *=)

Property                @property  /  @x.setter  /  @x.deleter
Class method            @classmethod  def f(cls, ...)
Static method           @staticmethod  def f(...)
Abstract method         @abstractmethod  (requires ABC base class)
Abstract property       @property + @abstractmethod

Inheritance             class Child(Parent): ...
Multiple inheritance    class Child(A, B, C): ...
MRO inspection          ClassName.__mro__  or  ClassName.mro()
Cooperative super()     super().method(...)
Check inheritance       isinstance(obj, Class)  /  issubclass(Child, Parent)
```

---

*Built for Python LLD interviews — focus on clear abstractions, SOLID design, and idiomatic Python.*

---

## 14. Worked LLD Problems

### How to approach any LLD problem (5-step framework)

```
1. Clarify requirements    — ask about scale, edge cases, actors
2. Identify entities       — nouns → classes
3. Define relationships    — IS-A vs HAS-A, cardinality (1:1, 1:N, M:N)
4. Define interfaces first — what can each entity DO? (methods)
5. Write code bottom-up    — leaf classes first, then aggregators, then the facade
```

---

### 14.1 Parking Lot

**Requirements:**
- Multiple floors, each with parking spots of three sizes: Small, Medium, Large
- Vehicle types: Motorcycle (fits Small+), Car (fits Medium+), Truck (Large only)
- Issue a ticket on entry; calculate fee on exit (hourly, per vehicle type)
- Support pluggable pricing strategies

**Entities & relationships:**
```
ParkingLot  HAS-MANY  ParkingFloor
ParkingFloor HAS-MANY ParkingSpot
ParkingSpot  HAS-ONE  Vehicle  (when occupied)
Ticket       HAS-ONE  Vehicle, HAS-ONE ParkingSpot
PricingStrategy <<interface>>
```

```python
from abc import ABC, abstractmethod
from enum import Enum, auto
from datetime import datetime
from typing import Optional, List, Dict
import math


# ── Enums ──────────────────────────────────────────────────────────────────────

class VehicleType(Enum):
    MOTORCYCLE = auto()
    CAR = auto()
    TRUCK = auto()

class SpotSize(Enum):
    SMALL = auto()
    MEDIUM = auto()
    LARGE = auto()


# ── Vehicle hierarchy ──────────────────────────────────────────────────────────

class Vehicle(ABC):
    def __init__(self, license_plate: str, vehicle_type: VehicleType):
        self.license_plate = license_plate
        self.vehicle_type = vehicle_type

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.license_plate!r})"

class Motorcycle(Vehicle):
    def __init__(self, plate: str):
        super().__init__(plate, VehicleType.MOTORCYCLE)

class Car(Vehicle):
    def __init__(self, plate: str):
        super().__init__(plate, VehicleType.CAR)

class Truck(Vehicle):
    def __init__(self, plate: str):
        super().__init__(plate, VehicleType.TRUCK)


# ── ParkingSpot ────────────────────────────────────────────────────────────────

class ParkingSpot:
    # Which vehicle types fit in each spot size
    _FITS: Dict[SpotSize, set] = {
        SpotSize.SMALL:  {VehicleType.MOTORCYCLE},
        SpotSize.MEDIUM: {VehicleType.MOTORCYCLE, VehicleType.CAR},
        SpotSize.LARGE:  {VehicleType.MOTORCYCLE, VehicleType.CAR, VehicleType.TRUCK},
    }

    def __init__(self, spot_id: str, size: SpotSize):
        self.spot_id = spot_id
        self.size = size
        self._vehicle: Optional[Vehicle] = None

    @property
    def is_available(self) -> bool:
        return self._vehicle is None

    def can_fit(self, vehicle: Vehicle) -> bool:
        return vehicle.vehicle_type in self._FITS[self.size]

    def park(self, vehicle: Vehicle) -> None:
        if not self.is_available:
            raise ValueError(f"Spot {self.spot_id} already occupied")
        if not self.can_fit(vehicle):
            raise ValueError(f"{vehicle} doesn't fit in {self.size.name} spot")
        self._vehicle = vehicle

    def vacate(self) -> Vehicle:
        if self.is_available:
            raise ValueError(f"Spot {self.spot_id} is empty")
        vehicle, self._vehicle = self._vehicle, None
        return vehicle

    def __repr__(self) -> str:
        status = "free" if self.is_available else f"occupied by {self._vehicle}"
        return f"Spot({self.spot_id}, {self.size.name}, {status})"


# ── Ticket ─────────────────────────────────────────────────────────────────────

class Ticket:
    def __init__(self, ticket_id: str, vehicle: Vehicle, spot: ParkingSpot):
        self.ticket_id = ticket_id
        self.vehicle = vehicle
        self.spot = spot
        self.entry_time: datetime = datetime.now()
        self.exit_time: Optional[datetime] = None

    def close(self) -> None:
        self.exit_time = datetime.now()

    @property
    def duration_hours(self) -> float:
        end = self.exit_time or datetime.now()
        return (end - self.entry_time).total_seconds() / 3600

    def __repr__(self) -> str:
        return f"Ticket({self.ticket_id!r}, {self.vehicle})"


# ── Pricing strategies (Strategy pattern) ─────────────────────────────────────

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, ticket: Ticket) -> float: ...

class HourlyPricing(PricingStrategy):
    _RATES = {
        VehicleType.MOTORCYCLE: 20,
        VehicleType.CAR:        40,
        VehicleType.TRUCK:      80,
    }

    def calculate(self, ticket: Ticket) -> float:
        hours = max(1, math.ceil(ticket.duration_hours))
        return hours * self._RATES[ticket.vehicle.vehicle_type]

class FlatRatePricing(PricingStrategy):
    def __init__(self, rate: float):
        self._rate = rate

    def calculate(self, ticket: Ticket) -> float:
        return self._rate


# ── ParkingFloor ───────────────────────────────────────────────────────────────

class ParkingFloor:
    def __init__(self, floor_number: int, spots: List[ParkingSpot]):
        self.floor_number = floor_number
        self._spots = spots

    def find_spot(self, vehicle: Vehicle) -> Optional[ParkingSpot]:
        return next(
            (s for s in self._spots if s.is_available and s.can_fit(vehicle)),
            None,
        )

    def availability(self) -> Dict[SpotSize, int]:
        counts: Dict[SpotSize, int] = {s: 0 for s in SpotSize}
        for spot in self._spots:
            if spot.is_available:
                counts[spot.size] += 1
        return counts


# ── ParkingLot (facade) ────────────────────────────────────────────────────────

class ParkingLot:
    def __init__(self, name: str, floors: List[ParkingFloor], pricing: PricingStrategy):
        self.name = name
        self._floors = floors
        self._pricing = pricing
        self._active_tickets: Dict[str, Ticket] = {}
        self._counter = 0

    def _new_ticket_id(self) -> str:
        self._counter += 1
        return f"TKT-{self._counter:05d}"

    def park(self, vehicle: Vehicle) -> Ticket:
        for floor in self._floors:
            spot = floor.find_spot(vehicle)
            if spot:
                spot.park(vehicle)
                ticket = Ticket(self._new_ticket_id(), vehicle, spot)
                self._active_tickets[ticket.ticket_id] = ticket
                print(f"[ENTRY] {vehicle} → {spot.spot_id}  |  Ticket: {ticket.ticket_id}")
                return ticket
        raise RuntimeError("Parking lot is full")

    def exit(self, ticket_id: str) -> float:
        ticket = self._active_tickets.pop(ticket_id, None)
        if not ticket:
            raise ValueError(f"Ticket {ticket_id!r} not found")
        ticket.close()
        ticket.spot.vacate()
        fee = self._pricing.calculate(ticket)
        print(f"[EXIT]  {ticket.vehicle}  |  Duration: {ticket.duration_hours:.2f}h  |  Fee: ₹{fee}")
        return fee

    def display_availability(self) -> None:
        print(f"\n── {self.name} availability ──")
        for floor in self._floors:
            print(f"  Floor {floor.floor_number}: {floor.availability()}")


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    spots_f1 = [
        ParkingSpot("F1-S1", SpotSize.SMALL),
        ParkingSpot("F1-M1", SpotSize.MEDIUM),
        ParkingSpot("F1-M2", SpotSize.MEDIUM),
        ParkingSpot("F1-L1", SpotSize.LARGE),
    ]
    lot = ParkingLot("Central Park", [ParkingFloor(1, spots_f1)], HourlyPricing())

    t1 = lot.park(Car("KA-01-1234"))
    t2 = lot.park(Motorcycle("KA-02-9999"))
    lot.display_availability()
    lot.exit(t1.ticket_id)
```

**Key design decisions:**
- `_FITS` dict in `ParkingSpot` is the single source of truth for size compatibility — no if-else chains in multiple places
- `PricingStrategy` is injected → swap pricing without touching `ParkingLot`
- `ParkingLot` is the facade — callers never touch `Floor` or `Spot` directly
- `Ticket` owns the duration logic — `PricingStrategy` only needs a `Ticket`

---

### 14.2 Library Management System

**Requirements:**
- Books have multiple physical copies (BookItems)
- Members can borrow up to 5 books; blocked if overdue
- 14-day loan period; ₹1/day fine after that
- Search by title, author, ISBN
- Librarians add/remove book items

**Entities & relationships:**
```
Library     HAS-ONE  Catalog
Catalog     HAS-MANY Book
Book        HAS-MANY BookItem          (1 ISBN, many physical copies)
Member      HAS-MANY Lending (active)
Lending     HAS-ONE  BookItem, Member  (join entity)
```

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional
import uuid


# ── Enums ──────────────────────────────────────────────────────────────────────

class BookStatus(Enum):
    AVAILABLE  = auto()
    LOANED     = auto()
    RESERVED   = auto()
    LOST       = auto()

class MemberStatus(Enum):
    ACTIVE    = auto()
    SUSPENDED = auto()


# ── Book & BookItem ────────────────────────────────────────────────────────────

class Book:
    def __init__(self, isbn: str, title: str, author: str, subject: str):
        self.isbn = isbn
        self.title = title
        self.author = author
        self.subject = subject
        self._items: List["BookItem"] = []

    def add_item(self, item: "BookItem") -> None:
        self._items.append(item)

    def remove_item(self, barcode: str) -> None:
        self._items = [i for i in self._items if i.barcode != barcode]

    def available_items(self) -> List["BookItem"]:
        return [i for i in self._items if i.status == BookStatus.AVAILABLE]

    def __repr__(self) -> str:
        return f"Book({self.isbn!r}, {self.title!r}, copies={len(self._items)})"


class BookItem:
    def __init__(self, barcode: str, book: Book):
        self.barcode = barcode
        self.book = book
        self.status = BookStatus.AVAILABLE

    def __repr__(self) -> str:
        return f"BookItem({self.barcode!r}, {self.status.name})"


# ── Lending (the transaction) ──────────────────────────────────────────────────

class Lending:
    LOAN_DAYS = 14
    FINE_PER_DAY = 1.0

    def __init__(self, book_item: BookItem, member: "Member"):
        self.lending_id: str = uuid.uuid4().hex[:8]
        self.book_item = book_item
        self.member = member
        self.checkout_date: datetime = datetime.now()
        self.due_date: datetime = self.checkout_date + timedelta(days=self.LOAN_DAYS)
        self.return_date: Optional[datetime] = None

    @property
    def is_returned(self) -> bool:
        return self.return_date is not None

    @property
    def is_overdue(self) -> bool:
        end = self.return_date or datetime.now()
        return end > self.due_date

    @property
    def fine(self) -> float:
        if not self.is_overdue:
            return 0.0
        end = self.return_date or datetime.now()
        days = (end - self.due_date).days
        return days * self.FINE_PER_DAY

    def __repr__(self) -> str:
        return f"Lending({self.lending_id!r}, {self.book_item.barcode!r})"


# ── Member ─────────────────────────────────────────────────────────────────────

class Member:
    MAX_BOOKS = 5

    def __init__(self, member_id: str, name: str):
        self.member_id = member_id
        self.name = name
        self.status = MemberStatus.ACTIVE
        self._active: List[Lending] = []
        self._history: List[Lending] = []

    def can_borrow(self) -> bool:
        if self.status != MemberStatus.ACTIVE:
            return False
        if len(self._active) >= self.MAX_BOOKS:
            return False
        if any(l.is_overdue for l in self._active):
            return False
        return True

    def _add_lending(self, lending: Lending) -> None:
        self._active.append(lending)

    def _close_lending(self, lending: Lending) -> float:
        self._active.remove(lending)
        self._history.append(lending)
        return lending.fine

    def __repr__(self) -> str:
        return f"Member({self.member_id!r}, {self.name!r}, books={len(self._active)})"


# ── Catalog ────────────────────────────────────────────────────────────────────

class Catalog:
    def __init__(self):
        self._books: Dict[str, Book] = {}   # isbn → Book

    def add_book(self, book: Book) -> None:
        self._books[book.isbn] = book

    def search_by_title(self, title: str) -> List[Book]:
        q = title.lower()
        return [b for b in self._books.values() if q in b.title.lower()]

    def search_by_author(self, author: str) -> List[Book]:
        q = author.lower()
        return [b for b in self._books.values() if q in b.author.lower()]

    def search_by_isbn(self, isbn: str) -> Optional[Book]:
        return self._books.get(isbn)


# ── Library (facade) ───────────────────────────────────────────────────────────

class Library:
    def __init__(self, name: str):
        self.name = name
        self.catalog = Catalog()
        self._members: Dict[str, Member] = {}
        self._lendings: Dict[str, Lending] = {}  # lending_id → Lending

    def register_member(self, member: Member) -> None:
        self._members[member.member_id] = member

    def checkout(self, member_id: str, isbn: str) -> Lending:
        member = self._members.get(member_id)
        if not member:
            raise ValueError("Member not found")
        if not member.can_borrow():
            raise ValueError("Member cannot borrow: overdue books or limit reached")

        book = self.catalog.search_by_isbn(isbn)
        if not book:
            raise ValueError(f"Book {isbn!r} not in catalog")

        available = book.available_items()
        if not available:
            raise ValueError("No copies currently available")

        item = available[0]
        item.status = BookStatus.LOANED

        lending = Lending(item, member)
        member._add_lending(lending)
        self._lendings[lending.lending_id] = lending

        print(f"[CHECKOUT] {member.name} borrowed '{book.title}' → due {lending.due_date.date()}")
        return lending

    def return_book(self, lending_id: str) -> float:
        lending = self._lendings.get(lending_id)
        if not lending:
            raise ValueError("Lending record not found")

        lending.return_date = datetime.now()
        lending.book_item.status = BookStatus.AVAILABLE

        fine = lending.member._close_lending(lending)
        msg = f"Fine: ₹{fine:.1f}" if fine else "No fine"
        print(f"[RETURN]  '{lending.book_item.book.title}' returned by {lending.member.name}. {msg}")
        return fine


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    lib = Library("City Library")

    book = Book("978-0-13-468599-1", "Clean Code", "Robert Martin", "Programming")
    book.add_item(BookItem("BC001", book))
    book.add_item(BookItem("BC002", book))
    lib.catalog.add_book(book)

    alice = Member("M001", "Alice")
    lib.register_member(alice)

    lending = lib.checkout("M001", "978-0-13-468599-1")
    lib.return_book(lending.lending_id)
```

**Key design decisions:**
- `Book` ≠ `BookItem`: one ISBN can have many physical copies — a common mistake is merging them
- `Lending` is the join entity between `Member` and `BookItem`, and owns all transaction logic (fine, due date)
- `Member.can_borrow()` encapsulates all borrowing rules — one place to change policy
- `Library` is the facade; external code never manipulates `BookItem.status` directly

---

### 14.3 Elevator System

**Requirements:**
- N elevators, M floors
- External requests: person on floor X presses UP/DOWN
- Internal requests: passenger inside presses destination floor
- SCAN algorithm (elevator services requests in its current direction first)
- Dispatcher picks the elevator with minimum cost

**Entities & relationships:**
```
ElevatorSystem  HAS-MANY  Elevator
ElevatorSystem  IS        Dispatcher
Elevator        HAS       two priority queues (up / down)
Request         VALUE OBJECT (floor + direction)
```

```python
from enum import Enum, auto
from typing import List, Optional
import heapq


# ── Enums ──────────────────────────────────────────────────────────────────────

class Direction(Enum):
    UP   = auto()
    DOWN = auto()
    IDLE = auto()

class DoorStatus(Enum):
    OPEN   = auto()
    CLOSED = auto()


# ── Elevator ───────────────────────────────────────────────────────────────────

class Elevator:
    def __init__(self, elevator_id: int):
        self.elevator_id = elevator_id
        self.current_floor = 0
        self.direction = Direction.IDLE
        self.door = DoorStatus.CLOSED
        self._up_stops: list = []    # min-heap  → serve ascending
        self._down_stops: list = []  # max-heap via negation → serve descending

    # ── public API ─────────────────────────────────────────────────────────────

    def add_stop(self, floor: int) -> None:
        if floor > self.current_floor:
            heapq.heappush(self._up_stops, floor)
        elif floor < self.current_floor:
            heapq.heappush(self._down_stops, -floor)
        # floor == current_floor: already here, open doors
        else:
            self._open_doors()

    def step(self) -> None:
        """Advance one floor toward the next stop (SCAN algorithm)."""
        target = self._next_target()
        if target is None:
            self.direction = Direction.IDLE
            return

        self.direction = Direction.UP if target > self.current_floor else Direction.DOWN
        # Move one floor at a time
        self.current_floor += 1 if self.direction == Direction.UP else -1

        if self.current_floor == target:
            self._open_doors()
            self._close_doors()

    def cost_to_serve(self, floor: int) -> int:
        """Heuristic: floors to travel before reaching `floor`."""
        return abs(self.current_floor - floor)

    # ── internals ──────────────────────────────────────────────────────────────

    def _next_target(self) -> Optional[int]:
        """SCAN: continue in current direction; reverse when exhausted."""
        if self.direction in (Direction.UP, Direction.IDLE):
            if self._up_stops:
                return self._up_stops[0]        # peek
            if self._down_stops:
                return -self._down_stops[0]
        else:  # DOWN
            if self._down_stops:
                return -self._down_stops[0]
            if self._up_stops:
                return self._up_stops[0]
        return None

    def _consume_target(self, floor: int) -> None:
        if self.direction in (Direction.UP, Direction.IDLE) and self._up_stops and self._up_stops[0] == floor:
            heapq.heappop(self._up_stops)
        elif self._down_stops and -self._down_stops[0] == floor:
            heapq.heappop(self._down_stops)

    def _open_doors(self) -> None:
        self.door = DoorStatus.OPEN
        print(f"  Elevator {self.elevator_id} ── doors OPEN  at floor {self.current_floor}")

    def _close_doors(self) -> None:
        self.door = DoorStatus.CLOSED
        self._consume_target(self.current_floor)
        print(f"  Elevator {self.elevator_id} ── doors CLOSED at floor {self.current_floor}")

    def __repr__(self) -> str:
        return f"Elevator({self.elevator_id}, floor={self.current_floor}, {self.direction.name})"


# ── ElevatorSystem (dispatcher + facade) ──────────────────────────────────────

class ElevatorSystem:
    def __init__(self, num_elevators: int, num_floors: int):
        self.num_floors = num_floors
        self.elevators: List[Elevator] = [Elevator(i) for i in range(num_elevators)]

    # External request (hall button)
    def call_elevator(self, floor: int, direction: Direction) -> Elevator:
        if not (0 <= floor < self.num_floors):
            raise ValueError(f"Floor {floor} out of range")
        elevator = self._dispatch(floor)
        elevator.add_stop(floor)
        print(f"[DISPATCH] Floor {floor} ({direction.name}) → Elevator {elevator.elevator_id}")
        return elevator

    # Internal request (cabin button)
    def select_floor(self, elevator_id: int, floor: int) -> None:
        self.elevators[elevator_id].add_stop(floor)
        print(f"[SELECT]   Elevator {elevator_id} → Floor {floor}")

    def step_all(self) -> None:
        for e in self.elevators:
            e.step()

    def status(self) -> None:
        for e in self.elevators:
            print(f"  {e}")

    def _dispatch(self, floor: int) -> Elevator:
        return min(self.elevators, key=lambda e: e.cost_to_serve(floor))


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    system = ElevatorSystem(num_elevators=2, num_floors=10)

    e = system.call_elevator(floor=5, direction=Direction.UP)
    system.select_floor(e.elevator_id, floor=8)

    print("\nSimulating movement:")
    for _ in range(10):
        system.step_all()
    system.status()
```

**Key design decisions:**
- SCAN (two heaps) is simpler and fairer than FCFS — use it as the default unless asked for something specific
- `step()` moves one floor at a time — makes the simulation testable at each tick
- `cost_to_serve()` is a pluggable heuristic; you can swap to "same-direction" dispatching without changing `ElevatorSystem`
- External vs internal requests are both funnelled through `add_stop()` — they differ only in *who* calls it

---

### 14.4 Movie Ticket Booking (BookMyShow)

**Requirements:**
- Theatres have Screens; Screens run Shows for a Movie
- Each Show has Seats with different types (Regular / Premium / VIP) and prices
- Users book 1–N seats for a show; seats are temporarily blocked during payment
- Booking can be confirmed or cancelled (releases seats)
- Prevent double-booking (seat locked before payment completes)

**Entities & relationships:**
```
Theatre     HAS-MANY  Screen
Screen      HAS-MANY  Seat (physical, reused across shows)
Show        HAS-ONE   Movie, Screen
Show        HAS-MANY  ShowSeat      (show-specific seat state)
Booking     HAS-ONE   Show, User
Booking     HAS-MANY  ShowSeat
```

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
    BLOCKED   = auto()   # temporarily held during checkout
    BOOKED    = auto()

class BookingStatus(Enum):
    PENDING   = auto()
    CONFIRMED = auto()
    CANCELLED = auto()


# ── Core domain objects ────────────────────────────────────────────────────────

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
    """Physical seat in a screen — row/number never change."""
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
    seats: List[Seat] = field(default_factory=list)


@dataclass
class Theatre:
    theatre_id: str
    name: str
    city: str
    screens: List[Screen] = field(default_factory=list)


# ── ShowSeat — per-show mutable state ──────────────────────────────────────────

class ShowSeat:
    """
    Wraps a physical Seat with show-specific status and price.
    Status transitions: AVAILABLE → BLOCKED → BOOKED
                                    BLOCKED → AVAILABLE  (on cancel/timeout)
    """
    PRICES: Dict[SeatType, float] = {
        SeatType.REGULAR: 150,
        SeatType.PREMIUM: 250,
        SeatType.VIP:     500,
    }

    def __init__(self, seat: Seat):
        self.seat = seat
        self.status = SeatStatus.AVAILABLE
        self.price: float = self.PRICES[seat.seat_type]

    def block(self) -> None:
        if self.status != SeatStatus.AVAILABLE:
            raise ValueError(f"Seat {self.seat} is not available (status={self.status.name})")
        self.status = SeatStatus.BLOCKED

    def confirm(self) -> None:
        if self.status != SeatStatus.BLOCKED:
            raise ValueError(f"Seat {self.seat} must be BLOCKED before confirming")
        self.status = SeatStatus.BOOKED

    def release(self) -> None:
        self.status = SeatStatus.AVAILABLE

    def __repr__(self) -> str:
        return f"ShowSeat({self.seat}, {self.status.name})"


# ── Show ───────────────────────────────────────────────────────────────────────

class Show:
    def __init__(self, show_id: str, movie: Movie, screen: Screen, start_time: datetime):
        self.show_id = show_id
        self.movie = movie
        self.screen = screen
        self.start_time = start_time
        # One ShowSeat per physical seat
        self._show_seats: Dict[str, ShowSeat] = {
            s.seat_id: ShowSeat(s) for s in screen.seats
        }

    def available_seats(self) -> List[ShowSeat]:
        return [ss for ss in self._show_seats.values() if ss.status == SeatStatus.AVAILABLE]

    def get_show_seat(self, seat_id: str) -> ShowSeat:
        ss = self._show_seats.get(seat_id)
        if not ss:
            raise ValueError(f"Seat {seat_id!r} not in this show")
        return ss

    def block_seats(self, seat_ids: List[str]) -> List[ShowSeat]:
        show_seats = [self.get_show_seat(sid) for sid in seat_ids]
        for ss in show_seats:
            ss.block()          # raises if any seat is unavailable
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

class Booking:
    def __init__(self, booking_id: str, user_id: str, show: Show, show_seats: List[ShowSeat]):
        self.booking_id = booking_id
        self.user_id = user_id
        self.show = show
        self.show_seats = show_seats
        self.status = BookingStatus.PENDING
        self.total_amount: float = sum(ss.price for ss in show_seats)
        self.created_at = datetime.now()

    def confirm(self) -> None:
        self.show.confirm_seats([ss.seat.seat_id for ss in self.show_seats])
        self.status = BookingStatus.CONFIRMED
        print(f"[CONFIRMED] {self.booking_id}  seats={[ss.seat for ss in self.show_seats]}  ₹{self.total_amount}")

    def cancel(self) -> None:
        self.show.release_seats([ss.seat.seat_id for ss in self.show_seats])
        self.status = BookingStatus.CANCELLED
        print(f"[CANCELLED] {self.booking_id}")

    def __repr__(self) -> str:
        return f"Booking({self.booking_id!r}, {self.status.name}, ₹{self.total_amount})"


# ── BookingService (facade) ────────────────────────────────────────────────────

class BookingService:
    def __init__(self):
        self._bookings: Dict[str, Booking] = {}

    def initiate(self, user_id: str, show: Show, seat_ids: List[str]) -> Booking:
        """Block seats and create a PENDING booking."""
        show_seats = show.block_seats(seat_ids)   # atomic; raises on conflict
        booking_id = uuid.uuid4().hex[:8].upper()
        booking = Booking(booking_id, user_id, show, show_seats)
        self._bookings[booking_id] = booking
        print(f"[PENDING]  {booking_id}  {show}  seats={seat_ids}")
        return booking

    def confirm(self, booking_id: str) -> Booking:
        """Called after successful payment."""
        booking = self._get(booking_id)
        if booking.status != BookingStatus.PENDING:
            raise ValueError("Only PENDING bookings can be confirmed")
        booking.confirm()
        return booking

    def cancel(self, booking_id: str) -> None:
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
    # Setup
    seats = [
        Seat("S1", "A", 1, SeatType.REGULAR),
        Seat("S2", "A", 2, SeatType.REGULAR),
        Seat("S3", "B", 1, SeatType.PREMIUM),
        Seat("S4", "C", 1, SeatType.VIP),
    ]
    screen = Screen("SC1", "Screen 1", seats)
    theatre = Theatre("TH1", "PVR Cinemas", "Bangalore", [screen])
    movie = Movie("M1", "Inception", 148)

    show = Show("SH1", movie, screen, datetime(2024, 6, 15, 18, 30))
    service = BookingService()

    # Alice books S1 and S3
    booking = service.initiate("user_alice", show, ["S1", "S3"])
    service.confirm(booking.booking_id)

    # Bob tries to book S1 (already booked) — raises ValueError
    try:
        service.initiate("user_bob", show, ["S1"])
    except ValueError as e:
        print(f"[ERROR] {e}")

    print(f"\nAvailable seats: {show.available_seats()}")
```

**Key design decisions:**
- `Seat` (physical) vs `ShowSeat` (show-specific state) is the crucial split — seats are reused across shows but status is per-show
- `block_seats()` is the atomic lock — all-or-nothing, called before payment begins; prevents double-booking at the service layer
- `Booking.confirm()` / `cancel()` delegate seat state changes back to `Show` — single source of truth
- `BookingService` is the facade; the controller/API layer only talks to it

---

### LLD Problem-Solving Template

Use this skeleton at the start of every LLD interview:

```python
from abc import ABC, abstractmethod
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import uuid

# 1. Enums for all states / types
class Status(Enum):
    ...

# 2. Value objects / simple data holders (dataclass or frozen dataclass)
@dataclass(frozen=True)
class Address:
    ...

# 3. Core entities (mutable, own business rules)
class Entity:
    def __init__(self, ...):
        self.id = uuid.uuid4().hex[:8]
        ...

    def some_action(self) -> None:
        # validate → mutate → notify
        ...

# 4. Interfaces / abstract base classes
class Repository(ABC):
    @abstractmethod
    def save(self, entity: Entity) -> None: ...

    @abstractmethod
    def find_by_id(self, id: str) -> Optional[Entity]: ...

# 5. Strategies / policies (pluggable behaviors)
class PricingPolicy(ABC):
    @abstractmethod
    def calculate(self, ...) -> float: ...

# 6. Service / Facade (orchestrates entities, owns use-case logic)
class DomainService:
    def __init__(self, repo: Repository, policy: PricingPolicy):
        self._repo = repo
        self._policy = policy

    def do_use_case(self, ...) -> ...:
        # 1. fetch  2. validate  3. execute  4. persist  5. return
        ...
```
