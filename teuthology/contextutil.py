import contextlib
import sys
import logging
import time
import itertools

log = logging.getLogger(__name__)

@contextlib.contextmanager
def nested(*managers):
    """
    Like contextlib.nested but takes callables returning context
    managers, to avoid the major reason why contextlib.nested was
    deprecated.

    This version also logs any exceptions early, much like run_tasks,
    to ease debugging. TODO combine nested and run_tasks.
    """
    exits = []
    vars = []
    exc = (None, None, None)
    try:
        for mgr_fn in managers:
            mgr = mgr_fn()
            exit = mgr.__exit__
            enter = mgr.__enter__
            vars.append(enter())
            exits.append(exit)
        yield vars
    except Exception:
        log.exception('Saw exception from nested tasks')
        exc = sys.exc_info()
    finally:
        while exits:
            exit = exits.pop()
            try:
                if exit(*exc):
                    exc = (None, None, None)
            except Exception:
                exc = sys.exc_info()
        if exc != (None, None, None):
            # Don't rely on sys.exc_info() still containing
            # the right information. Another exception may
            # have been raised and caught by an exit method
            raise exc[0], exc[1], exc[2]


class MaxWhileTries(Exception):
    pass


class safe_while(object):
    """
    A context manager to remove boiler plate code that deals with `while` loops
    that need a given number of tries and some seconds to sleep between each
    one of those tries.

    The most simple example possible will try 10 times sleeping for 6 seconds:

        >>> from teuthology.contexutil import safe_while
        >>> with safe_while() as bomb:
        ...    while 1:
        ...        bomb()
        ...        # repetitive code here
        ...
        Traceback (most recent call last):
        ...
        MaxWhileTries: reached maximum tries (5) after waiting for 75 seconds

    Yes, this adds yet another level of indentation but it allows you to
    implement while loops exactly the same as before with just 1 more
    indentation level and one extra call. Everything else stays the same,
    code-wise. So adding this helper to existing code is simpler.

    The defaults are to start the sleeping time at 6 seconds and try 10 times.
    Setting the increment value will cause the sleep time to increase by that
    value at each step.

    You may also optionally pass in an "action" string to be used in the raised
    exception's error message to aid in log readability.
    """

    def __init__(self, sleep=6, increment=0, tries=10, action=None,
                 _sleeper=None):
        self.sleep = sleep
        self.increment = increment
        self.tries = tries
        self.counter = 0
        self.sleep_current = sleep
        self.action = action
        self.sleeper = _sleeper or time.sleep

    def _make_error_msg(self):
        """
        Sum the total number of seconds we waited while providing the number
        of tries we attempted
        """
        total_seconds_waiting = sum(
            itertools.islice(
                itertools.count(self.sleep, self.increment),
                self.tries
            )
        )
        msg = 'reached maximum tries ({tries})' + \
            'after waiting for {total} seconds'
        if self.action:
            msg = "'{action}'" + msg

        msg = msg.format(
            action=self.action,
            tries=self.tries,
            total=total_seconds_waiting,
        )
        return msg

    def __call__(self):
        self.counter += 1
        if self.counter > self.tries:
            error_msg = self._make_error_msg()
            raise MaxWhileTries(error_msg)
        self.sleeper(self.sleep_current)
        self.sleep_current += self.increment

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
