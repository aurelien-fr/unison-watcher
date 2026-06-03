import time
import fnmatch
import argparse
import subprocess
import os
from pathlib import Path

from watchdog.observers import Observer

from watchdog.events import (
    FileSystemEventHandler,
    FileModifiedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
)

import threading


def is_local_dir(p: str) -> bool:
    return Path(p).is_dir()


def load_ignore_patterns(u_profile_file: Path):
    """
    Load ignore patterns from a unison profilename file.

    The config file should contain lines in the following format:
        ignore = pattern

    Example:
        ignore = *.log
        ignore = node_modules
        or with unison ignore = Name *.bak

    Args:
        u_profile_file (Path): Path to the configuration file.

    Returns:
        list[str]: A list of ignore patterns (glob-style).
    """
    patterns = []

    if not u_profile_file.is_file():
        raise FileNotFoundError(f"{u_profile_file} does not exist")

    with u_profile_file.open("r") as f:
        for line in f:
            line = line.strip()

            if line.startswith("ignore"):
                pattern = line.split("=")[-1].strip()
                pattern = pattern.replace(" ", "")
                patterns.append(pattern)

    return patterns


def load_watched_dir(u_profile_file: Path) -> Path:
    """
    Load local watched directory from a unison profilename file.

    Args:
        u_profile_file (Path): Path to the configuration file.
    """

    root_dirs = []

    if not u_profile_file.is_file():
        raise FileNotFoundError(f"{u_profile_file} does not exist")

    with u_profile_file.open("r") as f:
        for line in f:
            line = line.strip()

            if line.startswith("root"):
                pattern = line.split("=")[-1].strip()
                pattern = pattern.replace(" ", "")
                root_dirs.append(pattern)

    for root in root_dirs:
        if is_local_dir(root):
            return Path(root)

    return Path()


def is_ignored(path: Path, patterns):
    """
    Check if a given path matches any ignore pattern.

    Matching is done using glob patterns (fnmatch).

    Args:
        path (Path): Relative path to check.
        patterns (list[str]): List of glob patterns.

    Returns:
        bool: True if the path should be ignored, False otherwise.
    """
    path_str = str(path)

    for pattern in patterns:
        if fnmatch.fnmatch(path_str, pattern) or pattern in path_str:
            return True

    return False


class Handler(FileSystemEventHandler):
    """
    Custom event handler for file system events.

    This handler:
    - Filters ignored paths
    - Applies a debounce mechanism
    - Executes a command on file changes
    """

    def __init__(self, ignore_patterns, command, watch_dir: Path, debounce):
        """
        Initialize the handler.

        Args:
            ignore_patterns (list[str]): Ignore ignore_patterns.
            command (str): Command to execute on change.
            watch_dir (Path): Root directory being watched.
            debounce (float): Minimum delay between command executions (seconds).
        """
        self.ignore_patterns = ignore_patterns
        self.command = command
        self.watch_dir = watch_dir
        self.debounce = debounce

        self.timer = None
        self.lock = threading.Lock()

    def on_any_event(self, event):
        """
        Handle any file system event.

        This method:
        - Ignores directory events
        - Filters ignored paths
        - Applies debounce logic
        - Executes the configured command
        """
        try:
            path = Path(str(event.src_path)).relative_to(self.watch_dir)
        except ValueError:
            return

        if is_ignored(path, self.ignore_patterns):
            return

        print(f"[{time.ctime()}] {event.event_type} on {event.src_path}")

        self._schedule_command()

    def _schedule_command(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()

            self.timer = threading.Timer(self.debounce, self._run_command)
            self.timer.start()

    def _run_command(self):
        with self.lock:
            self.timer = None

        print(f"[{time.ctime()}] Running command...")
        subprocess.run(self.command, shell=True)


def main():
    """
    Main entry point of the unison file watcher.

    This function:
    - Parses CLI arguments
    - Loads ignore patterns and watched dir
    - Starts the file system observer
    - Keeps the process running until interrupted
    """
    parser = argparse.ArgumentParser(
        description="Execute 'unison' when changes are made on watched directory, using unison configuration file"
    )

    parser.add_argument("profilename",
                        help="Unison profilename, passed to unison call")

    parser.add_argument("options",
                        nargs="?",
                        help="Unison options, passed to unison call")

    parser.add_argument(
        "-d",
        "--debounce",
        type=float,
        default=0.5,
        help="Delay between two executions (in seconds)"
    )

    args = parser.parse_args()

    if not args.profilename:
        parser.error("Unison profilename is mandatory. Create a .prf file under ~/.unison")

    unison_env_dir = os.environ.get("UNISON")

    if unison_env_dir is not None:
        print(f"Using UNISON env var ({unison_env_dir})")
        unison_home = Path(unison_env_dir)
    else:
        unison_home = Path.home() / ".unison"

    cfg_file = Path((unison_home / args.profilename).with_suffix(".prf"))

    patterns = load_ignore_patterns(cfg_file)
    watch_dir = load_watched_dir(cfg_file)

    print(f"===================================================================")
    print(f"Watched folder: {watch_dir}")
    print(f"Ignored patterns: {patterns}")
    print(f"===================================================================")

    event_handler = Handler(
        patterns,
        f"unison {args.profilename} {args.options}",
        watch_dir,
        args.debounce
    )

    observer = Observer()
    observer.schedule(event_handler, path=str(watch_dir), recursive=True,
                      event_filter=[
                          FileModifiedEvent,
                          FileCreatedEvent,
                          FileDeletedEvent,
                          FileMovedEvent,
                      ],
                      )

    observer.start()
    print(f"Watching {watch_dir}... (debounce={args.debounce}s)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
