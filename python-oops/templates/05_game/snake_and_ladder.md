# 05 — Snake and Ladder

## What is this problem testing?

This problem tests whether you can model an event-driven board game where landing on a cell triggers an automatic position change. The key challenges are: representing snakes and ladders through a shared abstraction rather than separate if-else chains, abstracting randomness so the game is testable, and handling edge cases like overshoot and multiple dice cleanly. Interviewers are watching for the `BoardEntity` abstraction, a `Dice` class rather than a raw `random` call, and a sparse `Dict` for the board rather than a 100-element list.

---

## Requirements

- NxN board (default 10×10, cells numbered 1 to 100)
- 2–6 players, each starting at position 0 (off the board)
- Players take turns rolling one or more dice (default: one six-sided die)
- **Snake:** landing on a snake's head slides the player down to its tail (lower number)
- **Ladder:** landing on a ladder's bottom climbs the player up to its top (higher number)
- First player to reach **exactly** cell 100 wins
- **Overshoot:** if a roll would take a player past 100, they stay in place
- Snakes and ladders are configurable at game setup
- Support multiple dice (e.g., rolling two dice and summing the result)

---

## Clarifying questions to ask in interview

1. **Can two players share a cell?** — Most implementations allow it; clarify whether any collision rule applies (e.g., one player sends the other back to start).
2. **What happens at exactly 100 vs overshoot?** — Does the player need to land on exactly 100, or does reaching ≥ 100 count as a win? (Standard rules: exact landing required; overshoot means stay in place.)
3. **Can a snake send you past position 1, or a ladder send you past 100?** — Typically no; clarify that snakes only go downward and ladders only go upward.
4. **What if a ladder's top or a snake's head has another entity on it?** — Clarify whether chaining is allowed (land on ladder → reach top → land on snake → slide down again).
5. **Should the game support saving and replaying a game?** — This opens the door to discussing the Command pattern for turn history.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| The numbered grid | `Board` |
| A redirect rule at a cell | `BoardEntity` (abstract) |
| A snake (head → tail) | `Snake` |
| A ladder (bottom → top) | `Ladder` |
| A player token | `Player` |
| A die (or dice) | `Dice` |
| Sequence of fixed rolls (for testing) | `MockDice` |
| Who goes next | `TurnManager` |
| Whole game | `Game` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Redirect a player at a special cell | `redirect(position) → int` | `BoardEntity` |
| Add a snake or ladder | `add_entity(entity)` | `Board` |
| Calculate new position after a roll | `move(current_pos, roll) → int` | `Board` |
| Roll the die | `roll() → int` | `Dice` |
| Whose turn is it | `current()` | `TurnManager` |
| Advance to next active player | `next()` | `TurnManager` |
| Update a player's position | `position` (field) | `Player` |
| Mark a player as winner | `has_won` (field) | `Player` |
| Run the game | `play()` | `Game` |
| Execute a single turn | `_take_turn(player)` | `Game` |
| Show the current board state | `display_board()` | `Game` |

---

## Relationships

```
Game  (Facade)
 ├── Board
 │     └── _entities: Dict[int, BoardEntity]
 │              ├── Snake  (head → tail)
 │              └── Ladder (bottom → top)
 ├── List[Player]
 ├── TurnManager
 └── Dice  (rollable, mockable for testing)

BoardEntity  <<abstract>>
 ├── Snake
 └── Ladder
```

> Think of `Game` as the host who runs the evening. The `Board` is the physical game board lying on the table — it knows where every snake and ladder sits. Each `Player` is a token on the board. `Dice` is the cup of dice being passed around. `TurnManager` is the person pointing at who goes next. `Snake` and `Ladder` are the printed rules on the board — when your token lands on them, the board itself tells you where to go.

---

## Design decisions

### 1. Why `BoardEntity` as an abstract class for both Snake and Ladder?

Both Snake and Ladder do the same thing from the game's perspective: when a player lands on a specific cell, they get redirected to a different cell. The interface is identical — `redirect(position) → int`. Without this abstraction you end up writing:

```python
if position in snakes:
    position = snakes[position]
elif position in ladders:
    position = ladders[position]
```

This if-else chain must be edited every time you add a new entity type (e.g., a power-up cell or a warp portal). With `BoardEntity`, you just write:

```python
if position in self._entities:
    position = self._entities[position].redirect(position)
```

Adding a new type is just a new subclass — the board's `move()` method never changes. This is the Open/Closed Principle.

### 2. Why wrap `random.randint` in a `Dice` class?

Calling `random.randint(1, 6)` directly in the game loop makes the game impossible to test automatically — you cannot control what it returns. A `Dice` class lets you inject a `MockDice` in tests that returns a predetermined sequence of rolls. This is the Strategy pattern: `Game` only knows `dice.roll()`, not whether it is real or mocked.

### 3. Why `Dict[int, BoardEntity]` instead of a full list of 100 cells?

A standard board has 100 cells but typically only 15–20 of them have snakes or ladders. Storing all 100 cells in a list wastes memory and makes the code noisier. A dictionary keyed by cell number is sparse — only cells with entities exist in it — and lookup is O(1). Normal cells are simply absent from the dictionary.

### 4. How to handle overshoot?

Check inside `Board.move()` before applying any entity redirect:

```python
new_pos = current_pos + roll
if new_pos > self.size:   # overshoot — stay in place
    return current_pos
```

This keeps the overshoot rule in one place and out of the game loop.

### 5. How would you add a new cell type (e.g., a power-up that doubles your next roll)?

Create a `PowerUp(BoardEntity)` subclass that overrides `redirect`. Add instances to the board via `add_entity`. The rest of the code — `Board.move()`, `Game._take_turn()`, `TurnManager` — changes not at all. This is the Open/Closed Principle in action.

---

## Complete Code

Imports and the abstract base first.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random
```

`BoardEntity` defines the single interface that every special cell must implement.

```python
class BoardEntity(ABC):
    """
    Abstract base for anything that redirects a player on the board.

    Subclasses: Snake (redirects downward), Ladder (redirects upward).
    Any future cell type (warp, power-up) follows the same interface.
    """

    @abstractmethod
    def redirect(self, position: int) -> int:
        """
        Given the position a player just landed on, return where
        they actually end up.
        """
        ...
```

**What just happened?** The entire contract for Snake and Ladder is captured in one four-line method. `Board.move()` will call this without caring whether the entity is a snake or a ladder.

---

`Snake` and `Ladder` — two concrete implementations of `BoardEntity`.

```python
class Snake(BoardEntity):
    """
    A snake occupies one cell (its head) and sends players to a lower cell (its tail).

    Example: head=62, tail=19 — landing on 62 drops you to 19.
    """

    def __init__(self, head: int, tail: int) -> None:
        if tail >= head:
            raise ValueError(f"Snake tail ({tail}) must be below head ({head}).")
        self.head = head
        self.tail = tail

    def redirect(self, position: int) -> int:
        """If the player landed on the head, send them to the tail."""
        return self.tail if position == self.head else position

    def __repr__(self) -> str:
        return f"Snake({self.head} → {self.tail})"


class Ladder(BoardEntity):
    """
    A ladder occupies one cell (its bottom) and sends players to a higher cell (its top).

    Example: bottom=4, top=14 — landing on 4 climbs you to 14.
    """

    def __init__(self, bottom: int, top: int) -> None:
        if top <= bottom:
            raise ValueError(f"Ladder top ({top}) must be above bottom ({bottom}).")
        self.bottom = bottom
        self.top = top

    def redirect(self, position: int) -> int:
        """If the player landed on the bottom, send them to the top."""
        return self.top if position == self.bottom else position

    def __repr__(self) -> str:
        return f"Ladder({self.bottom} → {self.top})"
```

**What just happened?** Both classes validate their data at construction time — you cannot accidentally create a snake that goes upward or a ladder that goes downward. The `redirect` method is identical in shape for both, which is why the abstract base works perfectly here.

---

`Dice` and `MockDice` — randomness abstraction and its test double.

```python
class Dice:
    """
    A standard N-sided die.

    Wrapping random.randint() here means any caller can be tested
    by swapping in a MockDice — the caller never knows the difference.
    """

    def __init__(self, sides: int = 6) -> None:
        self.sides = sides

    def roll(self) -> int:
        """Return a random integer between 1 and sides (inclusive)."""
        return random.randint(1, self.sides)


class MockDice(Dice):
    """
    A dice that returns a predetermined sequence of values.

    Used in unit tests to remove randomness from the game.

    Example:
        dice = MockDice([4, 3, 6, 1])
        dice.roll()  # → 4
        dice.roll()  # → 3
    """

    def __init__(self, values: List[int]) -> None:
        super().__init__()
        self._values = list(values)
        self._index = 0

    def roll(self) -> int:
        if self._index >= len(self._values):
            raise IndexError("MockDice ran out of values.")
        value = self._values[self._index]
        self._index += 1
        return value
```

---

`Player` — a simple data container for each player's state.

```python
@dataclass
class Player:
    """
    Represents one player's token on the board.

    position=0 means the player has not yet entered the board.
    has_won is set to True the moment they reach the final cell.
    """
    player_id: int
    name: str
    position: int = 0
    has_won: bool = False

    def __str__(self) -> str:
        return f"{self.name} (pos={self.position})"
```

---

`Board` — the game board that knows where every snake and ladder sits.

```python
class Board:
    """
    An NxN grid numbered 1 to size.

    Only cells that contain a snake or ladder are stored — all other
    cells are treated as normal (no redirect). This sparse Dict[int, BoardEntity]
    is O(1) to look up and far simpler than a full list of 100 cells.
    """

    def __init__(self, size: int = 100) -> None:
        self.size = size
        self._entities: Dict[int, BoardEntity] = {}

    def add_entity(self, position: int, entity: BoardEntity) -> None:
        """Register a snake or ladder at the given board position."""
        if not (1 <= position <= self.size):
            raise ValueError(f"Position {position} is outside the board (1–{self.size}).")
        self._entities[position] = entity

    def move(self, current_pos: int, roll: int) -> int:
        """
        Calculate a player's new position after rolling `roll`.

        Rules applied in order:
        1. Overshoot — if new_pos > size, return current_pos unchanged.
        2. Entity redirect — if new_pos has a snake or ladder, apply it.
        3. Normal move — return new_pos.
        """
        new_pos = current_pos + roll

        # Rule 1: overshoot — stay in place
        if new_pos > self.size:
            return current_pos

        # Rule 2: snake or ladder redirect
        if new_pos in self._entities:
            redirected = self._entities[new_pos].redirect(new_pos)
            return redirected

        # Rule 3: normal move
        return new_pos
```

**What just happened?** All three rules — overshoot, redirect, normal move — live inside `Board.move()`. The game loop never needs to know about them. This is the Single Responsibility Principle: the board owns movement rules; the game loop just asks "where does this roll take me?"

---

`TurnManager` — cycles through active players, skipping winners.

```python
class TurnManager:
    """
    Passes the turn to the next player who has not yet won.

    When all remaining players win (edge case: simultaneous win is impossible
    here, but the skip logic handles any future variant), the game ends.
    """

    def __init__(self, players: List[Player]) -> None:
        if not players:
            raise ValueError("Need at least one player.")
        self._players = players
        self._index = 0

    def current(self) -> Player:
        """Return the player whose turn it is right now."""
        return self._players[self._index]

    def next(self) -> None:
        """Advance to the next player who has not won, wrapping around."""
        n = len(self._players)
        for _ in range(n):
            self._index = (self._index + 1) % n
            if not self._players[self._index].has_won:
                return
```

---

`Game` — the Facade that ties everything together.

```python
class Game:
    """
    The single entry point for a Snake and Ladder game.

    Callers create a Game and call play(). All internal collaborators
    (Board, TurnManager, Dice, Players) are hidden. This is the Facade pattern.
    """

    def __init__(
        self,
        players: List[Player],
        board: Board,
        dice: Dice,
        num_dice: int = 1,
    ) -> None:
        if not (2 <= len(players) <= 6):
            raise ValueError("Snake and Ladder requires 2–6 players.")
        self.players = players
        self.board = board
        self.dice = dice
        self.num_dice = num_dice
        self.turn_manager = TurnManager(players)
        self._winner: Optional[Player] = None

    def _roll_all_dice(self) -> int:
        """Roll `num_dice` dice and return the sum."""
        return sum(self.dice.roll() for _ in range(self.num_dice))

    def _take_turn(self, player: Player) -> None:
        """
        Execute a single turn for one player:
        1. Roll the dice.
        2. Ask the board where the roll takes the player.
        3. Update the player's position.
        4. Check for a win.
        """
        roll = self._roll_all_dice()
        old_pos = player.position
        new_pos = self.board.move(old_pos, roll)
        player.position = new_pos

        # Build a human-readable description of what happened
        if new_pos == old_pos and old_pos + roll > self.board.size:
            detail = f"rolled {roll} — overshoot! Stays at {old_pos}."
        elif new_pos != old_pos + roll:
            entity = self.board._entities.get(old_pos + roll)
            if isinstance(entity, Snake):
                detail = f"rolled {roll} → landed on snake head {old_pos + roll} → slid to {new_pos}!"
            else:
                detail = f"rolled {roll} → landed on ladder at {old_pos + roll} → climbed to {new_pos}!"
        else:
            detail = f"rolled {roll} → moved to {new_pos}."

        print(f"  {player.name}: {detail}")

        if player.position == self.board.size:
            player.has_won = True
            self._winner = player

    def display_board(self) -> None:
        """Print all players' current positions."""
        print("\n  --- Board State ---")
        for p in self.players:
            status = "WON" if p.has_won else f"cell {p.position}"
            print(f"    {p.name}: {status}")
        print()

    def play(self) -> None:
        """Run the full game loop until one player reaches cell 100."""
        print("=== Snake and Ladder started! ===\n")
        self.display_board()

        while self._winner is None:
            player = self.turn_manager.current()
            print(f"{player.name}'s turn:")
            self._take_turn(player)

            if self._winner:
                self.display_board()
                print(f"*** {self._winner.name} wins! ***")
                return

            self.turn_manager.next()

        self.display_board()
```

**What just happened?** The game loop is short and readable because every rule is delegated: `board.move()` handles overshoot and redirects, `turn_manager.next()` handles player cycling, and `_take_turn()` handles one player's full turn. `Game.play()` just orchestrates.

---

Standard board setup with classic snake and ladder positions.

```python
def create_standard_board() -> Board:
    """
    Build a classic 100-cell Snake and Ladder board.

    Snake positions (head → tail):
        62 → 19,  47 → 5,  56 → 15,  99 → 40,  92 → 73,  87 → 24,  64 → 60

    Ladder positions (bottom → top):
        4 → 14,   9 → 31,  20 → 38,  28 → 84,  40 → 59,  51 → 67,  63 → 81,  71 → 91
    """
    board = Board(size=100)

    # Snakes
    for head, tail in [(62, 19), (47, 5), (56, 15), (99, 40), (92, 73), (87, 24), (64, 60)]:
        board.add_entity(head, Snake(head=head, tail=tail))

    # Ladders
    for bottom, top in [(4, 14), (9, 31), (20, 38), (28, 84), (40, 59), (51, 67), (63, 81), (71, 91)]:
        board.add_entity(bottom, Ladder(bottom=bottom, top=top))

    return board
```

---

Full playable usage example with 3 players.

```python
if __name__ == "__main__":
    players = [
        Player(player_id=1, name="Alice"),
        Player(player_id=2, name="Bob"),
        Player(player_id=3, name="Charlie"),
    ]

    board = create_standard_board()
    dice = Dice(sides=6)

    game = Game(players=players, board=board, dice=dice, num_dice=1)
    game.play()

    # ── Bonus: two-dice variant ──────────────────────────────────────────
    print("\n=== Two-dice variant ===")
    players2 = [
        Player(player_id=1, name="Alice"),
        Player(player_id=2, name="Bob"),
    ]
    game2 = Game(players=players2, board=create_standard_board(), dice=Dice(), num_dice=2)
    game2.play()

    # ── Bonus: deterministic test run with MockDice ──────────────────────
    print("\n=== MockDice test run (first 3 turns) ===")
    players3 = [
        Player(player_id=1, name="Alice"),
        Player(player_id=2, name="Bob"),
    ]
    # Sequence: Alice rolls 4 (ladder at 4→14), Bob rolls 3, Alice rolls 5 (snake check)
    mock = MockDice([4, 3, 5])
    game3 = Game(players=players3, board=create_standard_board(), dice=mock)
    # We'll manually drive 3 turns instead of play() to avoid exhausting MockDice
    game3._take_turn(players3[0])   # Alice rolls 4 → ladder → cell 14
    game3._take_turn(players3[1])   # Bob   rolls 3 → cell 3
    game3._take_turn(players3[0])   # Alice rolls 5 → cell 19 (no entity)
    game3.display_board()
```

---

## Step-by-step walkthrough

We trace 3 turns using the standard board and `MockDice([4, 3, 5])`. Both players start at position 0.

**Turn 1 — Alice rolls 4**

```
old_pos = 0
roll    = 4
new_pos = 0 + 4 = 4

Board check: cell 4 is a Ladder(bottom=4, top=14).
Ladder.redirect(4) → 14

Alice.position = 14
```

Alice climbed a ladder and jumped from cell 4 all the way to cell 14.

```
Alice: cell 14
Bob:   cell 0
```

**Turn 2 — Bob rolls 3**

```
old_pos = 0
roll    = 3
new_pos = 0 + 3 = 3

Board check: cell 3 has no entity.
Bob.position = 3
```

A normal move. Bob advances to cell 3.

```
Alice: cell 14
Bob:   cell 3
```

**Turn 3 — Alice rolls 5**

```
old_pos = 14
roll    = 5
new_pos = 14 + 5 = 19

Board check: cell 19 has no entity.
Alice.position = 19
```

Another normal move. Alice advances to cell 19.

```
Alice: cell 19
Bob:   cell 3
```

> Now imagine a later turn where Alice reaches cell 62. `Snake(head=62, tail=19)` would call `redirect(62) → 19` and she would slide all the way back to 19 — losing 43 cells of progress in one unlucky roll.

---

## Common interview mistakes

1. **Hardcoding snakes and ladders inside `Board.__init__`.**
   The board should accept entities through `add_entity` so callers can create different board configurations for different difficulties or game variants. Hardcoding them in the constructor makes the class impossible to reuse.

2. **Calling `random.randint` directly in the game loop.**
   This makes the game untestable — you cannot force a specific roll sequence to verify that snakes and ladders trigger correctly. Wrapping randomness in a `Dice` class and injecting `MockDice` in tests is the fix.

3. **No overshoot handling.**
   Without the `if new_pos > self.size: return current_pos` guard in `Board.move()`, a player can end up at position 103 and the win condition `position == 100` is never triggered. The game runs forever.

4. **Checking the win condition before applying the snake or ladder redirect.**
   The correct order is: apply roll → apply redirect → check win. If you check win immediately after the roll and before the redirect, a player who rolls onto cell 100 via a snake's head (if one were placed there) would be declared the winner instead of being sent back. Apply everything, then check.

5. **`TurnManager` tightly coupled to `Game`.**
   Embedding turn logic inside `Game` (e.g., `self._current_player_index += 1`) makes it impossible to unit-test turn cycling independently, and it forces `Game` to know about player count. A standalone `TurnManager` class keeps both classes focused and independently testable.

---

## Key patterns used

| Pattern | Where it appears | Why it helps |
|---|---|---|
| **Template Method** | `Game.play()` game loop | The loop structure is fixed; individual steps delegate to `Board`, `Dice`, `TurnManager` |
| **Strategy** | `Dice` / `MockDice` | Swap real randomness for deterministic values in tests without changing `Game` |
| **Open/Closed** | `BoardEntity` / `Snake` / `Ladder` | Add new cell types (power-ups, portals) as new subclasses — `Board.move()` never changes |
| **Facade** | `Game` class | One entry point hides `Board`, `TurnManager`, `Dice`, and `Player` from the caller |
| **Command** | Turn history (extension point) | Each turn's roll and position change can be stored as an immutable record for replay/undo |


---

[← Back to Game Template](template.md)
