# 08 — Protocols (Structural Subtyping)

## What is this?

A Protocol lets you describe what an object needs to be *able to do*, without requiring it to inherit from any particular class. If an object has the right methods, it qualifies — no paperwork needed.

---

## The "duck typing" idea

> "If it walks like a duck and quacks like a duck, then it is a duck."

This old saying captures how Python handles types in practice. Python does not check *what class* an object is — it checks *what the object can do*. If you pass an object to a function that calls `.draw()` on it, Python only cares whether that object has a `.draw()` method. It doesn't care if the object inherits from some `Drawable` base class.

**Structural subtyping** is the formal name for this idea: a type is compatible with another type if its *structure* (its methods and attributes) matches — regardless of its inheritance tree.

Protocols are Python's way of making this duck typing explicit and checkable by type checkers like `mypy`.

---

## Protocol vs ABC — what is the difference?

> Imagine two employers checking candidates:
>
> **ABC employer:** "I only hire people who have a diploma from MY approved school. Even if you know everything, you need that piece of paper."
>
> **Protocol employer:** "I don't care where you studied. Show me you can do the job, and you're hired."

This maps directly to the code:

- **ABC (nominal subtyping):** A class must explicitly inherit from the ABC to be considered compatible. Third-party classes you can't modify are excluded.
- **Protocol (structural subtyping):** Any class that has the right methods qualifies automatically — even if it was written by someone else who never heard of your Protocol.

| | ABC | Protocol |
|---|---|---|
| Requires explicit inheritance? | Yes — `class Foo(MyABC)` | No — just have the right methods |
| Works with third-party classes? | No (you'd need to modify them) | Yes — they qualify automatically |
| Checked at runtime with `isinstance`? | Yes | Only with `@runtime_checkable` |
| Best for... | Related classes you control with shared implementation | Interfaces across codebases, especially third-party code |
| Catch mistakes at... | Object creation time | Type-check time (mypy) or optionally at runtime |

---

## A simple example: the `Drawable` Protocol

This code defines a `Drawable` protocol, then shows that both `Circle` and `Square` satisfy it — even though neither one inherits from `Drawable`.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Drawable(Protocol):
    def draw(self) -> None: ...
    def resize(self, factor: float) -> None: ...
```

Notice the method bodies are just `...` (ellipsis). These are not real implementations — they are just descriptions of the shape (the signature) that conforming classes must match.

Now write two completely independent classes. They never import or mention `Drawable`:

```python
class Circle:
    def __init__(self, radius: float):
        self.radius = radius

    def draw(self) -> None:
        print(f"Drawing circle with radius {self.radius}")

    def resize(self, factor: float) -> None:
        self.radius *= factor


class Square:
    def __init__(self, side: float):
        self.side = side

    def draw(self) -> None:
        print(f"Drawing square with side {self.side}")

    def resize(self, factor: float) -> None:
        self.side *= factor
```

Now write a function that works with anything that looks like a `Drawable`:

```python
def render(shape: Drawable) -> None:
    shape.draw()

c = Circle(5.0)
s = Square(3.0)

render(c)   # Drawing circle with radius 5.0
render(s)   # Drawing square with side 3.0
```

> **What just happened?**
> `Circle` and `Square` never inherited from `Drawable`. They simply have the same method signatures. Python's type system (and mypy) recognises them as compatible with `Drawable` purely because they have the right structure. No inheritance required.

---

## `@runtime_checkable` and `isinstance()`

By default, you cannot use `isinstance()` to check if an object matches a Protocol at runtime — Protocols are a static (type-checker) concept. Adding `@runtime_checkable` switches this on:

```python
c = Circle(5.0)

print(isinstance(c, Drawable))   # True  — Circle has draw() and resize()

# A string is NOT Drawable — it has no draw() method
print(isinstance("hello", Drawable))   # False
```

This is useful when you need to branch logic at runtime based on capabilities — for example, checking whether a plugin object supports optional behaviour before calling it.

> **Important caveat:** `@runtime_checkable` only checks whether the *method names* exist — it does not check the method signatures (parameter types). It is a quick capability check, not a deep validation.

---

## Why Protocols shine with third-party code

This is where Protocols really earn their place. Suppose you are using a library that gives you a `PDFDocument` class. You cannot modify that class — it is someone else's code. But it happens to have a `.draw()` and a `.resize()` method.

Without Protocols, you would have to create an adapter or a wrapper just to make `PDFDocument` work with your `render()` function.

With Protocols, it just works:

```python
# From some third-party library you cannot touch
class PDFDocument:
    def draw(self) -> None:
        print("Rendering PDF page")

    def resize(self, factor: float) -> None:
        print(f"Scaling PDF by {factor}")

# No inheritance, no adapters needed
doc = PDFDocument()
render(doc)   # Rendering PDF page  — it just works!
```

> **Key takeaway:** If you define your interfaces as Protocols, any class that has the right methods automatically works — whether it's your code, library code, or a class written five years ago by someone who never heard of your system.

---

## A more complete example: the `Saveable` Protocol

Here is another example that shows Protocols working across different object types:

```python
from typing import Protocol

class Saveable(Protocol):
    def save(self) -> str: ...
    def load(self, data: str) -> None: ...


class UserProfile:
    def __init__(self, name: str):
        self.name = name

    def save(self) -> str:
        return f'{{"name": "{self.name}"}}'

    def load(self, data: str) -> None:
        import json
        self.name = json.loads(data)["name"]


class GameState:
    def __init__(self, level: int):
        self.level = level

    def save(self) -> str:
        return f'{{"level": {self.level}}}'

    def load(self, data: str) -> None:
        import json
        self.level = json.loads(data)["level"]


def backup(item: Saveable) -> str:
    """Works with anything that has save() and load()."""
    return item.save()


profile = UserProfile("Alice")
game = GameState(42)

print(backup(profile))   # {"name": "Alice"}
print(backup(game))      # {"level": 42}
```

---

## When to use Protocol vs ABC

Use **ABC** when:
- The classes are closely related and share a family identity (e.g., all `PaymentProcessor` subclasses)
- You want to share implementation in the base class (concrete methods, shared attributes)
- You control all the classes that will implement it
- You want the subtyping relationship to be explicit and documented

Use **Protocol** when:
- You are defining a capability rather than a family (e.g., "anything that can be drawn")
- You might need to work with third-party code you cannot modify
- The classes implementing it are unrelated in domain but happen to share methods
- You want a lightweight interface with no inheritance overhead

---

## Common mistakes

**1. Using ABC when Protocol would be simpler**

If you only want to say "this function needs an object with a `.send()` method", you do not need a full ABC with inheritance. A Protocol is cleaner and more flexible:

```python
# OVERKILL for a simple capability check
from abc import ABC, abstractmethod
class Sendable(ABC):
    @abstractmethod
    def send(self, msg: str) -> bool: ...

# BETTER — no inheritance required anywhere
from typing import Protocol
class Sendable(Protocol):
    def send(self, msg: str) -> bool: ...
```

**2. Forgetting `@runtime_checkable` when using `isinstance()`**

Without the decorator, `isinstance()` raises a `TypeError` at runtime:

```python
from typing import Protocol

class Drawable(Protocol):   # missing @runtime_checkable
    def draw(self) -> None: ...

c = Circle(5)
isinstance(c, Drawable)
# TypeError: Protocols with non-method members don't support issubclass()
```

Add `@runtime_checkable` above the class if you need runtime `isinstance()` checks.

**3. Expecting `@runtime_checkable` to check method signatures**

`isinstance(obj, MyProtocol)` only checks that the method *names* exist — not the parameter types or return types. Do not rely on it for deep validation:

```python
class Broken:
    def draw(self):   # Wrong signature — takes no arguments
        pass

    def resize(self):  # Also wrong
        pass

# This still returns True! Only the names are checked, not the signatures.
print(isinstance(Broken(), Drawable))   # True
```

**4. Writing real code in Protocol method bodies**

Protocol methods should have `...` or `pass` as their body. If you put real logic there, it will never run — it is just a specification, not an implementation.

---

## Quick summary

| Concept | Plain English |
|---|---|
| `Protocol` | Describes a set of methods an object must have — without requiring inheritance |
| Structural subtyping | "If it has the right methods, it qualifies" |
| `@runtime_checkable` | Allows `isinstance(obj, MyProtocol)` to work at runtime |
| vs ABC | ABC requires inheritance; Protocol only requires compatible methods |
| Best use case | Third-party code, unrelated classes that share a capability |

**The one-sentence rule:** Use a Protocol when you want to define *what an object can do* without caring *where it comes from*.
