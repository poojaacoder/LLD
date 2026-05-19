# 02 — Library Management System

## What is this problem testing?

This problem tests whether you understand that a single conceptual item (a book) can have two distinct levels of abstraction: the catalog entry (title, author, ISBN — shared data) and the physical copy (barcode, current status — per-instance data). It also evaluates your ability to model a join entity (`Lending`) that carries its own business rules (due dates, fines), and whether you correctly encapsulate borrowing policy inside the `Member` class rather than scattering it across the facade.

---

## Requirements

- Books have one or more physical copies (`BookItem`); one ISBN, many barcodes
- Members can borrow up to 5 books at a time
- A member with any overdue book is blocked from borrowing more
- Loan period is 14 days; a fine of ₹1/day accrues after that
- Search the catalog by title, author, or ISBN
- Librarians can add and remove physical copies from the catalog

---

## Clarifying questions to ask in interview

1. **Can a member reserve a book that is currently on loan?** — Determines whether you need a reservation queue on `BookItem`.
2. **What happens if a member loses a book?** — Do you need a `LOST` status and a replacement fee beyond the daily fine?
3. **Is the fine calculated on calendar days or business days?** — Simplest assumption is calendar days; confirm before coding.
4. **Can a librarian renew a loan?** — Extends the due date; adds a `renew()` method to `Lending`.
5. **Do members have different tiers?** — A premium member might borrow 10 books. This affects where `MAX_BOOKS` lives.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Library | `Library` |
| Book (catalog entry) | `Book` |
| Physical copy | `BookItem` |
| Member | `Member` |
| Loan/transaction | `Lending` |
| Catalog (collection of books) | `Catalog` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Add a physical copy | `add_item(item)` | `Book` |
| Remove a physical copy | `remove_item(barcode)` | `Book` |
| Find available copies | `available_items()` | `Book` |
| Search by title/author/ISBN | `search_by_*()` | `Catalog` |
| Check if member can borrow | `can_borrow() -> bool` | `Member` |
| Borrow a book | `checkout(member_id, isbn)` | `Library` |
| Return a book | `return_book(lending_id)` | `Library` |
| Calculate fine | `fine` (property) | `Lending` |

---

## Relationships

```
Library ──────── HAS-ONE  ────► Catalog
Library ──────── HAS-MANY ────► Member

Catalog ─────────HAS-MANY ────► Book
Book ─────────── HAS-MANY ────► BookItem   (1 ISBN, N physical copies)

Member ──────────HAS-MANY ────► Lending    (active loans)
Lending ─────────HAS-ONE  ────► BookItem
Lending ─────────HAS-ONE  ────► Member

Library ─────────HAS-MANY ────► Lending    (all loans, keyed by ID)
```

> Think of it like a public library you visit. `Book` is the card in the card-catalogue — it has the title, author, and ISBN. `BookItem` is the actual physical book on the shelf with a barcode sticker on the spine. One entry in the catalogue can correspond to 10 copies on 10 different shelves. `Lending` is the slip the librarian stamps when you take the book home.

---

## Design decisions

### 1. `Book` vs `BookItem` — the critical split

**Decision:** `Book` stores shared metadata (ISBN, title, author). `BookItem` stores per-copy state (barcode, `AVAILABLE`/`LOANED`/`LOST` status).

**Why:** If you merge them, every copy of "Clean Code" would need its own title and author fields. More importantly, when a copy is loaned, you need to mark *that specific copy* as unavailable while the other copies remain available.

**Alternative considered:** A single `Book` class with a `copies_available` counter. Rejected because it loses track of *which specific copy* a member has, making returns ambiguous.

### 2. `Lending` as a join entity that owns transaction logic

**Decision:** `Lending` is a full class, not a tuple or dict. It owns `checkout_date`, `due_date`, `return_date`, and the `fine` property.

**Why:** The borrowing transaction has its own lifecycle and its own data. Keeping fine calculation inside `Lending` means `Library.return_book()` does not need to know the formula — it just calls `lending.fine`.

### 3. `Member.can_borrow()` encapsulates all policy

**Decision:** All borrowing rules (active status, book limit, overdue check) live in one method on `Member`.

**Why:** If the library changes policy — say, students can borrow 10 books — you change one method in one place. `Library.checkout()` does not need to be touched.

### 4. `Library` as the Facade

**Decision:** External code calls `lib.checkout()` and `lib.return_book()`. It never directly sets `book_item.status`.

**Why:** If a `BookItem.status` change needs to trigger notifications (email to waiting members) in the future, the facade is the right place to add that. Callers do not break.

---

## Complete Code

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional
import uuid


# ── Enums ──────────────────────────────────────────────────────────────────────
# Use enums instead of strings like "available" — typos become NameErrors, not bugs.

class BookStatus(Enum):
    AVAILABLE  = auto()   # on the shelf, ready to borrow
    LOANED     = auto()   # currently borrowed by a member
    RESERVED   = auto()   # held for a specific member
    LOST       = auto()   # reported lost; cannot be borrowed

class MemberStatus(Enum):
    ACTIVE    = auto()
    SUSPENDED = auto()    # e.g., unpaid fines or policy violations


# ── Book & BookItem ────────────────────────────────────────────────────────────
# Book = the catalog entry (one per ISBN)
# BookItem = one physical copy of that book (many per ISBN)

class Book:
    def __init__(self, isbn: str, title: str, author: str, subject: str):
        self.isbn = isbn
        self.title = title
        self.author = author
        self.subject = subject
        self._items: List["BookItem"] = []   # all physical copies of this book

    def add_item(self, item: "BookItem") -> None:
        # A librarian calls this when a new copy arrives at the library
        self._items.append(item)

    def remove_item(self, barcode: str) -> None:
        # Remove a specific copy by barcode (e.g., damaged or lost)
        self._items = [i for i in self._items if i.barcode != barcode]

    def available_items(self) -> List["BookItem"]:
        # Return only the copies that are currently on the shelf
        return [i for i in self._items if i.status == BookStatus.AVAILABLE]

    def __repr__(self) -> str:
        return f"Book({self.isbn!r}, {self.title!r}, copies={len(self._items)})"


class BookItem:
    def __init__(self, barcode: str, book: Book):
        self.barcode = barcode
        self.book = book                        # back-reference to the catalog entry
        self.status = BookStatus.AVAILABLE      # new copies start on the shelf

    def __repr__(self) -> str:
        return f"BookItem({self.barcode!r}, {self.status.name})"


# ── Lending (the transaction / join entity) ────────────────────────────────────
# A Lending record is created when a book is checked out.
# It carries all the data for one borrowing event and computes its own fine.

class Lending:
    LOAN_DAYS = 14       # default loan period
    FINE_PER_DAY = 1.0   # ₹1 per day overdue

    def __init__(self, book_item: BookItem, member: "Member"):
        self.lending_id: str = uuid.uuid4().hex[:8]   # short unique ID
        self.book_item = book_item
        self.member = member
        self.checkout_date: datetime = datetime.now()
        # Due date is calculated once at creation and never changes
        self.due_date: datetime = self.checkout_date + timedelta(days=self.LOAN_DAYS)
        self.return_date: Optional[datetime] = None    # set when the book comes back

    @property
    def is_returned(self) -> bool:
        return self.return_date is not None

    @property
    def is_overdue(self) -> bool:
        # If not returned yet, compare against current time
        end = self.return_date or datetime.now()
        return end > self.due_date

    @property
    def fine(self) -> float:
        # Fine only accrues for overdue books
        if not self.is_overdue:
            return 0.0
        end = self.return_date or datetime.now()
        # timedelta.days gives the integer day count (not fractional hours)
        days = (end - self.due_date).days
        return days * self.FINE_PER_DAY

    def __repr__(self) -> str:
        return f"Lending({self.lending_id!r}, {self.book_item.barcode!r})"


# ── Member ─────────────────────────────────────────────────────────────────────
# Member manages its own borrowing state.
# All policy rules live in can_borrow() — one place to update when policy changes.

class Member:
    MAX_BOOKS = 5   # class constant — max active loans per member

    def __init__(self, member_id: str, name: str):
        self.member_id = member_id
        self.name = name
        self.status = MemberStatus.ACTIVE
        self._active: List[Lending] = []    # currently borrowed books
        self._history: List[Lending] = []   # returned books (audit trail)

    def can_borrow(self) -> bool:
        # Rule 1: member must be in good standing
        if self.status != MemberStatus.ACTIVE:
            return False
        # Rule 2: cannot hold more than MAX_BOOKS at once
        if len(self._active) >= self.MAX_BOOKS:
            return False
        # Rule 3: no borrowing if any current book is overdue
        if any(l.is_overdue for l in self._active):
            return False
        return True

    def _add_lending(self, lending: Lending) -> None:
        # Called by Library — moves lending into this member's active list
        self._active.append(lending)

    def _close_lending(self, lending: Lending) -> float:
        # Called by Library on return — moves to history, returns the fine owed
        self._active.remove(lending)
        self._history.append(lending)
        return lending.fine

    def __repr__(self) -> str:
        return f"Member({self.member_id!r}, {self.name!r}, books={len(self._active)})"


# ── Catalog ────────────────────────────────────────────────────────────────────
# Catalog is a searchable collection of Book records.
# It is separate from Library so it can be tested independently.

class Catalog:
    def __init__(self):
        self._books: Dict[str, Book] = {}   # isbn → Book

    def add_book(self, book: Book) -> None:
        self._books[book.isbn] = book

    def search_by_title(self, title: str) -> List[Book]:
        # Case-insensitive substring match
        q = title.lower()
        return [b for b in self._books.values() if q in b.title.lower()]

    def search_by_author(self, author: str) -> List[Book]:
        q = author.lower()
        return [b for b in self._books.values() if q in b.author.lower()]

    def search_by_isbn(self, isbn: str) -> Optional[Book]:
        # Exact match — ISBN is the primary key
        return self._books.get(isbn)


# ── Library (facade) ───────────────────────────────────────────────────────────
# Library is the single entry point.
# It orchestrates: validate member → find copy → create lending record → update status.
# External code never touches BookItem.status directly.

class Library:
    def __init__(self, name: str):
        self.name = name
        self.catalog = Catalog()                         # publicly accessible for search
        self._members: Dict[str, Member] = {}
        self._lendings: Dict[str, Lending] = {}          # all lendings by ID

    def register_member(self, member: Member) -> None:
        self._members[member.member_id] = member

    def checkout(self, member_id: str, isbn: str) -> Lending:
        # Step 1: validate the member exists and can borrow
        member = self._members.get(member_id)
        if not member:
            raise ValueError("Member not found")
        if not member.can_borrow():
            raise ValueError("Member cannot borrow: overdue books or limit reached")

        # Step 2: find the book and an available copy
        book = self.catalog.search_by_isbn(isbn)
        if not book:
            raise ValueError(f"Book {isbn!r} not in catalog")

        available = book.available_items()
        if not available:
            raise ValueError("No copies currently available")

        # Step 3: claim the first available copy
        item = available[0]
        item.status = BookStatus.LOANED   # mark it as taken

        # Step 4: create and register the lending record
        lending = Lending(item, member)
        member._add_lending(lending)
        self._lendings[lending.lending_id] = lending

        print(f"[CHECKOUT] {member.name} borrowed '{book.title}' → due {lending.due_date.date()}")
        return lending

    def return_book(self, lending_id: str) -> float:
        lending = self._lendings.get(lending_id)
        if not lending:
            raise ValueError("Lending record not found")

        # Step 1: stamp the return date (Lending.fine uses this)
        lending.return_date = datetime.now()

        # Step 2: free the physical copy
        lending.book_item.status = BookStatus.AVAILABLE

        # Step 3: remove from member's active loans; collect fine
        fine = lending.member._close_lending(lending)
        msg = f"Fine: ₹{fine:.1f}" if fine else "No fine"
        print(f"[RETURN]  '{lending.book_item.book.title}' returned by {lending.member.name}. {msg}")
        return fine


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    lib = Library("City Library")

    # Add a book with two physical copies
    book = Book("978-0-13-468599-1", "Clean Code", "Robert Martin", "Programming")
    book.add_item(BookItem("BC001", book))
    book.add_item(BookItem("BC002", book))
    lib.catalog.add_book(book)

    # Register a member
    alice = Member("M001", "Alice")
    lib.register_member(alice)

    # Borrow and return
    lending = lib.checkout("M001", "978-0-13-468599-1")
    lib.return_book(lending.lending_id)
```

---

## Step-by-step walkthrough

```python
lib = Library("City Library")
```
Creates the library with an empty `Catalog` and empty member/lending dictionaries.

```python
book = Book("978-0-13-468599-1", "Clean Code", "Robert Martin", "Programming")
book.add_item(BookItem("BC001", book))
book.add_item(BookItem("BC002", book))
lib.catalog.add_book(book)
```
- One `Book` catalog entry is created for ISBN `978-...`.
- Two `BookItem` objects (physical copies with barcodes `BC001`, `BC002`) are attached to it. Both start as `AVAILABLE`.
- The book is registered in the catalog under its ISBN.

**What just happened?** The catalog now has one book with two borrowable copies. If you called `book.available_items()` you would get both items back.

```python
alice = Member("M001", "Alice")
lib.register_member(alice)
```
Alice is created with `status = ACTIVE`, zero active loans, zero history. She is stored in the library's member dict.

```python
lending = lib.checkout("M001", "978-0-13-468599-1")
```
- Library looks up Alice — she exists and `can_borrow()` returns `True` (active, 0 loans, no overdue).
- Library looks up the book by ISBN — found.
- `book.available_items()` returns `[BC001, BC002]`. The first one (`BC001`) is selected.
- `BC001.status` is set to `LOANED`.
- A `Lending` object is created with a `due_date` 14 days from now.
- The lending is added to Alice's `_active` list and to the library's `_lendings` dict.
- The ticket is returned to the caller.

**What just happened?** Alice now holds one active loan. `BC001` is marked `LOANED` so no one else can borrow it. `BC002` is still available.

```python
lib.return_book(lending.lending_id)
```
- Library looks up the lending by ID.
- `lending.return_date` is stamped with the current time.
- `BC001.status` is set back to `AVAILABLE`.
- `lending.member._close_lending(lending)` moves it from Alice's `_active` to `_history` and returns the fine (₹0 if returned on time).
- The fine amount is printed and returned.

---

## Common interview mistakes

1. **Merging `Book` and `BookItem`** — This is the most common mistake. If you have a single `Book` class, you cannot track which specific copy Alice has (needed when she returns it), and you cannot have some copies loaned while others are available.

2. **Putting fine calculation in `Library.return_book()`** — Writing `days_overdue * 1.0` directly in the facade. This means `Lending` is just a data bag with no behavior. The fine formula belongs to `Lending` — it owns the transaction data.

3. **Checking borrowing rules in `Library.checkout()` instead of `Member`** — Writing `if len(member._active) >= 5` inside the library. If policy changes (students get 10 books), you have to find and update the facade instead of just changing `Member.MAX_BOOKS`.

4. **Using a counter instead of `uuid`** — Using `self._counter += 1` for lending IDs is fine in a single process, but `uuid` is better practice for distributed systems. Mention this trade-off.

5. **Not handling the "no available copies" case** — Silently returning `None` or crashing with an `IndexError` when `available_items()` is empty. Always raise a meaningful `ValueError`.

---

## Key patterns used

- **Facade** — `Library` is the single public API; catalog and member internals are hidden
- **Single Responsibility** — `Book` (metadata), `BookItem` (physical state), `Lending` (transaction), `Member` (borrowing policy), `Catalog` (search) — each has exactly one job
- **Encapsulation** — `Member.can_borrow()` hides all borrowing rules; `Lending.fine` hides the fee formula
- **Enumeration** — `BookStatus`, `MemberStatus` make invalid states visible at a glance
- **Composition** — `Library` composes `Catalog` and `Member` lists rather than inheriting from them
- **Domain modeling** — `Lending` is a *join entity* with its own lifecycle, not just a foreign-key pair
