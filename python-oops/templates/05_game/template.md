# Template 05: Game

---

## 1. What is the Game Template?

Picture a board game night: two or more players sit around a table, take turns making moves on a shared board, and someone wins (or the game ends in a draw) when a specific condition is met.

In plain English: **players take turns performing moves on a shared board or arena, following rules, until a win, draw, or end condition is reached.**

This template applies to a surprisingly wide range of systems. Once you recognise the pattern you can model Chess, Tic-Tac-Toe, Snake & Ladders, Wordle, and Battleship with the same skeleton — only the rules and win condition change.

---

## 2. How to Recognise This Template

When the interviewer says any of these words, reach for this template:

| Trigger word | What it maps to |
|---|---|
| players | `Player` class (human or AI) |
| turns / whose turn | `TurnManager` |
| board / grid / arena | `Board` |
| move / action / step | `Move` value object |
| valid move / illegal move | `MoveValidator` |
| win condition / game over | `WinChecker` |
| score / points | field on `Player` or `Board` |
| undo / replay | `CommandHistory` (Command pattern) |
| AI opponent | `AIPlayer` (Strategy pattern) |

If you hear **at least two** of these, you are almost certainly looking at a Game problem.

---

## 3. Real-World Examples

- **Chess** — 8x8 board, complex piece movement rules, check/checkmate win condition
- **Tic-Tac-Toe** — 3x3 grid, simple rules, three-in-a-row win condition (great for demo code)
- **Snake & Ladders** — linear board, dice-driven movement, reach square 100 to win
- **Scrabble** — tile rack, word placement on a 15x15 grid, score-based end condition
- **Ludo** — four players, tokens, dice, safe zones
- **Battleship** — hidden boards, coordinate-based attacks, all-ships-sunk win condition
- **Wordle** — single-player word guessing, six attempts, letter-position feedback

All of these share the same game loop and the same set of classes. The rules differ; the structure does not.

---

## 4. Core Building Blocks

> **Board / Arena** is like the playing surface at the centre of the table — it holds the current state of the game. Every player looks at the same board.

> **Player** is the decision-maker — human or AI. A human reads the board and types a move; an AI runs an algorithm and returns a move. From the game's perspective, they look identical.

> **Piece / Token** is what a player moves around the board (a chess rook, a Ludo token). Some games have no separate pieces — the board cell *is* the piece (Tic-Tac-Toe's X and O).

> **Move** is a value object — a lightweight description of *what* the player wants to do (row 1, column 2; or "move piece from E2 to E4"). It carries no logic, just data.

> **Turn Manager** is like the person at the table who says "your turn" — it cycles through the list of players and always knows whose turn it is.

> **Rules Engine / Move Validator** is the rulebook. Before any move is applied to the board it passes through the validator. Invalid moves are rejected without changing game state.

> **Win Condition Checker** is the referee. After every valid move it inspects the board and decides whether the game is over and who won (if anyone).

---

## 5. Class Relationship Diagram

```
Game  (Facade — the single entry point)
 ├── Board
 ├── TurnManager ──manages──> List[Player]
 ├── MoveValidator  <<abstract>>
 ├── WinChecker     <<abstract>>
 └── CommandHistory  (stores Move objects for undo/redo)

Player  <<abstract>>
 ├── HumanPlayer   (reads input from console / UI)
 └── AIPlayer      (Strategy pattern — pluggable algorithm)
```

**What just happened?**
- `Game` is a Facade. It owns all the collaborating objects and exposes one method: `play()`. Callers never need to touch `Board`, `TurnManager`, or `WinChecker` directly.
- `Player` is abstract so `Game` never needs to know whether it is talking to a human or an AI. This is the Strategy pattern at work.
- `MoveValidator` and `WinChecker` are abstract so you can swap in different rule sets without touching `Board` or `Game`. A Chess validator and a Tic-Tac-Toe validator implement the same interface.

---

## 6. The Generic Game Loop

Every turn-based game — no matter how complex — follows this exact loop:

```python
def play(self) -> None:
    while not self.is_over():                           # (1)
        player = self.turn_manager.current_player()    # (2)
        move = player.get_move(self.board)             # (3)
        if self.validator.is_valid(move, self.board):  # (4)
            self.board.apply(move)                     # (5)
            self.history.record(move)                  # (6)
            if self.win_checker.check(self.board, player):  # (7)
                print(f"{player} wins!")
                return
            self.turn_manager.next_turn()              # (8)
        else:
            print("Invalid move, try again.")          # (9)
```

Line-by-line explanation:

1. **`while not self.is_over()`** — keep playing until someone wins or the board is full (draw). `is_over` checks both conditions.
2. **`current_player()`** — ask the Turn Manager whose turn it is. It knows; you do not need to track it manually.
3. **`player.get_move(self.board)`** — ask the current player for their move. A `HumanPlayer` prompts the user; an `AIPlayer` runs an algorithm. The game loop does not care which one it is.
4. **`is_valid(move, self.board)`** — consult the validator *before* changing anything. If the move is illegal, no state changes at all.
5. **`board.apply(move)`** — only now do we actually change the board. This is the single point of state mutation.
6. **`history.record(move)`** — log the move so we can undo it later (Command pattern).
7. **`win_checker.check()`** — inspect the board after every move. This is a separate class, not a method on `Board`, because win logic can be complex and may vary by game variant.
8. **`next_turn()`** — advance to the next player. The Turn Manager handles wrap-around (after the last player, it goes back to the first).
9. **Invalid move path** — we simply ask again. State is unchanged because we rejected the move before `apply`.

---

## 7. Generic Skeleton Code

The example below models **Tic-Tac-Toe** because it is the simplest possible game that uses every building block. The same structure scales to Chess or Battleship.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import random


# ---------------------------------------------------------------------------
# Move — a value object (just data, no logic)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Move:
    """
    Describes a player's intended action.

    `frozen=True` makes Move immutable — a move recorded in history
    can never be accidentally changed after the fact.
    """
    row: int
    col: int
    player_symbol: str  # 'X' or 'O'


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------

class Board:
    """
    Holds the current state of the 3x3 grid.

    The board knows how to display itself and how to apply a move,
    but it does NOT know the win condition — that belongs to WinChecker.
    """

    SIZE = 3

    def __init__(self) -> None:
        # A 2D grid pre-filled with spaces (empty cells)
        self.grid: list[list[str]] = [
            [" " for _ in range(self.SIZE)]
            for _ in range(self.SIZE)
        ]

    def apply(self, move: Move) -> None:
        """Place the player's symbol on the board."""
        self.grid[move.row][move.col] = move.player_symbol

    def is_valid_position(self, row: int, col: int) -> bool:
        """True if the cell exists and is still empty."""
        if not (0 <= row < self.SIZE and 0 <= col < self.SIZE):
            return False
        return self.grid[row][col] == " "

    def is_full(self) -> bool:
        """True when every cell has been filled (used to detect draws)."""
        return all(self.grid[r][c] != " "
                   for r in range(self.SIZE)
                   for c in range(self.SIZE))

    def display(self) -> None:
        """Print the board in a readable format."""
        print()
        for row in self.grid:
            print(" | ".join(row))
            print("-" * 9)
        print()


# ---------------------------------------------------------------------------
# Player hierarchy
# ---------------------------------------------------------------------------

class Player(ABC):
    """
    Abstract base for all player types.

    The game loop only calls `get_move` — it never checks whether the
    player is human or AI. This is the Strategy pattern.
    """

    def __init__(self, name: str, symbol: str) -> None:
        self.name = name
        self.symbol = symbol

    @abstractmethod
    def get_move(self, board: Board) -> Move:
        """Ask the player for their next move."""
        ...

    def __str__(self) -> str:
        return f"{self.name} ({self.symbol})"


class HumanPlayer(Player):
    """Reads a move from standard input."""

    def get_move(self, board: Board) -> Move:
        while True:
            try:
                raw = input(f"{self.name}, enter row and col (e.g. 1 2): ")
                row, col = map(int, raw.strip().split())
                return Move(row=row, col=col, player_symbol=self.symbol)
            except (ValueError, IndexError):
                print("  Please enter two numbers separated by a space.")


class AIPlayer(Player):
    """
    Picks a random empty cell.

    In a real system this would be replaced with Minimax, MCTS, or
    a neural network — but from the game's perspective, nothing changes.
    That is the power of the Strategy pattern.
    """

    def get_move(self, board: Board) -> Move:
        empty_cells = [
            (r, c)
            for r in range(Board.SIZE)
            for c in range(Board.SIZE)
            if board.grid[r][c] == " "
        ]
        row, col = random.choice(empty_cells)
        print(f"{self.name} plays at ({row}, {col})")
        return Move(row=row, col=col, player_symbol=self.symbol)


# ---------------------------------------------------------------------------
# Turn Manager
# ---------------------------------------------------------------------------

class TurnManager:
    """
    Cycles through players in order.

    Think of it as passing the dice around the table — it always knows
    whose turn it is and advances cleanly to the next player.
    """

    def __init__(self, players: list[Player]) -> None:
        if not players:
            raise ValueError("Need at least one player.")
        self._players = players
        self._index = 0

    def current_player(self) -> Player:
        return self._players[self._index]

    def next_turn(self) -> None:
        """Advance to the next player, wrapping around to the first."""
        self._index = (self._index + 1) % len(self._players)


# ---------------------------------------------------------------------------
# Move Validator
# ---------------------------------------------------------------------------

class MoveValidator(ABC):
    """Abstract: concrete subclasses encode the rules for one game variant."""

    @abstractmethod
    def is_valid(self, move: Move, board: Board) -> bool:
        ...


class TicTacToeMoveValidator(MoveValidator):
    """A move is valid if the target cell exists and is empty."""

    def is_valid(self, move: Move, board: Board) -> bool:
        return board.is_valid_position(move.row, move.col)


# ---------------------------------------------------------------------------
# Win Checker
# ---------------------------------------------------------------------------

class WinChecker(ABC):
    """
    Abstract: checks whether the game is over after each move.

    Separating this from Board keeps Board small and focused on state.
    WinChecker can be complex (chess checkmate) without polluting Board.
    """

    @abstractmethod
    def check(self, board: Board, last_player: Player) -> bool:
        """Return True if `last_player` has won."""
        ...


class TicTacToeWinChecker(WinChecker):
    """
    Checks all rows, columns, and both diagonals for three in a row.
    """

    def check(self, board: Board, last_player: Player) -> bool:
        s = last_player.symbol
        g = board.grid
        n = Board.SIZE

        # Check rows and columns
        for i in range(n):
            if all(g[i][j] == s for j in range(n)):   # row i
                return True
            if all(g[j][i] == s for j in range(n)):   # column i
                return True

        # Check diagonals
        if all(g[i][i] == s for i in range(n)):        # top-left to bottom-right
            return True
        if all(g[i][n - 1 - i] == s for i in range(n)):  # top-right to bottom-left
            return True

        return False


# ---------------------------------------------------------------------------
# Command History (for undo)
# ---------------------------------------------------------------------------

class CommandHistory:
    """
    Records every move in order so we can replay or undo.

    This is the Command pattern: each `Move` object is a command
    that can be stored, inspected, and reversed.
    """

    def __init__(self) -> None:
        self._history: list[Move] = []

    def record(self, move: Move) -> None:
        self._history.append(move)

    def undo_last(self, board: Board) -> Optional[Move]:
        """
        Remove the last move from the board.
        Returns the undone Move, or None if history is empty.
        """
        if not self._history:
            return None
        last_move = self._history.pop()
        # Erase the symbol from the board
        board.grid[last_move.row][last_move.col] = " "
        return last_move


# ---------------------------------------------------------------------------
# Game Facade
# ---------------------------------------------------------------------------

class Game:
    """
    The single entry point for the game.

    Callers only need to create a Game and call play() — all
    the internal collaborators are hidden. This is the Facade pattern.
    """

    def __init__(
        self,
        players: list[Player],
        board: Board,
        validator: MoveValidator,
        win_checker: WinChecker,
    ) -> None:
        self.board = board
        self.turn_manager = TurnManager(players)
        self.validator = validator
        self.win_checker = win_checker
        self.history = CommandHistory()
        self._over = False

    def is_over(self) -> bool:
        return self._over or self.board.is_full()

    def play(self) -> None:
        """Run the game until someone wins or the board is full."""
        print("Game started!")
        self.board.display()

        while not self.is_over():
            player = self.turn_manager.current_player()
            move = player.get_move(self.board)

            if self.validator.is_valid(move, self.board):
                self.board.apply(move)
                self.history.record(move)
                self.board.display()

                if self.win_checker.check(self.board, player):
                    print(f"{player} wins!")
                    self._over = True
                    return

                self.turn_manager.next_turn()
            else:
                print("  Invalid move — that cell is already taken or out of bounds.")

        if not self._over:
            print("It's a draw!")


# ---------------------------------------------------------------------------
# Quick demo: human vs AI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    players = [
        HumanPlayer(name="Alice", symbol="X"),
        AIPlayer(name="Bot",   symbol="O"),
    ]

    game = Game(
        players=players,
        board=Board(),
        validator=TicTacToeMoveValidator(),
        win_checker=TicTacToeWinChecker(),
    )

    game.play()
```

**What just happened?**

1. `Move` is `frozen=True` so a recorded move can never be mutated — safe to store in history.
2. `Board.apply()` does exactly one thing: change a cell. It does not check validity (that is `MoveValidator`'s job) and it does not check for a win (that is `WinChecker`'s job). Single responsibility.
3. Swapping `HumanPlayer` for `AIPlayer` requires zero changes to `Game` or `Board`.
4. `CommandHistory.undo_last()` erases the last move from the board. In a real system you would also decrement `TurnManager` back one step.
5. To port this to Chess: write `ChessMoveValidator`, `ChessWinChecker`, and a `ChessBoard` with `SIZE = 8`. `Game`, `TurnManager`, `Player`, and `CommandHistory` stay exactly the same.

---

## 8. Design Patterns Used

| Pattern | Where it appears | Why it helps |
|---|---|---|
| **Strategy** | `Player` / `HumanPlayer` / `AIPlayer` | Swap AI algorithm or input method without changing `Game` |
| **Template Method** | The `play()` game loop | The loop structure is fixed; individual steps are delegated to swappable collaborators |
| **Command** | `Move` + `CommandHistory` | Store moves as objects so they can be recorded, replayed, and undone |
| **Facade** | `Game` class | Hide `Board`, `TurnManager`, `WinChecker` etc. behind one clean entry point |
| **Abstract class / Interface** | `Player`, `MoveValidator`, `WinChecker` | Enforce a contract so any concrete implementation works with `Game` |

---

## 9. Key Design Decisions for the Interview

### Why separate WinChecker from Board?
`Board` is responsible for *storing* state. `WinChecker` is responsible for *interpreting* that state. Combining them violates the Single Responsibility Principle and makes it hard to support game variants (e.g., a 5-in-a-row variant of Tic-Tac-Toe would need a completely different win check but the same board).

### How to implement undo / redo?
Use the Command pattern. Each `Move` is a lightweight command object. `CommandHistory` maintains a stack. Undo pops the last move and reverses its effect on the board (set the cell back to empty, or restore a captured piece in Chess). Redo pushes it back. This works cleanly without the board needing to know anything about history.

### How to add an AI player without changing Game?
Extend `Player` with a new subclass (e.g., `MinimaxAIPlayer`) and pass it into the `Game` constructor. Because `Game` only calls `player.get_move(board)`, nothing else changes. This is the Open/Closed Principle: open for extension, closed for modification.

### How to support a variable number of players?
`TurnManager` already takes a `list[Player]`. Passing three or four players to it works without any other changes. The game loop always asks `turn_manager.current_player()` and then calls `next_turn()` — it never hard-codes "player 1 then player 2".

---


---

## 11. Problems Using This Template

- [Tic-Tac-Toe](tic_tac_toe.md) — N×N board, win checker, undo with Command pattern
- [Chess](chess.md) — piece hierarchy, move validation per type, check/checkmate detection
- [Snake and Ladder](snake_and_ladder.md) — BoardEntity abstraction, testable dice, overshoot handling

## 10. Common Mistakes

1. **Putting win-condition logic inside Board.**
   `Board` stores state; win checking is a separate concern. When win logic lives in `Board`, adding a new game variant forces you to edit the core state class — risky and hard to test.

2. **Hard-coding two players.**
   Writing `if current_player == player1: next = player2` breaks the moment someone asks you to support a 4-player variant. Always use a `TurnManager` with a list.

3. **Letting `get_move` mutate the board directly.**
   `Player.get_move()` should return a `Move` value object. The mutation must happen through `board.apply()` inside the game loop, *after* validation. Players should never touch the board themselves.

4. **Checking for a win before applying the move.**
   Always apply first, then check. Checking before `apply` means you are inspecting the board from the *previous* state — you will never detect a win.

5. **Forgetting the draw condition.**
   Every bounded board game can end in a draw. `is_over()` must check `board.is_full()` as well as whether someone has won. Leaving this out means the game loop will run forever after the board fills up with no winner.
