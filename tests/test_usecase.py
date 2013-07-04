import sys, os, shutil, glob
import unittest
import pkgutil

import testenv
import fake_filesystem
import fake_filesystem_shutil
import fake_filesystem_glob

from papers import papers_cmd
from papers import color
from papers.p3 import io, input


    # code for fake fs

real_os = os
real_open = open
real_shutil = shutil
real_glob = glob

fake_os, fake_open, fake_shutil, fake_glob = None, None, None, None

def _mod_list():
    ml = []
    import papers
    for importer, modname, ispkg in pkgutil.walk_packages(
                                        path=papers.__path__,
                                        prefix=papers.__name__+'.',
                                        onerror=lambda x: None):
        ml.append(__import__(modname, fromlist = 'dummy'))
    return ml

mod_list = _mod_list()

def _create_fake_fs():
    global fake_os, fake_open, fake_shutil, fake_glob

    fake_fs = fake_filesystem.FakeFilesystem()
    fake_os = fake_filesystem.FakeOsModule(fake_fs)
    fake_open = fake_filesystem.FakeFileOpen(fake_fs)
    fake_shutil = fake_filesystem_shutil.FakeShutilModule(fake_fs)
    fake_glob = fake_filesystem_glob.FakeGlobModule(fake_fs)

    fake_fs.CreateDirectory(fake_os.path.expanduser('~'))
    __builtins__['open'] = fake_open
    __builtins__['file'] = fake_open

    sys.modules['os']     = fake_os
    sys.modules['shutil'] = fake_shutil
    sys.modules['glob']   = fake_glob

    for md in mod_list:
        md.os = fake_os
        md.shutil = fake_shutil

    return fake_fs

def _copy_data(fs):
    """Copy all the data directory into the fake fs"""
    for filename in real_os.listdir('data/'):
        filepath = 'data/' + filename
        if real_os.path.isfile(filepath):
            with real_open(filepath, 'r') as f:
                fs.CreateFile(filepath, contents = f.read())
        if real_os.path.isdir(filepath):
            fs.CreateDirectory(filepath)


    # redirecting output

def redirect(f):
    def newf(*args, **kwargs):
        old_stderr, old_stdout = sys.stderr, sys.stdout
        stdout = io.StringIO()
        stderr = io.StringIO()
        sys.stdout, sys.stderr = stdout, stderr
        try:
            return f(*args, **kwargs), stdout, stderr
        finally:
            sys.stderr, sys.stdout = old_stderr, old_stdout
    return newf


    # automating input

real_input = input

class FakeInput():
    """ Replace the input() command, and mock user input during tests

        Instanciate as :
        input = FakeInput(['yes', 'no'])
        then replace the input command in every module of the package :
        input.as_global()
        Then :
        input() returns 'yes'
        input() returns 'no'
        input() raise IndexError
     """

    def __init__(self, inputs = None):
        self.inputs = list(inputs) or []
        self._cursor = 0

    def as_global(self):
        for md in mod_list:
            md.input = self

    def add_input(self, inp):
        self.inputs.append(inp)

    def __call__(self):
        inp = self.inputs[self._cursor]
        self._cursor += 1
        return inp


    # putting it all together

def _execute_cmds(cmds, fs = None):
    """ Execute a list of commands, and capture their output

    A command can be a string, or a tuple of size 2 or 3.
    In the latter case, the command is :
    1. a string reprensenting the command to execute
    2. the user inputs to feed to the command during execution
    3. the output excpected, verified with assertEqual

    """

    if fs is None:
        fs = _create_fake_fs()
        _copy_data(fs)

    outs = []
    for cmd in cmds:
        if hasattr('__iter__', cmd):
            if len(cmd) == 2:
                input = FakeInput(cmd[2])
                input.as_global()

            _, stdout, stderr = redirect(papers_cmd.execute)(cmd[0].split())
            if len(cmd) == 3:
                actual_out  = color.undye(stdout.getvalue())
                correct_out = color.undye(cmd[2])
                self.assertEqual(actual_out, correct_out)

        else:
            assert type(cmd) == str
            _, stdout, stderr = redirect(papers_cmd.execute)(cmd.split())

        print stderr
        outs.append(color.undye(stdout.getvalue()))

    return outs


    # actual tests

class TestInit(unittest.TestCase):

    def test_init(self):
        fs = _create_fake_fs()
        papers_cmd.execute('papers init -p paper_test2'.split())
        self.assertEqual(set(fake_os.listdir('/paper_test2/')), {'bibdata', 'doc', 'meta', 'papers.yaml'})


class TestAdd(unittest.TestCase):

    def test_add(self):

        fs = _create_fake_fs()
        _copy_data(fs)

        papers_cmd.execute('papers init'.split())
        papers_cmd.execute('papers add -b /data/pagerank.bib -d /data/pagerank.pdf'.split())

    def test_add2(self):

        fs = _create_fake_fs()
        _copy_data(fs)

        papers_cmd.execute('papers init -p /not_default'.split())
        papers_cmd.execute('papers add -b /data/pagerank.bib -d /data/pagerank.pdf'.split())
        self.assertEqual(set(fake_os.listdir('/not_default/doc')), {'Page99.pdf'})


class TestList(unittest.TestCase):

    def test_list(self):

        fs = _create_fake_fs()
        _copy_data(fs)

        papers_cmd.execute('papers init -p /not_default2'.split())
        papers_cmd.execute('papers list'.split())
        papers_cmd.execute('papers add -b /data/pagerank.bib -d /data/pagerank.pdf'.split())
        papers_cmd.execute('papers list'.split())

class TestInput(unittest.TestCase):

    def test_input(self):

        input = FakeInput(['yes', 'no'])
        self.assertEqual(input(), 'yes')
        self.assertEqual(input(), 'no')
        with self.assertRaises(IndexError):
            input()

    def test_input(self):
        other_input = FakeInput(['yes', 'no'])
        other_input.as_global()
        self.assertEqual(color.input(), 'yes')
        self.assertEqual(color.input(), 'no')
        with self.assertRaises(IndexError):
            color.input()


class TestUsecase(unittest.TestCase):

    def test_first(self):

        correct = ['Initializing papers in /paper_first.\n',
                   'Added: Page99\n',
                   '0: [Page99] L. Page et al. "The PageRank Citation Ranking Bringing Order to the Web"  (1999) \n',
                   '',
                   '',
                   'search network\n',
                   '0: [Page99] L. Page et al. "The PageRank Citation Ranking Bringing Order to the Web"  (1999) search network\n',
                   'search network\n']

        cmds = ['papers init -p paper_first/',
                'papers add -d data/pagerank.pdf -b data/pagerank.bib',
                'papers list',
                'papers tag',
                'papers tag Page99 network+search',
                'papers tag Page99',
                'papers tag search',
                'papers tag 0',
               ]

        self.assertEqual(correct, _execute_cmds(cmds))

    def test_second(self):

        cmds = ['papers init -p paper_second/',
                'papers add -b data/pagerank.bib',
                'papers add -d data/turing-mind-1950.pdf -b data/turing1950.bib',
                'papers add -b data/martius.bib',
                'papers add -b data/10.1371%2Fjournal.pone.0038236.bib',
                'papers list',
                'papers attach Page99 data/pagerank.pdf'
               ]

        _execute_cmds(cmds)

    def test_third(self):

        cmds = ['papers init',
                'papers add -b data/pagerank.bib',
                'papers add -d data/turing-mind-1950.pdf -b data/turing1950.bib',
                'papers add -b data/martius.bib',
                'papers add -b data/10.1371%2Fjournal.pone.0038236.bib',
                'papers list',
                'papers attach Page99 data/pagerank.pdf',
                'papers remove -f Page99',
                'papers remove -f turing1950computing',
               ]

        _execute_cmds(cmds)

