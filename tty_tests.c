/*
 * tty tests in C
 *
 * I'm debugging why scp/rsync won't send progress output to retry.py
 * and it looks like it's not my script at fault :-/
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    int is_tty = isatty(STDOUT_FILENO);
    int pgrp = getpgrp();
    int tc_pgrp = tcgetpgrp(STDOUT_FILENO);

    // This is the initial test scp does
    fprintf(stderr, "isatty reports %d\n", is_tty);

    // This test is from can_output() in progressbar.c
    fprintf(stderr, "pgrps are %d and %d\n", pgrp, tc_pgrp);

    exit(0);
}
