#!/bin/bash
#
# Sleep for a random time, influenced by $1
#
r=$[ 1 + $[ RANDOM % 5 ]]
t=$(expr $r \* $1)
sleep $t
exit 0;
