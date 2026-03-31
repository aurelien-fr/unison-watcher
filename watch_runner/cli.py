import pprint
import time
import fnmatch
import argparse
import subprocess
from pathlib import Path
import pprint

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def load_ignore_patterns(config_file: Path):
    """
    Load ignore patterns from a configuration file.

    The config file should contain lines in the following format:
        ignore = pattern

    Example:
        ignore = *.log
        ignore = node_modules

    Args:
        config_file (Path): Path to the configuration file.

    Returns:
        list[str]: A list of ignore patterns (glob-style).
    """
    patterns = []

    if not config_file:
        return patterns

    with config_file.open("r") as f:
        for line in f:
            line = line.strip()

            if line.startswith("ignore ="):
                pattern = line.split("=")[-1].strip()
                pattern = pattern.split(" ")[-1].strip()
                patterns.append(pattern)

    return patterns


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

    def __init__(self, patterns, command, watch_dir: Path, debounce):
        """
        Initialize the handler.

        Args:
            patterns (list[str]): Ignore patterns.
            command (str): Command to execute on change.
            watch_dir (Path): Root directory being watched.
            debounce (float): Minimum delay between command executions (seconds).
        """
        self.patterns = patterns
        self.command = command
        self.watch_dir = watch_dir
        self.debounce = debounce
        self.last_run = 0

    def on_any_event(self, event):
        """
        Handle any file system event.

        This method:
        - Ignores directory events
        - Filters ignored paths
        - Applies debounce logic
        - Executes the configured command
        """
        if event.event_type not in ["modified", "created", "deleted", "moved"]:
            return

        if event.is_directory:
            return

        try:
            path = Path(str(event.src_path)).relative_to(self.watch_dir)
        except ValueError:
            return  # outside watched directory

        if is_ignored(path, self.patterns):
            return

        now = time.time()

        if now - self.last_run < self.debounce:
            return

        self.last_run = now

        print(f" ==== [{time.ctime()}] {event.event_type} on {event.src_path}")

        subprocess.run(self.command, shell=True)


def main():
    """
    Main entry point of the file watcher.

    This function:
    - Parses CLI arguments
    - Loads ignore patterns
    - Starts the file system observer
    - Keeps the process running until interrupted
    """
    parser = argparse.ArgumentParser(
        description="File watcher with ignore rules and debounce"
    )

    parser.add_argument(
        "--cfg",
        type=Path,
        help="Configuration file (with ignore = ... rules)"
    )

    parser.add_argument(
        "-w",
        "--watch-dir",
        type=Path,
        required=True,
        help="Directory to watch"
    )

    parser.add_argument(
        "-c",
        "--command",
        required=True,
        help="Command to execute"
    )

    parser.add_argument(
        "-d",
        "--debounce",
        type=float,
        default=0.5,
        help="Delay between two executions (in seconds)"
    )

    args = parser.parse_args()

    patterns = load_ignore_patterns(args.cfg)

    print(f"===================================================================")
    print(f"Watched folder: {args.watch_dir}")
    print(f"Ignored patterns: {patterns}")
    print(f"===================================================================")

    event_handler = Handler(
        patterns,
        args.command,
        args.watch_dir,
        args.debounce
    )

    observer = Observer()
    observer.schedule(event_handler, str(args.watch_dir), recursive=True)

    observer.start()
    print(f"Watching {args.watch_dir}... (debounce={args.debounce}s)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()