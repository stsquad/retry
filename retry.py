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
from math import sqrt

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

    # Short options
    parser.add_argument('-b', '--bisect', default=False,
                        action='store_true', help="GIT bisect support")
    parser.add_argument('-c', '--count', action="store_true", default=False,
                        help="In conjunction with -n/--limit "
                        "count total successes.")
    parser.add_argument('-s', '--stdout', default=False, action='store_true',
                        help="Grab stdout (assume single line)")
    parser.add_argument('-g', '--git', action="store_true", default=False,
                        help="Print git information in header")
    parser.add_argument('-l', '--log', default=None, help="File to log to")
    parser.add_argument('-n', '--limit', dest="limit", type=int,
                        help="Only loop around this many times")
    parser.add_argument('-m', '--modulate', dest="modulate",
                        help="Modulate sequence, replaces @ in the command line")
    parser.add_argument('-q', '--quiet', default=None, action="store_true",
                        help="Supress all output")
    parser.add_argument('-t', '--test', dest="test",
                        action='store_true', default=False,
                        help="Test without retrying")
    parser.add_argument('-v', '--verbose', dest="verbose", action='count')

    # Long only options
    parser.add_argument('--delay', type=parse_delay, default=1,
                        help="Sleep for N (s)ecs, (m)ins or (h)ours between retries.")
    parser.add_argument('--invert',
                        action='store_const', const=True, default=False,
                        help="Invert the exit code test")
    parser.add_argument('--notty', action='store_true', default=False,
                        help="Don't attempt to grab tty control")
    parser.add_argument('--pass', dest="success",
                        type=int, default=0,
                        help="Defined what a pass is.")
    parser.add_argument('--timeout', type=int, help="Set timeout")

    # The main argument, what we run
    parser.add_argument('command', nargs='*',
                        help="The command to run. "
                        "You should precede with -- "
                        "to avoid confusion about its flags")

    args = parser.parse_args()

    # Do a little validation/checking
    if not args.notty:
        try:
            os.open('/dev/tty', os.O_RDWR)
        except OSError:
            args.notty = True

    # bisect support needs some defaults
    if args.bisect:
        if not args.log:
            args.log = "bisect.log"

    # setup logging
    if args.quiet:
        logger.setLevel(logging.ERROR)
    if args.verbose:
        if args.verbose == 1: logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    if args.log:
        handler = logging.FileHandler(args.log, mode="a")
    else:
        handler = logging.StreamHandler()

    lfmt = logging.Formatter('%(message)s')
    handler.setFormatter(lfmt)
    logger.addHandler(handler)

    if args.limit is None:
        if args.count:
            sys.exit("Define a limit if running a success count")
        if args.notty:
            sys.exit("Define a limit if running without a controlling tty")
        if args.invert:
            sys.exit("Define a limit if you have inverted return code test")

    if args.modulate:
        modulate_list=[]
        fields=args.modulate.split(",")
        for f in fields:
            if bool(re.search("[0-9]+-[0-9]+", f)):
                r=f.split("-")
                modulate_list.extend(range(int(r[0]), int(r[1])+1))
            else:
                modulate_list.append(f)

        args.modulate = modulate_list


    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("retry.py called with %s", args)

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
    os.close(tty)


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

    if breakdown: logger.info("Results summary:")

    for ret, res in sorted_results.iteritems():
        count = len(res)
        total_time = 0.0
        for _ in res:
            total_time += _.time
            if _.is_pass: total_passes += 1

        perc = (count/float(total_runs))*100
        avg_time = total_time/count

        # calculate deviation
        varience = 0
        for r in res:
            varience += (r.time - avg_time)**2

        if count > 1:
            varience = varience / (count - 1)

        if breakdown:
            logger.info("%d: %d times (%.2f%%), avg time %.3f (%.2f varience/%.2f deviation)",
                        ret, count, perc, avg_time, varience, sqrt(varience))

    logger.info("Ran command %d times, %d passes", total_runs, total_passes)
    return (total_runs - total_passes)


class Timeout(Exception):
    "Timeout exception"

    def __str__(self):
        return "timeout"


def timeout_handler(signum, frame):
    #pylint: disable=unused-argument
    "Timeout handler"
    raise Timeout


def run_command(runcmd, notty=False, timeout=None):
    """Run a runcmd, letting it take tty and optionally timing out"""

    logger.debug("running: %s (notty=%s, %s timeout)",
                 runcmd, notty, "with" if timeout else "without")

    if timeout:
        signal.alarm(timeout)

    pef = None if notty else become_tty_fg
    sub = subprocess.Popen(runcmd, close_fds=True, preexec_fn=pef)
    try:
        while sub.poll() is None:
            sleep(0.25)

        return_code = sub.returncode
    except Timeout:
        logger.info("Timed out, sending SIGTERM to %d!", sub.pid)
        sub.send_signal(signal.SIGTERM)
        sleep(10)
        if sub.poll() is None:
            logger.info("Still there, sending SIGKILL to %d!!", sub.pid)
            sub.send_signal(signal.SIGKILL)
            sleep(5)
            print ("SUBPROCESS needed killing, build may break without reseting terminal...")
            print ("The reset will suspend shell, type 'fg' <CR> to continue")
            # clear/reset the terminal
            subprocess.call(["reset"])

        return_code = -1

    signal.alarm(0)

    return return_code

def run_command_grab_stdout(runcmd):
    """Run a command, grabbbing its stdout and returning both it and the result"""

    logger.debug("running: %s", runcmd)
    return_code = 0

    try:
        out = subprocess.check_output(runcmd)
    except subprocess.CalledProcessError, err:
        return_code = err.returncode
        out = err.output

    out = out.rstrip()
    return (return_code, out)


def bisect_prepare_step(notty=False, max_builds=1):
    """Run the bisect prepare step

    For C projects this involves running make.
    """

    git_revision = subprocess.check_output("git describe --tags", shell=True)
    logger.info("Bisect step for %s", git_revision.rstrip())

    if os.path.isfile("Makefile"):
        logger.info("Building Makefile based project")
        builds = 0
        while builds < max_builds:
            build_ok = run_command(["make", "-j9"], notty)
            if build_ok == 0:
                logger.info("Build %d finished OK", builds)
                break
            else:
                logger.info("Build %d failed: %d", builds, build_ok)

            builds += 1

        if build_ok != 0:
            logger.info("Couldn't finish build after %d attempt", builds)
            return False

    return True


def retry(args, command):
    """The main retry loop."""

    logger.info("retry.py called with %s", command)

    signal.signal(signal.SIGALRM, timeout_handler)

    if args.bisect:
        if not bisect_prepare_step(args.notty):
            # Source code cannot be tested
            logger.info("Can't run test step (failed prepare)")
            return 125
    elif args.git:
        git_desc = subprocess.check_output("git describe", shell=True)
        git_desc_all = subprocess.check_output("git describe --all", shell=True)
        logger.info("Source code is @ %s or %s", git_desc.rstrip(), git_desc_all.rstrip())


    pass_count = 0
    Result = namedtuple("Result", ["is_pass", "result", "time"])
    results = []

    logger.info("Results:")
    logger.info("Run, Ret, Pass/Fail, Time, Total Pass, Total Run%s",
                (", output" if args.stdout else ""))

    for run_count in itertools.count(start=1):
        start_time = time()

        if args.stdout:
            (return_code, output) = run_command_grab_stdout(command)
        else:
            return_code = run_command(command, args.notty, args.timeout)

        run_time = time() - start_time

        # Did the test pass/fail
        success = (return_code == args.success)
        if args.invert:
            success = not success
        if success:
            pass_count += 1

        # Log the result
        results.append(Result(success, return_code, run_time))

        logger.info("%d, %d, %s, %f, %d, %d, %s",
                    run_count,
                    return_code, "PASS" if success else "FALSE", run_time,
                    pass_count, run_count,
                    output if args.stdout else "-")

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

    # fix any broken terminals
    subprocess.call(["tset", "-c"])

    return process_results(results, args.count)


if __name__ == "__main__":
    args = parse_arguments()

    if args.modulate:
        final_result = 0
        for m in args.modulate:
            command = []
            for c in args.command:
                if c is "@":
                    command.append(str(m))
                else:
                    command.append(c)
            final_result += retry(args, command)
    else:
        final_result = retry(args, args.command)

    exit(final_result)
