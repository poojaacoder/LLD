# 02 — The Four Pillars of OOP

## What is this?

The four pillars are the core ideas that make Object-Oriented Programming different from just writing functions. Understanding them well is the difference between writing code that "works" and writing code that is easy to change, test, and extend — which is exactly what LLD interviews are testing.

---

## The Four Pillars at a Glance

| Pillar | One-sentence summary |
|--------|---------------------|
| Encapsulation | Bundle data and behavior together, and control who can touch what |
| Inheritance | Let a new class reuse and extend an existing class |
| Polymorphism | Let different objects respond to the same message in their own way |
| Abstraction | Show only what is necessary; hide the internal complexity |

---

## Pillar 1 — Encapsulation

### The analogy

> Think of a medicine capsule. All the powder (data) is inside the hard shell. You don't poke the shell open to adjust the powder — you just swallow the capsule as designed. The shell *controls access* to what's inside.
>
> Or think of a TV remote. You press the "Volume Up" button without knowing whether the remote sends infrared or Bluetooth. The *interface* (the buttons) is clean and simple; the *implementation* (the circuit board) is hidden.

Encapsulation means:
1. Put related data and the methods that work with that data inside one class.
2. Use access conventions (or properties) to prevent outside code from changing the data in invalid ways.

### Code

This `Temperature` class stores a value in Celsius but prevents anyone from setting a temperature below absolute zero. Without encapsulation, any code could just write `temp._celsius = -999` and nothing would stop it.

```python
class Temperature:
    def __init__(self, celsius: float):
        self._celsius = celsius   # _celsius is "protected"

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
        # Computed from celsius — no separate variable needed
        return self._celsius * 9 / 5 + 32


t = Temperature(100)
print(t.celsius)      # 100
print(t.fahrenheit)   # 212.0

t.celsius = 25        # Uses the setter — validation runs
print(t.fahrenheit)   # 77.0

t.celsius = -300      # Raises ValueError
```

> **What just happened?**
> From the outside, `t.celsius = 25` looks like a simple attribute assignment. But Python secretly calls the `@celsius.setter` method, which runs the validation before allowing the change. This is encapsulation: the *interface* is simple, the *protection* is hidden inside.

> **Key takeaway:** Encapsulation is not just about making things private. It is about bundling data with the logic that keeps it valid, so no external code can accidentally corrupt your object's state.

---

## Pillar 2 — Inheritance

### The analogy

> Think of family traits. A child inherits their parent's eye color and height tendencies, but also has their own personality. In code, a child class *inherits* all the data and methods of the parent class, and can add new ones or change existing ones.

Inheritance models IS-A relationships. An `ElectricCar` IS-A `Vehicle`. It gets everything `Vehicle` has for free, and can specialize the parts that are different (like how it starts).

### Code

The `Vehicle` parent class defines the common behavior. `ElectricCar` calls `super().__init__()` to run the parent's setup, then adds its own `battery_kwh` and overrides `start()`.

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
        super().__init__(make, model)      # run Vehicle's __init__ first
        self.battery_kwh = battery_kwh    # add ElectricCar-specific data

    def start(self) -> str:               # override — replace Vehicle's version
        return f"{self.describe()} silently starts (battery: {self.battery_kwh}kWh)"

    def charge(self) -> str:              # new method — only on ElectricCar
        return "Charging..."


car = ElectricCar("Tesla", "Model 3", 82)
print(car.start())               # Tesla Model 3 silently starts (battery: 82kWh)
print(car.describe())            # Tesla Model 3  ← inherited from Vehicle
print(isinstance(car, Vehicle))  # True  ← ElectricCar IS-A Vehicle
```

> **What just happened?**
> `car.describe()` was never defined in `ElectricCar`, but Python found it by walking up to `Vehicle`. That is inheritance in action. Meanwhile, `car.start()` finds `ElectricCar`'s version first — that is method overriding.

> **Key takeaway:** Always call `super().__init__()` at the top of a child class's `__init__`. If you forget, the parent's setup never runs and you will get mysterious `AttributeError`s later.

### When NOT to use inheritance

Inheritance is often overused. Only use it when there is a genuine IS-A relationship. Ask yourself: "Can I say a `ChildClass` IS-A `ParentClass` without it sounding weird?" If yes, inheritance may be appropriate. If no — for example, a `UserManager` is not really a `Database` — use composition instead (covered in a later file).

---

## Pillar 3 — Polymorphism

### The analogy

> The word "polymorphism" literally means "many forms." Think of the word "open": you can open a door, open a file, open a bank account. Each action is called "open" but does something completely different depending on what you apply it to.
>
> In code, polymorphism means different objects can respond to the same method call in their own way.

Python supports two flavors of polymorphism:

**Flavor 1 — Method overriding (class hierarchy)**
Multiple classes share a common parent and each provides its own version of the same method.

**Flavor 2 — Duck typing (no shared parent required)**
Python does not care about the class hierarchy — it only cares whether the object has the method you are calling. "If it walks like a duck and quacks like a duck, it's a duck."

### Code: Method Overriding

Each `Shape` subclass has its own `area()` method. The loop treats them all identically — it just calls `area()` and lets each object figure out how to calculate it.

```python
import math

class Shape:
    def area(self) -> float:
        raise NotImplementedError("Subclasses must implement area()")

class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = radius

    def area(self) -> float:
        return math.pi * self.radius ** 2

class Rectangle(Shape):
    def __init__(self, w: float, h: float):
        self.w, self.h = w, h

    def area(self) -> float:
        return self.w * self.h


shapes = [Circle(5), Rectangle(4, 6)]
for s in shapes:
    print(round(s.area(), 2))
# 78.54
# 24
```

> **What just happened?**
> The loop does not know or care whether it has a `Circle` or a `Rectangle`. It just calls `area()`. Python dispatches the call to the right version at runtime. This is why you can add a `Triangle` class later and the loop will still work without any changes.

### Code: Duck Typing

Python does not require a shared parent class for polymorphism. If two objects both have a `quack()` method, they can be used interchangeably — even if they have nothing else in common.

```python
class Duck:
    def quack(self):
        return "Quack!"

class Person:
    def quack(self):
        return "I'm quacking like a duck!"

def make_it_quack(obj):
    # This function doesn't care about the type — only the capability
    print(obj.quack())


make_it_quack(Duck())    # Quack!
make_it_quack(Person())  # I'm quacking like a duck!
```

> **Key takeaway:** Duck typing is Python's most idiomatic form of polymorphism. In LLD interviews, you will often write functions that accept "any object that has method X" rather than requiring a specific class. This makes your code more flexible and easier to test.

---

## Pillar 4 — Abstraction

### The analogy

> Think of driving a car. You interact with the steering wheel, the accelerator, and the brakes. You do not need to know about the engine timing, the fuel injection, or the ABS controller. The *dashboard interface* hides all that complexity. You just use the car at a higher level of abstraction.

Abstraction means hiding the implementation details and exposing only what the caller needs to know. In Python, the primary tool for abstraction is the **Abstract Base Class (ABC)**.

An abstract class:
- Cannot be instantiated directly (you can't create an `ABC` object).
- Defines the *contract* — the methods that every subclass must implement.
- Can include shared concrete methods too.

### Code

`PaymentProcessor` defines the contract: every payment system must be able to `process_payment` and `refund`. But *how* each one does it is hidden inside the concrete subclass. The caller only sees the clean interface.

```python
from abc import ABC, abstractmethod

class PaymentProcessor(ABC):
    @abstractmethod
    def process_payment(self, amount: float) -> bool:
        """Process a payment. Return True on success."""
        ...

    @abstractmethod
    def refund(self, transaction_id: str) -> bool:
        """Issue a refund. Return True on success."""
        ...

    # Concrete method — shared by all subclasses
    def validate_amount(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")


class StripeProcessor(PaymentProcessor):
    def process_payment(self, amount: float) -> bool:
        self.validate_amount(amount)   # use the shared method
        print(f"Processing ${amount} via Stripe")
        return True

    def refund(self, transaction_id: str) -> bool:
        print(f"Refunding {transaction_id} via Stripe")
        return True


class PayPalProcessor(PaymentProcessor):
    def process_payment(self, amount: float) -> bool:
        self.validate_amount(amount)
        print(f"Processing ${amount} via PayPal")
        return True

    def refund(self, transaction_id: str) -> bool:
        print(f"Refunding {transaction_id} via PayPal")
        return True


# This would raise TypeError: Can't instantiate abstract class
# processor = PaymentProcessor()

# This works fine
stripe = StripeProcessor()
stripe.process_payment(49.99)   # Processing $49.99 via Stripe

# And this function works with ANY PaymentProcessor subclass
def checkout(processor: PaymentProcessor, amount: float) -> None:
    success = processor.process_payment(amount)
    if success:
        print("Payment complete!")

checkout(PayPalProcessor(), 99.0)
```

> **What just happened?**
> `PaymentProcessor()` would throw an error because Python refuses to create an abstract class directly — it forces you to provide a concrete implementation. `checkout()` does not know or care whether it is talking to Stripe or PayPal; it just calls `process_payment()`. To add a new payment provider, you create a new subclass — no existing code changes.

> **Key takeaway:** Abstraction and polymorphism work together. You define a contract (abstraction), and different objects fulfill that contract in their own way (polymorphism). This is the foundation of every pluggable, extensible LLD design.

---

## How the Pillars Work Together

In a real LLD design you use all four pillars at once:

```
Abstraction  → defines the interface (what can this thing DO?)
Encapsulation → protects the data (how does it keep itself valid?)
Inheritance   → reuses and specializes behavior (what IS this thing?)
Polymorphism  → lets different things respond to the same call (how do I use it uniformly?)
```

In the payment example:
- `PaymentProcessor` is **abstraction** — it is a contract, not an implementation.
- Each processor's internal state is **encapsulated** — callers don't touch it directly.
- `StripeProcessor` and `PayPalProcessor` **inherit** from `PaymentProcessor`.
- `checkout()` exhibits **polymorphism** — it works with any processor.

---

## Common Mistakes

**1. Inheriting just to reuse code (when there is no IS-A relationship)**
```python
# Wrong — an EmailSender is not a "kind of" Database
class EmailSender(Database):
    ...

# Right — EmailSender HAS-A database reference (composition)
class EmailSender:
    def __init__(self, db: Database):
        self._db = db
```

**2. Forgetting `super().__init__()` in a child class**
```python
class Animal:
    def __init__(self, name):
        self.name = name

class Dog(Animal):
    def __init__(self, name, breed):
        # Forgot super().__init__(name)!
        self.breed = breed

d = Dog("Rex", "Lab")
print(d.name)   # AttributeError — name was never set
```

**3. Raising `NotImplementedError` instead of using `@abstractmethod`**
```python
# This works but has a flaw: Python won't stop you from instantiating Shape
class Shape:
    def area(self):
        raise NotImplementedError

# Better: use ABC — Python raises TypeError at instantiation time, not later
from abc import ABC, abstractmethod
class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...
```

**4. Breaking encapsulation by accessing `_private` variables directly**
```python
acc = BankAccount("Alice", 1000)
acc._balance = -99999   # bypasses all validation — don't do this
```

**5. Confusing abstraction with secrecy**
Abstraction is not about hiding things for security. It is about reducing complexity for the caller. A well-named method `process_payment()` is "abstract" because the caller does not need to know *how* it works, not because we are trying to hide secrets.

---

## Quick Summary

- **Encapsulation** — bundle data and behavior; use properties to protect data from invalid changes.
- **Inheritance** — IS-A relationship; child classes reuse and extend parent classes; always call `super().__init__()`.
- **Polymorphism** — the same method call works differently on different objects; Python's duck typing makes this very flexible.
- **Abstraction** — hide complexity behind a clean interface; use `ABC` and `@abstractmethod` to define contracts that subclasses must fulfill.

Next up: [03 — Magic / Dunder Methods](03_magic_methods.md)
