# 11. Design Patterns

## What is this?

Design patterns are tried-and-tested solutions to problems that come up again and again in software design. Think of them as named recipes — once you know the recipe, you can recognize the problem and apply the solution confidently in any LLD interview.

---

## Patterns covered in this file

| Category | Pattern | One-line problem it solves |
|---|---|---|
| Creational | Singleton | Ensure only ONE instance of a class ever exists |
| Creational | Factory Method | Create objects without hardcoding which class to use |
| Creational | Builder | Build complex objects step by step without a messy constructor |
| Structural | Decorator | Add features to an object at runtime without changing its class |
| Structural | Adapter | Make two incompatible interfaces work together |
| Behavioral | Observer | Notify many objects automatically when something changes |
| Behavioral | Strategy | Swap out an algorithm or behavior at runtime |
| Behavioral | Command | Wrap actions as objects so you can undo/redo them |

---

## Creational Patterns

Creational patterns are about **how objects are created**. The goal is to hide the messy "new object" logic and give the rest of your code clean, flexible ways to get the objects it needs.

---

### Singleton

**Problem this solves:** You need exactly one shared instance of something — a config loader, a database connection pool, a logger. If you let code call `MyClass()` freely, you might accidentally create duplicates.

> Think of a country's president. There is always exactly one president at a time. No matter how many times you ask "who is the president?", you get the same person — not a new one each time.

#### Basic Singleton

This code overrides `__new__` (the method Python calls before `__init__`) to check if an instance already exists. If it does, it returns the existing one instead of making a new one.

```python
class Singleton:
    _instance = None  # class-level store for the one instance

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            # First call: actually create the object
            cls._instance = super().__new__(cls)
        return cls._instance  # every call returns the same object

    def __init__(self, value: int = 0):
        # Guard: __init__ runs every time Singleton() is called,
        # even when we return the existing instance — so we check
        if not hasattr(self, "_initialized"):
            self.value = value
            self._initialized = True


s1 = Singleton(10)
s2 = Singleton(20)
print(s1 is s2)    # True  — same object in memory
print(s1.value)    # 10   — init only ran once; s2 did NOT reset it
```

> **What just happened?** Even though we called `Singleton(20)` a second time, Python returned the original object. The `_initialized` guard stops `__init__` from overwriting `value` on that second call.

#### Thread-Safe Singleton

In a multi-threaded app, two threads could both see `_instance is None` at the same time and both try to create a new instance. The fix is a **double-checked lock**: check once before the lock (fast path), and once after (safe path).

```python
import threading

class ThreadSafeSingleton:
    _instance = None
    _lock = threading.Lock()  # shared class-level lock

    def __new__(cls):
        if cls._instance is None:          # 1st check — fast, no lock overhead
            with cls._lock:                # acquire lock only when needed
                if cls._instance is None:  # 2nd check — safe, inside lock
                    cls._instance = super().__new__(cls)
        return cls._instance
```

> **When to use in LLD interviews:** Any time the problem mentions a shared resource with global state — config manager, connection pool, print spooler, cache. Mention thread-safety if concurrency is in scope.

---

### Factory Method

**Problem this solves:** Your code needs to create objects, but you don't want a giant `if channel == "email": ... elif channel == "sms": ...` block. Adding a new type should not require editing existing code.

> Think of a vending machine. You press a button labeled "Cola" and the machine gives you a Cola. You don't care which shelf it came from or how the mechanism works — you just know the button and get the product.

The registry-based factory stores a mapping of "key → class". New types can be **registered** without touching the creation logic.

```python
from abc import ABC, abstractmethod

# Abstract product — defines what every notification must do
class Notification(ABC):
    @abstractmethod
    def send(self, message: str) -> None: ...

# Concrete products — each knows how to send in its own way
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
    # Registry maps string keys to classes
    _registry: dict = {
        "email": EmailNotification,
        "push":  PushNotification,
        "sms":   SMSNotification,
    }

    @classmethod
    def create(cls, channel: str) -> Notification:
        klass = cls._registry.get(channel.lower())
        if not klass:
            raise ValueError(f"Unknown channel: {channel}")
        return klass()  # creates the right class without any if-else

    @classmethod
    def register(cls, channel: str, klass: type) -> None:
        # Open/Closed principle in action: extend without modifying
        cls._registry[channel] = klass


n = NotificationFactory.create("email")
n.send("Hello!")   # Email: Hello!

# Adding a new channel type — no changes to existing code needed
class SlackNotification(Notification):
    def send(self, message: str) -> None:
        print(f"Slack: {message}")

NotificationFactory.register("slack", SlackNotification)
NotificationFactory.create("slack").send("Hi team!")  # Slack: Hi team!
```

> **What just happened?** The factory looks up the class from its registry and calls it. Adding Slack required zero changes to `NotificationFactory.create()` — we just registered a new entry.

> **When to use in LLD interviews:** Whenever the problem involves creating different "types" of something based on a string or enum — payment methods, vehicle types, notification channels, report formats.

---

### Builder

**Problem this solves:** Objects with many optional parameters lead to ugly, error-prone constructors: `Pizza("large", "thick", True, False, ["mushrooms"], "pesto")`. What does `True` mean? Which field is which?

The Builder pattern lets you set each field by name, in any order, using method chaining.

> Think of ordering a custom pizza. You tell the server: "large please… thick crust… add mushrooms… extra cheese." Each instruction is clear and optional. When you're done you say "that's it" (`.build()`).

Each setter method returns `self` — this is called a **fluent interface**. It allows you to chain calls like `.crust("thick").add_topping("mushrooms").extra_cheese()`.

```python
from dataclasses import dataclass, field
from typing import List

# The final product — a simple data holder
@dataclass
class Pizza:
    size: str
    crust: str
    toppings: List[str] = field(default_factory=list)
    extra_cheese: bool = False
    sauce: str = "tomato"

# The builder — collects your choices, then assembles the Pizza
class PizzaBuilder:
    def __init__(self, size: str):
        # Sensible defaults — you only need to override what you want
        self._size = size
        self._crust = "thin"
        self._toppings: List[str] = []
        self._extra_cheese = False
        self._sauce = "tomato"

    def crust(self, crust: str) -> "PizzaBuilder":
        self._crust = crust
        return self   # returning self enables method chaining

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
        # Assemble — this is where validation could go too
        return Pizza(
            size=self._size,
            crust=self._crust,
            toppings=self._toppings,
            extra_cheese=self._extra_cheese,
            sauce=self._sauce,
        )


# Each line reads like plain English
pizza = (
    PizzaBuilder("large")
    .crust("thick")
    .add_topping("mushrooms")
    .add_topping("peppers")
    .extra_cheese()
    .build()
)
print(pizza)
# Pizza(size='large', crust='thick', toppings=['mushrooms', 'peppers'],
#        extra_cheese=True, sauce='tomato')
```

> **What just happened?** We built a complex object without a 6-argument constructor. Each option is named, optional, and readable. The `build()` call signals "I'm done choosing."

> **When to use in LLD interviews:** Complex objects with 4+ optional fields — HTTP request builders, query builders, notification builders, config objects.

---

## Structural Patterns

Structural patterns are about **how objects are composed together** — how you build larger structures from smaller pieces.

---

### Decorator Pattern (object version — not `@decorator` syntax)

**Problem this solves:** You want to add features to an object dynamically, at runtime, without creating a subclass explosion. For a coffee shop: `CoffeeWithMilk`, `CoffeeWithSugar`, `CoffeeWithMilkAndSugar`… this gets out of hand fast with inheritance.

> Think of a plain coffee cup. You can add milk, sugar, flavors — each addition wraps the cup but the cup itself doesn't change. You can stack additions in any order.

The key idea: a `Decorator` wraps an object that has **the same interface**. It forwards calls to the wrapped object and adds its own behavior on top.

```python
from abc import ABC, abstractmethod

# The interface — both the base coffee and all decorators implement this
class Coffee(ABC):
    @abstractmethod
    def cost(self) -> float: ...

    @abstractmethod
    def description(self) -> str: ...

# The base object — the simplest possible coffee
class SimpleCoffee(Coffee):
    def cost(self) -> float:
        return 1.0

    def description(self) -> str:
        return "Simple coffee"

# Base decorator — wraps a Coffee and forwards calls by default
# Concrete decorators only override what they need to change
class CoffeeDecorator(Coffee, ABC):
    def __init__(self, coffee: Coffee):
        self._coffee = coffee  # holds the object being wrapped

    def cost(self) -> float:
        return self._coffee.cost()  # delegate to wrapped object

    def description(self) -> str:
        return self._coffee.description()

# Each add-on is a tiny class that wraps the previous coffee
class Milk(CoffeeDecorator):
    def cost(self) -> float:
        return self._coffee.cost() + 0.25  # base cost + milk cost

    def description(self) -> str:
        return self._coffee.description() + ", milk"

class Sugar(CoffeeDecorator):
    def cost(self) -> float:
        return self._coffee.cost() + 0.10

    def description(self) -> str:
        return self._coffee.description() + ", sugar"

class Vanilla(CoffeeDecorator):
    def cost(self) -> float:
        return self._coffee.cost() + 0.50

    def description(self) -> str:
        return self._coffee.description() + ", vanilla"


# Wrapping order: Sugar wraps Milk, Milk wraps SimpleCoffee
coffee = Sugar(Milk(SimpleCoffee()))
print(coffee.description())   # Simple coffee, milk, sugar
print(coffee.cost())          # 1.35

# Different combination — any order, any number of add-ons
fancy = Vanilla(Sugar(Milk(Milk(SimpleCoffee()))))
print(fancy.description())    # Simple coffee, milk, milk, sugar, vanilla
print(fancy.cost())           # 2.10
```

> **What just happened?** Each decorator wraps the previous object. When you call `.cost()` it unwinds the stack — Sugar asks Milk, Milk asks SimpleCoffee, and the results are summed as the call returns. No subclass explosion needed.

> **When to use in LLD interviews:** Anything involving stacking optional features — middleware layers, logging/caching wrappers, UI widget add-ons, stream processing.

---

### Adapter

**Problem this solves:** You have existing code that expects interface A, but you need to use a class with interface B. You can't change either class (maybe one is a third-party library).

> You're in Europe and your US laptop charger won't fit the EU socket. You don't rebuild the wall socket or the charger — you use an adapter that sits between them and translates.

```python
# What the rest of your code already uses — the expected interface
class EUSocket:
    def plug_in(self, eu_plug) -> str:
        return "EU plug connected"

# A third-party class you want to use, but it has a different interface
class USPlug:
    def connect(self) -> str:         # "connect" instead of "plug_in"
        return "US plug connected"

# The adapter: presents the EUSocket interface, but internally
# delegates to the USPlug — it "translates" between the two
class USToEUAdapter:
    def __init__(self, us_plug: USPlug):
        self._us_plug = us_plug

    def plug_in(self, eu_plug=None) -> str:
        # Caller thinks it's talking to an EU-compatible device
        # Adapter translates by calling the US plug's method
        return self._us_plug.connect()


socket = EUSocket()
us_plug = USPlug()
adapter = USToEUAdapter(us_plug)

print(socket.plug_in(None))    # EU plug connected
print(adapter.plug_in(None))   # US plug connected — works in EU context!
```

> **What just happened?** The adapter wraps a `USPlug` but exposes a `plug_in()` method, so code written for `EUSocket` can use it without any changes.

> **When to use in LLD interviews:** Integrating with third-party APIs, legacy systems, or any time you need to make two existing interfaces compatible.

---

## Behavioral Patterns

Behavioral patterns are about **how objects communicate and share responsibilities**.

---

### Observer

**Problem this solves:** Many parts of your system need to react when something changes — but the thing that changes shouldn't need to know about every subscriber. You want a clean "publish/subscribe" model.

> Think of a YouTube channel. The channel (Subject) doesn't know who all its subscribers are individually. When a new video is uploaded, YouTube automatically notifies everyone who subscribed. Subscribers can join or leave at any time.

```python
from abc import ABC, abstractmethod
from typing import List

# Observer interface — anything that wants to be notified implements this
class Observer(ABC):
    @abstractmethod
    def update(self, event: str, data) -> None: ...

# Subject — the thing being watched
class Subject:
    def __init__(self):
        self._observers: List[Observer] = []
        self._state = None

    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)  # subscribe

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)  # unsubscribe

    def notify(self, event: str) -> None:
        # Tell every subscriber what happened
        for obs in self._observers:
            obs.update(event, self._state)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value) -> None:
        self._state = value
        self.notify("state_changed")  # auto-notify on every state change


# Two different subscribers — they react differently to the same event
class Logger(Observer):
    def update(self, event: str, data) -> None:
        print(f"[LOG] {event}: {data}")

class AlertService(Observer):
    def update(self, event: str, data) -> None:
        # Only reacts to critical states — ignores others
        if data and data.get("critical"):
            print(f"[ALERT] Critical state detected: {data}")


store = Subject()
store.attach(Logger())
store.attach(AlertService())

store.state = {"status": "ok"}
# [LOG] state_changed: {'status': 'ok'}
# (AlertService stays silent — not critical)

store.state = {"status": "down", "critical": True}
# [LOG] state_changed: {'status': 'down', 'critical': True}
# [ALERT] Critical state detected: {'status': 'down', 'critical': True}
```

> **What just happened?** The `Subject` broadcasts to all subscribers every time its state changes. Each subscriber decides independently what to do with the notification. The Subject doesn't need to know anything about its subscribers.

> **When to use in LLD interviews:** Event systems, notification services, real-time dashboards, stock price feeds, UI updates (MVC's View updating when Model changes).

---

### Strategy

**Problem this solves:** You have a class that needs to do something, but the *how* should be swappable. Without Strategy you end up with a big `if algorithm == "quicksort":` block inside your class.

> Think of a GPS navigation app. You choose your "strategy": fastest route, shortest route, avoid highways. The app uses whichever strategy you picked, and you can change it mid-trip. The car doesn't care — it just follows directions.

```python
from abc import ABC, abstractmethod
from typing import List

# Strategy interface — all sorting algorithms must implement this
class SortStrategy(ABC):
    @abstractmethod
    def sort(self, data: List[int]) -> List[int]: ...

# Two concrete strategies — different algorithms, same interface
class BubbleSort(SortStrategy):
    def sort(self, data: List[int]) -> List[int]:
        arr = data[:]  # don't mutate the input
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
        left  = [x for x in data if x < pivot]
        mid   = [x for x in data if x == pivot]
        right = [x for x in data if x > pivot]
        return self.sort(left) + mid + self.sort(right)

# Context — uses whichever strategy is plugged in
class Sorter:
    def __init__(self, strategy: SortStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: SortStrategy) -> None:
        self._strategy = strategy  # swap at runtime

    def sort(self, data: List[int]) -> List[int]:
        return self._strategy.sort(data)


sorter = Sorter(QuickSort())
print(sorter.sort([3, 1, 4, 1, 5]))   # [1, 1, 3, 4, 5]

# Switch to BubbleSort without changing the Sorter class at all
sorter.set_strategy(BubbleSort())
print(sorter.sort([3, 1, 4, 1, 5]))   # [1, 1, 3, 4, 5]
```

> **What just happened?** `Sorter` doesn't know or care how sorting works. You plug in any strategy that satisfies the interface. Need a new algorithm? Add a class — don't touch `Sorter`.

> **When to use in LLD interviews:** Payment processing (Stripe vs PayPal vs cash), pricing/discount rules, routing algorithms, compression algorithms, authentication methods.

---

### Command

**Problem this solves:** You want to turn actions into objects so you can queue them, log them, and — most importantly — **undo** them.

> Think of a text editor's Ctrl+Z. The editor doesn't just execute your typing — it stores each action as a "command object" with enough information to reverse it. Ctrl+Z pops the last command and calls its undo.

```python
from abc import ABC, abstractmethod
from typing import List

# Command interface — every action needs execute AND undo
class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...

# The thing being operated on — the "receiver"
class TextEditor:
    def __init__(self):
        self.text = ""

    def insert(self, text: str) -> None:
        self.text += text

    def delete(self, n: int) -> None:
        self.text = self.text[:-n]  # remove last n characters

# A concrete command — knows how to insert AND how to undo it
class InsertCommand(Command):
    def __init__(self, editor: TextEditor, text: str):
        self.editor = editor
        self.text = text

    def execute(self) -> None:
        self.editor.insert(self.text)

    def undo(self) -> None:
        # To undo an insert, delete the same number of characters
        self.editor.delete(len(self.text))

# History — stores all executed commands; enables undo
class CommandHistory:
    def __init__(self):
        self._history: List[Command] = []

    def execute(self, command: Command) -> None:
        command.execute()
        self._history.append(command)  # remember it for undo

    def undo(self) -> None:
        if self._history:
            # Pop the most recent command and reverse it
            self._history.pop().undo()


editor = TextEditor()
history = CommandHistory()

history.execute(InsertCommand(editor, "Hello"))
history.execute(InsertCommand(editor, " World"))
print(editor.text)   # Hello World

history.undo()
print(editor.text)   # Hello   (the " World" insert was reversed)

history.undo()
print(editor.text)   # (empty)
```

> **What just happened?** Each action is stored as an object in the history stack. Calling `undo()` pops the last command and runs its reverse. Adding a new action type (e.g., `DeleteCommand`, `FormatCommand`) requires no changes to `CommandHistory`.

> **When to use in LLD interviews:** Any system with undo/redo — text editors, drawing apps, transaction logs, task queues, macro recorders.

---

## Common Mistakes

**Singleton:**
- Forgetting the `_initialized` guard — `__init__` runs every time you call `Singleton()`, even when returning the existing instance, which can reset your state.
- Not using a lock in multi-threaded code — two threads can both pass the first `if _instance is None` check simultaneously.

**Factory:**
- Using `if-else` chains instead of a registry — every new type forces you to edit the factory method, violating Open/Closed.

**Builder:**
- Forgetting to `return self` in setter methods — without it, you can't chain calls.
- Mutating the same builder to create multiple objects without resetting it first.

**Decorator:**
- Confusing the object Decorator pattern with Python's `@decorator` function syntax — they're different things. This pattern uses class wrapping.
- Not forwarding all interface methods in the base decorator, causing some calls to silently do nothing.

**Observer:**
- Modifying the `_observers` list while iterating over it during `notify()` — iterate over a copy instead: `for obs in list(self._observers)`.
- Not detaching observers that are no longer needed — causes memory leaks.

**Strategy:**
- Putting strategy selection logic inside the context class (`if condition: use strategy A`) — the whole point is that the context should not know which strategy it's running.

**Command:**
- Forgetting to implement `undo()` — undo support is the main reason to use Command in the first place.

---

## Quick Summary

- **Singleton** — one instance, globally accessible, optionally thread-safe
- **Factory Method** — registry-based creation; adding new types requires no changes to existing code
- **Builder** — fluent interface for complex objects; each method returns `self` to enable chaining; call `.build()` at the end
- **Decorator** — wrap an object with the same interface to add behavior; stack multiple decorators freely
- **Adapter** — translate one interface to another; neither original class is modified
- **Observer** — Subject broadcasts to all attached Observers on state change; Observers can attach/detach freely
- **Strategy** — plug in different algorithms at runtime; the Context class never changes
- **Command** — actions as objects; enables undo/redo via a history stack

---

## Pattern Summary Table

| Pattern | Category | Problem it solves | Common LLD use case |
|---|---|---|---|
| Singleton | Creational | Guarantee one shared instance | Config manager, DB connection pool, Logger |
| Factory Method | Creational | Create objects without if-else by type | Notification channels, payment processors, report types |
| Builder | Creational | Construct complex objects step by step | Pizza/order builder, HTTP request builder, query builder |
| Decorator | Structural | Add features to objects at runtime | Coffee add-ons, middleware, logging wrappers |
| Adapter | Structural | Make incompatible interfaces compatible | Third-party API integration, legacy system bridge |
| Observer | Behavioral | Auto-notify many objects on state change | Event system, UI updates, stock feed, alerts |
| Strategy | Behavioral | Swap algorithms or behaviors at runtime | Sorting, pricing rules, payment methods, routing |
| Command | Behavioral | Wrap actions as objects for undo/redo | Text editor, transaction log, task queue |
