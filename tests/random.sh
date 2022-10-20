#!/bin/bash
#
# Randomly return 0 or error value between 1 and 10
#
r=$RANDOM
threshold=${1:+16364}
if [ $r -ge $threshold ]; then
    exit $[ 1 + $[ RANDOM % 10 ]]
fi
exit 0;
