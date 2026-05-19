# 01 — Classes and Objects

## What is this?

A class is a blueprint that describes what a thing looks like and what it can do. An object is one specific thing built from that blueprint — it has its own data, but shares the same shape as every other object made from the same class.

---

## The Blueprint Analogy

> Imagine an architect's blueprint for a house. The blueprint itself is not a house — you can't live in it. But you can build many houses from it. Each house has its own address and its own furniture, yet they all have the same number of rooms and the same floor plan.
>
> A **class** is the blueprint. An **object** (also called an instance) is a house built from it.

---

## Defining a Class

The simplest possible class just groups related data and behavior in one place. Here is a class called `Dog` with two pieces of data (name and breed) and one behavior (bark):

```python
class Dog:
    def __init__(self, name: str, breed: str):
        self.name = name
        self.breed = breed

    def bark(self) -> str:
        return f"{self.name} says: Woof!"


rex = Dog("Rex", "German Shepherd")
buddy = Dog("Buddy", "Labrador")

print(rex.bark())    # Rex says: Woof!
print(buddy.bark())  # Buddy says: Woof!
```

> **What just happened?**
> `Dog("Rex", "German Shepherd")` calls `__init__` and creates a brand-new object. `rex` and `buddy` are separate objects — changing `rex.name` will not affect `buddy`. The method `bark` is shared code (defined once in the class), but each call uses the specific object's data via `self`.

---

## `__init__`: The Constructor

`__init__` is the method Python calls automatically the moment you create an object. Think of it as the setup step — you use it to give the new object its starting data.

`self` is just a name for "the object being created right now". Python passes it automatically; you never provide it when calling.

```python
class Point:
    def __init__(self, x: float, y: float):
        self.x = x   # instance variable: belongs to this specific object
        self.y = y

p1 = Point(3, 4)
p2 = Point(0, 0)

print(p1.x)   # 3
print(p2.x)   # 0  — completely separate from p1
```

---

## Instance Variables vs Class Variables

An **instance variable** lives on a specific object. A **class variable** lives on the class itself and is shared by every object made from that class.

Think of a bank: every account has its own balance (instance variable), but all accounts share the same interest rate that the bank sets (class variable).

```python
class BankAccount:
    # Class variable — shared across ALL BankAccount objects
    interest_rate = 0.05

    def __init__(self, owner: str, balance: float = 0.0):
        # Instance variables — unique per object
        self.owner = owner
        self._balance = balance

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self._balance += amount

    def apply_interest(self) -> None:
        self._balance += self._balance * BankAccount.interest_rate


acc1 = BankAccount("Alice", 1000)
acc2 = BankAccount("Bob", 500)

# Changing the class variable affects every instance
BankAccount.interest_rate = 0.07

acc1.apply_interest()
print(acc1._balance)   # 1070.0  — uses the new 0.07 rate
print(acc2._balance)   # 500.0   — not changed yet, but would also use 0.07 on next call
```

> **Key takeaway:** Use class variables for data that is truly shared across all objects (like a counter, or a configuration value). Use instance variables for data that is unique per object (like a name or a balance). Accidentally using a class variable where you meant an instance variable is a very common bug — if you modify a mutable class variable on one instance, it can affect all instances.

---

## `__repr__` vs `__str__`: Two Ways to Display an Object

Python gives you two ways to convert an object to a string:

- `__repr__` is for **developers**. It should give an unambiguous description, ideally one you could paste into Python and recreate the object. Used in the REPL, in logs, and when you print a list containing your objects.
- `__str__` is for **end users**. It should be readable and friendly. Used when you call `print()` directly on an object.

> Think of `__repr__` as the technical spec sheet for a product, and `__str__` as the marketing copy on the box.

Here is a complete `BankAccount` that shows both:

```python
class BankAccount:
    interest_rate = 0.05

    def __init__(self, owner: str, balance: float = 0.0):
        self.owner = owner
        self._balance = balance
        self.__account_id = id(self)     # name-mangled (explained below)

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self._balance += amount

    def __repr__(self) -> str:
        # Unambiguous — for developers, logs, debugging
        return f"BankAccount(owner={self.owner!r}, balance={self._balance})"

    def __str__(self) -> str:
        # Readable — for end users
        return f"{self.owner}'s account: ${self._balance:.2f}"


acc = BankAccount("Alice", 1000)
print(acc)           # Alice's account: $1000.00   ← __str__ is used
print(repr(acc))     # BankAccount(owner='Alice', balance=1000.0)  ← __repr__

accounts = [acc, BankAccount("Bob", 200)]
print(accounts)      # [BankAccount(...), BankAccount(...)]  ← __repr__ inside a list
```

> **Rule of thumb:** Always define `__repr__`. Only define `__str__` if you want a different, friendlier format for end users. If only `__repr__` is defined, `print()` will use it as a fallback.

---

## Name Mangling: `_x` vs `__x`

Python does not have true `private` variables like Java or C++. Instead it uses naming conventions and a trick called name mangling.

| Prefix | Meaning | What Python does |
|--------|---------|-----------------|
| `balance` | Public — anyone can read/write | Nothing special |
| `_balance` | "Protected" by convention | Signals "don't touch this from outside", but Python doesn't stop you |
| `__balance` | "Private" via name mangling | Python renames it to `_ClassName__balance`, making accidental access harder |

```python
class BankAccount:
    def __init__(self, owner: str, balance: float):
        self.owner = owner          # public
        self._balance = balance     # protected by convention
        self.__account_id = id(self)  # name-mangled

acc = BankAccount("Alice", 1000)

print(acc.owner)      # Alice  — fine
print(acc._balance)   # 1000.0 — works, but the underscore says "please don't"

# This raises AttributeError:
# print(acc.__account_id)

# But you CAN still access it with the mangled name (don't do this outside tests):
print(acc._BankAccount__account_id)   # works
```

> **Common mistake:** Thinking `__x` makes a variable truly private and inaccessible. It doesn't — Python just renames it. The double underscore is primarily to avoid name collisions in subclasses, not to enforce security. For most code, a single underscore `_x` is the right choice.

---

## A Complete Working Example

Here is a `BankAccount` that brings everything together — class variables, instance variables, `__repr__`, `__str__`, and both access levels:

```python
class BankAccount:
    interest_rate = 0.05   # shared by all accounts

    def __init__(self, owner: str, balance: float = 0.0):
        self.owner = owner
        self._balance = balance          # protected — use methods to change it
        self.__account_id = id(self)     # private — internal ID

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if amount > self._balance:
            raise ValueError("Insufficient funds")
        self._balance -= amount

    def get_balance(self) -> float:
        return self._balance

    def __repr__(self) -> str:
        return f"BankAccount(owner={self.owner!r}, balance={self._balance})"

    def __str__(self) -> str:
        return f"{self.owner}'s account: ${self._balance:.2f}"


# Try it out
acc = BankAccount("Alice", 1000)
acc.deposit(500)
acc.withdraw(200)

print(acc)            # Alice's account: $1300.00
print(repr(acc))      # BankAccount(owner='Alice', balance=1300.0)
print(acc.get_balance())   # 1300.0

try:
    acc.withdraw(9999)
except ValueError as e:
    print(e)   # Insufficient funds
```

---

## Common Mistakes

**1. Forgetting `self` in method definitions**
```python
# Wrong — Python will raise a TypeError when you call greet()
class Dog:
    def greet():        # missing self
        return "Woof"

# Right
class Dog:
    def greet(self):
        return "Woof"
```

**2. Using a mutable default argument in `__init__`**
```python
# Wrong — all instances share the same list!
class Cart:
    def __init__(self, items=[]):   # dangerous mutable default
        self.items = items

# Right — create a new list for each instance
class Cart:
    def __init__(self):
        self.items = []
```

**3. Confusing class variables and instance variables**
```python
class Counter:
    count = 0   # class variable

    def increment(self):
        self.count += 1   # WRONG: this creates an instance variable, doesn't change the class variable

# Right: reference the class explicitly
class Counter:
    count = 0

    def increment(self):
        Counter.count += 1
```

**4. Calling `__init__` directly**
```python
# Wrong
dog = Dog.__init__("Rex", "Labrador")   # __init__ returns None

# Right
dog = Dog("Rex", "Labrador")
```

---

## Quick Summary

- A **class** is a blueprint. An **object** (instance) is a thing built from that blueprint.
- `__init__` is the constructor — it runs automatically when you create an object.
- `self` refers to the specific object being worked on.
- **Instance variables** (`self.x`) are unique per object. **Class variables** are shared by all objects.
- `__repr__` is for developers (debugging, logs). `__str__` is for end users (`print()`).
- Single underscore `_x` means "protected by convention." Double underscore `__x` triggers name mangling — harder to access accidentally, but not truly private.

Next up: [02 — Four Pillars of OOP](02_four_pillars.md)
