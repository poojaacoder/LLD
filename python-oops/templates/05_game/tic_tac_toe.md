# 05 — Tic-Tac-Toe

## What is this problem testing?

This problem tests whether you can apply the Game template to its simplest possible form. Interviewers are watching for how cleanly you separate the board (state storage) from the win checker (state evaluation), whether you abstract `Player` so a human and an AI are interchangeable, and whether you know the Command pattern for undo. Getting these three right demonstrates that you understand the template — not just the rules of Tic-Tac-Toe.

---

## Requirements

- 3×3 board — but design for any N×N size
- Two players: X and O — each can be human or AI
- Validate moves: reject occupied cells and out-of-bounds positions
- Detect win: three in a row, column, or diagonal
- Detect draw: board is full with no winner
- Support undo of the last move
- Display the board after every valid move

---

## Clarifying questions to ask in interview

1. **Fixed board size or configurable?** — Should the board always be 3×3, or should we design for N×N from the start? (Answer: design for N×N — it forces a better abstraction.)
2. **Human vs human, human vs AI, or AI vs AI?** — Do we need to support all three combinations, or just one?
3. **What constitutes an AI player?** — A random mover is enough to demonstrate the pattern; do we need Minimax?
4. **Should undo go back one full round (both players' last move) or just one half-move?** — Clarifies how `TurnManager` interacts with undo.
5. **Is concurrency a concern?** — Could two requests try to play simultaneously, or is this a single-threaded turn loop?

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Board / grid | `Board` |
| Cell symbol (X, O, empty) | `Symbol` enum |
| A player's intended action | `Move` |
| Player (human or AI) | `Player`, `HumanPlayer`, `AIPlayer` |
| Who goes next | `TurnManager` |
| Win / draw evaluation | `WinChecker`, `TicTacToeWinChecker` |
| Recorded list of moves | `MoveHistory` |
| Whole game | `Game` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Place a symbol | `apply(move)` | `Board` |
| Remove last symbol | `undo(move)` | `Board` |
| Check cell is free & in-bounds | `is_valid(move)` | `Board` |
| Check board is full | `is_full()` | `Board` |
| Print the grid | `display()` | `Board` |
| Ask for the next move | `get_move(board)` | `Player` |
| Whose turn is it | `current_player()` | `TurnManager` |
| Advance to next player | `next_turn()` | `TurnManager` |
| Check win after a move | `check(board, player)` | `WinChecker` |
| Record a move | `record(move)` | `MoveHistory` |
| Undo the last move | `undo_last(board)` | `MoveHistory` |
| Run the game | `play()` | `Game` |

---

## Relationships

```
Game  (Facade)
 ├── Board
 ├── TurnManager ──manages──► List[Player]
 ├── WinChecker  <<abstract>>
 └── MoveHistory

Player  <<abstract>>
 ├── HumanPlayer  (reads input)
 └── AIPlayer     (picks random empty cell)

WinChecker  <<abstract>>
 └── TicTacToeWinChecker
```

> Think of `Game` as the referee sitting above the table. The `Board` is the physical grid on the table. Each `Player` decides where to mark. `WinChecker` is the rulebook the referee consults after each mark. `MoveHistory` is the notepad the referee uses to undo a disputed move.

---

## Design decisions

### 1. Why is `WinChecker` separate from `Board`?

`Board` is responsible for *storing* which symbols sit in which cells. `WinChecker` is responsible for *interpreting* whether that arrangement means someone has won. If you merge them, then when a teammate asks "can we make it 5-in-a-row instead of 3?" you have to edit the core state class — risky. With a separate `WinChecker` you just swap in a new subclass.

### 2. How does N×N support work?

Pass `size` to `Board.__init__` and to `TicTacToeWinChecker.__init__`. The win checker's loops use `self.size` instead of the literal `3`. Nothing else changes.

### 3. Why the Command pattern for undo?

Each `Move` is a frozen dataclass — an immutable record of what happened. `MoveHistory` holds a stack of these records. To undo, pop the last record and call `board.undo(move)`, which clears that cell. No extra state is needed because the move carries everything required to reverse it.

### 4. Why abstract `Player`?

`Game` only ever calls `player.get_move(board)`. It never asks "are you human?". This means you can swap `HumanPlayer` for `AIPlayer` — or for a `MinimaxPlayer` you write next week — without touching a single line of `Game`. This is the Strategy pattern.

### 5. How would you add a 3-player mode?

Pass a third `Player` to `TurnManager`. The modulo arithmetic in `next_turn()` already handles any number of players. `WinChecker` would need a third symbol — but `TurnManager` and `Game` change not at all.

---

## Complete Code

The imports and enums first — these are the vocabulary the rest of the code uses.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
import random
```

`Symbol` gives us three named constants instead of scattered strings like `"X"`, `"O"`, `" "`.

```python
class Symbol(Enum):
    X     = "X"
    O     = "O"
    EMPTY = " "
```

`Move` is a frozen dataclass — immutable after creation so it is safe to store in history.

```python
@dataclass(frozen=True)
class Move:
    """
    A value object: describes what a player wants to do.
    Carries no logic — just data.
    """
    row: int
    col: int
    symbol: Symbol  # which symbol to place
```

**What just happened?** `frozen=True` means Python will raise a `FrozenInstanceError` if any code tries to change a move's fields after creation. This is exactly what we want for a history log.

---

`Board` stores state only. It does not know about winning.

```python
class Board:
    """
    Holds the N×N grid of Symbol values.

    Responsibilities:
    - apply / undo a move
    - answer whether a position is valid and empty
    - tell callers whether the board is full
    - display itself
    """

    def __init__(self, size: int = 3) -> None:
        self.size = size
        # 2-D list of Symbol.EMPTY
        self._grid: list[list[Symbol]] = [
            [Symbol.EMPTY] * size for _ in range(size)
        ]

    def apply(self, move: Move) -> None:
        """Place the move's symbol on the board. Caller must validate first."""
        self._grid[move.row][move.col] = move.symbol

    def undo(self, move: Move) -> None:
        """Erase the cell that this move occupied, restoring it to EMPTY."""
        self._grid[move.row][move.col] = Symbol.EMPTY

    def is_valid(self, move: Move) -> bool:
        """True only if the cell exists AND is currently empty."""
        r, c = move.row, move.col
        if not (0 <= r < self.size and 0 <= c < self.size):
            return False
        return self._grid[r][c] == Symbol.EMPTY

    def is_full(self) -> bool:
        """True when every cell has been filled (used to detect draws)."""
        return all(
            self._grid[r][c] != Symbol.EMPTY
            for r in range(self.size)
            for c in range(self.size)
        )

    def at(self, row: int, col: int) -> Symbol:
        """Read a cell without exposing the internal grid."""
        return self._grid[row][col]

    def display(self) -> None:
        """Print the board in a readable format."""
        print()
        separator = ("---+" * self.size).rstrip("+")
        for r, row in enumerate(self._grid):
            print(" | ".join(cell.value for cell in row))
            if r < self.size - 1:
                print(separator)
        print()
```

**What just happened?** `Board.apply` and `Board.undo` are perfectly symmetric — apply places a symbol, undo erases it. The board never decides whether a move is *legal* (that is `Game`'s job) or whether a player has *won* (that is `WinChecker`'s job).

---

`Player` hierarchy — the Strategy pattern.

```python
class Player(ABC):
    """
    Abstract base for all player types.

    The game loop never checks if a player is human or AI —
    it just calls get_move() and trusts the result.
    """

    def __init__(self, name: str, symbol: Symbol) -> None:
        self.name = name
        self.symbol = symbol

    @abstractmethod
    def get_move(self, board: Board) -> Move:
        """Return the player's chosen move. Must NOT mutate the board."""
        ...

    def __str__(self) -> str:
        return f"{self.name} ({self.symbol.value})"


class HumanPlayer(Player):
    """Reads a row and column from standard input."""

    def get_move(self, board: Board) -> Move:
        while True:
            try:
                raw = input(f"{self.name}, enter row col (0-indexed, e.g. 1 2): ")
                row, col = map(int, raw.strip().split())
                return Move(row=row, col=col, symbol=self.symbol)
            except (ValueError, IndexError):
                print("  Please type two numbers separated by a space.")


class AIPlayer(Player):
    """
    Picks a random empty cell.

    In production this would be a Minimax or MCTS algorithm —
    but Game never needs to know the difference. That is the
    Strategy pattern at work.
    """

    def get_move(self, board: Board) -> Move:
        empty = [
            (r, c)
            for r in range(board.size)
            for c in range(board.size)
            if board.at(r, c) == Symbol.EMPTY
        ]
        row, col = random.choice(empty)
        print(f"  {self.name} plays at ({row}, {col})")
        return Move(row=row, col=col, symbol=self.symbol)
```

---

`TurnManager` — cycles through any number of players.

```python
class TurnManager:
    """
    Always knows whose turn it is and advances cleanly to the next player.

    Works for 2 players, 3 players, or more — the modulo arithmetic
    handles any list length without if-else chains.
    """

    def __init__(self, players: list[Player]) -> None:
        if not players:
            raise ValueError("Need at least one player.")
        self._players = players
        self._index = 0

    def current_player(self) -> Player:
        return self._players[self._index]

    def next_turn(self) -> None:
        """Advance to the next player, wrapping around after the last one."""
        self._index = (self._index + 1) % len(self._players)

    def previous_turn(self) -> None:
        """Step back one player — used after an undo."""
        self._index = (self._index - 1) % len(self._players)
```

---

`WinChecker` — evaluates the board after each move.

```python
class WinChecker(ABC):
    """
    Abstract base: concrete subclasses implement the win condition
    for a specific game or variant.
    """

    @abstractmethod
    def check(self, board: Board, player: Player) -> bool:
        """Return True if `player` has just won."""
        ...


class TicTacToeWinChecker(WinChecker):
    """
    Three (or N) of the same symbol in any row, column, or diagonal.

    Works for any N×N board because it reads board.size instead of
    hard-coding the number 3.
    """

    def check(self, board: Board, player: Player) -> bool:
        s = player.symbol
        n = board.size

        # Check every row
        for r in range(n):
            if all(board.at(r, c) == s for c in range(n)):
                return True

        # Check every column
        for c in range(n):
            if all(board.at(r, c) == s for r in range(n)):
                return True

        # Top-left → bottom-right diagonal
        if all(board.at(i, i) == s for i in range(n)):
            return True

        # Top-right → bottom-left diagonal
        if all(board.at(i, n - 1 - i) == s for i in range(n)):
            return True

        return False
```

**What just happened?** The win checker never touches the board's internal `_grid` directly — it uses the public `board.at(r, c)` accessor. This means you could swap the board's internal representation (say, a flat list instead of a 2-D list) without breaking the win checker.

---

`MoveHistory` — Command pattern for undo.

```python
class MoveHistory:
    """
    Records every applied move in order.

    Each Move is an immutable command object. To undo, pop the last
    one and ask the board to reverse its effect.
    """

    def __init__(self) -> None:
        self._stack: list[Move] = []

    def record(self, move: Move) -> None:
        self._stack.append(move)

    def undo_last(self, board: Board) -> Optional[Move]:
        """
        Erase the last move from the board and return it.
        Returns None if there is nothing to undo.
        """
        if not self._stack:
            return None
        last = self._stack.pop()
        board.undo(last)
        return last

    def __len__(self) -> int:
        return len(self._stack)
```

---

`Game` — the Facade that ties everything together.

```python
class Game:
    """
    The single entry point.

    Callers create a Game and call play(). They never need to
    touch Board, TurnManager, WinChecker, or MoveHistory directly.
    That is the Facade pattern.
    """

    def __init__(
        self,
        players: list[Player],
        board: Board,
        win_checker: WinChecker,
    ) -> None:
        self.board = board
        self.turn_manager = TurnManager(players)
        self.win_checker = win_checker
        self.history = MoveHistory()
        self._winner: Optional[Player] = None

    @property
    def is_over(self) -> bool:
        return self._winner is not None or self.board.is_full()

    def play(self) -> None:
        """Run the game loop until someone wins or the board is full."""
        print("Game started!")
        self.board.display()

        while not self.is_over:
            player = self.turn_manager.current_player()
            move = player.get_move(self.board)

            if self.board.is_valid(move):
                self.board.apply(move)          # (1) mutate state
                self.history.record(move)       # (2) record for undo
                self.board.display()

                if self.win_checker.check(self.board, player):  # (3) evaluate
                    print(f"{player} wins!")
                    self._winner = player
                    return

                self.turn_manager.next_turn()   # (4) advance only on valid move
            else:
                print("  Invalid move — cell is occupied or out of bounds.")

        if self._winner is None:
            print("It's a draw!")

    def undo(self) -> None:
        """
        Undo the last move and step the turn back by one.
        Safe to call at any point — does nothing if history is empty.
        """
        undone = self.history.undo_last(self.board)
        if undone:
            self.turn_manager.previous_turn()
            print(f"  Undid move at ({undone.row}, {undone.col})")
            self.board.display()
        else:
            print("  Nothing to undo.")
```

**What just happened?** The game loop follows the template exactly: check validity → apply → record → check win → advance turn. Notice that `turn_manager.next_turn()` is called only after a valid move. If the move is invalid, we stay on the same player and ask again.

---

Full playable usage:

```python
if __name__ == "__main__":
    # Human vs AI on the classic 3×3 board
    players = [
        HumanPlayer(name="Alice", symbol=Symbol.X),
        AIPlayer(name="Bot",      symbol=Symbol.O),
    ]

    game = Game(
        players=players,
        board=Board(size=3),
        win_checker=TicTacToeWinChecker(),
    )

    game.play()

    # ── Bonus: 4×4 board, AI vs AI ──────────────────────────────────────
    print("\n=== 4×4 AI vs AI demo ===")
    game2 = Game(
        players=[
            AIPlayer(name="Alpha", symbol=Symbol.X),
            AIPlayer(name="Beta",  symbol=Symbol.O),
        ],
        board=Board(size=4),
        win_checker=TicTacToeWinChecker(),
    )
    game2.play()
```

---

## Step-by-step walkthrough

We trace a 5-move game on the default 3×3 board. X always goes first.

**Initial board**

```
  |   |
--+---+--
  |   |
--+---+--
  |   |
```

**Move 1 — X plays (0, 0)**

X chooses the top-left corner. `board.is_valid(Move(0,0,X))` is `True`. `board.apply` places X. Win check: no three in a row yet.

```
X |   |
--+---+--
  |   |
--+---+--
  |   |
```

**Move 2 — O plays (1, 1)**

O takes the centre. Board updated. No win yet.

```
X |   |
--+---+--
  | O |
--+---+--
  |   |
```

**Move 3 — X plays (0, 1)**

X starts building the top row.

```
X | X |
--+---+--
  | O |
--+---+--
  |   |
```

**Move 4 — O plays (0, 2)**

O blocks the top-right corner to prevent X from completing the top row immediately.

```
X | X | O
--+---+--
  | O |
--+---+--
  |   |
```

**Move 5 — X plays (2, 0)**

X switches strategy and takes the bottom-left corner.

```
X | X | O
--+---+--
  | O |
--+---+--
X |   |
```

Win check: rows — none. Columns — none. Main diagonal: (0,0)=X, (1,1)=O — not all X. Anti-diagonal: (0,2)=O — not all X. No win yet. Game continues.

*(Eventually X plays (1,0) and (2,0) already occupied, but imagine X gets the left column: (0,0), (1,0), (2,0) all X — win checker finds column 0 is all X, returns True.)*

**Final state (X wins via left column)**

```
X | X | O
--+---+--
X | O |
--+---+--
X |   |
```

`TicTacToeWinChecker.check()` scans column 0: `board.at(0,0)=X`, `board.at(1,0)=X`, `board.at(2,0)=X` — all equal to X's symbol. Returns `True`. Game prints `"Alice (X) wins!"`.

---

## Common interview mistakes

1. **Hardcoding win check for 3×3.** Writing `if grid[0][0] == grid[0][1] == grid[0][2]` for every row. This breaks the moment the interviewer says "make it N×N." Always loop over `range(board.size)`.

2. **Putting win logic inside `Board`.** Merging `check_win()` into `Board` gives it two responsibilities: storing state and evaluating state. When the win condition changes (e.g., a variant that wins on 4 in a row), you have to edit `Board` — the most central class. Keep them separate.

3. **Not validating occupied cells.** Forgetting to check `board.at(r, c) == Symbol.EMPTY` in `is_valid`. Without this, two symbols can occupy the same cell and win checks become unreliable.

4. **Mutating the board inside `Player.get_move`.** `get_move` should return a `Move` value object. The board mutation must happen inside the game loop after validation. Players should never touch the board directly.

5. **Checking win before applying the move.** Calling `win_checker.check()` before `board.apply()` means you inspect the state from the previous turn. You will never detect a win until one move too late (if ever).

---

## Key patterns used

| Pattern | Where it appears | Why it helps |
|---|---|---|
| **Strategy** | `Player` / `HumanPlayer` / `AIPlayer` | Swap AI algorithm without changing `Game` |
| **Command** | `Move` + `MoveHistory` | Store moves as objects so they can be undone |
| **Template Method** | The `play()` game loop | Fixed structure, steps delegated to collaborators |
| **Facade** | `Game` class | One entry point hides all internal complexity |
| **Abstract class** | `Player`, `WinChecker` | Enforces a contract; any subclass works with `Game` |
