Test Writing By Example
=======================

Writing A Verifier Test
-----------------------

Since all testing in gem5 right now entirely follows the same format,
(run a config of gem5, then compare output to a known standard) Whimsy
tries to make this common case simple and the intent explicit. Whimsy
provides a general utility function :func:`whimsy.gem5.suite.gem5_verify_config` and mixin
:class:`whimsy.gem5.verifier.Verifier` classes.

Let's create a simple test which can runs gem5 and a config file for all
ISAs and optimization versions and checks that the exit status of gem5
was 0.

.. code:: python

    from testlib import *

    verifier = VerifyReturncode(0)

    gem5_verify_config(
        name='simple_gem5_returncode_test',

        # Pass our returncode verifier here.
        verifiers=(verifier,),

        # Use the pretend config file in the same directory as this test.
        config=joinpath(getcwd(), 'simple-config.py'),
    )

We could then use the list command to look at the tests we have created.

.. code:: bash

    $ ./main.py list . --tests
    ==========================================================================================
    Loading Tests

    Discovered 30 tests and 15 testsuites in /home/swilson/Projects/whimsy/docs/examples/simple_returncode_test.py
    ==========================================================================================
    Listing all TestCases.
    ==========================================================================================
    docs/examples:TestCase:simple_gem5_returncode_test [X86 - opt]
    docs/examples:TestCase:simple_gem5_returncode_test [X86 - opt] (VerifyReturncode verifier)
    docs/examples:TestCase:simple_gem5_returncode_test [SPARC - opt]
    docs/examples:TestCase:simple_gem5_returncode_test [SPARC - opt] (VerifyReturncode verifier)
    docs/examples:TestCase:simple_gem5_returncode_test [ALPHA - opt]
    docs/examples:TestCase:simple_gem5_returncode_test [ALPHA - opt] (VerifyReturncode verifier)
    docs/examples:TestCase:simple_gem5_returncode_test [RISCV - opt]
    docs/examples:TestCase:simple_gem5_returncode_test [RISCV - opt] (VerifyReturncode verifier)
	... 22 More tests elided...

A less contrived example is to run gem5 using a config and a test
program. Here's an example of how to do this as well:

.. code:: python

    from testlib import *

    verifiers = (
            # Create a verifier that will check that the output 
            # contains the regex 'hello'
            verifier.MatchRegex('hello'),

            # The se.py script is dumb and sets a strange return code on success.
            verifier.VerifyReturncode(1),)
    hello_program = TestProgram('hello', 'X86', 'linux')

    gem5_verify_config(
        name='test_hello',

        # We now rely on the hello_program to be built before this test is run.
        fixtures=(hello_program,),
        verifiers=verifiers,

        # Use the se.py config from configs/example/se.py
        config=joinpath(config.base_dir, 'configs', 'example','se.py'),

        # Give the config the command and path.
        config_args=['--cmd', hello_program.path],

        # The hello_program only works on the X86 ISA.
        valid_isas=('X86',)
    )

The new additions to pick out from this example are:

-  We are handing a tuple of verifiers to ``gem5_verify_config``. We can
   provide any number of these.
-  We created a ``TestProgram`` - a fixture which will be ``setup``
   before our suite runs. We can also hand any number of these to
   ``gem5_verify_config``.
-  We can hand config arguments by passing and array of flags/args under
   the kwarg ``config_args``

Running Your Test
~~~~~~~~~~~~~~~~~

There are now a few ways to run this last suite we've just created.

First we could run every test in the directory it's stored in. Assuming you
file is stored in ``tests/gem5/example/test-hello.py``. we would run it
by executing the command:

.. code:: bash

    ext/whimsy/main.py run tests/gem5

If we only want to run this specific suite we need to run by giving the
uid:

.. code:: bash

    ext/whimsy/main.py run tests/gem5 --uid 'gem5/example/test-hello:TestSuite:simple_gem5_returncode_test [X86 - opt]'

If we want to run all the tests with the X86 tag we could run it with
one of the tags that was automatically added by ``gem5_verify_config``:

.. code:: bash

    ext/whimsy/main.py run tests/gem5 --tags X86

A Test From Scratch
-------------------

The ``gem5_verify_config`` method covers all the use cases of the old
testing framework as far as I know, however the major reason for
creating a new framework is so we have test cases that **actually test
something**. (It's of my opinion that the old tests are all but useless
and should be scrapped save for a couple for top level functional
testing.) As such, advanced users should be able to create their own
tests easily.

As a 'simple' example we'll duplicate some functionality of
``gem5_verify_config`` and create a test that manually spawns gem5 and
checks it's return code.

.. code:: python

    from testlib import *

    # Create a X86/gem5.opt target fixture.
    gem5 = Gem5Fixture(constants.x86_tag, constants.opt_tag)

    # Use the helper function wrapper which creates a TestCase out of this
    # function. The test will automatically get the name of this function. The
    # fixtures provided will automatically be given to us by the test runner as
    # a dictionary of the format fixture.name -> fixture
    @testfunction(fixtures=(gem5,), 
                  tags=[constants.x86_tag, constants.opt_tag])
    def test_gem5_returncode(fixtures):

        # Collect our gem5 fixture using the standard name and get the path of it.
        gem5 = fixtures[constants.gem5_binary_fixture_name].path

        command = [
            gem5,
            config=joinpath(config.base_dir, 'configs', 'example','se.py'),
        ]

        try: 
            # Run the given command sending it's output to our log at a low
            # priorirty verbosity level.
            log_call(command)
        except CalledProcessError as e:
            if e.returncode == 1:
                # We can fail by raising an exception
                raise e 

            elif e.returncode == 2:
                # We can also fail manually with the fail method.
                test.fail("Return code was 2?!")

        # Returncode was 0
        # When we return this test will be marked as passed.

Since the test function was not placed into a test suite by us, when it
is collected by the ``TestLoader`` it will automatically be placed into
a ``TestSuite`` with the name of the module.

Writing Your Own Fixtures
~~~~~~~~~~~~~~~~~~~~~~~~~

:class:`whimsy.fixture.Fixture` objects are a major component in writing
modular and composable tests while reducing code reuse. There are quite a few
``Fixture`` classes built in, but they might not be sufficient.

We'll pretend we have a test that requires we create a very large empty
blob file so gem5 can use it as a disk. *(This might be a bit contrived.)*

.. code:: python

    from testlib import *
    import os

    class DiskGeneratorFixture(Fixture):
        def __init__(self, path, size, name):
            super(DiskGeneratorFixture, self).__init__(
                  name, 
                  # Don't build this at startup, wait until a test that uses this runs.
                  lazy_init=True, 
                  # If multiple test suites use this, don't rebuild this fixture each time.
                  build_once=True)

            self.path = path
            self.size = size

        def setup(self):
            # This method is called from the Runner when a TestCase that uses this
            # fixture is about to run.

            super(DiskGeneratorFixture, self).setup()

            # Create the file using the dd program.
            log_call(['dd', 'if=/dev/zero', 'of=%s' % self.path, 'count=%d' % self.size])

        def teardown(self):
            # This method is called after the test or suite that uses this fixture
            # is done running.

            # Remove the file.
            os.remove(self.path)


.. include:: migrating.rst
