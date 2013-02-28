#!/usr/bin/python
#
# Rsync Retry Script
#
# This script is a wrapper around rsync for dodgy links. The basic premise is it keeps retrying the rsync until eventual sucess.
#

from argparse import ArgumentParser
from os import kill, getenv, O_NONBLOCK
from subprocess import Popen, STDOUT, PIPE
from fcntl import fcntl, F_SETFL
import shlex
import signal
import sys

#
# Command line options
#
parser=ArgumentParser(description='Rsync resty script. Keep calling rsync until eventual success')
parser.add_argument('source', help="source of files")
parser.add_argument('--rargs', dest="rsync_args", help="options to pass to rsync")
parser.add_argument('-d', '--dir', dest="destdir", default=getenv("HOME")+"/tmp", help="base directory for copy")
parser.add_argument('-v', '--verbose', dest="verbose", action='count')
parser.add_argument('-t', '--test', dest="test", action='store_const', const=True, help="Just check what we would copy")

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

	cmd = "rsync"
	if args.rsync_args: cmd = "%s -%s" % (cmd, args.rsync_args)
	cmd = "%s %s" % (cmd, args.source)
	if not args.test: cmd = "%s %s" % (cmd, args.destdir)

	if args.verbose:
		print "rsync command: %s" % (cmd)
		print "rsync command: %s" % (shlex.split(cmd))

	# Trap SIGTERM, SIGINT nicely
	signal.signal(signal.SIGINT, signal_handler)

	complete=False
	while not complete:
		p = Popen(cmd, shell=True, bufsize=1, stdout=PIPE,stderr=STDOUT)
		if args.verbose:
			print "Running: pid:%d, rc:%s" % (p.pid, p.returncode)
		fcntl(p.stdout.fileno(), F_SETFL, O_NONBLOCK)
		running = True
		while running:
			try:
				out = p.stdout.read()
				if len(out)>0: sys.stdout.write(out)
			except IOError:
				pass
			except:
				print "another exceptions"

			x = p.poll()
			if x != None:
				print "child finished: x=%s rc = %d" % (x, p.returncode)
				running = False
				if p.returncode == 0:
					complete=True

		print "Finished loop and complete = %s" % (complete)
