# 04 — Properties and Descriptors

## What is this?

A `@property` lets you use an attribute like a normal variable on the outside, while secretly running validation or computation on the inside. Descriptors take that same idea and let you reuse it across many different classes — they are how Python's own `@property` works under the hood.

---

## The problem: public attributes vs getter/setter methods

Imagine you have a `Circle` class and you start out with a plain attribute:

```python
class Circle:
    def __init__(self, radius):
        self.radius = radius   # anyone can set this to -5 and nothing complains
```

The usual fix in other languages is to add `get_radius()` and `set_radius()` methods. But then every caller has to change from `circle.radius` to `circle.get_radius()`. That is annoying.

> Think of `@property` as a bouncer at the door. From the outside, people still just say "radius". But behind the scenes the bouncer checks their ID (validates the value) before letting them in.

Python's `@property` gives you the best of both worlds: attribute-style access on the outside, full control on the inside. And you can add validation later without changing any existing caller code.

---

## @property, @x.setter, and @x.deleter

Start with a plain read-only property. This code defines `radius` as a property — calling `circle.radius` runs the function and returns `self._radius`.

```python
class Circle:
    def __init__(self, radius: float):
        self._radius = radius   # note the underscore — this is the "backing store"

    @property
    def radius(self) -> float:
        return self._radius
```

> **Key takeaway:** The underscore on `self._radius` is the actual storage. The property named `radius` is just a controlled doorway to it. Never name them the same thing — Python will recurse forever.

Now add a setter so the property can also be written to. The setter runs whenever someone does `circle.radius = value`:

```python
    @radius.setter
    def radius(self, value: float) -> None:
        if value < 0:
            raise ValueError("Radius cannot be negative")
        self._radius = value
```

And optionally a deleter, which runs when someone does `del circle.radius`:

```python
    @radius.deleter
    def radius(self) -> None:
        del self._radius
```

Here is the full class together, including a computed property:

```python
import math

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
        return math.pi * self._radius ** 2
```

> **What just happened?** From the outside, `circle.radius = 5` and `print(circle.area)` look like normal attribute access. But Python silently routes them through the setter and getter functions. The caller never needs to know.

---

## Computed (read-only) properties

A property with no setter is read-only — Python will raise an `AttributeError` if anyone tries to set it. This is perfect for values that are *derived* from other fields rather than stored directly.

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
    def fahrenheit(self) -> float:    # derived — always in sync, never stale
        return self._celsius * 9 / 5 + 32
```

This means `fahrenheit` is always correct because it is calculated fresh each time, not stored separately. There is no risk of `celsius` and `fahrenheit` going out of sync.

```python
t = Temperature(100)
print(t.fahrenheit)   # 212.0
t.celsius = 0
print(t.fahrenheit)   # 32.0 — automatically updated
# t.fahrenheit = 100  # AttributeError: can't set attribute
```

> **Key takeaway:** Use a read-only property (no setter) whenever a value can be *calculated* from other stored values. Don't store it separately — you will forget to update it.

---

## Descriptors — what they are and when you need them

A `@property` is tied to one attribute on one class. If you want the *same validation logic* applied to five different attributes on three different classes, you would have to copy and paste the property five times.

> Think of a descriptor like a reusable stamp. Instead of writing "must be positive" on every page by hand, you carve a stamp once and press it wherever you need it.

A descriptor is a class that defines `__get__`, `__set__`, and/or `__delete__`. When you assign an instance of that class as a class-level attribute, Python will call those methods automatically whenever the attribute is accessed.

This pattern is how Django/SQLAlchemy model fields work — `name = CharField(max_length=100)` is a descriptor instance sitting on the class.

### Building a PositiveNumber descriptor

The special `__set_name__` method is called by Python at class-creation time. It tells the descriptor what attribute name it is being assigned to, so it can store the value under a unique private name.

```python
class PositiveNumber:
    """A descriptor that enforces positive values on any attribute."""

    def __set_name__(self, owner, name: str) -> None:
        # Called automatically when the class is created.
        # name = the attribute name (e.g. "price" or "quantity")
        self.name = name
        self.private_name = f"_{name}"   # e.g. "_price"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self   # accessed on the class itself, not an instance
        return getattr(obj, self.private_name, None)

    def __set__(self, obj, value: float) -> None:
        if value <= 0:
            raise ValueError(f"{self.name} must be positive, got {value}")
        setattr(obj, self.private_name, value)
```

Now attach it to a class just like a class variable. Each assignment (`price = PositiveNumber()`) creates a separate descriptor instance with its own `name`:

```python
class Product:
    price = PositiveNumber()       # one descriptor for "price"
    quantity = PositiveNumber()    # a separate descriptor for "quantity"

    def __init__(self, name: str, price: float, quantity: int):
        self.name = name
        self.price = price          # triggers PositiveNumber.__set__ for "price"
        self.quantity = quantity    # triggers PositiveNumber.__set__ for "quantity"

p = Product("Widget", 9.99, 10)
print(p.price)      # 9.99  — triggers __get__
# p.price = -1      # ValueError: price must be positive, got -1
# p.quantity = 0    # ValueError: quantity must be positive, got 0
```

> **What just happened?** `PositiveNumber` is written once. Both `price` and `quantity` share the same validation logic. To add a third validated field, just add `stock = PositiveNumber()`. No copy-pasting.

### How `__set_name__` keeps things separate

Without `__set_name__`, both `price` and `quantity` would try to store their values under the same private name, overwriting each other. `__set_name__` runs at class-definition time and gives each descriptor its own private slot (`_price`, `_quantity`).

```python
class Product:
    price = PositiveNumber()     # __set_name__ called with name="price"
    quantity = PositiveNumber()  # __set_name__ called with name="quantity"
    # Python calls __set_name__ automatically for each assignment
```

---

## When to use property vs descriptor

| Situation | Use |
|---|---|
| One attribute on one class needs validation or computation | `@property` |
| The same validation logic is needed on 3+ attributes or 2+ classes | Descriptor |
| Building a framework, ORM, or data validation library | Descriptor |
| Quick, everyday class where you just want to protect one field | `@property` |

The rule of thumb: start with `@property`. If you catch yourself copy-pasting the same property logic more than twice, reach for a descriptor.

---

## Common mistakes

### 1. Using `self.x` instead of `self._x` in the property body

This is the most common beginner error and causes infinite recursion:

```python
# WRONG — infinite recursion
class Circle:
    @property
    def radius(self):
        return self.radius   # this calls the property again, forever!

    @radius.setter
    def radius(self, value):
        self.radius = value  # same problem

# CORRECT — use underscore for the backing store
class Circle:
    @property
    def radius(self):
        return self._radius  # reads the plain attribute

    @radius.setter
    def radius(self, value):
        self._radius = value  # stores to the plain attribute
```

### 2. Defining a setter before the property

The `@radius.setter` decorator only works after `@property` has been applied and the property object exists. Always define the getter first.

### 3. Forgetting that a property without a setter is read-only

```python
# If you only define @property and not @x.setter:
c = Circle(5)
c.radius = 10   # AttributeError: can't set attribute
```

This is often intentional for computed properties, but surprising if you forgot the setter.

### 4. Storing the value under the same name as the property

```python
# WRONG
@property
def name(self):
    return self.name   # infinite recursion

# CORRECT
@property
def name(self):
    return self._name  # different name with underscore
```

---

## Quick summary

- `@property` lets you use attribute-style syntax while adding validation or computation behind the scenes.
- The backing store uses an underscore: `self._radius` stores the real value; `self.radius` is the controlled doorway.
- `@x.setter` adds write access; `@x.deleter` adds delete access.
- A property with no setter is read-only — great for computed values derived from other fields.
- Descriptors (`__get__`, `__set__`, `__set_name__`) are reusable property logic — use them when the same validation is needed on many attributes or classes.
- The most common mistake is using `self.x` instead of `self._x` inside a property body, which causes infinite recursion.
