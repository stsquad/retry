retry.py
========

A simple wrapper script to keep retrying until success.

I originally wrote this as a simple wrapper script that monitored the return
code from rsync and retried the sync if it was non-zero (i.e. failed to complete).
This is useful if you have a very dodgy link which occasionally goes down causing#
the current rsync session to bail-out.

I have since decided it's much more useful as a general purpose retry wrapper so
I've made it a lot more generic. The original behaviour can be run by:

    retry.py -v -- rsync user@host:path/ .
    
