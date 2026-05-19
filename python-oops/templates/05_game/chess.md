# 05 — Chess

## What is this problem testing?

This problem tests deep domain modelling under time pressure. Interviewers are watching for whether you can decompose a complex system into focused classes, whether each piece encapsulates its own movement rules (polymorphism), and whether you separate concerns such as move validation, check detection, and board state so that none of these responsibilities collapses into a single God object. Chess is intentionally scope-heavy — the real skill is scoping down intelligently while keeping the design extensible.

---

## Requirements

- 8×8 board, two players: White and Black
- Six piece types: King, Queen, Rook, Bishop, Knight, Pawn
- Each piece generates its own legal moves
- Turn enforcement: White moves first, then alternate
- Basic move validation: correct turn, piece belongs to the moving player, destination is reachable
- Check detection: a move that leaves the moving player's king in check is illegal
- Checkmate detection: current player is in check with no legal moves
- Stalemate detection: current player is not in check but has no legal moves
- Pawn promotion: pawn reaching the last rank becomes a Queen (basic)
- Move history for undo support

---

## Clarifying questions to ask in interview

1. **Full piece rules or design focus?** — Should I implement all six pieces completely, or show the design and implement two or three as examples? (This is the most important question — Chess is too large for a 45-minute interview without scoping.)
2. **Special moves in scope?** — Should I handle castling and en passant, or leave them as extension points?
3. **Who detects check — the board or a separate class?** — Prompts the interviewer to think about SRP before you start coding.
4. **Is undo one half-move or one full round?** — Important for move history design.
5. **Do we need a UI or just a printable board?** — Establishes whether Unicode symbols or ASCII letters are sufficient.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| Board / grid | `Board` |
| Player colour | `Color` enum |
| Piece category | `PieceType` enum |
| Cell address | `Position` frozen dataclass |
| A player's intended action | `Move` frozen dataclass |
| Generic piece | `Piece` abstract class |
| King, Queen, Rook, Bishop, Knight, Pawn | Six concrete `Piece` subclasses |
| Who goes next | `TurnManager` |
| Move legality (turn + piece rules) | `MoveValidator` |
| Check / checkmate / stalemate | `CheckDetector` |
| Recorded list of moves | `MoveHistory` |
| Whole game | `Game` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Get all reachable squares | `get_valid_moves(board)` | `Piece` (each subclass) |
| Place a piece | `place_piece(pos, piece)` | `Board` |
| Remove a piece | `remove_piece(pos)` | `Board` |
| Read a cell | `get_piece(pos)` | `Board` |
| Check cell is empty | `is_empty(pos)` | `Board` |
| Check cell has an enemy | `has_enemy(pos, color)` | `Board` |
| Print the board | `display()` | `Board` |
| Validate the full move | `validate(move, board, turn)` | `MoveValidator` |
| Detect check | `is_in_check(board, color)` | `CheckDetector` |
| Detect checkmate | `is_checkmate(board, color)` | `CheckDetector` |
| Detect stalemate | `is_stalemate(board, color)` | `CheckDetector` |
| Advance / reverse turn | `next_turn()`, `previous_turn()` | `TurnManager` |
| Record / undo a move | `record(move)`, `undo_last(board)` | `MoveHistory` |
| Run the game loop | `play()` | `Game` |

---

## Relationships

```
Game  (Facade)
 ├── Board  (8×8 grid of Optional[Piece])
 ├── TurnManager
 ├── MoveValidator
 ├── CheckDetector
 └── MoveHistory

Piece  <<abstract>>
 ├── King
 ├── Queen
 ├── Rook
 ├── Bishop
 ├── Knight
 └── Pawn
      └── get_valid_moves(board) → list[Move]
```

> Think of `Board` as the physical board on the table — it only knows which piece sits where. `CheckDetector` is the tournament arbiter who studies the position and declares "you're in check". `MoveValidator` is the player's coach who says "you can't make that move, it would leave your king exposed". `Game` is the match director who keeps everything running in order.

---

## Design decisions

### 1. Why does each Piece know its own valid moves?

If you put all movement logic in `Board` or `MoveValidator`, you get a massive `if isinstance(piece, Rook): ...` chain. Every time you add a new piece type you have to edit that central class. With polymorphism, adding a new piece means creating a new subclass — existing code does not change. This is the Open/Closed Principle.

### 2. Why is `CheckDetector` separate from `Board`?

Board stores state. Check detection interprets that state by simulating enemy moves. The logic is complex — iterating all enemy pieces and testing whether any can reach the king. Mixing this into `Board` would make the state class enormous and hard to test in isolation.

### 3. Why is `Position` a frozen dataclass?

Positions are used as dictionary keys (to map cells to pieces) and stored inside `Move` objects. Mutable objects cannot be dict keys in Python. `frozen=True` also gives us value equality: `Position(3, 4) == Position(3, 4)` is `True`, so two independently created positions for the same square compare equal without writing a custom `__eq__`.

### 4. How do you detect checkmate vs stalemate?

Both require that the current player has zero legal moves. The difference is whether the king is currently in check. Algorithm: generate all moves for all pieces of the current colour. For each candidate move, apply it on a copy of the board, check whether the king is still in check, then undo. If no move escapes check and the player is in check → checkmate. If no move exists and the player is not in check → stalemate.

### 5. How would you add castling?

`has_moved` on `King` and `Rook` is tracked. A `CastlingValidator` (or an extension of `MoveValidator`) checks: neither piece has moved, no pieces between them, king not currently in check, king does not pass through check. The move itself is a special `Move` subclass or a move with a flag. The existing structure accommodates this without altering any other class.

---

## Complete Code

Imports and enums first.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
```

`Color` and `PieceType` replace magic strings throughout the codebase.

```python
class Color(Enum):
    WHITE = "White"
    BLACK = "Black"

    def opponent(self) -> Color:
        """Convenience: return the other colour."""
        return Color.BLACK if self == Color.WHITE else Color.WHITE


class PieceType(Enum):
    KING   = auto()
    QUEEN  = auto()
    ROOK   = auto()
    BISHOP = auto()
    KNIGHT = auto()
    PAWN   = auto()
```

`Position` is a value object and a dict key.

```python
@dataclass(frozen=True)
class Position:
    """
    A cell address on the board.

    frozen=True → hashable → usable as dict key.
    Value equality: Position(0, 0) == Position(0, 0) is True.
    """
    row: int  # 0 = rank 1 (white's back rank)
    col: int  # 0 = a-file

    def is_valid(self) -> bool:
        return 0 <= self.row <= 7 and 0 <= self.col <= 7

    def __add__(self, other: Position) -> Position:
        """Add two positions as vectors: useful for sliding piece logic."""
        return Position(self.row + other.row, self.col + other.col)
```

`Move` records everything needed to apply or undo it.

```python
@dataclass(frozen=True)
class Move:
    """
    A value object describing one half-move (ply).

    Stores the captured piece so undo can restore it without searching.
    """
    from_pos: Position
    to_pos:   Position
    piece:    "Piece"                       # the piece being moved
    captured: Optional["Piece"] = None     # piece on to_pos before the move
    promotion: Optional[PieceType] = None  # set when a pawn promotes
```

**What just happened?** `Move` stores `captured` so that `MoveHistory.undo_last()` can put the captured piece back without any extra lookups. This is part of why making `Move` a rich value object pays off.

---

`Piece` is the abstract base for all six piece types.

```python
class Piece(ABC):
    """
    A chess piece knows its colour, its type, and whether it has moved.
    Most importantly it knows how to generate its own valid destination squares.
    """

    # Unicode symbols for display (white pieces first, then black)
    _SYMBOLS: dict[tuple[Color, PieceType], str] = {
        (Color.WHITE, PieceType.KING):   "♔",
        (Color.WHITE, PieceType.QUEEN):  "♕",
        (Color.WHITE, PieceType.ROOK):   "♖",
        (Color.WHITE, PieceType.BISHOP): "♗",
        (Color.WHITE, PieceType.KNIGHT): "♘",
        (Color.WHITE, PieceType.PAWN):   "♙",
        (Color.BLACK, PieceType.KING):   "♚",
        (Color.BLACK, PieceType.QUEEN):  "♛",
        (Color.BLACK, PieceType.ROOK):   "♜",
        (Color.BLACK, PieceType.BISHOP): "♝",
        (Color.BLACK, PieceType.KNIGHT): "♞",
        (Color.BLACK, PieceType.PAWN):   "♟",
    }

    def __init__(self, color: Color, piece_type: PieceType) -> None:
        self.color = color
        self.piece_type = piece_type
        self.has_moved = False  # used for castling (King/Rook) and pawn double-move

    @property
    def symbol(self) -> str:
        return self._SYMBOLS[(self.color, self.piece_type)]

    @abstractmethod
    def get_valid_moves(self, pos: Position, board: "Board") -> list[Move]:
        """
        Return all squares this piece can move to from `pos`.
        Does NOT filter out moves that leave the king in check —
        that is MoveValidator's job.
        """
        ...

    def __repr__(self) -> str:
        return f"{self.color.value} {self.piece_type.name}"
```

---

The six concrete piece classes. Each implements `get_valid_moves` with its correct movement rules.

```python
class King(Piece):
    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.KING)

    def get_valid_moves(self, pos: Position, board: "Board") -> list[Move]:
        moves = []
        # King moves one step in any of the 8 directions
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                target = pos + Position(dr, dc)
                if not target.is_valid():
                    continue
                if board.is_empty(target) or board.has_enemy(target, self.color):
                    captured = board.get_piece(target)
                    moves.append(Move(pos, target, self, captured))
        return moves


class Knight(Piece):
    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.KNIGHT)

    _OFFSETS = [
        (-2, -1), (-2, 1), (-1, -2), (-1, 2),
        ( 1, -2), ( 1, 2), ( 2, -1), ( 2,  1),
    ]

    def get_valid_moves(self, pos: Position, board: "Board") -> list[Move]:
        moves = []
        for dr, dc in self._OFFSETS:
            target = pos + Position(dr, dc)
            if not target.is_valid():
                continue
            if board.is_empty(target) or board.has_enemy(target, self.color):
                captured = board.get_piece(target)
                moves.append(Move(pos, target, self, captured))
        return moves


def _sliding_moves(
    piece: Piece,
    pos: Position,
    board: "Board",
    directions: list[tuple[int, int]],
) -> list[Move]:
    """
    Helper for pieces that slide in straight lines (Rook, Bishop, Queen).
    Extends in each direction until the board edge or a blocking piece.
    """
    moves = []
    for dr, dc in directions:
        current = pos + Position(dr, dc)
        while current.is_valid():
            if board.is_empty(current):
                moves.append(Move(pos, current, piece))
            elif board.has_enemy(current, piece.color):
                moves.append(Move(pos, current, piece, board.get_piece(current)))
                break  # can capture but not pass through
            else:
                break  # friendly piece blocks the path
            current = current + Position(dr, dc)
    return moves


class Rook(Piece):
    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.ROOK)

    def get_valid_moves(self, pos: Position, board: "Board") -> list[Move]:
        return _sliding_moves(self, pos, board, [(1,0),(-1,0),(0,1),(0,-1)])


class Bishop(Piece):
    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.BISHOP)

    def get_valid_moves(self, pos: Position, board: "Board") -> list[Move]:
        return _sliding_moves(self, pos, board, [(1,1),(1,-1),(-1,1),(-1,-1)])


class Queen(Piece):
    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.QUEEN)

    def get_valid_moves(self, pos: Position, board: "Board") -> list[Move]:
        # Queen = Rook directions + Bishop directions
        all_dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]
        return _sliding_moves(self, pos, board, all_dirs)


class Pawn(Piece):
    def __init__(self, color: Color) -> None:
        super().__init__(color, PieceType.PAWN)

    def get_valid_moves(self, pos: Position, board: "Board") -> list[Move]:
        moves = []
        # White pawns move up (decreasing row in our 0=rank1 convention).
        # Black pawns move down.
        direction = -1 if self.color == Color.WHITE else 1
        start_row = 6 if self.color == Color.WHITE else 1  # starting rank for double-step
        promo_row  = 0 if self.color == Color.WHITE else 7  # promotion rank

        # ── Single step forward ──
        one_ahead = pos + Position(direction, 0)
        if one_ahead.is_valid() and board.is_empty(one_ahead):
            if one_ahead.row == promo_row:
                # Promotion: represent as a move with promotion flag
                moves.append(Move(pos, one_ahead, self, promotion=PieceType.QUEEN))
            else:
                moves.append(Move(pos, one_ahead, self))

            # ── Double step from starting row ──
            if pos.row == start_row and not self.has_moved:
                two_ahead = pos + Position(direction * 2, 0)
                if two_ahead.is_valid() and board.is_empty(two_ahead):
                    moves.append(Move(pos, two_ahead, self))

        # ── Diagonal captures ──
        for dc in (-1, 1):
            diag = pos + Position(direction, dc)
            if diag.is_valid() and board.has_enemy(diag, self.color):
                captured = board.get_piece(diag)
                if diag.row == promo_row:
                    moves.append(Move(pos, diag, self, captured, PieceType.QUEEN))
                else:
                    moves.append(Move(pos, diag, self, captured))

        return moves
```

**What just happened?** The `_sliding_moves` helper captures the shared logic of Rook, Bishop, and Queen in one place. Without it, all three classes would contain nearly identical while-loops. Queen simply delegates to the helper with all eight directions.

---

`Board` — state only, no win logic.

```python
class Board:
    """
    Holds the 8×8 grid as a dict from Position → Piece.
    Absent keys mean empty squares.
    """

    def __init__(self) -> None:
        self._grid: dict[Position, Piece] = {}
        self._setup()

    # ── State access ──────────────────────────────────────────────────────

    def get_piece(self, pos: Position) -> Optional[Piece]:
        return self._grid.get(pos)

    def place_piece(self, pos: Position, piece: Piece) -> None:
        self._grid[pos] = piece

    def remove_piece(self, pos: Position) -> Optional[Piece]:
        return self._grid.pop(pos, None)

    def is_empty(self, pos: Position) -> bool:
        return pos not in self._grid

    def has_enemy(self, pos: Position, color: Color) -> bool:
        piece = self._grid.get(pos)
        return piece is not None and piece.color != color

    def find_king(self, color: Color) -> Optional[Position]:
        """Locate the king of the given colour — needed for check detection."""
        for pos, piece in self._grid.items():
            if piece.color == color and piece.piece_type == PieceType.KING:
                return pos
        return None

    def all_pieces(self, color: Color) -> list[tuple[Position, Piece]]:
        """Return all (position, piece) pairs for the given colour."""
        return [(pos, p) for pos, p in self._grid.items() if p.color == color]

    # ── Apply / undo a move ───────────────────────────────────────────────

    def apply_move(self, move: Move) -> None:
        """Mutate the board to reflect the move. Caller validates first."""
        self.remove_piece(move.from_pos)
        if move.promotion:
            # Promote the pawn to a Queen (or whatever piece_type was chosen)
            self.place_piece(move.to_pos, Queen(move.piece.color))
        else:
            self.place_piece(move.to_pos, move.piece)
        move.piece.has_moved = True

    def undo_move(self, move: Move) -> None:
        """Reverse the mutation made by apply_move."""
        self.remove_piece(move.to_pos)
        self.place_piece(move.from_pos, move.piece)
        if move.captured:
            self.place_piece(move.to_pos, move.captured)
        # Note: has_moved is not reversed here for simplicity.
        # A production implementation would store the previous has_moved value in Move.

    # ── Display ───────────────────────────────────────────────────────────

    def display(self) -> None:
        print()
        print("   a  b  c  d  e  f  g  h")
        for row in range(7, -1, -1):  # rank 8 at the top
            rank = row + 1
            line_parts = []
            for col in range(8):
                piece = self._grid.get(Position(row, col))
                line_parts.append(piece.symbol if piece else "·")
            print(f"{rank}  {'  '.join(line_parts)}")
        print()

    # ── Starting position ─────────────────────────────────────────────────

    def _setup(self) -> None:
        """Place all 32 pieces in the standard chess starting position."""
        back_rank = [
            PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN,
            PieceType.KING, PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK,
        ]
        piece_classes = {
            PieceType.ROOK:   Rook,
            PieceType.KNIGHT: Knight,
            PieceType.BISHOP: Bishop,
            PieceType.QUEEN:  Queen,
            PieceType.KING:   King,
            PieceType.PAWN:   Pawn,
        }
        for col, pt in enumerate(back_rank):
            self.place_piece(Position(0, col), piece_classes[pt](Color.WHITE))  # rank 1
            self.place_piece(Position(7, col), piece_classes[pt](Color.BLACK))  # rank 8
        for col in range(8):
            self.place_piece(Position(1, col), Pawn(Color.WHITE))  # rank 2
            self.place_piece(Position(6, col), Pawn(Color.BLACK))  # rank 7
```

**What just happened?** Storing the grid as a `dict[Position, Piece]` (rather than a 2-D list) makes empty-cell checks O(1): `pos not in self._grid`. It also means iterating all pieces is straightforward — no need to scan for `None` values.

---

`CheckDetector` — interprets the board position.

```python
class CheckDetector:
    """
    Evaluates whether a king is under attack, in checkmate, or in stalemate.

    Uses Board.apply_move / Board.undo_move to test candidate positions
    without permanently changing game state.
    """

    def is_in_check(self, board: Board, color: Color) -> bool:
        """True if the king of `color` is attacked by any enemy piece."""
        king_pos = board.find_king(color)
        if king_pos is None:
            return False  # should not happen in a legal game
        opponent = color.opponent()
        for pos, piece in board.all_pieces(opponent):
            for move in piece.get_valid_moves(pos, board):
                if move.to_pos == king_pos:
                    return True
        return False

    def get_all_legal_moves(self, board: Board, color: Color) -> list[Move]:
        """
        Return every move for `color` that does NOT leave their king in check.
        This is the core of both checkmate and stalemate detection.
        """
        legal = []
        for pos, piece in board.all_pieces(color):
            for move in piece.get_valid_moves(pos, board):
                board.apply_move(move)
                if not self.is_in_check(board, color):
                    legal.append(move)
                board.undo_move(move)
        return legal

    def is_checkmate(self, board: Board, color: Color) -> bool:
        """In check AND no legal moves."""
        return (
            self.is_in_check(board, color)
            and len(self.get_all_legal_moves(board, color)) == 0
        )

    def is_stalemate(self, board: Board, color: Color) -> bool:
        """Not in check BUT no legal moves."""
        return (
            not self.is_in_check(board, color)
            and len(self.get_all_legal_moves(board, color)) == 0
        )
```

**What just happened?** `get_all_legal_moves` applies each candidate move, tests check, then immediately undoes it. This is the standard "make-and-unmake" technique. It is O(pieces × moves-per-piece) per call — fine for a 45-minute interview; a production engine would add caching.

---

`MoveValidator` — the full legality check.

```python
class MoveValidator:
    """
    Validates that a proposed move is legal:
      1. It is the correct player's turn.
      2. The move appears in the piece's own candidate moves.
      3. The move does not leave the moving player's king in check.
    """

    def __init__(self, check_detector: CheckDetector) -> None:
        self._detector = check_detector

    def validate(self, move: Move, board: Board, current_turn: Color) -> bool:
        # Rule 1: correct turn
        if move.piece.color != current_turn:
            print("  Not your piece.")
            return False

        # Rule 2: the piece can reach to_pos by its own movement rules
        piece = board.get_piece(move.from_pos)
        if piece is None or piece is not move.piece:
            print("  No such piece at that position.")
            return False
        candidate_targets = {m.to_pos for m in piece.get_valid_moves(move.from_pos, board)}
        if move.to_pos not in candidate_targets:
            print(f"  {piece} cannot move to {move.to_pos}.")
            return False

        # Rule 3: move does not leave own king in check
        board.apply_move(move)
        in_check_after = self._detector.is_in_check(board, current_turn)
        board.undo_move(move)
        if in_check_after:
            print("  That move leaves your king in check.")
            return False

        return True
```

---

`TurnManager` and `MoveHistory` — unchanged from the Tic-Tac-Toe skeleton but shown here for completeness.

```python
class TurnManager:
    def __init__(self) -> None:
        self._turn = Color.WHITE  # White always moves first

    def current(self) -> Color:
        return self._turn

    def next_turn(self) -> None:
        self._turn = self._turn.opponent()

    def previous_turn(self) -> None:
        self._turn = self._turn.opponent()  # opponent is its own inverse for 2-player


class MoveHistory:
    def __init__(self) -> None:
        self._stack: list[Move] = []

    def record(self, move: Move) -> None:
        self._stack.append(move)

    def undo_last(self, board: Board) -> Optional[Move]:
        if not self._stack:
            return None
        last = self._stack.pop()
        board.undo_move(last)
        return last

    def __len__(self) -> int:
        return len(self._stack)
```

---

`Game` — the Facade.

```python
class Game:
    """
    The single entry point. play() runs the interactive game loop.
    """

    def __init__(self) -> None:
        self.board       = Board()
        self.turn_mgr    = TurnManager()
        self.detector    = CheckDetector()
        self.validator   = MoveValidator(self.detector)
        self.history     = MoveHistory()
        self._game_over  = False

    def _parse_input(self, raw: str, color: Color) -> Optional[Move]:
        """
        Parse a move entered as 'e2 e4'.
        Returns a Move or None if parsing fails.
        """
        try:
            parts = raw.strip().lower().split()
            if len(parts) != 2:
                raise ValueError
            def to_pos(s: str) -> Position:
                col = ord(s[0]) - ord('a')   # 'a' → 0, 'b' → 1, ...
                row = int(s[1]) - 1           # '1' → 0, '2' → 1, ...
                return Position(row, col)
            from_pos = to_pos(parts[0])
            to_pos_  = to_pos(parts[1])
            piece = self.board.get_piece(from_pos)
            if piece is None:
                print("  No piece at that square.")
                return None
            captured = self.board.get_piece(to_pos_)
            return Move(from_pos, to_pos_, piece, captured)
        except (ValueError, IndexError):
            print("  Enter moves like 'e2 e4'.")
            return None

    def play(self) -> None:
        print("Chess — type moves as 'e2 e4'. Type 'undo' to undo.")
        self.board.display()

        while not self._game_over:
            color = self.turn_mgr.current()
            print(f"{color.value}'s turn.")

            # Check / checkmate / stalemate before asking for input
            if self.detector.is_checkmate(self.board, color):
                winner = color.opponent()
                print(f"Checkmate! {winner.value} wins!")
                return
            if self.detector.is_stalemate(self.board, color):
                print("Stalemate! It's a draw.")
                return
            if self.detector.is_in_check(self.board, color):
                print(f"  {color.value} is in check!")

            raw = input("Move: ").strip()
            if raw.lower() == "undo":
                undone = self.history.undo_last(self.board)
                if undone:
                    self.turn_mgr.previous_turn()
                    print(f"  Undid {undone.piece} move.")
                    self.board.display()
                else:
                    print("  Nothing to undo.")
                continue

            move = self._parse_input(raw, color)
            if move is None:
                continue

            if self.validator.validate(move, self.board, color):
                self.board.apply_move(move)
                self.history.record(move)
                self.board.display()
                self.turn_mgr.next_turn()
```

---

Usage example:

```python
if __name__ == "__main__":
    game = Game()
    game.play()
```

To run Scholar's Mate (4-move checkmate) at the prompt, enter these moves in order:

```
e2 e4
e7 e5
f1 c4
b8 c6
d1 h5
a7 a6
h5 f7
```

White's Queen on h5 and Bishop on c4 together attack f7 — checkmate.

---

## Step-by-step walkthrough — Scholar's Mate

We trace the four key moves of the fastest checkmate in chess.

**After `e2 e4`** — White's king's pawn advances two squares. `Pawn.get_valid_moves` at (1,4) returns a double-step to (3,4) because `has_moved` is `False` and (2,4) and (3,4) are both empty.

**After `e7 e5`** — Black mirrors. Board is symmetric in the centre.

**After `f1 c4`** — White's Bishop slides diagonally from (0,5) to (3,2). `_sliding_moves` extends along the (1,1) direction: (1,4) has White's pawn — blocked. (1,-1) direction: empty until edge. The (1,1) direction from (0,5): (1,6), (2,7) — edge. The diagonal towards (3,2): (1,4) has pawn — blocked that direction. The correct diagonal (decreasing row, decreasing col from f1 going towards c4) reaches (3,2) unobstructed.

**After `d1 h5`** — White's Queen moves to (4,7). Now both the Queen and Bishop have diagonals converging on f7 — Position (1,5), guarded only by Black's King.

**After `h5 f7` — Checkmate.** `MoveValidator.validate` checks: Queen at (4,7) can reach (1,5) diagonally, the square has Black's Pawn (captured), and applying the move does not leave White's king in check. `board.apply_move` places the Queen on (1,5) and removes the pawn. `CheckDetector.is_checkmate(board, BLACK)` is now called: Black's king at (0,4) is attacked by the White Queen on (1,5). `get_all_legal_moves` iterates every Black piece — no move exists that removes the attack. Returns `True`. Game prints `"Checkmate! White wins!"`.

---

## Common interview mistakes

1. **All move logic in `Board` (God object).** Writing `board.get_rook_moves()`, `board.get_knight_moves()` etc. as methods on `Board` means every new piece requires editing the central state class. Use polymorphism: each piece class owns its own `get_valid_moves`.

2. **Not checking if a move leaves the king in check.** Generating moves from the piece's movement rules alone is insufficient. A bishop move that unblocks a rook attack on the king is illegal. `MoveValidator` must apply the move, test for check, then undo.

3. **Hardcoding starting positions.** Writing `Position(0, 0)` for a Rook in three different places. `Board._setup()` is the single source of truth for the starting position — change it there and it propagates everywhere.

4. **Not treating `Position` as a value object.** Using plain tuples or lists as dict keys. Mutable lists cannot be dict keys. A `frozen=True` dataclass gives hashability and value equality for free.

5. **Forgetting `has_moved`.** Pawn double-step is only legal on the first move. Castling requires that neither the King nor the chosen Rook has moved. Without `has_moved` on `Piece`, you cannot enforce these rules without scanning move history on every turn.

---

## Key patterns used

| Pattern | Where it appears | Why it helps |
|---|---|---|
| **Polymorphism / Strategy** | Each `Piece` subclass implements `get_valid_moves` | Add a new piece without touching any existing class |
| **Command** | `Move` + `MoveHistory` | Store half-moves as immutable objects for undo |
| **Facade** | `Game` class | One entry point hides Board, Validator, Detector |
| **Single Responsibility** | `Board` (state), `CheckDetector` (evaluation), `MoveValidator` (legality) | Each class has exactly one reason to change |
| **Open/Closed Principle** | New piece = new subclass, zero changes elsewhere | Extend without modifying existing code |


---

[← Back to Game Template](template.md)
