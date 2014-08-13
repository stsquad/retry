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
    
Other Features
--------------

I've added the -c/--count option for use in testing situations. If you
have a program that fails occasionally you can run -n iterations and
get a summary of the return codes at the end of your run.

Ideally your test program should return different error codes for
different failure cases.
