# Template 04: Social Feed

---

## 1. What is the Social / Feed Template?

Think of Twitter, Instagram, or LinkedIn. Users sign up, follow other users, post content, and see a personalised stream of posts from people they follow. On top of that, they can like, comment, and get notified when something interesting happens.

In plain English: **users connect with each other, create content, and see a personalised feed of content from the people they follow.**

This template covers the core patterns that make all of those systems tick, at a level you can sketch out in a 45-minute interview.

---

## 2. How to Recognise This Template

When the interviewer says any of these words, reach for this template:

| Trigger word | What it maps to |
|---|---|
| followers / following | `User` with a social graph |
| feed / timeline | `FeedService` |
| post / tweet / question | `Content` / `Post` |
| like / upvote / react | `Interaction` |
| comment / reply | `Comment` (a child `Content`) |
| share / retweet | `Share` interaction |
| notification / alert | `NotificationService` (Observer) |
| fan-out / delivery | push vs pull feed model |

If you hear **at least two** of these signals, this is almost certainly a Social Feed problem.

---

## 3. Real-World Examples

- **Twitter / X** — tweets, retweets, likes, chronological and ranked feeds
- **Instagram** — photos/reels, stories, explore feed
- **LinkedIn** — posts, reactions, connections vs followers
- **Stack Overflow** — questions, answers, upvotes, reputation, notifications
- **Reddit** — posts, comments, upvotes, subreddits, frontpage feed
- **WhatsApp Groups** — messages, reactions, group membership

All of these share the same skeleton. The details differ, but the building blocks are identical.

---

## 4. Core Building Blocks

> **User** is like a person at a party — they have a name tag (profile), a list of people they are listening to (following), and a list of people who are listening to them (followers).

> **Content** is like a sticky note posted on a bulletin board — it has an author, a body, and a timestamp.

> **Connection** is the act of deciding to follow someone — it is a directed edge in a social graph (A follows B does not mean B follows A).

> **Feed** is like a personalised newspaper that assembles itself from all the bulletin boards of people you follow.

> **Interaction** is anything you do *to* a piece of content — sticking a thumbs-up on it (like), writing a response (comment), or passing it to your own bulletin board (share).

> **Notification** is a tap on the shoulder — the system tells you that something relevant happened (someone followed you, liked your post, or replied to you).

---

## 5. Class Relationship Diagram

```
User ──follows──> User
 |
 └── creates ──> Post
                  └── has many ──> Interaction (Like / Comment / Share)

FeedService
 └── uses ──> FeedStrategy  <<abstract>>
                  ├── ChronologicalFeed   (newest first)
                  └── RankedFeed          (scored by engagement)

NotificationService  (Observer pattern)
 └── notifies on:
       - new follower
       - like on your post
       - comment on your post
```

**What just happened?**
- `User` is both a producer (creates posts) and a consumer (reads a feed).
- `FeedStrategy` is swappable — swap `ChronologicalFeed` for `RankedFeed` without touching `FeedService`.
- `NotificationService` listens for events and delivers alerts without the core domain classes knowing it exists.

---

## 6. Two Feed Generation Approaches

### Approach A — Pull Model (fan-out on read)

The feed is generated *on demand* when the user opens the app. The system queries all followees and merges their recent posts at read time.

```python
# Pull model: assemble the feed fresh every time the user requests it
def get_feed_pull(user: User, all_posts: list[Post], limit: int = 20) -> list[Post]:
    """
    Collect every post written by people this user follows,
    sort them newest-first, and return the top `limit` posts.
    """
    feed_posts = [
        post for post in all_posts
        if post.author_id in user.following   # only posts from people I follow
    ]
    feed_posts.sort(key=lambda p: p.created_at, reverse=True)
    return feed_posts[:limit]
```

**Pros:** Always fresh. No extra storage needed. Simple to implement.
**Cons:** Slow for users who follow thousands of people (heavy read-time query).

---

### Approach B — Push Model (fan-out on write)

When a user publishes a post, the system *immediately pushes* that post into every follower's pre-built feed cache. Reading the feed is just fetching from the cache — it is instant.

```python
# Push model: when a post is created, push it into every follower's feed cache
def on_post_created(post: Post, author: User, feed_cache: dict[str, list[Post]]) -> None:
    """
    Called the moment a new post is saved.
    Push the post into each follower's personal feed cache.
    """
    for follower_id in author.followers:
        feed_cache[follower_id].insert(0, post)   # newest first
        # In production you'd cap the cache size, e.g. keep only last 500 posts
```

**Pros:** Reads are O(1) — just fetch from cache. Great for most users.
**Cons:** If a celebrity (10 million followers) posts, you must update 10 million caches — a huge write spike.

**Interview tip:** The classic answer for celebrity / high-follower accounts is a **hybrid model** — use push for normal users, and fall back to pull for verified accounts with massive follower counts, merging the two results at read time.

---

## 7. Generic Skeleton Code

The code below is intentionally minimal. In an interview you would write these classes on a whiteboard or in a shared editor, so every line counts.

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


# ---------------------------------------------------------------------------
# Core domain objects
# ---------------------------------------------------------------------------

@dataclass
class Post:
    """A piece of content created by a user."""
    post_id: str
    author_id: str
    body: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    likes: int = 0
    comments: list[str] = field(default_factory=list)  # comment IDs


class User:
    """
    Represents a person on the platform.

    Think of `followers` as the audience list and `following` as
    the list of bulletin boards this user has subscribed to.
    """

    def __init__(self, user_id: str, name: str) -> None:
        self.user_id = user_id
        self.name = name
        self.followers: set[str] = set()   # user_ids of people who follow me
        self.following: set[str] = set()   # user_ids of people I follow
        self.posts: list[Post] = []

    def follow(self, other: User) -> None:
        """I start following `other`. This is a directed action."""
        self.following.add(other.user_id)
        other.followers.add(self.user_id)

    def create_post(self, body: str) -> Post:
        """Create a new post and attach it to this user's profile."""
        post = Post(
            post_id=f"post_{len(self.posts) + 1}",
            author_id=self.user_id,
            body=body,
        )
        self.posts.append(post)
        return post

    def __repr__(self) -> str:
        return f"User({self.name!r})"


# ---------------------------------------------------------------------------
# Feed strategies (Strategy pattern)
# ---------------------------------------------------------------------------

class FeedStrategy(ABC):
    """
    Abstract base: every concrete strategy must implement `generate`.

    Using an abstract class here lets us swap feed algorithms without
    changing FeedService at all — this is the Strategy pattern.
    """

    @abstractmethod
    def generate(self, user: User, all_posts: list[Post], limit: int) -> list[Post]:
        """Return a personalised list of posts for `user`."""
        ...


class ChronologicalFeed(FeedStrategy):
    """Simplest possible feed: newest posts from followees, in order."""

    def generate(self, user: User, all_posts: list[Post], limit: int) -> list[Post]:
        relevant = [p for p in all_posts if p.author_id in user.following]
        relevant.sort(key=lambda p: p.created_at, reverse=True)
        return relevant[:limit]


class RankedFeed(FeedStrategy):
    """
    Scored feed: boost posts that have more likes.

    In a real system the scoring function would be much more complex
    (recency, relationship strength, media type, etc.), but this
    illustrates the concept cleanly.
    """

    def generate(self, user: User, all_posts: list[Post], limit: int) -> list[Post]:
        relevant = [p for p in all_posts if p.author_id in user.following]
        # Simple score: likes + recency bonus (newer posts score higher)
        relevant.sort(key=lambda p: p.likes, reverse=True)
        return relevant[:limit]


# ---------------------------------------------------------------------------
# Notification service (Observer pattern)
# ---------------------------------------------------------------------------

class NotificationObserver(Protocol):
    """
    Any object that wants to receive notifications must implement `notify`.

    Using `Protocol` means we never need to inherit from a base class —
    duck typing is enough.
    """

    def notify(self, event_type: str, payload: dict) -> None:
        ...


class NotificationService:
    """
    Broadcasts events to all registered observers.

    Think of this as a radio station: any listener who has tuned in
    (registered) will receive every broadcast.
    """

    def __init__(self) -> None:
        self._observers: list[NotificationObserver] = []

    def register(self, observer: NotificationObserver) -> None:
        self._observers.append(observer)

    def emit(self, event_type: str, payload: dict) -> None:
        """Fire an event. Every registered observer is called."""
        for observer in self._observers:
            observer.notify(event_type, payload)


class PrintNotificationObserver:
    """Concrete observer: just prints the notification (useful for demos)."""

    def notify(self, event_type: str, payload: dict) -> None:
        print(f"[NOTIFICATION] {event_type}: {payload}")


# ---------------------------------------------------------------------------
# Feed service (Facade)
# ---------------------------------------------------------------------------

class FeedService:
    """
    The public-facing surface for feed operations.

    It hides the complexity of strategy selection and notification
    behind a simple API. This is the Facade pattern.
    """

    def __init__(
        self,
        strategy: FeedStrategy,
        notification_service: NotificationService,
    ) -> None:
        self._strategy = strategy
        self._notifications = notification_service
        self._all_posts: list[Post] = []   # shared post store (simplified)

    def publish(self, author: User, body: str) -> Post:
        """User publishes a post; observers are notified."""
        post = author.create_post(body)
        self._all_posts.append(post)
        self._notifications.emit("new_post", {
            "author": author.name,
            "post_id": post.post_id,
        })
        return post

    def get_feed(self, user: User, limit: int = 20) -> list[Post]:
        """Return a personalised feed for `user` using the active strategy."""
        return self._strategy.generate(user, self._all_posts, limit)

    def like(self, user: User, post: Post) -> None:
        """User likes a post; the post author gets a notification."""
        post.likes += 1
        self._notifications.emit("like", {
            "liked_by": user.name,
            "post_id": post.post_id,
        })

    def follow(self, follower: User, followee: User) -> None:
        """follower starts following followee; followee gets a notification."""
        follower.follow(followee)
        self._notifications.emit("new_follower", {
            "follower": follower.name,
            "followee": followee.name,
        })


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Set up users
    alice = User("u1", "Alice")
    bob   = User("u2", "Bob")
    carol = User("u3", "Carol")

    # Set up services
    notif_service = NotificationService()
    notif_service.register(PrintNotificationObserver())

    feed_service = FeedService(
        strategy=ChronologicalFeed(),
        notification_service=notif_service,
    )

    # Alice and Carol follow Bob
    feed_service.follow(alice, bob)
    feed_service.follow(carol, bob)

    # Bob publishes two posts
    p1 = feed_service.publish(bob, "Hello world!")
    p2 = feed_service.publish(bob, "Design patterns are fun.")

    # Alice likes Bob's first post
    feed_service.like(alice, p1)

    # Alice checks her feed
    print("\n--- Alice's feed ---")
    for post in feed_service.get_feed(alice):
        print(f"  [{post.created_at.strftime('%H:%M:%S')}] {post.body}  ❤ {post.likes}")
```

**What just happened?**

1. `User.follow()` updates both sides of the social graph in one call.
2. `FeedService.publish()` saves the post *and* fires a notification — callers don't need to do both steps separately.
3. Swapping `ChronologicalFeed()` for `RankedFeed()` in the constructor changes the entire feed algorithm without touching any other class.
4. `PrintNotificationObserver` could be swapped for an `EmailObserver` or `PushNotificationObserver` without changing `NotificationService`.

---

## 8. Design Patterns Used

| Pattern | Where it appears | Why it helps |
|---|---|---|
| **Strategy** | `FeedStrategy` / `ChronologicalFeed` / `RankedFeed` | Swap feed algorithms at runtime without changing `FeedService` |
| **Observer** | `NotificationService` + observers | Decouple event producers (post, like) from consumers (email, push) |
| **Facade** | `FeedService` | Single clean API hides the complexity of strategies, notifications, and post storage |
| **Dataclass / Value Object** | `Post` | Immutable-ish data carrier; cheap to create and pass around |

---

## 9. Key Design Decisions for the Interview

### Push vs Pull feed model
- **Pull** is simpler to start with. Mention it first, then explain why it breaks at scale.
- **Push** is faster to read but creates a write-time fan-out problem for popular users.
- **Hybrid**: push for users with < N followers, pull for celebrities. This is the answer that impresses interviewers.

### Handling celebrity users (millions of followers)
- Naive push means 10M cache writes every time a celebrity posts.
- Solution: skip the push for celebrity accounts. At read time, fetch the celebrity's latest posts separately and merge with the pre-built push feed. This is sometimes called the **"celebrity exception"** pattern.

### Pagination of the feed
- Never return an unbounded list. Always accept a `cursor` or `page` parameter.
- Cursor-based pagination (keyed on `created_at` + `post_id`) is better than offset-based for live feeds because new posts can shift offset results unpredictably.

### Notification fan-out
- Each event type (like, comment, follow) can trigger multiple notification channels (in-app, email, SMS, push).
- The Observer pattern handles this cleanly — each channel is a separate observer.
- For very high volume, fan-out would happen asynchronously via a message queue (Kafka, SQS) — worth mentioning even if you don't implement it.

---

## 10. Common Mistakes

1. **Putting feed logic inside `User`.**
   `User` is a domain object. Feed generation is a service concern. Mixing them makes `User` a giant class that is impossible to unit-test.

2. **Hard-coding the feed algorithm.**
   Writing `sort by time` directly inside a `get_feed` method means you have to rewrite the whole method to add ranking. Use `FeedStrategy` so algorithms are swappable.

3. **Forgetting the social graph is directed.**
   Alice following Bob does not mean Bob follows Alice. Always update *both* `user.following` and `other.followers` when a follow action happens.

4. **Returning all posts, not paginating.**
   In a real system a user might follow thousands of accounts. Returning every post in one call will time out. Always design `get_feed` to accept a `limit` (and ideally a cursor).

5. **Coupling notification delivery to the domain action.**
   Writing `send_email(follower)` directly inside `User.follow()` means you cannot add or remove notification channels without editing the core domain. Use the Observer pattern and keep notifications entirely separate.
