# 05 — Instance, Class, and Static Methods

## What is this?

Python has three kinds of methods on a class. They differ in what they can "see" — a regular method sees the specific object it was called on, a class method sees the class itself, and a static method sees neither. Knowing when to use each one is a surprisingly common LLD interview topic.

---

## The three method types at a glance

Before diving into each one, here is the full picture:

| Method type | First parameter | Can access | Defined with |
|---|---|---|---|
| Instance method | `self` (the object) | object state + class state | `def f(self, ...)` |
| Class method | `cls` (the class) | class state only | `@classmethod` |
| Static method | nothing | neither | `@staticmethod` |

> Think of it like a restaurant. An instance method is a specific waiter serving your table — they know your order and your table number. A class method is the restaurant manager — they know restaurant-wide things like how many tables are occupied. A static method is a recipe pinned to the kitchen wall — it is related to the restaurant, but it doesn't need to know anything about a specific table or even about today's service.

---

## Instance methods

This is the normal kind of method you write every day. The first parameter is always `self`, which is the specific object the method was called on.

Here is a simple counter class. The `describe` method uses `self` because the answer is different for each counter instance:

```python
class Counter:
    _count = 0   # class variable — shared by all instances

    def __init__(self, name: str):
        Counter._count += 1
        self.name = name
        self.id = Counter._count

    # Instance method — answer depends on which Counter object we are
    def describe(self) -> str:
        return f"Counter #{self.id}: {self.name}"
```

```python
c1 = Counter("A")
c2 = Counter("B")
print(c1.describe())   # Counter #1: A
print(c2.describe())   # Counter #2: B
```

> **Key takeaway:** Use an instance method whenever the behavior depends on the state of a *specific object*.

---

## Class methods

A class method receives the *class* (`cls`) as its first argument, not a specific instance. It is decorated with `@classmethod`.

Adding class methods to the counter example — these operate on the shared `_count` variable, not on any specific counter:

```python
    @classmethod
    def get_count(cls) -> int:
        return cls._count

    @classmethod
    def reset(cls) -> None:
        cls._count = 0
```

Notice we write `cls._count` instead of `Counter._count`. This matters for inheritance — if a subclass calls `get_count()`, `cls` will be that subclass, not `Counter`. More on this below.

```python
c1 = Counter("A")
c2 = Counter("B")
print(Counter.get_count())   # 2
Counter.reset()
print(Counter.get_count())   # 0
```

You can call class methods on an instance too (`c1.get_count()`), but calling them on the class (`Counter.get_count()`) makes the intent clearer.

> **Key takeaway:** Use a class method when the behavior belongs to the *class as a whole*, not to any particular instance.

---

## Static methods

A static method gets no automatic first argument at all — no `self`, no `cls`. It is decorated with `@staticmethod`. It is a plain function that lives inside the class because it is logically related to it.

Adding a static validation helper to the counter:

```python
    # Static method — pure utility, no access to instance or class state
    @staticmethod
    def validate_name(name: str) -> bool:
        return isinstance(name, str) and len(name) > 0
```

```python
print(Counter.validate_name("A"))    # True
print(Counter.validate_name(""))     # False
```

> Think of static methods as helper functions that are "namespaced" inside the class. They could live as a standalone function, but placing them on the class keeps related code together.

> **Key takeaway:** Use a static method for utility logic that is *related* to the class conceptually but does not depend on any object or class state.

---

## Putting it all together

Here is the full `Counter` class showing all three method types:

```python
class Counter:
    _count = 0

    def __init__(self, name: str):
        Counter._count += 1
        self.name = name
        self.id = Counter._count

    def describe(self) -> str:                  # instance method
        return f"Counter #{self.id}: {self.name}"

    @classmethod
    def get_count(cls) -> int:                  # class method
        return cls._count

    @classmethod
    def reset(cls) -> None:                     # class method
        cls._count = 0

    @staticmethod
    def validate_name(name: str) -> bool:       # static method
        return isinstance(name, str) and len(name) > 0


c1 = Counter("A")
c2 = Counter("B")
print(Counter.get_count())           # 2
print(Counter.validate_name("A"))    # True
print(c1.describe())                 # Counter #1: A
```

> **What just happened?** Three kinds of method, three different "views" of the world. `describe` knows about one specific counter. `get_count` knows about all counters. `validate_name` knows about neither — it just checks a string.

---

## The alternative constructor pattern (very common in LLD)

This is the most important use of `@classmethod` in real-world Python and LLD interviews. A class normally has one `__init__`. But sometimes you want multiple ways to *create* an object — from a string, from a file, from today's date, etc.

> Think of `@classmethod` constructors like the different entrances to a building. The front door (`__init__`) is the main way in. But there might be a side door for staff (`from_string`) and a delivery entrance for automated systems (`today`). They all put you inside the same building.

Here is a `Date` class with two alternative constructors:

```python
class Date:
    def __init__(self, year: int, month: int, day: int):
        self.year = year
        self.month = month
        self.day = day

    @classmethod
    def from_string(cls, date_str: str) -> "Date":
        """Create a Date from a 'YYYY-MM-DD' string."""
        year, month, day = map(int, date_str.split("-"))
        return cls(year, month, day)   # cls() instead of Date() — works for subclasses too

    @classmethod
    def today(cls) -> "Date":
        """Create a Date from today's actual date."""
        from datetime import date
        d = date.today()
        return cls(d.year, d.month, d.day)

    def __repr__(self) -> str:
        return f"Date({self.year}, {self.month}, {self.day})"
```

Now callers have multiple clean ways to create a `Date`:

```python
d1 = Date(2024, 1, 15)                  # normal constructor
d2 = Date.from_string("2024-01-15")     # from a string
d3 = Date.today()                       # from today's date
print(d2)   # Date(2024, 1, 15)
```

> **What just happened?** Instead of forcing the caller to parse the string themselves and then call `Date(...)`, we moved that logic inside the class where it belongs. Each class method constructor reads like plain English — `Date.from_string(...)`, `Date.today()`.

**Why use `cls(...)` instead of `Date(...)`?**

Because of inheritance. If someone creates a `BirthDate(Date)` subclass and calls `BirthDate.from_string(...)`, using `cls(...)` returns a `BirthDate` object (correct). Using `Date(...)` hardcoded would return a plain `Date` object (wrong).

---

## Static methods as pure utility

Static methods are great for helper logic that validates inputs, converts formats, or does calculations — but has no need to read or write class or instance state.

```python
class Temperature:
    def __init__(self, celsius: float):
        self.celsius = celsius

    @staticmethod
    def celsius_to_fahrenheit(c: float) -> float:
        return c * 9 / 5 + 32

    @staticmethod
    def fahrenheit_to_celsius(f: float) -> float:
        return (f - 32) * 5 / 9

print(Temperature.celsius_to_fahrenheit(100))   # 212.0
print(Temperature.fahrenheit_to_celsius(32))    # 0.0
```

These could be standalone functions, but placing them on `Temperature` keeps temperature-related logic in one place.

---

## Common mistakes

### 1. Using an instance method when a class method is appropriate

This ties class-level logic to a specific object, which is confusing:

```python
# WRONG — why does a specific counter have to call reset?
c1 = Counter("A")
c1.reset()    # works, but suggests the reset belongs to c1 specifically

# CORRECT — reset is a class-level concern
Counter.reset()
```

### 2. Using `Counter._count` instead of `cls._count` in a class method

```python
# FRAGILE — breaks if a subclass overrides _count
@classmethod
def get_count(cls) -> int:
    return Counter._count   # hardcoded class name

# CORRECT — uses whatever class called the method
@classmethod
def get_count(cls) -> int:
    return cls._count
```

### 3. Adding `self` to a static method or `@classmethod` decorator to a normal method

```python
# WRONG — static methods don't receive self
@staticmethod
def validate_name(self, name: str) -> bool:   # self here is actually the name argument!
    ...

# CORRECT
@staticmethod
def validate_name(name: str) -> bool:
    ...
```

### 4. Using `__init__` for everything instead of alternative constructors

```python
# MESSY — one constructor trying to handle every input format
def __init__(self, year=None, month=None, day=None, date_str=None):
    if date_str:
        year, month, day = map(int, date_str.split("-"))
    ...

# CLEAN — each constructor has a clear name and one job
d = Date.from_string("2024-01-15")
d = Date.today()
```

---

## Quick summary

- Instance methods (`def f(self, ...)`) — the default. Use when behavior depends on a specific object's state.
- Class methods (`@classmethod def f(cls, ...)`) — use when behavior belongs to the class as a whole, not one object. The most important use is the **alternative constructor** pattern: `Date.from_string(...)`, `Date.today()`.
- Static methods (`@staticmethod def f(...)`) — use for pure utility helpers that are logically related to the class but don't need access to any object or class state.
- In class methods, always use `cls(...)` instead of `ClassName(...)` — it keeps the code correct for subclasses.
- Alternative constructors are extremely common in LLD interviews — reach for them whenever you have multiple ways to create an object.
