import asyncio
from asyncio import Queue, AbstractEventLoop, Future, Task, gather
from logging import getLogger, Logger
from pathlib import Path

from pwo import TopicManager, Subscriber
from watchdog.events import FileMovedEvent, FileClosedEvent, FileCreatedEvent, FileModifiedEvent
from watchdog.events import FileSystemEventHandler, FileSystemEvent, PatternMatchingEventHandler
from watchdog.observers import Observer

log: Logger = getLogger(__name__)


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


observer = Observer()


def watch(path: Path, queue: Queue, loop: AbstractEventLoop,
          recursive: bool = False) -> None:
    """Watch a directory for changes."""
    handler = _EventHandler(queue, loop)

    observer.schedule(handler, str(path), recursive=recursive)
    observer.start()
    observer.join()
    loop.call_soon_threadsafe(queue.put_nowait, None)


class FileWatcher(PatternMatchingEventHandler):
    _topic_manager: TopicManager
    _loop: AbstractEventLoop
    _topic_manager_loop: Task
    _running_tasks : Future

    def __init__(self, path):
        super().__init__(patterns=['*.md'],
                         ignore_patterns=None,
                         ignore_directories=False,
                         case_sensitive=True)
        self._observer: Observer = Observer()
        self._observer.schedule(self, path=path, recursive=True)
        self._loop = asyncio.get_running_loop()
        self._topic_manager = TopicManager(self._loop)
        self._running_tasks = gather(
            self._loop.run_in_executor(None, self._observer.start),
            self._loop.create_task(self._topic_manager.process_events())
        )

    async def stop(self) -> None:
        def _observer_stop():
            self._observer.stop()
            self._observer.join()
            self._topic_manager.post_event(None)

        await self._loop.run_in_executor(None, _observer_stop)
        await self._running_tasks

    def subscribe(self, path: str) -> Subscriber:
        return self._topic_manager.subscribe(path)

    def on_any_event(self, event: FileSystemEvent) -> None:
        what = "directory" if event.is_directory else "file"

        def post_event(path):
            self._topic_manager.post_event(path)

        if isinstance(event, FileClosedEvent):
            log.debug("Closed %s: %s", what, event.src_path)
            # update_subscriptions()
        elif isinstance(event, FileMovedEvent):
            log.debug("Moved %s: %s to %s", what, event.src_path, event.dest_path)
            post_event(event.dest_path)
        elif isinstance(event, FileCreatedEvent):
            log.debug("Created %s: %s", what, event.src_path)
            post_event(event.src_path)
        elif isinstance(event, FileModifiedEvent):
            log.debug("Modified %s: %s", what, event.src_path)
            post_event(event.src_path)
