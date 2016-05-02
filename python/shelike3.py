# Shell like function for Python3.

from copy import deepcopy
from functools import update_wrapper
from glob import fnmatch
from io import StringIO
from itertools import count
import inspect
import os
import re
from subprocess import Popen, PIPE
import sys


def shellcmd(cmd):
    return Popen(cmd, shell=True, stdout=PIPE).stdout


def find(topdir, filepat):
    for path, dirlst, filelst in os.walk(topdir):
        for name in fnmatch.filter(filelst, filepat):
            yield os.path.join(path, name)


class pipeable:
    """This decorator makes a function useable in a pipe line.

    Either a function or a class can be given to the constructor.
    The first argument of the function should be a sequence.

    After decoration, if the function is called with
    1. Required number of arguments, the orginal function is called.
    2. One less number of arguments than required, the arguments are stored for
       use when it is called on the pipe line.
    3. Otherwise, raise TypeError exception.

    Currently, optional argument is not supported.
    """
    def __init__(self, method):
        self.func = method
        self.args = []
        self.kwds = {}
        self.reqlen = 0
        # Since we need to allow classes to be used in pipe, there are cases that
        # method is not a function.
        if hasattr(self.func, '__code__'):
            self.reqlen = self.func.__code__.co_argcount
        # makes the wrapper object looks like the wrapped function
        update_wrapper(self, method)

    def __call__(self, *args, **kwds):
        curlen = len(args) + len(kwds)
        # An ugly hack to handle classes.
        if curlen >= self.reqlen:
            return self.func(*args, **kwds)
        elif curlen != self.reqlen - 1:
            raise TypeError(
                'Arguments number wrong. required {} got {}'.format(
                    self.reqlen, curlen
                ))

        cpy = deepcopy(self)
        cpy.args = args
        cpy.kwds = kwds
        return cpy

    def __ror__(self, iter):
        # I want to put iter as the last argument of a function, then it seems
        # like currying a function when calling the decorated function with
        # less arguments. But *args can only come after normal arguments, so it
        # has to be the first argument in the function.
        return self.func(iter, *self.args, **self.kwds)


@pipeable
def cat(files):
    """Either give a file name or list of file."""
    if files.__class__ == str:
        files = [files]
    for f in files:
        with open(f) as s:
            for line in s:
                yield line


@pipeable
def shell(iter, cmd=None):
    """Invoke shell command and integrate it in the pipe line."""
    pipe = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE)
    return pipe.communicate(''.join(iter))[0].splitlines(True)


@pipeable
def grep(iter, match):
    if callable(match):
        fun = match
    else:
        fun = re.compile(match).match
    return filter(fun, iter)


@pipeable
def tr(iter, transform):
    return map(transform, iter)


class trclass:
    """apply arbitrary transform to each sequence element"""
    def __init__(self, transform):
        self.tr = transform

    def __ror__(self, iter):
        return map(self.tr, iter)


@pipeable
def printlines(iter, sep, filename):
    if filename is None:
        file = sys.stdout
    else:
        file = open(filename, 'w')
    first = True
    for line in iter:
        if first:
            file.write(str(line))
            first = False
        else:
            file.write(sep)
            file.write(str(line))
    if filename is not None:
        file.close()


@pipeable
def notempty(iter):
    """If the iterable sequence is empty"""
    for i in iter:
        return True
    return False


# those objects transform generator to list, tuple, dict or string
aslist = pipeable(list)
asdict = pipeable(dict)
astuple = pipeable(tuple)
asstring = pipeable(''.join)

# this object transforms seq to tuple sequence
enum = pipeable(lambda input: zip(count(), input))

if __name__ == '__main__':
    #######################
    # example 1: equivalent to shell grep ".*/bin/bash" /etc/passwd
    cat('/etc/passwd') | grep('.*/bin/bash') | printlines(sep='\n', filename=None)

    #######################
    # example 2: get a list of int's methods beginning with '__r'
    print(dir(int) | grep('__r') | aslist)

    #######################
    # example 3: useless; returns a dict {0:'l', 1:'a', 2:'m', 3:'b', 4:'d', 5:'a'} 
    print('lambda' | enum | asdict)
