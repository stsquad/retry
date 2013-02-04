#!/usr/bin/python
#
# Rsync Retry Script
#
# This script is a wrapper around rsync for dodgy links. The basic premise is it keeps retrying the rsync until eventual sucess.
#

from argparse import ArgumentParser
from os import getenv, O_NONBLOCK
from subprocess import Popen, PIPE
from fcntl import fcntl, F_SETFL
import shlex

#
# Command line options
#
parser=ArgumentParser(description='Rsync resty script. Keep calling rsync until eventual success')
parser.add_argument('source', help="source of files")
parser.add_argument('--rargs', dest="rsync_args", help="options to pass to rsync")
parser.add_argument('-d', '--dir', dest="destdir", default=getenv("HOME")+"/tmp", help="base directory for copy")
parser.add_argument('-v', '--verbose', dest="verbose", action='count')
parser.add_argument('-t', '--test', dest="test", action='store_const', const=True, help="Just check what we would copy")


# Start of code
if __name__ == "__main__":
    args = parser.parse_args()

    cmd = "rsync"
    if args.rsync_args: cmd = "%s -%s" % (cmd, args.rsync_args)
    cmd = "%s %s" % (cmd, args.source)
    if not args.test: cmd = "%s %s" % (cmd, args.destdir)

    if args.verbose:
        print "rsync command: %s" % (cmd)
        print "rsync command: %s" % (shlex.split(cmd))
        
    complete=False
    while not complete:
        p = Popen(cmd, shell=True, stdout=PIPE)
        fcntl(p.stdout.fileno(), F_SETFL, O_NONBLOCK)
        running = True
        while running:
            try:
                out = p.stdout.read()
                print "got: %s" % (out)
            except IOError:
                pass

            if p.poll():
                print "child finished"
                running = False


        complete = True
