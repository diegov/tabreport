#!/usr/bin/env bash

source ./rustflags

sed s/'^export '/''/gi ./rustflags | \
    grep -v '^#' | cut -d '=' -f 1 | while read -r l; do
    # Github's env file doesn't work when the value is quoted,
    # so this just strips the quotes
    echo "$l"="$(eval echo '$'"$l")"
done
