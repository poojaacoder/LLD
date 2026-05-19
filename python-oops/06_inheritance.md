# 06 — Inheritance Deep Dive

## What is this?

Inheritance lets one class automatically gain all the attributes and methods of another class, so you can build specialized versions without rewriting shared logic. This file covers everything from the basics of single inheritance all the way to Python's powerful (and sometimes tricky) multiple inheritance and the Mixin pattern.

---

## Single inheritance basics

The most common form: one child class extends one parent class.

> Think of inheritance like a job role hierarchy. A `Manager` IS-A `Employee` — they can do everything an employee does, plus a few extra things. You don't redefine "employee ID" and "name" on the Manager class; they are inherited automatically.

Here is a vehicle hierarchy. `ElectricCar` inherits everything from `Vehicle` and adds its own behavior on top:

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
        super().__init__(make, model)      # initialize the parent part first
        self.battery_kwh = battery_kwh    # then add the child-specific part

    def start(self) -> str:               # override the parent method
        return f"{self.describe()} silently starts (battery: {self.battery_kwh}kWh)"

    def charge(self) -> str:
        return "Charging..."


car = ElectricCar("Tesla", "Model 3", 82)
print(car.start())              # Tesla Model 3 silently starts (battery: 82kWh)
print(car.describe())           # Tesla Model 3  — inherited from Vehicle
print(isinstance(car, Vehicle)) # True — an ElectricCar IS-A Vehicle
```

> **What just happened?** `ElectricCar` only defines what is *different* about it. Everything else (`describe`, `make`, `model`) comes from `Vehicle` for free.

---

## Why `super().__init__()` matters

When a child class defines `__init__`, it completely replaces the parent's `__init__`. If you don't explicitly call `super().__init__(...)`, the parent's setup code never runs — and your object will be missing attributes.

```python
class ElectricCar(Vehicle):
    def __init__(self, make, model, battery_kwh):
        # WRONG — forgetting super()
        self.battery_kwh = battery_kwh
        # Now self.make and self.model are never set!
        # Calling car.describe() will raise AttributeError

        # CORRECT — call super() first, then do your own setup
        super().__init__(make, model)
        self.battery_kwh = battery_kwh
```

> Think of `super().__init__()` as signing the parent class's paperwork before you start customizing your desk. Skip it and your contract is incomplete.

**Why not just call `Vehicle.__init__(self, make, model)` directly?**

You can, and it works for simple single inheritance. But as soon as you have multiple inheritance, calling the parent class by name directly breaks the cooperative chain (explained below). Using `super()` is always the correct habit.

---

## Multiple inheritance and the diamond problem

Python allows a class to inherit from more than one parent at the same time. This is powerful but introduces a classic puzzle called the *diamond problem*.

Here `D` inherits from both `B` and `C`, which both inherit from `A`. Which version of `hello()` should `D` use?

```python
class A:
    def hello(self): return "A"

class B(A):
    def hello(self): return "B"

class C(A):
    def hello(self): return "C"

class D(B, C):   # inherits from both B and C
    pass
```

> Imagine a family tree where a child has both parents, and both parents have the same grandparent. If the child asks "what's our family recipe?", which parent's version wins? Python has a clear, deterministic answer.

```python
d = D()
print(d.hello())     # "B" — Python follows a specific lookup order
print(D.__mro__)
# (<class 'D'>, <class 'B'>, <class 'C'>, <class 'A'>, <class 'object'>)
```

> **What just happened?** `D.hello()` returns "B" because Python looks up the class hierarchy in MRO order: `D` → `B` → `C` → `A`. It finds `hello` on `B` first and stops there.

---

## MRO — Method Resolution Order

The MRO is the exact order Python searches through classes when looking up a method or attribute. Python uses an algorithm called **C3 linearization** to compute it.

You don't need to memorize the algorithm, just understand the rule:

> Walk the inheritance tree **left-to-right**. Never visit a class until all classes that inherit from it have been visited first. Never repeat a class.

For `class D(B, C)` where `B(A)` and `C(A)`:
1. Start with `D`
2. Go left first: `B`
3. `B`'s parent is `A`, but `C` also inherits from `A` — don't visit `A` yet
4. Go to `C` next
5. Now visit `A` (both `B` and `C` are done)
6. Finally `object` (the root of everything in Python)

Result: `D → B → C → A → object`

You can inspect the MRO of any class:

```python
print(D.__mro__)         # tuple form
print(D.mro())           # list form — same thing
```

This is useful for debugging inheritance problems. If a method isn't behaving as expected, check `__mro__` to see the lookup order.

---

## Cooperative multiple inheritance with super()

The real power of `super()` shows up with multiple inheritance. When every class in the chain calls `super()`, they form a cooperative chain — each one does its part and passes control to the next in MRO order.

> Think of it like an assembly line. Each worker (`LogMixin`, `ValidationMixin`, `Base`) does their step and then passes the product down the line. If any worker stops passing it on, the rest of the line never runs.

Here, `LogMixin` and `ValidationMixin` each add behavior *before* the real save:

```python
class LogMixin:
    def save(self) -> str:
        print("LogMixin: logging before save")
        return super().save()   # passes to the next class in MRO

class ValidationMixin:
    def save(self) -> str:
        print("ValidationMixin: validating before save")
        return super().save()   # passes to the next class in MRO

class Base:
    def save(self) -> str:
        print("Base: saving")
        return "saved"

class Model(LogMixin, ValidationMixin, Base):
    pass
```

When you call `Model().save()`, Python follows the MRO — `Model → LogMixin → ValidationMixin → Base`:

```python
m = Model()
m.save()
# LogMixin: logging before save
# ValidationMixin: validating before save
# Base: saving
```

> **What just happened?** Even though `LogMixin` doesn't know about `ValidationMixin`, and `ValidationMixin` doesn't know about `Base`, `super()` threads them together in the right order automatically. Remove any `super().save()` call and the chain breaks there.

---

## The Mixin pattern

A **Mixin** is a class designed *specifically* to be mixed into other classes to add a slice of behavior. Mixins:
- Are not meant to stand alone (you never instantiate a mixin by itself)
- Add one well-defined capability (serialization, timestamps, logging, etc.)
- Use `super()` so they work cooperatively

> Think of mixins like optional feature packs for a product. A `SerializableMixin` is the "export to JSON" pack. A `TimestampMixin` is the "track when it was created" pack. Snap them onto any class that needs those features.

### SerializableMixin — adds to_dict / from_dict

This mixin adds the ability to convert any object to and from a plain dictionary:

```python
class SerializableMixin:
    def to_dict(self) -> dict:
        return self.__dict__.copy()   # all instance attributes as a dict

    @classmethod
    def from_dict(cls, data: dict):
        obj = cls.__new__(cls)        # create a blank instance without calling __init__
        obj.__dict__.update(data)
        return obj
```

### TimestampMixin — adds created_at / updated_at

This mixin automatically records when an object was created:

```python
class TimestampMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)   # important: pass args along the chain
        from datetime import datetime
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
```

Notice `*args, **kwargs` and the `super().__init__()` call. This is the correct pattern for mixins — it ensures arguments flow through the MRO chain correctly.

### Using both mixins together

```python
class User(SerializableMixin, TimestampMixin):
    def __init__(self, name: str, email: str):
        super().__init__()   # triggers TimestampMixin.__init__ via MRO
        self.name = name
        self.email = email


u = User("Alice", "alice@example.com")
print(u.to_dict())
# {'created_at': '2024-01-15T10:30:00', 'updated_at': '2024-01-15T10:30:00',
#  'name': 'Alice', 'email': 'alice@example.com'}
```

> **What just happened?** `User` gains both `to_dict()` / `from_dict()` and automatic `created_at` / `updated_at` just by listing the mixins in the class definition. The `User.__init__` doesn't have to know anything about how timestamps work.

**When to use the mixin pattern:**
- Cross-cutting concerns (logging, serialization, caching, validation) that many unrelated classes share
- When composition of behaviors at class-definition time is cleaner than injecting objects at runtime

---

## isinstance() and issubclass()

These two built-ins let you check inheritance relationships at runtime.

`isinstance(obj, SomeClass)` checks whether an object is an instance of a class *or any of its subclasses*:

```python
car = ElectricCar("Tesla", "Model 3", 82)
print(isinstance(car, ElectricCar))  # True  — direct type
print(isinstance(car, Vehicle))      # True  — parent class also passes
print(isinstance(car, str))          # False
```

`issubclass(ChildClass, ParentClass)` checks the class hierarchy without needing an instance:

```python
print(issubclass(ElectricCar, Vehicle))   # True
print(issubclass(Vehicle, ElectricCar))   # False — reversed relationship
print(issubclass(ElectricCar, object))    # True  — everything inherits from object
```

> **Key takeaway:** Prefer `isinstance()` over `type(obj) == SomeClass` for type checks. `isinstance` respects inheritance; `type()` does not. If you have a `GasCar(Vehicle)` and your function checks `type(vehicle) == Vehicle`, gas cars will fail the check even though they are vehicles.

---

## Common mistakes

### 1. Forgetting to call super().__init__()

The single most common inheritance bug. Parent attributes silently never get set:

```python
class Animal:
    def __init__(self, name: str):
        self.name = name

class Dog(Animal):
    def __init__(self, name: str, breed: str):
        # WRONG — forgot super().__init__(name)
        self.breed = breed
        # self.name is never set!

d = Dog("Rex", "Labrador")
print(d.name)   # AttributeError: 'Dog' object has no attribute 'name'
```

Always call `super().__init__(...)` first in a child `__init__`.

### 2. Deep inheritance hierarchies

When class E inherits from D which inherits from C which inherits from B which inherits from A, the code becomes very hard to reason about. Changes to A can break E in unexpected ways (the "fragile base class" problem).

```python
# BAD — deep chain is hard to follow and modify
class A: ...
class B(A): ...
class C(B): ...
class D(C): ...
class E(D): ...   # what does E actually have? You have to trace 5 classes.

# BETTER — prefer composition or shallow hierarchies (max 2-3 levels)
```

The guideline: if you need more than 2-3 levels of inheritance, consider composition instead.

### 3. Calling the parent class by name instead of super()

```python
class ElectricCar(Vehicle):
    def __init__(self, make, model, battery_kwh):
        Vehicle.__init__(self, make, model)   # works for simple cases, but...
        # If ElectricCar is used in multiple inheritance, this bypasses the MRO
        # and other classes in the chain never get initialized.

        super().__init__(make, model)         # always prefer this
```

### 4. Mixin without super().__init__()

```python
class TimestampMixin:
    def __init__(self):
        # WRONG — no super() and no *args/**kwargs
        # This swallows any arguments meant for other classes in the MRO
        from datetime import datetime
        self.created_at = datetime.now().isoformat()

class TimestampMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)   # CORRECT — pass args along
        from datetime import datetime
        self.created_at = datetime.now().isoformat()
```

### 5. Inheriting when you should be composing

Inheritance says "IS-A". If you can't say "X is a Y" naturally in English, inheritance is the wrong tool:

```python
# BAD — a Car is not a Engine
class Engine:
    def start(self): ...

class Car(Engine):   # Car IS-A Engine? No.
    ...

# GOOD — a Car HAS-A Engine
class Car:
    def __init__(self):
        self.engine = Engine()   # composition
```

---

## Quick summary

- Single inheritance: `class Child(Parent)` — child gains all parent attributes and methods automatically.
- Always call `super().__init__(...)` in the child `__init__` — skipping it means parent attributes are never set.
- Multiple inheritance: `class D(B, C)` — Python uses MRO to decide which class's method wins.
- MRO rule: left-to-right, never repeat, never visit a class before all its subclasses are done. Inspect with `ClassName.__mro__`.
- Cooperative `super()`: when every class in the chain calls `super().method()`, they form an assembly line where each does its part in MRO order.
- Mixin pattern: small classes that add one capability (serialization, timestamps, etc.) and are designed to be mixed into other classes. Always use `super().__init__(*args, **kwargs)` inside a mixin.
- `isinstance(obj, Class)` respects inheritance — prefer it over `type()` equality checks.
- The two most common mistakes: forgetting `super().__init__()` and building inheritance hierarchies that are too deep.
