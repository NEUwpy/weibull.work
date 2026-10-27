#!/bin/bash
COMMAND="$1"
shift
FULL_COMMAND=$(printf "%q " "$COMMAND" "$@")
nsenter -m -u -i -n -p -t 1 sh -c "$FULL_COMMAND"
