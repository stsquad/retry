rsync_retry
===========

A wrapper around rsync for using on dodgy links.

This is a simple wrapper script that monitors the return code from rsync and
retries the sync if it was non-zero (i.e. failed to complete). This is useful
if you have a very dodgy link which occasionally goes down causing the current
rsync session to bail-out.
