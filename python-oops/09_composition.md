# 09 — Composition over Inheritance

## What is this?

Composition means building complex objects by combining simpler objects, rather than by creating long chains of parent-child class relationships. It is one of the most important ideas in object-oriented design.

---

## The core principle

> "Favour composition over inheritance."

This comes from the famous *Gang of Four* design patterns book, and it is repeated in nearly every OOP interview. But what does it actually mean?

**Inheritance** says: "I will get my behaviour by being a *kind of* something else."
**Composition** says: "I will get my behaviour by *having* a thing that does it."

> Analogy: Think about how a car works. A car does not *inherit* from an Engine — it *has* an engine. It also *has* wheels, seats, and a steering system. When the engine breaks, you swap it out without replacing the whole car. That's composition.
>
> Now imagine if CarWithHeater and CarWithAC both inherited from Car, and then you needed CarWithHeaterAndAC... the class tree explodes. Composition solves this.

---

## The classic problem: deep inheritance trees break

Let's walk through exactly why deep inheritance becomes painful. Suppose you are modelling animals.

You start simply:

```python
class Animal:
    pass

class FlyingAnimal(Animal):
    def fly(self):
        return "Flying with wings"

class SwimmingAnimal(Animal):
    def swim(self):
        return "Swimming"
```

This seems fine — until someone asks: "What about a duck? It both flies and swims."

You reach for multiple inheritance:

```python
class Duck(FlyingAnimal, SwimmingAnimal):
    pass
```

OK. Now: "What about a penguin? It swims but can't fly."

```python
class Penguin(SwimmingAnimal):
    pass
```

Now: "What about a bat? It flies but doesn't swim. And it hangs upside down."

The inheritance tree keeps growing. Every new requirement forces you to modify the existing hierarchy or create new intermediate classes. And the killer blow:

> What if the *way* something flies changes? Maybe some animals use wings, and others use jet packs. With inheritance, flying is baked into the class. To change it, you have to touch multiple classes and risk breaking everything.

This is called the **fragile base class problem**: changes to a parent class can unexpectedly break all its children.

---

## HAS-A vs IS-A

There is a simple test to decide between inheritance and composition. Ask yourself:

- Is this an "IS-A" relationship? (A Duck IS-A Bird)
- Or is this a "HAS-A" relationship? (A Duck HAS-A swimming ability)

> Think of it this way: A Manager IS-A Employee — that's inheritance. But a Manager HAS-A team — that's composition. You would never say "a Manager inherits from a Team."

**Inheritance (IS-A)** is right when:
- The child truly is a specialised version of the parent
- The child can be substituted wherever the parent is used without surprises (more on this in the SOLID principles file)
- The relationship is permanent and fundamental

**Composition (HAS-A)** is right when:
- You just need *some behaviour* from another object
- The behaviour might vary or need to be swapped out
- Multiple unrelated classes need the same capability

---

## The behaviour injection pattern (the composition solution)

Instead of inheriting flying behaviour, you create separate behaviour objects and *inject* them into the Animal. The animal then delegates to those objects.

Here is the full example. Notice how each behaviour is a tiny, focused class:

```python
# Each behaviour is its own simple class
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
```

Now the `Animal` class holds references to behaviour objects and delegates to them. It doesn't know or care *how* flying works — it just asks its behaviour object to handle it:

```python
class Animal:
    def __init__(self, name: str, fly_behavior, swim_behavior):
        self.name = name
        self._fly = fly_behavior    # HAS-A fly behaviour
        self._swim = swim_behavior  # HAS-A swim behaviour

    def fly(self) -> str:
        return self._fly.fly()     # delegate to the behaviour object

    def swim(self) -> str:
        return self._swim.swim()   # delegate to the behaviour object
```

Creating different animals is now just a matter of choosing which behaviours to combine:

```python
duck    = Animal("Duck",    FlyBehavior(),   SwimBehavior())
penguin = Animal("Penguin", NoFlyBehavior(), SwimBehavior())
eagle   = Animal("Eagle",   FlyBehavior(),   NoSwimBehavior())

print(duck.fly())      # Flying with wings
print(duck.swim())     # Swimming
print(penguin.fly())   # Can't fly
print(penguin.swim())  # Swimming
print(eagle.fly())     # Flying with wings
print(eagle.swim())    # Can't swim
```

> **What just happened?**
> Adding a new type of animal requires zero changes to the `Animal` class — just create a new combination. Adding a new type of flight (like "gliding") just means adding a new behaviour class. No existing code is touched, so nothing can break. This is composition at its best.

---

## The real power: swapping behaviour at runtime

With inheritance, an animal's behaviour is locked in at class definition time. With composition, you can change behaviour while the program is running:

```python
class Animal:
    def __init__(self, name: str, fly_behavior, swim_behavior):
        self.name = name
        self._fly = fly_behavior
        self._swim = swim_behavior

    def fly(self) -> str:
        return self._fly.fly()

    def swim(self) -> str:
        return self._swim.swim()

    # Swap the behaviour object at any time!
    def set_fly_behavior(self, behavior) -> None:
        self._fly = behavior


class JetpackFlyBehavior:
    def fly(self) -> str:
        return "Flying with a jetpack!"


penguin = Animal("Penguin", NoFlyBehavior(), SwimBehavior())
print(penguin.fly())   # Can't fly

# Give the penguin a jetpack
penguin.set_fly_behavior(JetpackFlyBehavior())
print(penguin.fly())   # Flying with a jetpack!
```

> **Key takeaway:** Composition gives you flexibility that inheritance cannot. You can change, mix, and replace behaviours without altering any class definition.

---

## A practical example: the Logger

Here is a more realistic example you might encounter in an interview. Instead of a deep `Logger` hierarchy, compose logging from separate handlers:

```python
# The "bad" inheritance approach creates an explosion:
# class FileLogger(Logger): ...
# class FileAndEmailLogger(FileLogger): ...
# class FileAndEmailAndDBLogger(FileAndEmailLogger): ...
# This gets unmanageable fast.

# The composition approach — each handler is independent:
class FileHandler:
    def write(self, message: str) -> None:
        print(f"[FILE] {message}")

class EmailHandler:
    def write(self, message: str) -> None:
        print(f"[EMAIL] {message}")

class DatabaseHandler:
    def write(self, message: str) -> None:
        print(f"[DB] {message}")


class Logger:
    def __init__(self, handlers: list):
        self._handlers = handlers   # HAS-A list of handlers

    def log(self, message: str) -> None:
        for handler in self._handlers:
            handler.write(message)


# Mix and match freely — no new classes needed
simple_logger = Logger([FileHandler()])
full_logger   = Logger([FileHandler(), EmailHandler(), DatabaseHandler()])

simple_logger.log("Server started")   # [FILE] Server started
full_logger.log("Critical error!")
# [FILE] Critical error!
# [EMAIL] Critical error!
# [DB] Critical error!
```

---

## When inheritance IS the right choice

Composition is not always better. Inheritance makes perfect sense for genuine IS-A relationships.

> If you can say "an X is always a Y, can do everything a Y can, and will never surprise code that expects a Y" — then inheritance is right.

Good uses of inheritance:
- `class Manager(Employee)` — a Manager is always an Employee
- `class Square(Shape)` — a Square is always a Shape (and uses an ABC contract)
- `class StripeProcessor(PaymentProcessor)` — implementing an abstract contract
- Mixins — small, focused additions of behaviour (like `SerializableMixin`)

The test: can you replace every instance of the parent with the child, and have the program still behave correctly? If yes, inheritance is fine. If no, you have a composition problem masquerading as inheritance.

---

## Side-by-side comparison

Here is the inheritance and composition solutions next to each other for a quick visual:

```python
# ── INHERITANCE APPROACH (fragile) ────────────────────────────────────

class Animal:
    pass

class FlyingAnimal(Animal):
    def fly(self): return "Flying"

class SwimmingAnimal(Animal):
    def swim(self): return "Swimming"

class Duck(FlyingAnimal, SwimmingAnimal): pass  # awkward diamond
class Penguin(SwimmingAnimal): pass             # can't fly — but what does it inherit?


# ── COMPOSITION APPROACH (flexible) ───────────────────────────────────

class FlyBehavior:
    def fly(self): return "Flying with wings"

class NoFlyBehavior:
    def fly(self): return "Can't fly"

class SwimBehavior:
    def swim(self): return "Swimming"

class Animal:
    def __init__(self, name, fly_b, swim_b):
        self.name = name
        self._fly  = fly_b
        self._swim = swim_b
    def fly(self):  return self._fly.fly()
    def swim(self): return self._swim.swim()

duck    = Animal("Duck",    FlyBehavior(),   SwimBehavior())
penguin = Animal("Penguin", NoFlyBehavior(), SwimBehavior())
# Adding a new animal = one new line, zero class modifications.
```

---

## Common mistakes

**1. Reaching for inheritance first**

The default reflex for many beginners is to inherit. Before you write `class X(Y)`, pause and ask: is this really an IS-A relationship, or am I just trying to reuse some code from `Y`? If it is the latter, composition is almost certainly the better choice.

**2. Using inheritance for code reuse alone**

```python
# BAD — User is not a "type of" dict, it just uses one internally
class User(dict):
    def get_name(self):
        return self["name"]

# GOOD — User HAS-A storage mechanism
class User:
    def __init__(self, data: dict):
        self._data = data

    def get_name(self):
        return self._data["name"]
```

**3. Deep inheritance trees (more than 2 levels)**

If you see a class hierarchy three or four levels deep — `Animal -> Mammal -> Dog -> Labrador` — that's a sign composition might have been a better fit. Deep hierarchies are brittle: changing `Mammal` can break `Labrador` in unexpected ways.

**4. Forgetting that composition requires you to wire things up**

Composition does have a small cost: you need to explicitly pass the behaviour objects in (or wire them via a factory). This is usually handled cleanly with dependency injection.

---

## Quick summary

| Concept | Plain English |
|---|---|
| Composition | Build objects by combining other objects (HAS-A) |
| Inheritance | Build classes by extending other classes (IS-A) |
| Behaviour injection | Pass behaviour objects in via the constructor |
| Fragile base class | When changing a parent breaks its children unexpectedly |
| When to use inheritance | Genuine IS-A relationships, especially with abstract base classes |
| When to use composition | When behaviour might vary, be swapped, or is shared across unrelated classes |

**The one-sentence rule:** If you are tempted to inherit just to reuse code, use composition instead — give the class an instance of the thing it needs, and delegate to it.
