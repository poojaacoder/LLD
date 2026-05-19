# 04 — Twitter / Social Media Feed

## What is this problem testing?

This problem tests your ability to model a social graph (who follows whom), design a feed generation system that can scale, wire up an event-driven notification system, and think about trade-offs between read speed and write cost. Interviewers are watching for whether you separate the feed algorithm from the service (Strategy pattern), decouple notifications from core actions (Observer pattern), and can articulate the classic push-vs-pull feed problem.

---

## Requirements

- Users can post tweets (text only, max 280 characters)
- Users can follow and unfollow other users
- Home timeline: see tweets from people you follow, newest first
- User timeline: see a specific user's own tweets, newest first
- Like and retweet a tweet
- Notifications: new follower, like on your tweet, retweet of your tweet, mention in a tweet
- Trending hashtags (basic — based on recent usage count)
- Search tweets by keyword or hashtag

---

## Clarifying questions to ask in interview

1. **Push or pull feed?** — Should the home timeline be pre-built when someone posts (push/fan-out on write), assembled on demand (pull/fan-out on read), or a hybrid? This is the single most important design question.
2. **How many followers can a user have?** — If celebrity accounts (millions of followers) are in scope, the push model will cause enormous write spikes and needs a different treatment.
3. **Are likes and retweet counts approximate or exact?** — Exact counts require locking or transactions; approximate counts (eventual consistency) are fine for a social feed.
4. **How far back does the home timeline go?** — Twitter-style systems typically cap the feed cache at ~800 tweets. Anything older is fetched from a separate archive query.
5. **Are tweets editable after posting?** — This significantly affects caching and immutability decisions.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| User | `User` |
| Tweet | `Tweet` |
| Like | tracked as a set on `Tweet` |
| Retweet | `Retweet` (or a flag on `Tweet`) |
| Follow relationship | `follow` / `unfollow` methods on `User` |
| Hashtag | `HashtagIndex` (maps tag → tweets) |
| Notification | `Notification` dataclass |
| Feed (home timeline) | `FeedStrategy` (abstract) |
| Service facade | `TwitterService` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Post a tweet | `post_tweet(content)` | `User`, `TwitterService` |
| Follow a user | `follow(other)` | `User`, `TwitterService` |
| Unfollow a user | `unfollow(other)` | `User`, `TwitterService` |
| Like a tweet | `like_tweet(user, tweet)` | `TwitterService` |
| Retweet | `retweet(user, tweet)` | `TwitterService` |
| Get home timeline | `get_home_timeline(user, limit)` | `TwitterService` |
| Get user timeline | `get_user_timeline(user, limit)` | `TwitterService` |
| Search by hashtag | `search_hashtag(tag)` | `TwitterService` |
| Get trending hashtags | `get_trending(top_n)` | `TwitterService` |
| Send notification | `notify(event, payload)` | `NotificationService` |
| Receive notification | `update(notification)` | `NotificationObserver` |

---

## Relationships

```
TwitterService (facade)
 ├── User ──HAS-MANY──► Tweet
 ├── User ──FOLLOWS──► User  (directed social graph)
 ├── Tweet ──HAS-MANY──► Like  (stored as a set of user_ids)
 ├── Tweet ──HAS-MANY──► Retweet
 ├── Tweet ──HAS-MANY──► Hashtag  (extracted at post time)
 │
 ├── FeedStrategy  <<abstract>>
 │       ├── PullFeedStrategy   (fan-out on read)
 │       └── PushFeedStrategy   (fan-out on write, uses feed cache on User)
 │
 ├── HashtagIndex  (tag → sorted list of tweets)
 │
 └── NotificationService  (Observer / Subject)
         ├── InAppNotification  (concrete observer)
         └── EmailNotification  (concrete observer)
```

> Think of Twitter as a bulletin board system. Each user has their own board (profile). When you follow someone, you are subscribing to their board. Your home feed is a daily digest assembled from every board you subscribe to. A notification is someone tapping you on the shoulder to say "hey, something happened to one of your posts."

**What just happened?**
- `TwitterService` is the single door into the system — callers never touch `User` or `Tweet` internals directly.
- `FeedStrategy` is swappable. You can start with `PullFeedStrategy` (simple) and later add `PushFeedStrategy` (fast reads) without touching `TwitterService`.
- `NotificationService` sits completely outside the core domain. Neither `Tweet` nor `User` knows notifications exist — they just do their job, and the service reacts.

---

## Why this is a Social / Feed template problem

Two challenges make this problem different from a simple CRUD system.

**Challenge 1 — Social graph traversal.** A user's home feed requires knowing every person they follow and collecting all of those people's tweets. With thousands of followees this becomes a potentially expensive query. The data structure you choose for storing the follow graph (sets, adjacency lists) directly affects how fast this query is.

**Challenge 2 — Feed generation strategy.** There are two fundamentally different approaches to building a feed, each with opposite trade-off profiles. This is the heart of the interview question. Knowing both approaches and when to use each one is what separates a good answer from a great one.

---

## Push vs Pull feed — the core trade-off

### Pull model (fan-out on read)

The feed is assembled on demand, every time the user opens the app. The system iterates all of the user's followees and merges their tweets at read time.

```python
# Pull model: build the feed fresh every time it is requested
def get_feed_pull(user: "User", limit: int = 20) -> list["Tweet"]:
    """
    Collect every tweet written by people this user follows,
    sort newest-first, and return the top `limit` results.
    """
    feed: list[Tweet] = []
    for followee_id in user.following:
        followee = user_registry[followee_id]   # look up the User object
        feed.extend(followee.tweets)
    feed.sort(key=lambda t: t.timestamp, reverse=True)
    return feed[:limit]
```

**Pro:** Always up-to-date. No extra storage. Trivially simple to implement.
**Con:** If you follow 5,000 accounts, this scans and merges up to 5,000 tweet lists every time you open the app. At scale this is extremely slow.

---

### Push model (fan-out on write)

When a user posts a tweet, the system immediately pushes that tweet into every follower's personal feed cache. Reading the feed is just returning that pre-built cache — it is nearly instant.

```python
# Push model: when a tweet is posted, fan it out to all followers immediately
def fan_out_to_followers(tweet: "Tweet", author: "User") -> None:
    """
    Called the moment a new tweet is saved.
    Insert it at the front of each follower's feed cache.
    """
    for follower_id in author.followers:
        follower = user_registry[follower_id]
        follower.feed_cache.insert(0, tweet)   # newest first
        # In production: cap the cache, e.g. keep only the last 800 tweets
        if len(follower.feed_cache) > 800:
            follower.feed_cache.pop()
```

**Pro:** Feed reads are O(1) — just fetch from cache. Great for the vast majority of users.
**Con:** A celebrity with 10 million followers triggers 10 million cache writes every time they tweet. This is called the **fan-out problem**.

---

### Hybrid model (the interview-winning answer)

Use push for ordinary users and pull for celebrities. At read time, merge the pre-built push feed with a fresh pull of any celebrities you follow.

> Think of it like a newspaper subscription. For your friends' posts (low volume), you get the paper delivered to your door each morning (push). For breaking news from major publications (celebrity accounts), you fetch the front page yourself on demand (pull). At breakfast you read both together.

```python
# Hybrid: push for normal users, pull for celebrity accounts
CELEBRITY_THRESHOLD = 100_000   # followers needed to be treated as a celebrity

def get_home_timeline_hybrid(user: "User", limit: int = 20) -> list["Tweet"]:
    # Start with the pre-built push feed (fast)
    feed = list(user.feed_cache)

    # For every celebrity the user follows, pull their tweets fresh
    for followee_id in user.following:
        followee = user_registry[followee_id]
        if len(followee.followers) >= CELEBRITY_THRESHOLD:
            feed.extend(followee.tweets[-50:])   # grab their last 50 tweets

    feed.sort(key=lambda t: t.timestamp, reverse=True)
    return feed[:limit]
```

---

## Design decisions

### 1. `FeedStrategy` as an abstract class — swap algorithms without changing `TwitterService`

If you hard-code the pull logic directly inside `TwitterService.get_home_timeline()`, you have to edit that method every time you want to change the feed algorithm. By making `FeedStrategy` an abstract class and injecting a concrete instance, you can change the entire feed mechanism by passing a different object at construction time — no other code changes.

### 2. Handling celebrity users (millions of followers)

Naively pushing to 10 million followers per tweet would take minutes and hammer the database. The hybrid model above solves this by skipping the push fan-out for celebrity accounts entirely and pulling their tweets fresh at read time. This keeps write costs manageable while keeping read costs low for most users.

### 3. Why `Tweet` should be immutable after posting

Once a tweet is out in the world, it may already be sitting in hundreds of thousands of feed caches. If you mutate a tweet in-place (e.g. fix a typo), all of those cached copies immediately show stale data. Treating `Tweet` as a value object — immutable after creation — keeps caches consistent. In practice, Twitter handles "edit tweet" by creating a new tweet with a reference to the original.

### 4. Trending hashtags — counter + time window, not a full scan

The naive approach is to scan all tweets and count hashtag occurrences. This is O(total tweets), which is unacceptably slow at scale. The correct approach is an `HashtagIndex` that maintains a running counter per hashtag. For time-windowed trending (e.g. "trending in the last hour"), you bucket counts by time window and expire old buckets.

### 5. How retweets appear in the feed

A retweet is shown as the original tweet with a "retweeted by X" label. This means `Retweet` is a thin wrapper that holds a reference to the original `Tweet` plus the retweeting user's identity. The original tweet is never copied — only referenced. This keeps storage compact and ensures that if the original tweet is updated, the retweet automatically reflects the change.

---

## Complete Code

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional
import re
import uuid


# ── Enums ──────────────────────────────────────────────────────────────────────

class NotificationType(Enum):
    NEW_FOLLOWER = auto()
    LIKE         = auto()
    RETWEET      = auto()
    MENTION      = auto()


# ── Value objects (dataclasses) ────────────────────────────────────────────────
# Dataclasses are perfect for "plain data" objects like Tweet and Notification.
# We treat Tweet as immutable after creation — see the frozen=True flag.
# frozen=True means Python will raise an error if you try to reassign any field.

@dataclass(frozen=True)
class Tweet:
    """
    An immutable record of a single tweet.

    Once posted, the content and metadata cannot change.
    Mutable counters (likes, retweets) live outside this object — on separate
    sets/dicts in TwitterService — so the dataclass can stay frozen.
    """
    tweet_id:  str
    author_id: str
    content:   str
    timestamp: datetime
    hashtags:  frozenset[str]   # extracted at post time; also immutable

    @staticmethod
    def extract_hashtags(content: str) -> frozenset[str]:
        """Pull every #word out of the tweet text and return them lowercase."""
        return frozenset(tag.lower() for tag in re.findall(r"#(\w+)", content))

    def __str__(self) -> str:
        return f"[{self.timestamp.strftime('%H:%M')}] @{self.author_id}: {self.content}"


@dataclass
class Notification:
    """A record of something that happened that the recipient should know about."""
    notif_id:  str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    notif_type: NotificationType = NotificationType.LIKE
    from_user:  str = ""          # who triggered the event
    to_user:    str = ""          # who should see this notification
    tweet:      Optional[Tweet] = None
    timestamp:  datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        base = f"[{self.notif_type.name}] from @{self.from_user} to @{self.to_user}"
        if self.tweet:
            return f"{base} on tweet '{self.tweet.content[:40]}'"
        return base


# ── Observer pattern: notification delivery ────────────────────────────────────
# NotificationObserver is the abstract "listener". Every concrete delivery
# channel (in-app, email, SMS) subclasses it and implements `update`.
# NotificationService is the "subject" — it keeps a list of observers and
# broadcasts to all of them whenever an event fires.

class NotificationObserver(ABC):
    @abstractmethod
    def update(self, notification: Notification) -> None:
        """Called by NotificationService when an event occurs."""
        ...


class InAppNotification(NotificationObserver):
    """Concrete observer: prints a notification to the console (simulates in-app alert)."""

    def update(self, notification: Notification) -> None:
        print(f"  [IN-APP] {notification}")


class EmailNotification(NotificationObserver):
    """Concrete observer: simulates sending an email."""

    def update(self, notification: Notification) -> None:
        print(f"  [EMAIL ] Sending email to @{notification.to_user}: {notification}")


class NotificationService:
    """
    Subject in the Observer pattern.

    Any component can call `notify()`. Every registered observer receives the event.
    Core domain classes (User, Tweet) never import this — they stay decoupled.
    """

    def __init__(self) -> None:
        self._observers: list[NotificationObserver] = []

    def register(self, observer: NotificationObserver) -> None:
        self._observers.append(observer)

    def notify(self, notification: Notification) -> None:
        """Broadcast a notification to all registered observers."""
        for observer in self._observers:
            observer.update(notification)


# ── User ───────────────────────────────────────────────────────────────────────
# User owns its social graph edges (followers / following) and its own tweets.
# It also holds a feed_cache list that the PushFeedStrategy writes into.

class User:
    def __init__(self, user_id: str, username: str) -> None:
        self.user_id   = user_id
        self.username  = username
        self.followers: set[str] = set()   # user_ids of people who follow ME
        self.following: set[str] = set()   # user_ids of people I follow
        self.tweets:    list[Tweet] = []
        self.feed_cache: list[Tweet] = []  # pre-built by PushFeedStrategy

    def follow(self, other: User) -> None:
        """I decide to follow `other`. Directed: other does NOT follow me back."""
        self.following.add(other.user_id)
        other.followers.add(self.user_id)

    def unfollow(self, other: User) -> None:
        """Undo a follow relationship."""
        self.following.discard(other.user_id)
        other.followers.discard(self.user_id)

    def post_tweet(self, content: str) -> Tweet:
        """Create and store a new tweet. Validates the 280-char limit."""
        if len(content) > 280:
            raise ValueError(f"Tweet too long: {len(content)} chars (max 280)")
        tweet = Tweet(
            tweet_id  = str(uuid.uuid4())[:8],
            author_id = self.user_id,
            content   = content,
            timestamp = datetime.utcnow(),
            hashtags  = Tweet.extract_hashtags(content),
        )
        self.tweets.append(tweet)
        return tweet

    def __repr__(self) -> str:
        return f"User(@{self.username})"


# ── Feed strategies (Strategy pattern) ─────────────────────────────────────────
# FeedStrategy is the abstract interface.
# TwitterService holds one concrete strategy and calls get_feed() through it.
# To switch from pull to push: change one line in TwitterService.__init__().

class FeedStrategy(ABC):
    @abstractmethod
    def get_feed(
        self,
        user: User,
        user_registry: dict[str, User],
        limit: int,
    ) -> list[Tweet]:
        """Return a home timeline for `user`, newest first, capped at `limit`."""
        ...


class PullFeedStrategy(FeedStrategy):
    """
    Fan-out on read: assemble the feed fresh every time it is requested.

    Simple and always accurate, but slow when the user follows many accounts.
    Good default for low-traffic or prototype systems.
    """

    def get_feed(
        self,
        user: User,
        user_registry: dict[str, User],
        limit: int,
    ) -> list[Tweet]:
        feed: list[Tweet] = []
        for fid in user.following:
            followee = user_registry.get(fid)
            if followee:
                feed.extend(followee.tweets)
        feed.sort(key=lambda t: t.timestamp, reverse=True)
        return feed[:limit]


class PushFeedStrategy(FeedStrategy):
    """
    Fan-out on write: the feed cache is pre-built when a tweet is posted.

    Reads are O(1). Writes are expensive for celebrity accounts.
    Use TwitterService.fan_out_tweet() to populate the cache.
    """

    def get_feed(
        self,
        user: User,
        user_registry: dict[str, User],
        limit: int,
    ) -> list[Tweet]:
        # The cache is already sorted (newest first) — just slice it
        return user.feed_cache[:limit]


# ── HashtagIndex ───────────────────────────────────────────────────────────────
# A lightweight inverted index: hashtag → list of tweets.
# Also tracks a simple counter per tag so get_trending() is O(top_n), not O(all tweets).

class HashtagIndex:
    def __init__(self) -> None:
        self._index:   dict[str, list[Tweet]] = {}   # tag → tweets
        self._counter: dict[str, int] = {}           # tag → usage count

    def index_tweet(self, tweet: Tweet) -> None:
        """Add a tweet to every hashtag it contains."""
        for tag in tweet.hashtags:
            self._index.setdefault(tag, []).append(tweet)
            self._counter[tag] = self._counter.get(tag, 0) + 1

    def search(self, tag: str) -> list[Tweet]:
        """Return all tweets containing `tag`, newest first."""
        tag = tag.lstrip("#").lower()
        tweets = self._index.get(tag, [])
        return sorted(tweets, key=lambda t: t.timestamp, reverse=True)

    def get_trending(self, top_n: int = 5) -> list[tuple[str, int]]:
        """Return the top_n hashtags by usage count as (tag, count) pairs."""
        sorted_tags = sorted(self._counter.items(), key=lambda x: x[1], reverse=True)
        return sorted_tags[:top_n]


# ── TwitterService (facade) ────────────────────────────────────────────────────
# The single entry point for all operations.
# Callers never touch User.tweets or Tweet internals directly.

class TwitterService:
    """
    Facade over the entire system.

    Holds the user registry, tweet store, hashtag index, like/retweet counts,
    and notification service. All public methods live here.
    """

    def __init__(
        self,
        feed_strategy: FeedStrategy,
        notification_service: NotificationService,
    ) -> None:
        self._feed_strategy  = feed_strategy
        self._notifications  = notification_service
        self._users:   dict[str, User]  = {}    # user_id → User
        self._tweets:  dict[str, Tweet] = {}    # tweet_id → Tweet
        self._likes:   dict[str, set[str]] = {} # tweet_id → set of user_ids who liked
        self._retweets: dict[str, set[str]] = {} # tweet_id → set of user_ids who retweeted
        self._hashtags = HashtagIndex()

    # ── Registration ──────────────────────────────────────────────────────────

    def register_user(self, user_id: str, username: str) -> User:
        user = User(user_id, username)
        self._users[user_id] = user
        return user

    # ── Social graph ──────────────────────────────────────────────────────────

    def follow(self, follower: User, followee: User) -> None:
        """follower starts following followee and followee gets a notification."""
        follower.follow(followee)
        self._notifications.notify(Notification(
            notif_type = NotificationType.NEW_FOLLOWER,
            from_user  = follower.username,
            to_user    = followee.username,
        ))

    def unfollow(self, follower: User, followee: User) -> None:
        follower.unfollow(followee)

    # ── Posting ───────────────────────────────────────────────────────────────

    def post_tweet(self, user: User, content: str) -> Tweet:
        """
        Post a tweet, index its hashtags, fan-out to followers if using push model,
        and fire a mention notification for any @username found in the content.
        """
        tweet = user.post_tweet(content)
        self._tweets[tweet.tweet_id] = tweet
        self._likes[tweet.tweet_id]    = set()
        self._retweets[tweet.tweet_id] = set()

        # Index hashtags for search and trending
        self._hashtags.index_tweet(tweet)

        # If using push model, fan the tweet out to all followers' caches now
        if isinstance(self._feed_strategy, PushFeedStrategy):
            self._fan_out_tweet(tweet, user)

        # Notify any @mentioned users
        for mentioned in re.findall(r"@(\w+)", content):
            if mentioned != user.username:
                self._notifications.notify(Notification(
                    notif_type = NotificationType.MENTION,
                    from_user  = user.username,
                    to_user    = mentioned,
                    tweet      = tweet,
                ))

        return tweet

    def _fan_out_tweet(self, tweet: Tweet, author: User) -> None:
        """Push model helper: insert the new tweet at the front of every follower's cache."""
        for follower_id in author.followers:
            follower = self._users.get(follower_id)
            if follower:
                follower.feed_cache.insert(0, tweet)

    # ── Interactions ──────────────────────────────────────────────────────────

    def like_tweet(self, user: User, tweet: Tweet) -> None:
        """Record a like and notify the tweet author."""
        self._likes[tweet.tweet_id].add(user.user_id)
        author = self._users.get(tweet.author_id)
        if author and author.user_id != user.user_id:
            self._notifications.notify(Notification(
                notif_type = NotificationType.LIKE,
                from_user  = user.username,
                to_user    = author.username,
                tweet      = tweet,
            ))

    def retweet(self, user: User, tweet: Tweet) -> None:
        """Record a retweet and notify the original author."""
        self._retweets[tweet.tweet_id].add(user.user_id)
        author = self._users.get(tweet.author_id)
        if author and author.user_id != user.user_id:
            self._notifications.notify(Notification(
                notif_type = NotificationType.RETWEET,
                from_user  = user.username,
                to_user    = author.username,
                tweet      = tweet,
            ))

    def like_count(self, tweet: Tweet) -> int:
        return len(self._likes.get(tweet.tweet_id, set()))

    def retweet_count(self, tweet: Tweet) -> int:
        return len(self._retweets.get(tweet.tweet_id, set()))

    # ── Timelines ─────────────────────────────────────────────────────────────

    def get_home_timeline(self, user: User, limit: int = 20) -> list[Tweet]:
        """Return tweets from people the user follows, newest first."""
        return self._feed_strategy.get_feed(user, self._users, limit)

    def get_user_timeline(self, user: User, limit: int = 20) -> list[Tweet]:
        """Return a specific user's own tweets, newest first."""
        return sorted(user.tweets, key=lambda t: t.timestamp, reverse=True)[:limit]

    # ── Discovery ─────────────────────────────────────────────────────────────

    def search_hashtag(self, tag: str) -> list[Tweet]:
        """Return all tweets containing the given hashtag, newest first."""
        return self._hashtags.search(tag)

    def get_trending(self, top_n: int = 5) -> list[tuple[str, int]]:
        """Return the top_n most-used hashtags as (hashtag, count) pairs."""
        return self._hashtags.get_trending(top_n)


# ── Usage example ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Wire up the notification service with two delivery channels
    notif_service = NotificationService()
    notif_service.register(InAppNotification())
    # Uncomment the next line to also receive email notifications:
    # notif_service.register(EmailNotification())

    # Create the service — using PullFeedStrategy to start (simple and correct)
    svc = TwitterService(
        feed_strategy       = PullFeedStrategy(),
        notification_service = notif_service,
    )

    # Register users
    alice   = svc.register_user("u1", "alice")
    bob     = svc.register_user("u2", "bob")
    charlie = svc.register_user("u3", "charlie")

    # Alice follows Bob and Charlie
    print("\n=== Follow actions ===")
    svc.follow(alice, bob)
    svc.follow(alice, charlie)

    # Bob tweets
    print("\n=== Bob tweets ===")
    t1 = svc.post_tweet(bob, "Hello Twitter! #firsttweet")

    # Charlie tweets with a hashtag and a mention
    print("\n=== Charlie tweets ===")
    t2 = svc.post_tweet(charlie, "Loving Python today! #python @alice check this out")

    # Alice checks her home timeline
    print("\n=== Alice's home timeline ===")
    for tweet in svc.get_home_timeline(alice):
        likes    = svc.like_count(tweet)
        retweets = svc.retweet_count(tweet)
        print(f"  {tweet}  [likes: {likes}  retweets: {retweets}]")

    # Alice likes Bob's tweet
    print("\n=== Alice likes Bob's tweet ===")
    svc.like_tweet(alice, t1)

    # Alice retweets Charlie's tweet
    print("\n=== Alice retweets Charlie's tweet ===")
    svc.retweet(alice, t2)

    # Search by hashtag
    print("\n=== Search #python ===")
    for tweet in svc.search_hashtag("#python"):
        print(f"  {tweet}")

    # Trending hashtags
    print("\n=== Trending hashtags ===")
    for tag, count in svc.get_trending():
        print(f"  #{tag}  ({count} tweets)")

    # Bob's own timeline
    print("\n=== Bob's user timeline ===")
    for tweet in svc.get_user_timeline(bob):
        print(f"  {tweet}")
```

---

## Step-by-step walkthrough

```python
svc.follow(alice, bob)
svc.follow(alice, charlie)
```
`alice.following` becomes `{"u2", "u3"}`. `bob.followers` and `charlie.followers` each now contain `"u1"`. Bob and Charlie each receive an `InAppNotification` of type `NEW_FOLLOWER`.

```python
t1 = svc.post_tweet(bob, "Hello Twitter! #firsttweet")
```
- `bob.post_tweet()` validates the length (17 chars — fine), creates a frozen `Tweet` dataclass, and appends it to `bob.tweets`.
- `TwitterService.post_tweet()` stores the tweet in `self._tweets`, creates empty like/retweet sets for it, and calls `self._hashtags.index_tweet(tweet)`.
- `HashtagIndex` adds `tweet` to `self._index["firsttweet"]` and increments `self._counter["firsttweet"]` to 1.
- Because we are using `PullFeedStrategy`, no fan-out happens at write time.
- No `@mentions` are found, so no mention notifications fire.

```python
t2 = svc.post_tweet(charlie, "Loving Python today! #python @alice check this out")
```
Same as above, but `hashtags = frozenset({"python"})`. Additionally, `re.findall(r"@(\w+)", content)` extracts `"alice"`. Since `"alice" != charlie.username`, a `MENTION` notification is sent to `@alice`.

**What just happened?** Two tweets are now indexed. `#python` has a count of 1 in the `HashtagIndex`. Alice's inbox has a mention notification.

```python
for tweet in svc.get_home_timeline(alice):
    ...
```
`PullFeedStrategy.get_feed()` iterates `alice.following = {"u2", "u3"}`. It collects `bob.tweets` (contains `t1`) and `charlie.tweets` (contains `t2`), sorts them newest-first, and returns both. Alice sees Charlie's tweet first because it was posted slightly later.

```python
svc.like_tweet(alice, t1)
```
`self._likes["<t1_id>"]` becomes `{"u1"}`. Bob's `user_id != alice.user_id`, so a `LIKE` notification fires to `@bob`.

```python
svc.retweet(alice, t2)
```
`self._retweets["<t2_id>"]` becomes `{"u1"}`. A `RETWEET` notification fires to `@charlie`.

**What just happened?** The full scenario completed. Alice followed two people, both tweeted, Alice saw both in her timeline, liked one, retweeted the other, and every action generated the right notification — all without `User` or `Tweet` knowing that notifications exist.

---

## Common interview mistakes

1. **Storing the social graph inside `User` only.** Having `user.following` as a set is fine for small-scale code. The mistake is letting `User.follow()` also update the feed cache, handle notifications, and index hashtags. Follow-graph management is a service concern. `User.follow()` should only update the two sets — everything else belongs in `TwitterService`.

2. **Hard-coding the feed algorithm.** Writing `feed = sorted([t for fid in user.following for t in users[fid].tweets], ...)` directly inside `get_home_timeline()` means the entire method must change when you want to add a push cache or a hybrid model. Extract feed generation into `FeedStrategy` so algorithms are swappable.

3. **Making `Tweet` mutable.** If tweet content can change after posting, every feed cache that already holds a reference to that tweet silently shows stale data. Use `@dataclass(frozen=True)` to make Python enforce immutability at runtime.

4. **No notification abstraction.** Writing `send_email(user)` directly inside `like_tweet()` couples the core domain action to a specific delivery channel. When you later add push notifications you have to edit `like_tweet()` again. Register notification channels as observers in `NotificationService` and keep them entirely separate.

5. **Implementing trending by scanning all tweets every time.** Calling `get_trending()` by iterating over every tweet ever posted is O(total tweets) — unusably slow in production. Maintain an `HashtagIndex` with a running counter that is updated at write time. `get_trending()` then only needs to sort the counter dict, which is O(unique hashtags) — orders of magnitude smaller.

---

## Key patterns used

| Pattern | Where it appears | Why it helps |
|---|---|---|
| **Strategy** | `FeedStrategy` / `PullFeedStrategy` / `PushFeedStrategy` | Swap feed generation algorithms without touching `TwitterService` |
| **Observer** | `NotificationService` + `NotificationObserver` subclasses | Decouple event producers (like, retweet, follow) from delivery channels (in-app, email) |
| **Facade** | `TwitterService` | Single clean API hides the complexity of feed strategies, hashtag indexing, and notifications |
| **Value Object** | `Tweet` (`frozen=True` dataclass) | Immutable after creation; safe to cache and share across many feed lists |
| **Enumeration** | `NotificationType` | Prevents magic strings; invalid notification types are unrepresentable |


---

[← Back to Social / Feed Template](template.md)
