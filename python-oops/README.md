# Python OOP for LLD Interviews

Low-Level Design (LLD) interviews test your ability to translate a real-world problem into clean, maintainable classes and relationships. Interviewers want to see that you know *when* to use inheritance vs composition, how to keep classes focused, and how to write code that is easy to extend without breaking what already works.

This guide takes you from zero OOP knowledge all the way to solving 18 full LLD problems across 6 design templates — the exact problems that show up at companies like Google, Amazon, Flipkart, and Uber.

---

## Learning Path

Work through these files in order. Each one builds on the last.

| # | File | Topic | What you will learn |
|---|------|--------|---------------------|
| 01 | [01_classes_and_objects.md](01_classes_and_objects.md) | Classes and Objects | Blueprints, instances, `__init__`, class vs instance variables, `__repr__` vs `__str__`, name mangling |
| 02 | [02_four_pillars.md](02_four_pillars.md) | Four Pillars of OOP | Encapsulation, Inheritance, Polymorphism, Abstraction — with analogies and code |
| 03 | [03_magic_methods.md](03_magic_methods.md) | Magic / Dunder Methods | Make your objects behave like built-in types: comparisons, containers, context managers, arithmetic |
| 04 | [04_properties.md](04_properties.md) | Properties and Descriptors | `@property`, getters/setters, computed attributes, descriptor protocol |
| 05 | [05_class_static_instance.md](05_class_static_instance.md) | Class vs Static vs Instance | When to use each method type, alternative constructors with `@classmethod` |
| 06 | [06_inheritance.md](06_inheritance.md) | Inheritance Deep Dive | MRO, C3 linearization, `super()`, mixins, cooperative multiple inheritance |
| 07 | [07_abstract_classes.md](07_abstract_classes.md) | Abstract Classes and Interfaces | `ABC`, `@abstractmethod`, abstract properties, enforcing contracts |
| 08 | [08_protocols.md](08_protocols.md) | Protocols (Structural Subtyping) | Duck typing made explicit, `Protocol` vs `ABC`, `runtime_checkable` |
| 09 | [09_composition.md](09_composition.md) | Composition over Inheritance | Why deep hierarchies break, how to use HAS-A instead of IS-A |
| 10 | [10_solid_principles.md](10_solid_principles.md) | SOLID Principles | SRP, OCP, LSP, ISP, DIP — with before/after examples |
| 11 | [11_design_patterns.md](11_design_patterns.md) | Design Patterns | Singleton, Factory, Builder, Decorator, Adapter, Observer, Strategy, Command |
| 12 | [12_dataclasses.md](12_dataclasses.md) | Dataclasses | Reduce boilerplate, `frozen=True`, `field()`, `__post_init__`, `asdict()` |
| 13 | [13_lld_patterns.md](13_lld_patterns.md) | LLD Interview Patterns | Modeling checklist, enums for state machines, DI containers, template method |


---

## LLD Problem Templates

Most LLD interview problems fall into one of 6 templates. Learn the template first, then the problems become much easier. Each folder contains a `template.md` (skeleton + explanation) and worked problems that use it.

| Template | Problems (click to open) | Key patterns |
|---|---|---|
| [Booking System](templates/01_booking_system/template.md) | [Parking Lot](templates/01_booking_system/parking_lot.md) · [Library](templates/01_booking_system/library_management.md) · [BookMyShow](templates/01_booking_system/bookmyshow.md) · [Hotel](templates/01_booking_system/hotel_management.md) · [Flight](templates/01_booking_system/flight_booking.md) | Strategy, State, Facade |
| [State Machine](templates/02_state_machine/template.md) | [Elevator](templates/02_state_machine/elevator_system.md) · [ATM](templates/02_state_machine/atm.md) · [Vending Machine](templates/02_state_machine/vending_machine.md) | State, Enum + transition dict |
| [Marketplace / Matching](templates/03_marketplace_matching/template.md) | [Uber](templates/03_marketplace_matching/uber.md) · [Splitwise](templates/03_marketplace_matching/splitwise.md) | Strategy, Observer, Facade |
| [Social / Feed](templates/04_social_feed/template.md) | [Twitter](templates/04_social_feed/twitter.md) · [Stack Overflow](templates/04_social_feed/stack_overflow.md) | Observer, Strategy, Facade |
| [Game](templates/05_game/template.md) | [Tic-Tac-Toe](templates/05_game/tic_tac_toe.md) · [Chess](templates/05_game/chess.md) · [Snake & Ladder](templates/05_game/snake_and_ladder.md) | Command, Strategy, Template Method |
| [Resource Management](templates/06_resource_management/template.md) | [LRU Cache](templates/06_resource_management/lru_cache.md) · [Rate Limiter](templates/06_resource_management/rate_limiter.md) · [Logging System](templates/06_resource_management/logging_system.md) | Singleton, Strategy, Chain of Responsibility |

> **Tip:** Before reading any problem solution, read the template first. You will recognise the skeleton immediately and spend your energy on the domain logic, not the structure.

---

## How to Use This Guide

1. **Read linearly first.** Files 01–13 are the foundation. Do not skip them even if you think you know OOP — the "Why" explanations and common-mistake sections are worth it.
2. **Type the code yourself.** Reading is passive. Open a Python file, type the examples, and run them. Break things on purpose.
3. **Before each LLD problem**, read the template for that problem category first, then apply the 5-step framework below before looking at the solution.
4. **Use `13_lld_patterns.md`** as a compact cheatsheet once you have worked through the numbered files — it has the full quick-reference at the bottom.

---

## 5-Step LLD Interview Framework

Use this every time you are given a design problem. Interviewers reward structured thinking far more than code volume.

**Step 1 — Clarify requirements**
Ask about scale, edge cases, and actors before writing a single line. "How many floors does the parking lot have?" is a great question. "Should I start coding?" is not.

**Step 2 — Identify entities**
Read the problem statement and underline every noun. Each noun is a candidate class. "Parking Lot has Floors, each Floor has Spots, each Spot can hold a Vehicle" gives you four classes immediately.

**Step 3 — Define relationships**
For each pair of classes ask: is this an IS-A relationship (inheritance) or a HAS-A relationship (composition)? A `Car` IS-A `Vehicle`. A `ParkingLot` HAS-MANY `ParkingFloor`s. Prefer composition when in doubt.

**Step 4 — Define interfaces first**
Before writing `__init__`, write the method signatures. What can a `ParkingSpot` *do*? It can `park()`, `vacate()`, check `is_available`. Defining capabilities before implementation keeps you from painting yourself into a corner.

**Step 5 — Write code bottom-up**
Start with leaf classes (the ones with no dependencies), then build aggregators on top of them, and finally write the facade (the single class the outside world talks to). This means you can test each layer independently.

> Think of it like building with Lego: you snap the small pieces together first, then the big frame goes on last.
