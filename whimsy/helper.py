'''
Helper classes for writing tests with this test library.
'''
import logging
import subprocess
import tempfile
import threading
import collections
import os

# Export CalledProcessError
from subprocess import CalledProcessError

import logger

def log_call(command, *popenargs, **kwargs):
    '''
    Calls the given process and automatically logs the command and output.

    If stdout or stderr are provided output will also be piped into those
    streams as well.

    :params stdout: Iterable of items to write to as we read from the
    subprocess.
    :params stderr: Iterable of items to write to as we read from the
    subprocess.
    '''
    if isinstance(command, str):
        cmdstr = command
    else:
        cmdstr = ' '.join(command)

    logger.log.trace('Logging call to command: %s' % cmdstr)

    stdout_redirect = kwargs.get('stdout', tuple())
    stderr_redirect = kwargs.get('stderr', tuple())

    if hasattr(stdout_redirect, 'write'):
        stdout_redirect = (stdout_redirect,)
    if hasattr(stderr_redirect, 'write'):
        stderr_redirect = (stderr_redirect,)

    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.PIPE
    p = subprocess.Popen(command, *popenargs, **kwargs)

    def log_output(log_level, pipe, redirects=tuple()):
        # Read iteractively, don't allow input to fill the pipe.
        for line in iter(pipe.readline, ''):
            for r in redirects:
                r.write(line)
            line = line.rstrip()
            logger.log.log(log_level, line)

    stdout_thread = threading.Thread(target=log_output,
                                     args=(logging.TRACE, p.stdout,
                                           stdout_redirect))
    stdout_thread.setDaemon(True)
    stdout_thread.start()

    stderr_thread = threading.Thread(target=log_output,
                                     args=(logging.TRACE, p.stderr,
                                           stderr_redirect))
    stderr_thread.setDaemon(True)
    stderr_thread.start()

    retval = p.wait()
    stdout_thread.join()
    stderr_thread.join()
    # Return the return exit code of the process.
    if retval != 0:
        raise CalledProcessError(retval, cmdstr)


# lru_cache stuff (Introduced in python 3.2+)
# Renamed and modified to cacheresult
class _HashedSeq(list):
    '''
    This class guarantees that hash() will be called no more than once per
    element. This is important because the cacheresult() will hash the key
    multiple times on a cache miss.

    From cpython 3.7
    '''

    __slots__ = 'hashvalue'

    def __init__(self, tup, hash=hash):
        self[:] = tup
        self.hashvalue = hash(tup)

    def __hash__(self):
        return self.hashvalue

def _make_key(args, kwds, typed,
             kwd_mark = (object(),),
             fasttypes = {int, str, frozenset, type(None)},
             tuple=tuple, type=type, len=len):
    '''
    Make a cache key from optionally typed positional and keyword arguments.
    The key is constructed in a way that is flat as possible rather than as
    a nested structure that would take more memory.  If there is only a single
    argument and its data type is known to cache its hash value, then that
    argument is returned without a wrapper. This saves space and improves
    lookup speed.

    From cpython 3.7
    '''
    key = args
    if kwds:
        key += kwd_mark
        for item in kwds.items():
            key += item
    if typed:
        key += tuple(type(v) for v in args)
        if kwds:
            key += tuple(type(v) for v in kwds.values())
    elif len(key) == 1 and type(key[0]) in fasttypes:
        return key[0]
    return _HashedSeq(key)


def cacheresult(function, typed=False):
    '''
    :param typed: If typed is True, arguments of different types will be cached
    separately. I.e. f(3.0) and f(3) will be treated as distinct calls
    with distinct results.

    From cpython 3.7
    '''
    sentinel = object()          # unique object used to signal cache misses
    make_key = _make_key         # build a key from the function arguments
    cache = {}
    def wrapper(*args, **kwds):
        # Simple caching without ordering or size limit
        key = _make_key(args, kwds, typed)
        result = cache.get(key, sentinel)
        if result is not sentinel:
            return result
        result = function(*args, **kwds)
        cache[key] = result
        return result
    return wrapper

class OrderedSet(collections.MutableSet):
    '''
    Maintain ordering of insertion in items to the set with quick iteration.

    http://code.activestate.com/recipes/576694/
    '''

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map or update:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def update(self, keys):
        for key in keys:
            self.add(key)

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)

def absdirpath(path):
    '''
    Return the directory component of the absolute path of the given path.
    '''
    return os.path.dirname(os.path.abspath(path))

joinpath = os.path.join

if __name__ == '__main__':
    log_call(' '.join(['echo', 'hello', ';sleep 3', '; echo yo']), shell=True)
