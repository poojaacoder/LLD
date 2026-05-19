# 04 — Stack Overflow

## What is this problem testing?

This problem tests your ability to model a content hierarchy (questions contain answers, which contain comments), share behaviour cleanly across multiple classes using mixins, and build a reputation system that reacts to events rather than mutating a single counter. Interviewers are watching for whether you reach for mixins to eliminate duplicated vote/comment logic, whether you separate search from storage, and whether you enforce role-based access without scattering `if moderator` checks everywhere.

---

## Requirements

- Users can post Questions and Answers
- Questions have tags (e.g. `python`, `java`)
- Users can vote questions and answers up or down — but not their own content
- The question author can mark one answer as the accepted answer
- Reputation changes on events: upvote received = +10, downvote received = −2, answer accepted = +15
- Users, questions, and answers can have Comments attached to them
- Search by keyword and/or tags
- Roles: Regular User, Moderator (can delete any post), Admin

---

## Clarifying questions to ask in the interview

1. **Can a user change their vote?** — Does casting a second vote cancel the first, flip it, or raise an error?
2. **What reputation is required to vote?** — Stack Overflow requires 15 reputation. Should we enforce a threshold?
3. **Is search exact-match or full-text?** — Are we matching exact keywords and tags, or do we need fuzzy/partial matching?
4. **Can a question have multiple accepted answers?** — Or is it strictly one, and marking a new one un-marks the old?
5. **What can a Moderator do that a Regular User cannot?** — Can they delete comments? Edit posts? Or only delete questions and answers?

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| User with a role and reputation | `User` |
| Question with tags and answers | `Question` |
| Answer that belongs to a question | `Answer` |
| Comment on a question or answer | `Comment` |
| Tag (e.g. `python`) | `Tag` |
| A single up or downvote | `Vote` (expressed as `VoteType` enum) |
| The voting capability | `Votable` mixin |
| The commenting capability | `Commentable` mixin |
| Service that finds questions | `SearchService` |
| Top-level coordinator | `StackOverflowService` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Post a question | `post_question(user, title, body, tags)` | `StackOverflowService` |
| Post an answer | `post_answer(user, body)` | `Question` / `StackOverflowService` |
| Vote on content | `vote(user, vote_type)` | `Votable` mixin |
| Accept an answer | `accept_answer(answer)` | `Question` / `StackOverflowService` |
| Add a comment | `add_comment(user, text)` | `Commentable` mixin |
| Search by keyword / tag | `search(keyword, tags)` | `SearchService` |
| Delete any post | `delete_post(actor, post)` | `StackOverflowService` |
| Check voting eligibility | `can_vote()` | `User` |
| Check delete permission | `can_delete(post)` | `User` |

---

## Relationships

```
StackOverflowService (facade)
 ├── User  HAS reputation (int)
 │         HAS role (UserRole enum)
 │         can_vote()  /  can_delete(post)
 │
 ├── Question(Votable, Commentable)
 │    ├── HAS-MANY Answer
 │    ├── HAS-MANY Tag
 │    ├── HAS-ONE  accepted_answer (Optional)
 │    └── post_answer()  /  accept_answer()
 │
 ├── Answer(Votable, Commentable)
 │    └── HAS-ONE question (back-reference)
 │
 ├── Comment  HAS-ONE author, text, timestamp
 │
 ├── Votable mixin
 │    └── vote(user, vote_type) — shared by Question AND Answer
 │
 ├── Commentable mixin
 │    └── add_comment(user, text) — shared by Question AND Answer
 │
 └── SearchService
      └── index_question(q)  /  search(keyword, tags)
```

> Think of it like a library notice board. A `Question` is a sheet of paper pinned to the board with sticky notes (`Comments`) and reply sheets (`Answers`) attached. Anyone walking past can give it a thumbs-up or thumbs-down sticker (`Vote`). The librarian (`Moderator`) can tear down any sheet. The reputation counter on your library card goes up each time someone rates your contribution.

---

## Design decisions

### 1. `Votable` as a mixin — avoid duplicating vote logic

**Decision:** Both `Question` and `Answer` inherit from a `Votable` mixin that contains all vote-handling code.

**Why:** Without the mixin, you would write an identical `_votes` dict, self-vote guard, double-vote guard, and `vote_count` property in both classes. Any bug fix has to be applied twice. The mixin means the logic lives once.

**Alternative considered:** A standalone `VoteService`. Rejected because it requires passing objects around and adds indirection without meaningful benefit at this scale.

### 2. `Commentable` as a mixin — same reason

**Decision:** `Question` and `Answer` both inherit `Commentable`, which owns `_comments` and `add_comment`.

**Why:** DRY — the comment model is identical for both content types. Mixing it in keeps each class focused on its own concerns.

### 3. Reputation is event-driven, not hardcoded in `User`

**Decision:** `User.reputation` is mutated by a `_apply_reputation_event(event)` method called from `vote()` and `accept_answer()`. Point values live in `ReputationEvent` enum members.

**Why:** If you hard-code `user.reputation += 10` inside `Votable.vote()`, changing the rules means hunting down every site where points are awarded. Centralising points in the enum and routing all changes through one method means you change the number in exactly one place.

**Alternative considered:** An `Observer` / event bus. Worth mentioning in the interview — for large systems you would emit `VoteEvent` and let a `ReputationService` handle it asynchronously. At this scale, direct mutation is simpler.

### 4. Self-vote prevention in `Votable.vote()`

**Decision:** The `vote()` method checks `if user.user_id == self.author.user_id: raise ValueError`.

**Why:** The rule "you cannot vote on your own content" is universal across all votable content types. Putting the guard in the mixin means it applies to both Questions and Answers automatically.

### 5. Separate `SearchService` (Single Responsibility Principle)

**Decision:** `SearchService` maintains its own index (a dict mapping keyword and tag to a list of questions). `Question` knows nothing about search.

**Why:** If `Question` owned search, adding a new indexing strategy (e.g. Elasticsearch) would require changing the `Question` class. `SearchService` can be swapped or upgraded independently.

### 6. Role-based access via `User.can_delete(post)`

**Decision:** `can_delete(post)` returns `True` if the user is the post's author, or if the user's role is `MODERATOR` or `ADMIN`.

**Why:** A single method encapsulates the permission logic. `StackOverflowService.delete_post()` calls it and raises if it returns `False` — callers never repeat the `if moderator or owner` pattern.

---

## Complete Code

Plain Python with no third-party dependencies. Read through the comments — each one explains *why*, not just *what*.

```python
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional
import uuid


# ── Enums ──────────────────────────────────────────────────────────────────────
# Enums give names to concepts that would otherwise be bare integers or strings.
# VoteType.UPVOTE is far clearer than the integer 1.

class VoteType(Enum):
    UPVOTE   = auto()
    DOWNVOTE = auto()


class UserRole(Enum):
    REGULAR   = auto()
    MODERATOR = auto()
    ADMIN     = auto()


class ReputationEvent(Enum):
    """
    Each member is the point change triggered by that event.
    Centralising numbers here means changing a rule is a one-line edit.
    """
    UPVOTE_RECEIVED   =  10
    DOWNVOTE_RECEIVED =  -2
    ANSWER_ACCEPTED   =  15
    UPVOTE_GIVEN      =  -1   # small cost for casting an upvote (mirrors real SO)


# ── User ───────────────────────────────────────────────────────────────────────
# User is a domain object. It knows its own reputation and role.
# It does NOT know how to search, index, or manage the full post graph —
# those concerns belong to SearchService and StackOverflowService.

class User:
    def __init__(self, username: str, role: UserRole = UserRole.REGULAR) -> None:
        self.user_id   = str(uuid.uuid4())
        self.username  = username
        self.reputation: int = 1   # new users start at 1 (mirrors real SO)
        self.role      = role

    # ── Permission helpers ──────────────────────────────────────────────────

    def can_vote(self) -> bool:
        # On real Stack Overflow you need ≥15 reputation to vote.
        # We enforce the same rule here.
        return self.reputation >= 15

    def can_delete(self, post: "Question | Answer") -> bool:
        # Owners can always delete their own content.
        # Moderators and Admins can delete anyone's content.
        is_owner = post.author.user_id == self.user_id
        is_privileged = self.role in (UserRole.MODERATOR, UserRole.ADMIN)
        return is_owner or is_privileged

    # ── Reputation mutation ─────────────────────────────────────────────────

    def _apply_reputation_event(self, event: ReputationEvent) -> None:
        # All reputation changes flow through this single method.
        # Never mutate self.reputation directly from outside this class.
        self.reputation += event.value

    def __repr__(self) -> str:
        return f"User({self.username!r}, rep={self.reputation})"


# ── Comment / Tag dataclasses ──────────────────────────────────────────────────
# Dataclasses are ideal for simple value-carrying objects.
# @dataclass auto-generates __init__, __repr__, and __eq__.

@dataclass
class Comment:
    comment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    author:     User = field(default=None)       # type: ignore[assignment]
    text:       str  = ""
    timestamp:  datetime = field(default_factory=datetime.utcnow)


@dataclass
class Tag:
    name: str   # e.g. "python", "java", "algorithms"

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Tag) and self.name == other.name


# ── Mixins ─────────────────────────────────────────────────────────────────────
# A mixin is a class designed to be *mixed into* other classes via multiple
# inheritance. It provides a well-defined slice of behaviour.
#
# Rule of thumb: a mixin should never stand on its own as a meaningful object.
# Votable on its own makes no sense — but Question(Votable, Commentable) does.

class Votable:
    """
    Mixin that gives any content type the ability to receive votes.

    Inheriting classes must have a self.author attribute (type User).
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

    # We use __init__ carefully in mixins. Because Python uses C3 MRO,
    # we call super().__init__(**kwargs) to cooperate with other mixins.
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)          # cooperate with Commentable / base class
        self._votes: Dict[str, VoteType] = {}  # user_id → VoteType

    @property
    def vote_count(self) -> int:
        # +1 for each upvote, -1 for each downvote
        return sum(
            1 if vt == VoteType.UPVOTE else -1
            for vt in self._votes.values()
        )

    def vote(self, user: User, vote_type: VoteType) -> None:
        # Guard 1: reputation threshold
        if not user.can_vote():
            raise PermissionError(
                f"{user.username} needs ≥15 reputation to vote "
                f"(current: {user.reputation})"
            )

        # Guard 2: no self-voting
        if user.user_id == self.author.user_id:   # type: ignore[attr-defined]
            raise ValueError("You cannot vote on your own content")

        # Guard 3: no double-voting (casting the same vote twice is ignored)
        if self._votes.get(user.user_id) == vote_type:
            raise ValueError("You have already cast this vote")

        # Remove old vote (if switching from up→down or down→up)
        old_vote = self._votes.get(user.user_id)

        # Record the new vote
        self._votes[user.user_id] = vote_type

        # Apply reputation to the content's author
        author: User = self.author   # type: ignore[attr-defined]
        if vote_type == VoteType.UPVOTE:
            author._apply_reputation_event(ReputationEvent.UPVOTE_RECEIVED)
            # If the voter is switching from a downvote, reverse the old penalty
            if old_vote == VoteType.DOWNVOTE:
                author._apply_reputation_event(
                    ReputationEvent.DOWNVOTE_RECEIVED  # cancel the earlier deduction
                    # We re-add the value, so we pass the inverse effect manually:
                )
                # Simpler: just add back the downvote penalty directly
                author.reputation -= ReputationEvent.DOWNVOTE_RECEIVED.value
        else:  # DOWNVOTE
            author._apply_reputation_event(ReputationEvent.DOWNVOTE_RECEIVED)
            if old_vote == VoteType.UPVOTE:
                # Reverse the earlier upvote bonus
                author.reputation -= ReputationEvent.UPVOTE_RECEIVED.value

        # Small reputation cost to the voter for casting an upvote
        if vote_type == VoteType.UPVOTE:
            user._apply_reputation_event(ReputationEvent.UPVOTE_GIVEN)


class Commentable:
    """
    Mixin that gives any content type the ability to collect Comments.
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._comments: List[Comment] = []

    def add_comment(self, user: User, text: str) -> Comment:
        comment = Comment(author=user, text=text)
        self._comments.append(comment)
        return comment

    @property
    def comments(self) -> List[Comment]:
        # Return a copy so callers cannot mutate the internal list directly
        return list(self._comments)


# ── Question ───────────────────────────────────────────────────────────────────
# Question inherits Votable and Commentable.
# Python resolves method calls using C3 MRO — both mixins' __init__ are called
# in the right order because they all call super().__init__(**kwargs).

class Question(Votable, Commentable):
    def __init__(
        self,
        author:  User,
        title:   str,
        body:    str,
        tags:    List[Tag],
    ) -> None:
        # Pass remaining kwargs up the MRO chain (satisfies cooperative init)
        super().__init__()
        self.question_id:      str = str(uuid.uuid4())
        self.author:           User = author
        self.title:            str  = title
        self.body:             str  = body
        self.tags:             List[Tag] = tags
        self._answers:         List["Answer"] = []
        self.accepted_answer:  Optional["Answer"] = None
        self.created_at:       datetime = datetime.utcnow()

    # ── Answer management ────────────────────────────────────────────────────

    def post_answer(self, user: User, body: str) -> "Answer":
        answer = Answer(author=user, body=body, question=self)
        self._answers.append(answer)
        return answer

    def accept_answer(self, answer: "Answer") -> None:
        # Only the question's author is allowed to mark an accepted answer
        if answer not in self._answers:
            raise ValueError("That answer does not belong to this question")
        self.accepted_answer = answer
        answer.is_accepted = True
        # Reward the answer's author
        answer.author._apply_reputation_event(ReputationEvent.ANSWER_ACCEPTED)

    @property
    def answers(self) -> List["Answer"]:
        return list(self._answers)

    @property
    def is_answered(self) -> bool:
        return self.accepted_answer is not None

    def __repr__(self) -> str:
        return f"Question({self.title!r}, votes={self.vote_count})"


# ── Answer ─────────────────────────────────────────────────────────────────────

class Answer(Votable, Commentable):
    def __init__(self, author: User, body: str, question: Question) -> None:
        super().__init__()
        self.answer_id:  str      = str(uuid.uuid4())
        self.author:     User     = author
        self.body:       str      = body
        self.question:   Question = question
        self.is_accepted: bool    = False
        self.created_at: datetime = datetime.utcnow()

    def __repr__(self) -> str:
        marker = " ✓" if self.is_accepted else ""
        return f"Answer({self.author.username!r}{marker}, votes={self.vote_count})"


# ── SearchService ──────────────────────────────────────────────────────────────
# Keeping search logic here (rather than on Question) respects SRP:
# Question knows about Q&A content; SearchService knows about indexing.

class SearchService:
    def __init__(self) -> None:
        # keyword → list of questions containing that keyword in title or body
        self._keyword_index: Dict[str, List[Question]] = {}
        # tag name → list of questions with that tag
        self._tag_index:     Dict[str, List[Question]] = {}

    def index_question(self, question: Question) -> None:
        # Index every word in the title and body
        words = (question.title + " " + question.body).lower().split()
        for word in words:
            self._keyword_index.setdefault(word, [])
            if question not in self._keyword_index[word]:
                self._keyword_index[word].append(question)

        # Index by tag
        for tag in question.tags:
            self._tag_index.setdefault(tag.name, [])
            if question not in self._tag_index[tag.name]:
                self._tag_index[tag.name].append(question)

    def search(
        self,
        keyword: Optional[str] = None,
        tags:    Optional[List[str]] = None,
    ) -> List[Question]:
        """
        Return questions matching the keyword AND/OR any of the provided tags.
        If both are given, results must satisfy both filters (AND logic).
        """
        results: Optional[set] = None

        if keyword:
            kw_matches = set(self._keyword_index.get(keyword.lower(), []))
            results = kw_matches if results is None else results & kw_matches

        if tags:
            for tag_name in tags:
                tag_matches = set(self._tag_index.get(tag_name, []))
                results = tag_matches if results is None else results & tag_matches

        if results is None:
            return []

        # Sort by vote count descending so the best answers surface first
        return sorted(results, key=lambda q: q.vote_count, reverse=True)


# ── StackOverflowService (Facade) ──────────────────────────────────────────────
# All external code talks to this one class.
# It coordinates User, Question, Answer, SearchService — callers never need
# to import or instantiate any of the inner classes directly.

class StackOverflowService:
    def __init__(self) -> None:
        self._users:     Dict[str, User]     = {}   # user_id → User
        self._questions: Dict[str, Question] = {}   # question_id → Question
        self._search     = SearchService()

    # ── User management ──────────────────────────────────────────────────────

    def register_user(
        self,
        username: str,
        role: UserRole = UserRole.REGULAR,
    ) -> User:
        user = User(username, role)
        self._users[user.user_id] = user
        return user

    # ── Content creation ─────────────────────────────────────────────────────

    def post_question(
        self,
        user:  User,
        title: str,
        body:  str,
        tags:  List[str],
    ) -> Question:
        tag_objects = [Tag(t) for t in tags]
        question = Question(author=user, title=title, body=body, tags=tag_objects)
        self._questions[question.question_id] = question
        self._search.index_question(question)
        return question

    def post_answer(self, user: User, question: Question, body: str) -> Answer:
        return question.post_answer(user, body)

    # ── Voting ────────────────────────────────────────────────────────────────

    def vote_question(
        self, user: User, question: Question, vote_type: VoteType
    ) -> None:
        question.vote(user, vote_type)

    def vote_answer(
        self, user: User, answer: Answer, vote_type: VoteType
    ) -> None:
        answer.vote(user, vote_type)

    # ── Accepting an answer ───────────────────────────────────────────────────

    def accept_answer(self, requester: User, answer: Answer) -> None:
        # Only the question author may accept an answer
        if requester.user_id != answer.question.author.user_id:
            raise PermissionError("Only the question author can accept an answer")
        answer.question.accept_answer(answer)

    # ── Comments ──────────────────────────────────────────────────────────────

    def add_comment(
        self,
        user:    User,
        target:  "Question | Answer",
        text:    str,
    ) -> Comment:
        return target.add_comment(user, text)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        keyword: Optional[str] = None,
        tags:    Optional[List[str]] = None,
    ) -> List[Question]:
        return self._search.search(keyword=keyword, tags=tags)

    # ── Moderation ────────────────────────────────────────────────────────────

    def delete_post(
        self,
        actor: User,
        post:  "Question | Answer",
    ) -> None:
        if not actor.can_delete(post):
            raise PermissionError(
                f"{actor.username} does not have permission to delete this post"
            )
        if isinstance(post, Question):
            self._questions.pop(post.question_id, None)
            print(f"[DELETE] Question {post.title!r} removed by {actor.username}")
        elif isinstance(post, Answer):
            post.question._answers.remove(post)
            print(f"[DELETE] Answer by {post.author.username} removed by {actor.username}")


# ── Usage ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    so = StackOverflowService()

    # Register users. Alice, Bob, and Charlie all start at 1 reputation.
    # We give them a head-start so they can vote (need ≥15).
    alice   = so.register_user("Alice")
    bob     = so.register_user("Bob")
    charlie = so.register_user("Charlie")
    mod     = so.register_user("Moderator_Mo", role=UserRole.MODERATOR)

    # Manually bump starting reputation so our demo users can vote
    alice.reputation   = 100
    bob.reputation     = 100
    charlie.reputation = 100

    # ── Step 1: Alice posts a question ────────────────────────────────────────
    q = so.post_question(
        alice,
        title="How do I reverse a list in Python?",
        body="I have a list and want to reverse it efficiently.",
        tags=["python", "list"],
    )
    print(f"Question posted: {q}")
    print(f"Alice rep after posting: {alice.reputation}\n")

    # ── Step 2: Bob and Charlie each post an answer ───────────────────────────
    a_bob     = so.post_answer(bob,     q, "Use list.reverse() to reverse in-place.")
    a_charlie = so.post_answer(charlie, q, "Use slicing: my_list[::-1] for a new reversed list.")
    print(f"Bob's answer:     {a_bob}")
    print(f"Charlie's answer: {a_charlie}\n")

    # ── Step 3: Alice upvotes Bob's answer ────────────────────────────────────
    so.vote_answer(alice, a_bob, VoteType.UPVOTE)
    print(f"After Alice upvotes Bob's answer:")
    print(f"  Bob's vote count:  {a_bob.vote_count}")
    print(f"  Bob rep:           {bob.reputation}")   # was 100, now 110
    print(f"  Alice rep (cost):  {alice.reputation}\n")  # was 100, now 99

    # ── Step 4: Charlie upvotes Bob's answer too ──────────────────────────────
    so.vote_answer(charlie, a_bob, VoteType.UPVOTE)
    print(f"After Charlie upvotes Bob's answer:")
    print(f"  Bob's vote count:  {a_bob.vote_count}")
    print(f"  Bob rep:           {bob.reputation}\n")  # now 120

    # ── Step 5: Alice accepts Bob's answer ────────────────────────────────────
    so.accept_answer(alice, a_bob)
    print(f"Alice accepted Bob's answer: {a_bob}")
    print(f"Bob rep after acceptance:    {bob.reputation}")  # +15 → 135
    print(f"Question is_answered:        {q.is_answered}\n")

    # ── Step 6: Add a comment ─────────────────────────────────────────────────
    so.add_comment(charlie, a_bob, "Great answer! Very clear.")
    print(f"Comments on Bob's answer: {a_bob.comments}\n")

    # ── Step 7: Search ────────────────────────────────────────────────────────
    results = so.search(keyword="reverse", tags=["python"])
    print(f"Search results for 'reverse' + tag 'python': {results}\n")

    # ── Step 8: Moderator deletes Charlie's answer ────────────────────────────
    so.delete_post(mod, a_charlie)
    print(f"Remaining answers on question: {q.answers}\n")

    # ── Final reputation summary ──────────────────────────────────────────────
    print("── Final reputation ──")
    for user in [alice, bob, charlie, mod]:
        print(f"  {user.username}: {user.reputation}")
```

---

## Step-by-step walkthrough

```python
so = StackOverflowService()
alice = so.register_user("Alice")
alice.reputation = 100
```
A fresh service is created. Alice is registered — she gets a unique `user_id`, starts with `role=REGULAR`, and we manually set `reputation=100` so the demo can vote immediately (normally she would earn this over time).

```python
q = so.post_question(
    alice,
    title="How do I reverse a list in Python?",
    body="I have a list and want to reverse it efficiently.",
    tags=["python", "list"],
)
```
`StackOverflowService.post_question()` creates `Tag("python")` and `Tag("list")` objects, wraps them in a `Question`, stores the question internally, and calls `SearchService.index_question(q)`. The search service splits the title and body into words and records this question under each word. It also records it under tag names `"python"` and `"list"`.

**What just happened?** One call to the facade created and indexed the question. Alice never touches `SearchService` directly.

```python
a_bob = so.post_answer(bob, q, "Use list.reverse() to reverse in-place.")
```
`so.post_answer()` delegates to `question.post_answer(bob, body)`, which creates an `Answer` object and appends it to `question._answers`. Bob's answer now has `vote_count = 0` and `is_accepted = False`.

```python
so.vote_answer(alice, a_bob, VoteType.UPVOTE)
```
`vote_answer` calls `a_bob.vote(alice, VoteType.UPVOTE)` — the `Votable` mixin kicks in. It checks: (1) Alice has ≥15 rep ✓, (2) Alice is not Bob ✓, (3) Alice has not already upvoted ✓. It records `_votes[alice.user_id] = UPVOTE`, calls `bob._apply_reputation_event(UPVOTE_RECEIVED)` (+10), and deducts 1 from Alice's reputation (`UPVOTE_GIVEN`).

**What just happened?** Bob's rep went from 100 → 110. Alice's rep went from 100 → 99. The vote count on `a_bob` is now +1.

```python
so.accept_answer(alice, a_bob)
```
The service verifies Alice is the question author, then calls `q.accept_answer(a_bob)`. This sets `q.accepted_answer = a_bob`, flips `a_bob.is_accepted = True`, and calls `bob._apply_reputation_event(ANSWER_ACCEPTED)` (+15). Bob is now at 125 reputation (110 + 15, before Charlie's upvote in the demo).

**What just happened?** The question is now `is_answered = True`. Bob earned 15 bonus reputation. Alice paid nothing — accepting an answer is free.

```python
results = so.search(keyword="reverse", tags=["python"])
```
`SearchService.search()` looks up `"reverse"` in `_keyword_index` (returns a set of matching questions), then intersects with questions tagged `"python"`. Alice's question matches both filters, so it is returned.

```python
so.delete_post(mod, a_charlie)
```
`mod.can_delete(a_charlie)` returns `True` because `mod.role == MODERATOR`. The service removes Charlie's answer from `q._answers`.

---

## Common interview mistakes

1. **Duplicating vote logic in both `Question` and `Answer`.** Writing a `vote()` method on each class separately means any fix (e.g., adding a self-vote guard) must be applied in two places. Use a `Votable` mixin and write it once.

2. **No self-vote prevention.** Forgetting this rule is one of the most common omissions. Always add `if user.user_id == self.author.user_id: raise ValueError` as the first check inside `vote()`.

3. **Hard-coding reputation deltas in `User`.** Writing `user.reputation += 10` scattered across `vote()`, `accept_answer()`, and anywhere else points are awarded makes it impossible to change the rules in one place. Put all point values in `ReputationEvent` and route every change through `user._apply_reputation_event()`.

4. **No role-based access control.** Implementing delete as `post.delete()` with no permission check means any user can delete any post. Always gate destructive operations with a `can_delete()` call that checks role and ownership.

5. **Implementing search as a linear scan.** Writing `[q for q in all_questions if keyword in q.body]` is O(n) and re-reads every question on every search. A real system uses a pre-built index. Even in an interview, mention that `SearchService.index_question()` maintains a dict so lookups are O(1) per keyword.

---

## Key patterns used

| Pattern | Where it appears | Why it helps |
|---|---|---|
| **Mixin** | `Votable`, `Commentable` | Share behaviour across `Question` and `Answer` without a forced inheritance chain |
| **Facade** | `StackOverflowService` | Single clean entry point — callers never import inner classes |
| **Strategy** | `SearchService` (swappable ranking) | `search()` could delegate to a `RankingStrategy` without changing `SearchService`'s interface |
| **Observer** (mentioned) | Reputation updates | In a large system, vote events would be published to a bus and `ReputationService` would listen — decouple producers from consumers |
| **Enumeration** | `VoteType`, `UserRole`, `ReputationEvent` | Prevent magic strings and numbers; make invalid states unrepresentable |
| **Dataclass** | `Comment`, `Tag` | Lightweight value objects with auto-generated `__init__` and `__repr__` |
