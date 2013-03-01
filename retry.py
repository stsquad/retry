#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Generic Retry Script
#
# Copyright (C) 2013, Alex Bennée <alex@bennee.com>
# License: GPLv3
#
# I originally wrote this as a wrapper around rsync for dodgy links.
# The basic premise was to keeps retrying the rsync until eventual success.
# Since then I realised it would be far more useful as a generic wrapper
# for any script that may fail or indeed need repeating.
#

from argparse import ArgumentParser
from subprocess import Popen, STDOUT, PIPE
from fcntl import fcntl, F_SETFL
import signal
import os
import sys
import pty
import select

#
# Command line options
#
parser=ArgumentParser(description='retry wrapper script. Keep calling the command until eventual success')
parser.add_argument('-v', '--verbose', dest="verbose", action='count')
parser.add_argument('-t', '--test', dest="test", action='store_const', const=True, help="Test without retrying")
parser.add_argument('-n', '--limit', dest="limit", type=int, help="Only loop around this many times")
parser.add_argument('--invert', action='store_const', const=True, default=False, help="Invert the exit code test")
parser.add_argument('command', nargs='*', help="The command to run. You can precede with -- to avoid confusion about it's flags")

# Globals
global p
global complete

def signal_handler(sig, frame):
    global p
    global complete
    print 'You caught %d Ctrl+C! Killing %d' % (sig, p.pid)
    print "state of process is: %s" % (p.poll())
    complete=True
    p.terminate()

# Start of code
if __name__ == "__main__":
    global complete
    args = parser.parse_args()

    if args.verbose: print "command is %s" % (args.command)
    if args.invert and args.limit==None:
        print "You must define a limit if you have inverted the return code test"
        exit(-1)

    # Find out our foreground process group
    our_tty = os.open("/dev/tty", os.O_RDONLY)
    our_tty_pgrp = os.tcgetpgrp(our_tty)
    if args.verbose > 1: print "terminal process group = %d" % (our_tty_pgrp)

    # Trap SIGTERM, SIGINT nicely
    signal.signal(signal.SIGINT, signal_handler)

    complete=False
    run_count=0
    while not complete:
        # flags
        return_code = 0
        running = True

        # we need a pty if we don't want children assuming they are not interactive
        master, slave = pty.openpty()
        m_pty = os.fdopen(master)
        fcntl(m_pty.fileno(), F_SETFL, os.O_NONBLOCK)
        io_poll = select.poll()
        io_poll.register(m_pty, (select.POLLIN|select.POLLPRI|select.POLLERR|select.POLLHUP))

        cmd = " ".join(args.command)
        p = Popen(cmd, shell=True, stdin=PIPE, stdout=slave, stderr=slave, close_fds=True)
        if args.verbose > 1: print "Running: pid:%d, rc:%s" % (p.pid, p.returncode)

        while running:
            # check we are still running
            if p.poll() != None:
                print "child finished: rc = %d" % (p.returncode)
                running = False
                return_code = p.returncode
                break

            # check for IO
            events = io_poll.poll(1000)
            #print "events is %s" % (events)
            for (fd, mask) in events:
                #print "m_pty fd is %d" % (m_pty.fileno())
                out = m_pty.read()
                sys.stdout.write(out)


        run_count = run_count + 1

        # Process our exit conditions
        if args.test == True: complete = True
        if run_count >= args.limit: complete = True
        if args.invert:
            if return_code != 0: complete = True
        else:
            if return_code == 0: complete = True

    print "Ran command %d times" % (run_count)
