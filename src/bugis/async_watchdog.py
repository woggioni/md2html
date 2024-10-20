import asyncio

from watchdog.events import FileSystemEventHandler, FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer
from watchdog.events import FileMovedEvent, FileClosedEvent, FileCreatedEvent, FileModifiedEvent
from pathlib import Path
from asyncio import Queue, AbstractEventLoop, Future, CancelledError, Task
from typing import Optional, Callable
from logging import getLogger


class Subscription:
    _unsubscribe_callback: Callable[['Subscription'], None]
    _event: Future
    _loop: AbstractEventLoop

    def __init__(self, unsubscribe: Callable[['Subscription'], None], loop: AbstractEventLoop):
        self._unsubscribe_callback = unsubscribe
        self._event: Future = loop.create_future()
        self._loop = loop

    def unsubscribe(self) -> None:
        self._unsubscribe_callback(self)

    async def wait(self, tout: float) -> bool:
        handle = self._loop.call_later(tout, lambda: self._event.cancel())
        try:
            await self._event
            return True
        except CancelledError:
            return False
        finally:
            handle.cancel()

    def notify(self) -> None:
        self._event.set_result(None)

    def reset(self) -> None:
        self._event = self._loop.create_future()


class _EventHandler(FileSystemEventHandler):
    _queue: Queue
    _loop: AbstractEventLoop

    def __init__(self, queue: Queue, loop: AbstractEventLoop,
                 *args, **kwargs):
        self._loop = loop
        self._queue = queue
        super(*args, **kwargs)

    def on_created(self, event: FileSystemEvent) -> None:
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)


class AsyncQueueIterator:
    _queue: Queue

    def __init__(self, queue: Queue):
        self._queue = queue

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item


observer = Observer()


def watch(path: Path, queue: Queue, loop: AbstractEventLoop,
          recursive: bool = False) -> None:
    """Watch a directory for changes."""
    handler = _EventHandler(queue, loop)

    observer.schedule(handler, str(path), recursive=recursive)
    observer.start()
    observer.join()
    loop.call_soon_threadsafe(queue.put_nowait, None)


class SubscriptionManager:
    _loop: AbstractEventLoop
    _queue: Queue
    _subscriptions: dict[str, set[Subscription]]

    def __init__(self, loop: AbstractEventLoop):
        self._subscriptions: dict[str, set[Subscription]] = dict()
        self._loop = loop
        self._queue = Queue()

    def subscribe(self, path: str) -> Subscription:
        subscriptions = self._subscriptions
        subscriptions_per_path = subscriptions.setdefault(path, set())

        def unsubscribe_callback(subscription):
            subscriptions_per_path.remove(subscription)

        result = Subscription(unsubscribe_callback, self._loop)
        subscriptions_per_path.add(result)
        return result

    def _notify_subscriptions(self, path):
        subscriptions = self._subscriptions
        subscriptions_per_path = subscriptions.get(path, None)
        if subscriptions_per_path:
            for s in subscriptions_per_path:
                s.notify()

    async def process_events(self):
        async for evt in AsyncQueueIterator(self._queue):
            self._notify_subscriptions(evt)

    def post_event(self, path):
        self._loop.call_soon_threadsafe(self._queue.put_nowait, path)


class FileWatcher(PatternMatchingEventHandler):
    _subscription_manager: SubscriptionManager
    _loop: AbstractEventLoop
    _subscription_manager_loop: Task

    def __init__(self, path):
        super().__init__(patterns=['*.md'],
                         ignore_patterns=None,
                         ignore_directories=False,
                         case_sensitive=True)
        self._observer: Observer = Observer()
        self._observer.schedule(self, path=path, recursive=True)
        self.logger = getLogger(FileWatcher.__name__)
        self._loop = asyncio.get_running_loop()
        self._subscription_manager = SubscriptionManager(self._loop)
        self._loop.run_in_executor(None, self._observer.start)
        self._subscription_manager_loop = self._loop.create_task(self._subscription_manager.process_events())

    async def stop(self) -> None:
        def _observer_stop():
            self._observer.stop()
            self._observer.join()
            self._subscription_manager.post_event(None)

        self._loop.run_in_executor(None, _observer_stop)
        await self._subscription_manager_loop

    def subscribe(self, path: str) -> Subscription:
        return self._subscription_manager.subscribe(path)

    def on_any_event(self, event: FileSystemEvent) -> None:
        what = "directory" if event.is_directory else "file"

        def post_event(path):
            self._subscription_manager.post_event(path)

        if isinstance(event, FileClosedEvent):
            self.logger.debug("Closed %s: %s", what, event.src_path)
            # update_subscriptions()
        elif isinstance(event, FileMovedEvent):
            self.logger.debug("Moved %s: %s to %s", what, event.src_path, event.dest_path)
            post_event(event.dest_path)
        elif isinstance(event, FileCreatedEvent):
            self.logger.debug("Created %s: %s", what, event.src_path)
            post_event(event.src_path)
        elif isinstance(event, FileModifiedEvent):
            self.logger.debug("Modified %s: %s", what, event.src_path)
            post_event(event.src_path)
