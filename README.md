# Watch runner

Execute any command on file changes. Ignored paths can be set thanks to a configuration file using glob patterns (fnmatch)

Initially developed  to be used with `unison` on a remote server that does not support to inotify option. This script can use the unison config file to exclude the same paths.

# Installation

``` shell
pipx install git+https://github.com/aurelien-fr/watch-runner.git
watch-runner -h
```
