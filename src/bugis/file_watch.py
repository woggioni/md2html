from threading import Lock
from typing import Optional, Callable
from os import getcwd
from watchdog.events import PatternMatchingEventHandler, FileSystemEvent, \
    FileCreatedEvent, FileModifiedEvent, FileClosedEvent, FileMovedEvent
from watchdog.observers import Observer
import logging
# from gevent.event import Event
from asyncio import Future, BaseEventLoop

class Subscription:
    _unsubscribe_callback: Callable[['Subscription'], None]
    _event: Future
    _loop: BaseEventLoop

    def __init__(self, unsubscribe: Callable[['Subscription'], None], loop: BaseEventLoop):
        self._unsubscribe_callback = unsubscribe
        self._event: Future = loop.create_future()
        self._loop = loop

    def unsubscribe(self) -> None:
        self._unsubscribe_callback(self)

    async def wait(self, tout: float) -> bool:
        handle = self._loop.call_later(tout, lambda: self._event.cancel())
        await self._event
        return self._event.wait(tout)

    def notify(self) -> None:
        self._event.set_result(None)

    def reset(self) -> None:
        self._event = self._loop.create_future()


class FileWatcher(PatternMatchingEventHandler):
    def __init__(self, path):
        super().__init__(patterns=['*.md'],
                         ignore_patterns=None,
                         ignore_directories=False,
                         case_sensitive=True)
        self.subscriptions: dict[str, set[Subscription]] = dict()
        self.observer: Observer = Observer()
        self.observer.schedule(self, path=path, recursive=True)
        self.observer.start()
        self.logger = logging.getLogger(FileWatcher.__name__)
        self._lock = Lock()

    def subscribe(self, path: str) -> Subscription:
        subscriptions = self.subscriptions
        subscriptions_per_path = subscriptions.setdefault(path, set())

        def unsubscribe_callback(subscription):
            with self._lock:
                subscriptions_per_path.remove(subscription)

        result = Subscription(unsubscribe_callback)
        subscriptions_per_path.add(result)
        return result

    def stop(self) -> None:
        self.observer.stop()
        self.observer.join()

    def on_any_event(self, event: FileSystemEvent) -> None:
        what = "directory" if event.is_directory else "file"

        def notify_subscriptions(path):
            with self._lock:
                subscriptions = self.subscriptions
                subscriptions_per_path = subscriptions.get(path, None)
                if subscriptions_per_path:
                    for s in subscriptions_per_path:
                        s.notify()

        if isinstance(event, FileClosedEvent):
            self.logger.debug("Closed %s: %s", what, event.src_path)
            # update_subscriptions()
        elif isinstance(event, FileMovedEvent):
            self.logger.debug("Moved %s: %s to %s", what, event.src_path, event.dest_path)
            notify_subscriptions(event.dest_path)
        elif isinstance(event, FileCreatedEvent):
            self.logger.debug("Created %s: %s", what, event.src_path)
            notify_subscriptions(event.src_path)
        elif isinstance(event, FileModifiedEvent):
            self.logger.debug("Modified %s: %s", what, event.src_path)
            notify_subscriptions(event.src_path)


if __name__ == '__main__':

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(threadName)s] (%(name)s) %(levelname)s %(message)s'
    )
    watcher = FileWatcher(getcwd())
    watcher.observer.join()

