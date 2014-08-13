#!/bin/bash
#
# Randomly return 0 or error value between 1 and 10
#
r=$RANDOM
if [ $r -ge 16364 ]; then
    exit $[ 1 + $[ RANDOM % 10 ]]
fi
exit 0;
