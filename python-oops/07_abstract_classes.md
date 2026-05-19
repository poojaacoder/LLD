# 07 — Abstract Classes and Interfaces

## What is this?

An abstract class is a class you can never create an object from directly — it exists purely as a template that other classes must follow. Think of it as a signed contract that says "if you want to be a PaymentProcessor, you MUST implement these exact methods."

---

## Why do abstract classes exist?

> Imagine you're a tech lead onboarding a new team. You write a job contract that says: "Every engineer on this team MUST be able to write code, review pull requests, and attend stand-ups." You don't care *how* they do it — but they cannot join the team without agreeing to all three.

An abstract class is that contract. It guarantees that every subclass will have the methods you depend on, so the rest of your code can work with any of them interchangeably.

**Without abstract classes**, you might write a base class with methods that just `raise NotImplementedError`. This works, but Python will only catch the mistake *at runtime* when someone actually calls the method. Abstract classes catch the mistake *earlier* — the moment someone tries to create an object from an incomplete class.

---

## The basics: `ABC` and `@abstractmethod`

To make a class abstract, you need two things from Python's `abc` module:
- Inherit from `ABC` (Abstract Base Class)
- Mark methods that *must* be implemented with `@abstractmethod`

Here is a simple payment processor example. The `PaymentProcessor` class defines what every payment method must be able to do, without specifying how.

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

    # Concrete method — shared logic every subclass gets for FREE
    def validate_amount(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be positive")
```

> **What just happened?**
> `PaymentProcessor` is now a contract. Any class that inherits from it *must* implement `process_payment` and `refund`. The `validate_amount` method is a bonus — it's real, working code that every subclass inherits automatically.

---

## You can't instantiate an abstract class — and that's the point

Try creating a `PaymentProcessor` directly and Python stops you immediately:

```python
# This will raise a TypeError right away — before any payment is attempted
processor = PaymentProcessor()
# TypeError: Can't instantiate abstract class PaymentProcessor
# with abstract methods process_payment, refund
```

This is useful because it makes the mistake obvious. Compare this to a normal base class where you'd only discover the problem later when someone called `process_payment()` and got a confusing `NotImplementedError`.

---

## A concrete subclass fulfils the contract

A concrete class is simply a class that implements all the abstract methods. Once it does, you can create objects from it normally.

```python
class StripeProcessor(PaymentProcessor):
    def process_payment(self, amount: float) -> bool:
        self.validate_amount(amount)   # inherited from PaymentProcessor
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


# Both work fine — they've both fulfilled the contract
stripe = StripeProcessor()
paypal = PayPalProcessor()

stripe.process_payment(99.99)   # Processing $99.99 via Stripe
paypal.process_payment(49.00)   # Processing $49.00 via PayPal
```

> **Key takeaway:** The rest of your code can be written against `PaymentProcessor` and it will work with Stripe, PayPal, or any future provider without modification. This is the power of programming to an abstraction.

---

## Concrete methods in an abstract class (shared default behavior)

Abstract classes can have normal, fully working methods too. These are methods where the behaviour is the same for all subclasses, so you put them in one place instead of copy-pasting.

Here is a `Notification` example with a `send_bulk` method that works for every channel:

```python
from abc import ABC, abstractmethod
from typing import List

class Notification(ABC):
    """Abstract base — cannot be instantiated directly."""

    @abstractmethod
    def send(self, recipient: str, message: str) -> bool:
        """Send a notification. Return True on success."""
        ...

    @abstractmethod
    def get_channel(self) -> str:
        """Return the channel name, e.g. 'email' or 'sms'."""
        ...

    # Concrete method — calls the abstract send() for each recipient
    # Every subclass gets this for free without writing it themselves
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


# send_bulk is inherited — we didn't write it in either subclass
email = EmailNotification()
results = email.send_bulk(["alice@example.com", "bob@example.com"], "Hello!")
# Email to alice@example.com: Hello!
# Email to bob@example.com: Hello!
```

> **Key takeaway:** Put shared logic in a concrete method inside the ABC. Each subclass inherits it automatically. Abstract methods handle what differs; concrete methods handle what's the same.

---

## Abstract properties

Sometimes you don't just want to enforce methods — you want to enforce *properties* (computed values accessed like attributes). You can combine `@property` and `@abstractmethod` for this.

The `Shape` class below forces every shape to provide `area` and `perimeter` as properties, while the `describe()` method is shared and works for free:

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @property
    @abstractmethod
    def area(self) -> float:
        """Every shape must implement area."""
        ...

    @property
    @abstractmethod
    def perimeter(self) -> float:
        """Every shape must implement perimeter."""
        ...

    # Concrete method — uses the abstract properties above
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


class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = radius

    @property
    def area(self) -> float:
        import math
        return math.pi * self.radius ** 2

    @property
    def perimeter(self) -> float:
        import math
        return 2 * math.pi * self.radius


sq = Square(5)
ci = Circle(3)

print(sq.describe())   # Area: 25.00, Perimeter: 20.00
print(ci.describe())   # Area: 28.27, Perimeter: 18.85
```

> **What just happened?**
> The `@property` decorator is listed *before* `@abstractmethod`. Order matters here — always put `@property` on top. This tells Python that the subclass must provide a property (not just any method) with that name.

---

## Putting it all together: the PaymentProcessor example

Here is a complete, realistic example you can use as a reference during interviews:

```python
from abc import ABC, abstractmethod
from typing import List

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


# PaymentProcessor()  # TypeError — caught immediately, not buried somewhere
stripe = StripeProcessor()
stripe.process_payment(49.99)   # Processing $49.99 via Stripe
```

---

## Common mistakes

**1. Forgetting to implement all abstract methods**

The most common mistake. If you miss even one abstract method, Python will refuse to create an instance:

```python
class BrokenProcessor(PaymentProcessor):
    def process_payment(self, amount: float) -> bool:
        return True
    # Forgot to implement refund()!

p = BrokenProcessor()
# TypeError: Can't instantiate abstract class BrokenProcessor
# with abstract method refund
```

The fix is simple: implement every method marked `@abstractmethod` in the parent.

**2. Putting `@abstractmethod` below `@property` (wrong order)**

```python
# WRONG — Python won't recognise this as an abstract property
@abstractmethod
@property
def area(self) -> float: ...

# CORRECT — @property must come first
@property
@abstractmethod
def area(self) -> float: ...
```

**3. Adding `@abstractmethod` without inheriting from `ABC`**

If you forget `(ABC)` in the class definition, `@abstractmethod` is silently ignored — the class becomes instantiable, defeating the whole purpose:

```python
# WRONG — ABC is missing, so @abstractmethod does nothing
class PaymentProcessor:
    @abstractmethod
    def process_payment(self, amount): ...

p = PaymentProcessor()  # No error! The contract is broken.

# CORRECT
from abc import ABC, abstractmethod
class PaymentProcessor(ABC):
    @abstractmethod
    def process_payment(self, amount): ...
```

**4. Using `raise NotImplementedError` instead of `@abstractmethod`**

`raise NotImplementedError` only fails at *call time* — you'd have to actually call the method to find out. `@abstractmethod` fails at *creation time*, which is much earlier and clearer.

---

## Quick summary

| Concept | What it does |
|---|---|
| `ABC` | Makes a class abstract — inherit from it to create a contract |
| `@abstractmethod` | Marks a method that subclasses MUST implement |
| `@property` + `@abstractmethod` | Enforces a computed attribute (put `@property` on top) |
| Concrete method in ABC | Shared logic all subclasses inherit for free |
| Instantiating an ABC | Raises `TypeError` immediately — by design |

**The one-sentence rule:** Use an abstract class when you want to define a contract (required methods) AND share some common implementation between related classes.
