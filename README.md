# Unison watcher

Execute 'unison' on local file changes using inotify, with watcher on specific files only.
Filtering is done by parsing unison '.prf' configuration file.

You may also pause, resume, and force sync with CLI commands.

# Installation

``` shell
pipx install git+https://github.com/aurelien-fr/unison-watcher.git
unison-watcher -h
```
