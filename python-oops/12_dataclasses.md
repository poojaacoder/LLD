# 12. Dataclasses

## What is this?

A dataclass is a shortcut for writing classes that mainly exist to hold data. Python automatically generates the boring boilerplate (`__init__`, `__repr__`, `__eq__`) so you can focus on what fields your class has, not the plumbing to set them up.

---

## The Problem Dataclasses Solve

Imagine you need a class to hold a 2D point (x, y). Without dataclasses, you write this:

```python
# Without dataclasses — lots of repetitive boilerplate
class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Point(x={self.x}, y={self.y})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y
```

That's 12 lines just to store two numbers. And if you add a third field, you have to update `__init__`, `__repr__`, and `__eq__` in three separate places.

> Think of a dataclass as a form template. Instead of writing "Name: _____, Age: _____" from scratch every time, you just fill in the blanks. Python fills in all the standard methods for you based on the fields you declare.

With `@dataclass`, the same class becomes:

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float
```

Four lines. Python generates `__init__`, `__repr__`, and `__eq__` automatically based on the field declarations.

---

## Basic `@dataclass`

This defines two fields (`x` and `y`) using type annotations. Python reads those annotations and writes the standard methods for you.

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float

    # You can still add your own methods — dataclass doesn't stop you
    def distance_from_origin(self) -> float:
        return (self.x**2 + self.y**2) ** 0.5


p1 = Point(3.0, 4.0)
p2 = Point(3.0, 4.0)
p3 = Point(1.0, 2.0)

print(p1)          # Point(x=3.0, y=4.0)   — __repr__ generated
print(p1 == p2)    # True                   — __eq__ generated (compares field values)
print(p1 == p3)    # False
print(p1.distance_from_origin())  # 5.0
```

> **Key takeaway:** Every field listed as a type annotation becomes a constructor parameter AND appears in `__repr__` AND is compared in `__eq__`. All for free.

---

## `frozen=True` — Immutable and Hashable

By default, dataclasses are mutable — you can change fields after creation. Adding `frozen=True` makes the object immutable: any attempt to change a field raises a `FrozenInstanceError`.

Immutability also makes the object **hashable**, which means you can use it as a dictionary key or put it in a set.

> Think of a frozen dataclass like a printed receipt. Once printed, the numbers don't change. You can file it in a folder (put it in a set) or use it as a reference (dict key).

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Point:
    x: float
    y: float


p = Point(1.0, 2.0)
# p.x = 5.0  # FrozenInstanceError: cannot assign to field 'x'

# Because it's hashable, it can live in a set or be a dict key
point_set = {Point(1, 2), Point(3, 4), Point(1, 2)}
print(point_set)    # {Point(x=1, y=2), Point(x=3, y=4)} — duplicates removed

lookup = {Point(0, 0): "origin", Point(1, 0): "x-axis"}
print(lookup[Point(0, 0)])  # "origin"
```

> **Key takeaway:** Use `frozen=True` for value objects — things that represent a value rather than an entity with changing state. Coordinates, currency amounts, date ranges, version numbers are all good candidates.

---

## `order=True` — Automatic Comparison

By default, dataclasses only support `==` and `!=`. Adding `order=True` generates `<`, `<=`, `>`, `>=` based on comparing fields **in the order they are declared**.

```python
from dataclasses import dataclass

@dataclass(order=True, frozen=True)
class Version:
    major: int
    minor: int
    patch: int = 0  # optional field with a default

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


v1 = Version(1, 2, 3)
v2 = Version(1, 3, 0)
v3 = Version(2, 0, 0)

print(v1 < v2)           # True  — 1.2.3 < 1.3.0
print(v2 < v3)           # True  — 1.3.0 < 2.0.0
print(sorted([v3, v1, v2]))  # [Version(1,2,3), Version(1,3,0), Version(2,0,0)]
print({v1, v2})          # set works because frozen=True makes it hashable
```

> **Key takeaway:** Comparison happens field by field, left to right — first `major` is compared; if equal, then `minor`; if equal, then `patch`. This is exactly the same logic you'd want for version numbers, dates, priorities, etc.

---

## `field()` — Fine-Grained Control Over Fields

Sometimes you need more control than a simple default value. The `field()` function lets you configure individual fields.

### Why you can't use mutable defaults directly

This is one of the most common Python mistakes:

```python
# WRONG — DO NOT DO THIS
@dataclass
class Config:
    tags: list = []  # This will raise a ValueError!
```

Python raises an error here because if it allowed this, ALL instances would share the **same list object**. Modifying one instance's `tags` would affect every other instance — a nasty hidden bug.

> Think of it this way: if you write `default = []` at the class level, there's only ONE list in memory, shared by all instances. It's like a class sharing one whiteboard — when one student erases and rewrites, everyone sees the change.

The fix is `field(default_factory=...)`, which tells Python to call a function to create a **fresh** list for each new instance:

```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080
    tags: List[str] = field(default_factory=list)   # creates a NEW list each time
    metadata: dict = field(default_factory=dict)     # creates a NEW dict each time


c1 = Config()
c2 = Config()
c1.tags.append("prod")

print(c1.tags)   # ['prod']
print(c2.tags)   # []  — c2 has its OWN separate list, untouched
```

> **Key takeaway:** Never use a mutable value (list, dict, set) as a plain default in a dataclass. Always wrap it in `field(default_factory=list)` or `field(default_factory=dict)`.

### Other useful `field()` options

```python
from dataclasses import dataclass, field

@dataclass
class Product:
    name: str
    price: float
    # repr=False — this field won't show up in the printed representation
    _internal_code: str = field(default="", repr=False)
    # compare=False — this field is ignored when comparing two Products
    last_viewed: str = field(default="", compare=False)
```

---

## `__post_init__` — Validation After Auto-Init

Python calls `__post_init__` right after the generated `__init__` finishes. This is where you put validation logic — things that need to run every time an instance is created but shouldn't live in `__init__` itself.

```python
from dataclasses import dataclass
from typing import List

@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Runs automatically after __init__ sets all the fields
        if self.port < 0 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")
        if not self.host:
            raise ValueError("Host cannot be empty")
        # Normalize the host to lowercase
        self.host = self.host.lower()


cfg = Config(port=8080)          # Works fine
print(cfg.host)                  # "localhost"

try:
    bad = Config(port=99999)     # Raises ValueError
except ValueError as e:
    print(e)                     # "Invalid port: 99999"
```

> **Key takeaway:** Use `__post_init__` for validation, normalization (like lowercasing), or computing derived fields from the inputs.

---

## `ClassVar` — Class-Level Variables That Are Not Fields

Sometimes you want a class-level variable that is shared across all instances — not a per-instance field. If you declare it as a normal annotation, `@dataclass` will treat it as a constructor parameter, which is wrong. Use `ClassVar` to tell dataclass "this is NOT a field."

```python
from dataclasses import dataclass, field
from typing import ClassVar, List

@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080
    tags: List[str] = field(default_factory=list)

    # ClassVar — shared across all instances, NOT a constructor param
    _instance_count: ClassVar[int] = 0
    DEFAULT_TIMEOUT: ClassVar[int] = 30  # a constant shared by all

    def __post_init__(self):
        Config._instance_count += 1


c1 = Config()
c2 = Config(port=9090)
print(Config._instance_count)   # 2  — shared count
print(Config.DEFAULT_TIMEOUT)   # 30

# ClassVar fields do NOT appear in __init__, __repr__, or __eq__
print(c1)  # Config(host='localhost', port=8080, tags=[])
           # _instance_count is NOT shown
```

> **Key takeaway:** `ClassVar` = "belongs to the class, not individual instances." Use it for counters, constants, or registries.

---

## `asdict()` and `astuple()` — Converting to Standard Types

Two utility functions let you convert a dataclass instance to a plain dict or tuple. Very useful for serialization (sending data to JSON APIs, databases, etc.).

```python
from dataclasses import dataclass, field, asdict, astuple
from typing import List

@dataclass
class Point:
    x: float
    y: float

@dataclass
class Config:
    host: str = "localhost"
    port: int = 8080
    tags: List[str] = field(default_factory=list)


# asdict — recursively converts to a dictionary
cfg = Config(tags=["prod", "us-east"])
print(asdict(cfg))
# {'host': 'localhost', 'port': 8080, 'tags': ['prod', 'us-east']}

# Great for JSON serialization:
import json
print(json.dumps(asdict(cfg)))
# '{"host": "localhost", "port": 8080, "tags": ["prod", "us-east"]}'

# astuple — converts to a plain tuple (fields in declaration order)
p = Point(3.0, 4.0)
print(astuple(p))   # (3.0, 4.0)

# Nested dataclasses are also converted recursively
@dataclass
class Line:
    start: Point
    end: Point

line = Line(Point(0, 0), Point(1, 1))
print(asdict(line))   # {'start': {'x': 0, 'y': 0}, 'end': {'x': 1, 'y': 1}}
```

> **Key takeaway:** `asdict()` is your best friend when you need to send a dataclass to a JSON API or database. It handles nested dataclasses automatically.

---

## Putting It All Together

Here is a realistic example that combines all the features above:

```python
from dataclasses import dataclass, field, asdict
from typing import ClassVar, List

@dataclass(order=True, frozen=True)
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
    tags: List[str] = field(default_factory=list)
    _instance_count: ClassVar[int] = 0

    def __post_init__(self):
        Config._instance_count += 1
        if self.port < 0 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")


# Version: frozen + order — can be sorted and used in sets/dicts
v1 = Version(1, 2, 3)
v2 = Version(1, 3, 0)
print(v1 < v2)      # True
print({v1, v2})     # works — frozen makes it hashable

# Config: validation + ClassVar + mutable defaults
cfg = Config(tags=["prod", "us-east"])
print(cfg)          # Config(host='localhost', port=8080, tags=['prod', 'us-east'])
print(asdict(cfg))  # {'host': 'localhost', 'port': 8080, 'tags': ['prod', 'us-east']}
print(Config._instance_count)  # 1
```

---

## When to Use What

| Situation | Best choice |
|---|---|
| You need `__init__`, `__repr__`, `__eq__` and the class holds data | `@dataclass` |
| You need the object to be hashable (dict key, set member) | `@dataclass(frozen=True)` |
| You need sortable objects | `@dataclass(order=True)` |
| You need immutable AND sortable | `@dataclass(order=True, frozen=True)` |
| Simple read-only records, no methods needed | `collections.namedtuple` or `typing.NamedTuple` |
| Complex business logic, not mainly data | Regular class |
| You need `__post_init__` validation | `@dataclass` (namedtuple can't do this) |

### Dataclass vs `namedtuple`

```python
from typing import NamedTuple

# NamedTuple — simpler, always immutable, no __post_init__
class Point(NamedTuple):
    x: float
    y: float

# Dataclass — more flexible, supports __post_init__, mutable by default
@dataclass
class Point:
    x: float
    y: float
```

Use `NamedTuple` for very simple value objects with no validation or methods. Use `@dataclass` for everything else.

---

## Common Mistakes

**Mutable default without `field()`:**
```python
# WRONG
@dataclass
class Bag:
    items: list = []   # ValueError! All instances share ONE list

# RIGHT
@dataclass
class Bag:
    items: list = field(default_factory=list)
```

**Forgetting that `frozen=True` prevents field mutation in `__post_init__`:**
```python
# This will fail at runtime
@dataclass(frozen=True)
class Config:
    host: str = "localhost"

    def __post_init__(self):
        self.host = self.host.lower()  # FrozenInstanceError!

# Fix: use object.__setattr__() for frozen dataclasses
    def __post_init__(self):
        object.__setattr__(self, "host", self.host.lower())
```

**Declaring `ClassVar` without importing it:**
```python
from typing import ClassVar  # Don't forget this import!
```

**Comparing dataclasses when `order=True` but `eq=False`:**
Setting `order=True` requires `eq=True` (the default). If you manually set `eq=False`, you'll get an error. Let Python handle both together.

**Using `astuple()` and being surprised by nested expansion:**
```python
@dataclass
class Line:
    start: Point
    end: Point

line = Line(Point(0,0), Point(1,1))
astuple(line)  # ((0, 0), (1, 1)) — nested tuples, not a flat tuple
```

---

## Quick Summary

- `@dataclass` auto-generates `__init__`, `__repr__`, `__eq__` from your field annotations
- `frozen=True` makes the object immutable and hashable (usable as dict key / set member)
- `order=True` generates comparison operators (`<`, `>`, etc.) based on field order
- `field(default_factory=list)` is the correct way to have a mutable default — never use a bare `[]`
- `__post_init__` runs after `__init__` and is the right place for validation
- `ClassVar` marks a class-level variable that should NOT become a constructor field
- `asdict()` converts a dataclass (including nested ones) to a plain `dict` — great for serialization
- `astuple()` converts to a plain `tuple`
