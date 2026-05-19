# 06 — Logging System

## What is this problem testing?

This problem tests your ability to design a system that **collects messages**, **filters them by severity**, and **routes them to multiple destinations** — all without any destination knowing about any other. Interviewers are watching for whether you apply the Singleton pattern correctly (including thread safety), whether you separate concerns between the logger, the handlers, and the formatter, and whether you use the Observer pattern to make the set of destinations extensible.

The four skill areas being assessed:

- **Singleton pattern** — ensuring one logger exists per application, with thread-safe initialisation
- **Chain of Responsibility** — each handler independently decides whether to process a message based on its own level threshold
- **Observer pattern** — handlers subscribe to the logger; adding a new destination requires zero changes to `Logger` itself
- **Log level filtering** — understanding the ordered severity scale and how it gates message processing at both the logger and handler level

---

## Requirements

- Support five log levels in ascending severity: **DEBUG < INFO < WARNING < ERROR < CRITICAL**
- Support multiple output handlers: **Console**, **File**, and **Remote** (simulated HTTP endpoint)
- Each handler has its own **minimum level threshold** — it ignores messages below that threshold
- The logger is a **Singleton** — the whole application shares one instance, regardless of how many modules import it
- Log messages are **formatted** with timestamp, level, logger name, and message text
- Handlers can be **added or removed at runtime** without restarting the application
- The logger itself also has a **minimum level** — messages below it are dropped before any handler sees them

---

## Clarifying questions to ask in interview

1. **Should the logger be a true Singleton or a module-level instance?** — Python's module system already makes a module-level `logger = Logger()` effectively a singleton (modules are imported once). A metaclass-based or `__new__`-based Singleton is more portable. Worth asking which flavour the interviewer wants.
2. **Is async or buffered logging required?** — Writing to a file or network on every log call can block the calling thread. A production logger uses a background thread and a queue. For this interview we implement synchronous logging but worth mentioning.
3. **Should `FileHandler` rotate logs?** — Real systems rotate log files by size or date. For the interview, a single file is fine, but noting this shows system design awareness.
4. **What should happen if `RemoteHandler` fails to send?** — Network calls can fail. Should the handler swallow the error silently, fall back to console, or raise? Worth confirming the desired failure mode.
5. **Should removing a handler affect in-flight log calls?** — Thread safety of `add_handler` / `remove_handler` is a subtle follow-up. Worth asking if the interviewer wants that level of detail.

---

## Identifying entities

| Noun in problem | Class |
|---|---|
| The log severity level | `LogLevel` (enum) |
| A single log event — all the data about one log call | `LogRecord` (dataclass) |
| Converts a `LogRecord` into a human-readable string | `LogFormatter` |
| Abstract output destination | `LogHandler` |
| Writes to stdout | `ConsoleHandler` |
| Writes to a file on disk | `FileHandler` |
| Sends to an HTTP endpoint | `RemoteHandler` |
| The application-wide logger — the Singleton | `Logger` |

---

## Identifying behaviors

| Verb in problem | Method | Lives on |
|---|---|---|
| Decide if a message should be processed | level comparison | `LogHandler.handle()` and `Logger.log()` |
| Convert a record to a string | `format(record) -> str` | `LogFormatter` |
| Process a single record (check level, then emit) | `handle(record)` | `LogHandler` (base class) |
| Write a formatted record to the destination | `emit(record)` | `ConsoleHandler`, `FileHandler`, `RemoteHandler` |
| Get the one application logger | `get_instance() -> Logger` | `Logger` (class method) |
| Register a new output destination | `add_handler(handler)` | `Logger` |
| Deregister an output destination | `remove_handler(handler)` | `Logger` |
| Create a record and dispatch it | `log(level, message, **extra)` | `Logger` |
| Convenience shorthand | `debug`, `info`, `warning`, `error`, `critical` | `Logger` |

---

## Relationships

```
Logger (Singleton)
 ├── _instance: Logger         (class variable — the one shared instance)
 ├── _lock: threading.Lock     (class variable — guards Singleton creation)
 ├── level: LogLevel           (minimum level the logger will process)
 ├── _handlers: List[LogHandler]
 │       ├── ConsoleHandler   (level=DEBUG  — sees everything)
 │       ├── FileHandler      (level=WARNING — only WARNING and above)
 │       └── RemoteHandler    (level=ERROR   — only ERROR and CRITICAL)
 └── _formatter: LogFormatter

LogRecord  (value object — created once, passed to all handlers)
 ├── timestamp: str
 ├── level: LogLevel
 ├── message: str
 ├── logger_name: str
 └── extra: dict

LogHandler  <<abstract>>
 ├── level: LogLevel
 ├── formatter: LogFormatter
 ├── handle(record)  ← checks level; calls emit() if above threshold
 └── emit(record)    <<abstract>>
```

> Think of the `Logger` as a TV news anchor. When something happens (a log call arrives), the anchor reads it once and then broadcasts it to every channel (handler). Each channel's producer (handler's level check) independently decides whether this story is important enough to air on their channel. The anchor does not know or care which channels broadcast it — they just read the news.

---

## Why this is a Resource Management problem

Console output, file handles, and network sockets are **shared resources**. Multiple parts of an application can try to write to the same file simultaneously, producing garbled output or race conditions. The logging system is the **access controller** that:

- **Gates access** — only messages above a handler's threshold reach that resource
- **Serialises writes** — one formatter and handler chain processes messages in order
- **Manages the file resource** — `FileHandler` owns the file handle and is responsible for opening and closing it cleanly

The Singleton ensures that no matter how many modules call `Logger.get_instance()`, there is always exactly one formatter, one list of handlers, and one set of resource handles. Duplicate loggers would create duplicate file handles, split output, and inconsistent state — the classic resource conflict.

---

## Design decisions

### 1. Why Singleton?

If you create `Logger()` in every module, each instance gets its own handler list and its own file handle. `module_a.py` writes to `app_a.log` and `module_b.py` writes to `app_b.log`. Searching the logs to trace a request across modules becomes a nightmare.

The Singleton guarantees all modules write to the same list of handlers. Adding a handler in one place affects every log call across the entire application.

### 2. Why Chain of Responsibility for handlers?

Each `LogHandler` decides independently whether to process a message. There is no central routing table that says "WARNING goes to file, ERROR goes to remote". Instead, every handler gets every message that passes the logger's own level gate, and each handler applies its own threshold.

The benefit: adding a new handler with a custom threshold requires zero changes to `Logger` or the existing handlers. You just append to the list.

### 3. Why `LogRecord` as a value object?

Without `LogRecord`, you would pass `(level, message, timestamp, extra)` as separate arguments through every method. Adding a new field (say, `thread_id`) means changing every method signature. With `LogRecord`, you add one field to the dataclass and every method signature stays the same.

> Think of `LogRecord` as an envelope. Once you stuff the letter into the envelope, you can hand it to any postal worker (handler) without them needing to know how many pages are inside.

### 4. Why separate `LogFormatter` from `LogHandler`?

If you hardcode the format string inside each handler, changing the timestamp format means editing every handler class. Extracting `LogFormatter` lets you:
- Swap the format in one place for all handlers
- Give different handlers different formats (compact for console, JSON for remote)
- Test formatting independently from I/O

### 5. Thread safety in Singleton with double-checked locking

A naive Singleton checks `if cls._instance is None: cls._instance = cls()`. If two threads both see `_instance is None` before either creates the instance, both create one — the Singleton breaks.

Fix: acquire a class-level lock before the check. But locking on every `get_instance()` call is slow. Double-checked locking acquires the lock only when the instance might not exist yet:

```python
if cls._instance is None:           # fast path: no lock if already created
    with cls._lock:
        if cls._instance is None:   # slow path: re-check inside the lock
            cls._instance = cls()
```

Once `_instance` is set, future calls take the fast path and never touch the lock.

---

## Complete Code

```python
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Dict, Any, Optional


# ── LogLevel ───────────────────────────────────────────────────────────────────
# IntEnum gives us integer comparison for free: DEBUG < INFO < WARNING < ERROR.
# Using integers (10, 20, 30, ...) leaves room to insert custom levels between
# the standard ones without breaking comparisons.

class LogLevel(IntEnum):
    DEBUG    = 10
    INFO     = 20
    WARNING  = 30
    ERROR    = 40
    CRITICAL = 50

    def __str__(self) -> str:
        return self.name   # "DEBUG", "INFO", etc. — used in formatted output


# ── LogRecord ──────────────────────────────────────────────────────────────────
# A value object. Created once when Logger.log() is called.
# Passed unchanged to every handler — no handler modifies it.
# Storing extra as a dict allows arbitrary context (request_id, user_id, etc.)

@dataclass
class LogRecord:
    timestamp: str           # formatted at creation time, e.g. "2026-05-18 14:23:01"
    level: LogLevel          # the severity level of this message
    message: str             # the human-readable log message
    logger_name: str         # identifies which Logger produced this record
    extra: Dict[str, Any] = field(default_factory=dict)   # optional key-value context


# ── LogFormatter ───────────────────────────────────────────────────────────────
# Converts a LogRecord into a plain string.
# Centralised here so changing the format affects every handler at once.
# Subclass or replace to produce JSON, XML, or any other format.

class LogFormatter:
    def format(self, record: LogRecord) -> str:
        """
        Default format: [TIMESTAMP] LEVEL (logger_name): message  {extra}
        Example:        [2026-05-18 14:23:01] WARNING (app): disk usage high  {'host': 'web-01'}
        """
        base = f"[{record.timestamp}] {record.level} ({record.logger_name}): {record.message}"
        if record.extra:
            base += f"  {record.extra}"
        return base


# ── LogHandler (abstract) ──────────────────────────────────────────────────────
# Base class for all output destinations.
# handle() is the Chain of Responsibility gate: it checks the level and calls
# emit() only if the message is important enough for this handler.
# Subclasses override emit() with the actual I/O.

class LogHandler(ABC):
    def __init__(self, level: LogLevel, formatter: Optional[LogFormatter] = None):
        self.level = level
        self.formatter = formatter or LogFormatter()   # use default if none given

    def handle(self, record: LogRecord) -> None:
        """
        Gate: process the record only if its level >= this handler's threshold.
        This is the Chain of Responsibility step — each handler is independent.
        """
        if record.level >= self.level:
            self.emit(record)

    @abstractmethod
    def emit(self, record: LogRecord) -> None:
        """Write the formatted record to this handler's destination."""
        ...


# ── ConsoleHandler ─────────────────────────────────────────────────────────────
# Writes to stdout. Typically set to DEBUG so it shows everything.

class ConsoleHandler(LogHandler):
    def emit(self, record: LogRecord) -> None:
        print(self.formatter.format(record))


# ── FileHandler ────────────────────────────────────────────────────────────────
# Appends to a file on disk.
# Typically set to WARNING or above to avoid filling disk with debug noise.
# Opens in append mode so existing content is preserved across restarts.

class FileHandler(LogHandler):
    def __init__(self, filepath: str, level: LogLevel, formatter: Optional[LogFormatter] = None):
        super().__init__(level, formatter)
        self.filepath = filepath
        # Open once at construction time; keep the handle alive for the logger's lifetime.
        # In production you would also handle rotation (by size or date).
        self._file = open(filepath, "a", encoding="utf-8")

    def emit(self, record: LogRecord) -> None:
        self._file.write(self.formatter.format(record) + "\n")
        self._file.flush()   # flush immediately so the file is readable without closing

    def close(self) -> None:
        """Release the file handle. Call this during application shutdown."""
        if not self._file.closed:
            self._file.close()

    def __del__(self) -> None:
        self.close()


# ── RemoteHandler ──────────────────────────────────────────────────────────────
# Simulates sending a log record to an HTTP endpoint (e.g. Datadog, Splunk).
# In a real implementation, this would use `requests.post` or an async HTTP client.
# Typically set to ERROR or CRITICAL so only high-severity alerts go over the network.

class RemoteHandler(LogHandler):
    def __init__(self, endpoint_url: str, level: LogLevel, formatter: Optional[LogFormatter] = None):
        super().__init__(level, formatter)
        self.endpoint_url = endpoint_url

    def emit(self, record: LogRecord) -> None:
        # Simulate an HTTP POST — in production replace this with a real HTTP call
        payload = {
            "level":   str(record.level),
            "message": record.message,
            "time":    record.timestamp,
            "extra":   record.extra,
        }
        print(f"[RemoteHandler] POST {self.endpoint_url} → {payload}")


# ── Logger (Singleton) ─────────────────────────────────────────────────────────
# The single application-wide logger.
# Thread-safe Singleton via double-checked locking.
# Acts as the Observer subject: handlers are the observers.

class Logger:
    _instance: Optional["Logger"] = None   # the one shared instance
    _lock = threading.Lock()               # protects Singleton creation only

    def __init__(self, name: str = "app", level: LogLevel = LogLevel.DEBUG):
        # __init__ is called by __new__ only on first creation.
        # Guard against accidental double-initialisation.
        if hasattr(self, "_initialised"):
            return
        self._initialised = True

        self.name = name
        self.level = level                   # logger-level gate (before handlers)
        self._handlers: List[LogHandler] = []
        self._handler_lock = threading.Lock()   # protects _handlers list

    @classmethod
    def get_instance(cls, name: str = "app", level: LogLevel = LogLevel.DEBUG) -> "Logger":
        """
        Return the existing Logger instance, or create it if this is the first call.
        Double-checked locking ensures thread safety without locking on every call.
        """
        if cls._instance is None:          # fast path — no lock once instance exists
            with cls._lock:
                if cls._instance is None:  # slow path — re-check inside the lock
                    cls._instance = cls(name, level)
        return cls._instance

    def add_handler(self, handler: LogHandler) -> None:
        """Register a new output destination. Thread-safe."""
        with self._handler_lock:
            if handler not in self._handlers:
                self._handlers.append(handler)

    def remove_handler(self, handler: LogHandler) -> None:
        """Deregister an output destination. Thread-safe."""
        with self._handler_lock:
            if handler in self._handlers:
                self._handlers.remove(handler)

    def log(self, level: LogLevel, message: str, **extra: Any) -> None:
        """
        Core logging method.
        1. Apply the logger-level gate — drop messages below self.level.
        2. Create a LogRecord (the value object).
        3. Pass it to every handler — each handler applies its own level gate.
        """
        # Gate 1: logger-level filter
        if level < self.level:
            return

        # Create the record — a snapshot of everything about this log event
        record = LogRecord(
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            level=level,
            message=message,
            logger_name=self.name,
            extra=extra
        )

        # Dispatch to all handlers (Chain of Responsibility)
        # Take a snapshot of the handlers list to avoid holding the lock during I/O
        with self._handler_lock:
            handlers_snapshot = list(self._handlers)

        for handler in handlers_snapshot:
            handler.handle(record)   # each handler applies its own level gate

    # ── Convenience methods ────────────────────────────────────────────────────
    # These are the methods callers actually use.
    # They are thin wrappers around log() — no logic, just readability.

    def debug(self, message: str, **extra: Any) -> None:
        self.log(LogLevel.DEBUG, message, **extra)

    def info(self, message: str, **extra: Any) -> None:
        self.log(LogLevel.INFO, message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        self.log(LogLevel.WARNING, message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        self.log(LogLevel.ERROR, message, **extra)

    def critical(self, message: str, **extra: Any) -> None:
        self.log(LogLevel.CRITICAL, message, **extra)


# ── Usage example ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Set up the Singleton logger with three handlers at different thresholds
    logger = Logger.get_instance(name="myapp", level=LogLevel.DEBUG)

    console_handler = ConsoleHandler(level=LogLevel.DEBUG)
    file_handler    = FileHandler(filepath="/tmp/app.log", level=LogLevel.WARNING)
    remote_handler  = RemoteHandler(
        endpoint_url="https://logs.example.com/ingest",
        level=LogLevel.ERROR
    )

    logger.add_handler(console_handler)
    logger.add_handler(file_handler)
    logger.add_handler(remote_handler)

    print("--- Logging at various levels ---")

    logger.debug("starting up", version="1.0.0")
    # Reaches: ConsoleHandler only (FileHandler threshold=WARNING, RemoteHandler threshold=ERROR)

    logger.info("user logged in", user_id="u-42")
    # Reaches: ConsoleHandler only

    logger.warning("disk usage above 80%", host="web-01", usage_pct=82)
    # Reaches: ConsoleHandler + FileHandler (both have threshold <= WARNING)

    logger.error("database connection failed", db="postgres-primary", attempt=3)
    # Reaches: ConsoleHandler + FileHandler + RemoteHandler (all thresholds met)

    logger.critical("out of memory — shutting down")
    # Reaches: all three handlers

    print()
    print("--- Singleton: both variables point to the same object ---")
    logger_ref2 = Logger.get_instance()
    print(f"Same instance? {logger is logger_ref2}")   # True

    print()
    print("--- Removing a handler at runtime ---")
    logger.remove_handler(remote_handler)
    logger.error("another DB error — remote handler is now gone")
    # Reaches: ConsoleHandler + FileHandler only

    # Clean up file handle
    file_handler.close()
```

**What just happened?** The `logger.warning(...)` call travels through two gates: first the logger's own level check (`WARNING >= DEBUG`, so it passes), then each handler's own check. `ConsoleHandler` has threshold `DEBUG` so it processes it. `FileHandler` has threshold `WARNING` so it processes it. `RemoteHandler` has threshold `ERROR` so it silently drops it. No routing table, no `if level == WARNING` branches — each handler is its own independent decision-maker.

---

## Step-by-step walkthrough

Let us trace what happens when `logger.warning("disk high")` is called with the three handlers set up above.

**Step 1: `Logger.warning` is called**

```python
logger.warning("disk high", host="web-01")
```

This calls `self.log(LogLevel.WARNING, "disk high", host="web-01")`.

**Step 2: Logger-level gate**

`LogLevel.WARNING (30) >= self.level (LogLevel.DEBUG = 10)` — passes. The message is not dropped here.

**Step 3: LogRecord is created**

```python
record = LogRecord(
    timestamp="2026-05-18 14:23:01",
    level=LogLevel.WARNING,
    message="disk high",
    logger_name="myapp",
    extra={"host": "web-01"}
)
```

This is the envelope. It is created once and handed to every handler.

**Step 4: Dispatch to handlers**

The logger iterates over `[ConsoleHandler, FileHandler, RemoteHandler]` and calls `handler.handle(record)` on each.

**Step 5: ConsoleHandler.handle(record)**

`record.level (WARNING=30) >= handler.level (DEBUG=10)` — passes. `emit()` is called. Output:
```
[2026-05-18 14:23:01] WARNING (myapp): disk high  {'host': 'web-01'}
```

**Step 6: FileHandler.handle(record)**

`record.level (WARNING=30) >= handler.level (WARNING=30)` — passes. `emit()` is called. The same formatted string is appended to `/tmp/app.log`.

**Step 7: RemoteHandler.handle(record)**

`record.level (WARNING=30) >= handler.level (ERROR=40)` — **fails**. `emit()` is NOT called. The remote endpoint receives nothing.

**What just happened?** The same `LogRecord` object passed through three independent gates. Two gates opened, one stayed closed. The logger itself did not decide who gets the message — it just distributed the envelope. Each handler made its own decision.

---

## Common interview mistakes

1. **Not thread-safe Singleton**
   The naive `if cls._instance is None: cls._instance = cls()` creates a race condition when two threads call `get_instance()` simultaneously before the instance exists. Use double-checked locking as shown above. Alternatively, use a module-level instance (`logger = Logger()` at the bottom of `logger.py`) — Python module imports are themselves a Singleton because Python caches modules after the first import.

2. **Handler processes messages below its level**
   Forgetting the `if record.level >= self.level` check in `handle()` means a `FileHandler` set to `WARNING` also receives and writes `DEBUG` messages. The log file fills with noise. The level check is the core invariant of the Chain of Responsibility step.

3. **Formatter tightly coupled to Handler**
   Writing the format string directly inside `ConsoleHandler.emit()` means you need to update every handler class to change the timestamp format. Extract to `LogFormatter`. Each handler calls `self.formatter.format(record)` — one format change, one place.

4. **Logger as a global variable instead of a Singleton**
   `logger = Logger()` at module level in `logger.py` is effectively a Singleton in Python. But `logger = Logger()` in every module that imports it creates N independent loggers. The pattern matters. Always use `Logger.get_instance()` (or the module-level instance from a dedicated `logger.py`) so every caller shares the same handler list.

5. **No `LogRecord` abstraction — passing raw strings**
   If `log(level, message)` calls `handler.handle(level, message)` instead of a `LogRecord`, then adding context fields (request ID, thread name, user ID) requires changing every method signature. `LogRecord` is the extensibility point — add a field once to the dataclass and every handler gets access to it through the same `.extra` dict.

---

## Key patterns used

- **Singleton** — `Logger.get_instance()` guarantees one shared instance across the entire application. Thread-safe via double-checked locking.
- **Chain of Responsibility** — `Logger.log()` passes the record to every handler in sequence. Each handler independently decides whether to process the record based on its own level threshold. No handler knows about any other.
- **Observer** — `Logger` is the subject (publisher). `LogHandler` subclasses are the observers (subscribers). `add_handler` subscribes; `remove_handler` unsubscribes. The logger does not know what any handler does with the record.
- **Strategy** — `LogFormatter` is the formatting strategy. Swap it to produce JSON logs, structured logs, or coloured terminal output — zero changes to `Logger` or any `LogHandler`.
