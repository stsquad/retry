#!/usr/bin/env python
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
# pylint: disable=C0321,invalid-name

# for Python3 cleanliness
from __future__ import print_function

from argparse import ArgumentParser
from time import sleep, time
from collections import namedtuple

import logging
import sys
import os
import signal
import subprocess
import itertools
import re

logger = logging.getLogger("retry")

#
# Command line options
#
def parse_arguments():
    """
    Read the arguments and return them to main.
    """
    parser = ArgumentParser(description="Retry wrapper script.")
    parser.add_argument('-v', '--verbose', default=0, dest="verbose", action='count')
    parser.add_argument('-l', '--log', default=None, help="File to log to")
    parser.add_argument('-t', '--test', dest="test",
                        action='store_true', default=False,
                        help="Test without retrying")
    parser.add_argument('--timeout', type=int, help="Set timeout")
    parser.add_argument('-n', '--limit', dest="limit", type=int,
                        help="Only loop around this many times")
    parser.add_argument('-c', '--count', action="store_true", default=False,
                        help="In conjunction with -n/--limit "
                        "count total successes.")
    parser.add_argument('--invert',
                        action='store_const', const=True, default=False,
                        help="Invert the exit code test")
    parser.add_argument('--delay', type=parse_delay, default=1,
                        help="Sleep for N (s)ecs, (m)ins or (h)ours between retries.")
    parser.add_argument('--pass', dest="success",
                        type=int, default=0,
                        help="Defined what a pass is.")
    parser.add_argument('--notty', action='store_true', default=False,
                        help="Don't attempt to grab tty control")
    parser.add_argument('command', nargs='*',
                        help="The command to run. "
                        "You should precede with -- "
                        "to avoid confusion about its flags")

    args = parser.parse_args()

    # Do a little validation/checking
    if not args.notty:
        try:
            tty_check = os.open('/dev/tty', os.O_RDWR)
        except OSError:
            args.notty = True

    # setup logging
    if args.verbose:
        if args.verbose == 1: logger.setLevel(logging.INFO)
        if args.verbose >= 2: logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    if args.log:
        handler = logging.FileHandler(args.log)
    else:
        handler = logging.StreamHandler()

    lfmt = logging.Formatter('%(message)s')
    handler.setFormatter(lfmt)
    logger.addHandler(handler)

    logger.info("command is %s", args.command)

    if args.limit is None:
        if args.count:
            sys.exit("Define a limit if running a success count")
        if args.notty:
            sys.exit("Define a limit if running without a controlling tty")
        if args.invert:
            sys.exit("Define a limit if you have inverted return code test")

    return args



def parse_delay(string):
    """Convert DELAY[smh] into seconds
    >>> parse_delay("1s")
    1
    >>> parse_delay("1m")
    60
    >>> parse_delay("2m")
    120
    """
    mult = 1
    if string.endswith("m"):
        mult = 60
    elif string.endswith("h"):
        mult = 60 * 60

    delay = int(re.findall("\\d+", string)[0])
    delay = delay * mult

    return delay


def become_tty_fg():
    """Become foreground tty.

    This is used before spawning the subprocess so key sequences are correctly passed down.
    We also use it to grab it back when sleeping.
    """
    os.setpgrp()
    hdlr = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    tty = os.open('/dev/tty', os.O_RDWR)
    os.tcsetpgrp(tty, os.getpgrp())
    signal.signal(signal.SIGTTOU, hdlr)


def wait_some(seconds, notty=False):
    """Sleep for a period.

    We grab the tty unless told not to so the user can hit Ctrl-C and exit.
    """

    try:
        logger.debug("waiting for %ds", seconds)
        sleep(seconds)
        return False
    except KeyboardInterrupt:
        return True


def process_results(results, breakdown=False):
    """Process the results

    We can either print a summary or do more detailed reporting on the results.
    """
    # First sort the results by return code
    sorted_results = {}
    for _ in results:
        try:
            sorted_results[_.result].append(_)
        except KeyError:
            sorted_results[_.result] = [_]

    total_runs = len(results)
    total_passes = 0

    if breakdown: print ("Results summary:")

    for ret, res in sorted_results.iteritems():
        count = len(res)
        total_time = 0.0
        for _ in res:
            total_time += _.time
            if _.is_pass: total_passes += 1

        perc = (count/float(total_runs))*100
        avg_time = total_time/count

        # calculate deviation
        deviation = 0
        for r in res:
            deviation += (r.time - avg_time)**2

        deviation = deviation / count

        if breakdown:
            print ("%d: %d times (%.2f%%), avg time %f (%f deviation)" %
                   (ret, count, perc, avg_time, deviation))

    print ("Ran command %d times, %d passes" % (total_runs, total_passes))
    return (total_runs - total_passes)


class Timeout(Exception):
    "Timeout exception"

    def __str__(self):
        return "timeout"


def timeout_handler(signum, frame):
    "Timeout handler"
    raise Timeout


def retry():
    """The main retry loop."""

    args = parse_arguments()

    pass_count = 0
    Result = namedtuple("Result", ["is_pass", "result", "time"])
    results = []
    signal.signal(signal.SIGALRM, timeout_handler)

    for run_count in itertools.count(start=1):
        start_time = time()
        if args.timeout:
            signal.alarm(args.timeout)

        pef = None if args.notty else become_tty_fg
        sub = subprocess.Popen(args.command, close_fds=True, preexec_fn=pef)
        try:
            return_code = sub.wait()
        except Timeout:
            sub.send_signal(signal.SIGKILL)
            return_code = -1

        signal.alarm(0)
        run_time = time() - start_time

        # Did the test pass/fail
        success = (return_code == args.success)
        if args.invert:
            success = not success
        if success:
            pass_count += 1

        # Log the result
        results.append(Result(success, return_code, run_time))

        logger.info("run %d: ret=%d (%s), time=%f (%d/%d)",
                    run_count,
                    return_code, "PASS" if success else "FALSE", run_time,
                    pass_count, run_count)

        if not args.notty:
            become_tty_fg()

        if args.count:
            if run_count >= args.limit:
                break
        else:
            if args.test is True:
                break
            if args.limit and run_count >= args.limit:
                break
            if success:
                break


        # now sleep, exit if user kills it
        if wait_some(args.delay, args.notty):
            break

    return process_results(results, args.count)


if __name__ == "__main__":
    r = retry()
    exit(r)
