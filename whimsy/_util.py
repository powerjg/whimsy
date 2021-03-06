'''
Contains utility functions used throughout the testframework.
'''
import collections
import difflib
import helper
import os
import re
import shutil
import stat
import tempfile
import time

# For now expose this here, we might need to make an implementation if not
# everyone has python 2.7
from collections import OrderedDict
from helper import absdirpath

class Enum(object):
    '''
    Generator for Enum objects.
    '''
    def __init__(self, enums):
        self.enums = []

        for idx, enum in enumerate(enums):
            new_enum = _EnumVal(enum, idx, self.enums)
            self.enums.append(new_enum)
            setattr(self, enum, new_enum)


class _EnumVal(object):
    def __init__(self, name, val, enums):
        self.val = val
        self.name = name
        self.enums = enums

    def __str__(self):
        return self.name

    def __cmp__(self, other):
        return self.val.__cmp__(other.val)


class Timer(object):
    def __init__(self, start=False):
        self.reset()

    def start(self):
        if self._start is None:
            self._start = time.time()

    def stop(self):
        self._finish = time.time()
        return self.runtime()

    def runtime(self):
        return self._finish - self._start

    def reset(self):
        self._start = self._finish = None


def iter_recursively(self, inorder=True, yield_container=False):
    '''
    Recursively iterate over all items contained in this collection.

    :param inorder: Traverses the tree in in-order fashion, returning nodes as
    well as leaves.
    '''
    for item in self:
        if isinstance(item, collections.Iterable):
            if inorder and not yield_container:
                # yield the node first
                yield item

            # Recurse into that node.
            for item_of_item in iter_recursively(
                    item, inorder,
                    yield_container):
                yield item_of_item
        else:
            # Otherwise just yield the leaf
            if yield_container:
                yield (self, item)
            else:
                yield item


unexpected_item_msg = \
        'Only TestSuites and TestCases should be contained in a TestSuite'

class AttrDict(object):
    '''Object which exposes its own internal dictionary through attributes.'''
    def __init__(self, dict_={}):
            self.__dict__.update(dict_)

    def __getattr__(self, attr):
        dict_ = self.__dict__
        if attr in dict_:
            return dict_[attr]
        raise AttributeError('Could not find %s attribute' % attr)

    def __setattr__(self, attr, val):
        self.__dict__[attr] = val


def _filter_file(fname, filters):
    with open(fname, "r") as file_:
        for line in file_:
            for regex in filters:
                if re.match(regex, line):
                    break
            else:
                yield line


def _copy_file_keep_perms(source, target):
    '''Copy a file keeping the original permisions of the target.'''
    st = os.stat(target)
    shutil.copy2(source, target)
    os.chown(target, st[stat.ST_UID], st[stat.ST_GID])


def _filter_file_inplace(fname, filters):
    '''
    Filter the given file writing filtered lines out to a temporary file, then
    copy that tempfile back into the original file.
    '''
    reenter = False
    (_, tfname) = tempfile.mkstemp(text=True)
    with open(tfname, 'w') as tempfile_:
        for line in _filter_file(fname, filters):
            tempfile_.write(line)

    # Now filtered output is into tempfile_
    _copy_file_keep_perms(tfname, fname)


def diff_out_file(ref_file, out_file, ignore_regexes=tuple()):
    if not os.path.exists(ref_file):
        raise OSError("%s doesn't exist in reference directory"\
                                     % ref_file)
    if not os.path.exists(out_file):
        raise OSError("%s doesn't exist in output directory" % out_file)

    _filter_file_inplace(out_file, ignore_regexes)
    _filter_file_inplace(ref_file, ignore_regexes)

    #try :
    (_, tfname) = tempfile.mkstemp(text=True)
    with open(tfname, 'r+') as tempfile_:
        try:
            helper.log_call(['diff', out_file, ref_file], stdout=tempfile_)
        except OSError:
            # Likely signals that diff does not exist on this system. fallback
            # to difflib
            with open(out_file, 'r') as outf, open(ref_file, 'r') as reff:
                diff = difflib.unified_diff(iter(reff.readline, ''),
                                            iter(outf.readline, ''),
                                            fromfile=ref_file,
                                            tofile=out_file)
                return ''.join(diff)
        except helper.CalledProcessError:
            tempfile_.seek(0)
            return ''.join(tempfile_.readlines())
        else:
            return None


def uid(testitem, class_name=None):
    '''
    The generic function used to produce uid of test objects.
    '''
    # Trim the file path to be the path relative to the parent of this
    # directory.
    filepath = testitem.path
    filepath = os.path.relpath(filepath,
                               os.path.commonprefix(
                                       (absdirpath(__file__),
                                       filepath)))
    fmt = '{file}:{class_}:{name}'
    if class_name is None:
        class_name = testitem.__class__.__name__
    return fmt.format(file=filepath, name=testitem.name,
                      class_=class_name)
