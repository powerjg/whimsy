
Migrating an Existing Test
--------------------------

Migrating an old test to whimsy takes a minor amount of work. We can use the
same :func:`whimsy.gem5.suite.gem5_verify_config` function and
:class:`whimsy.gem5.verifier.Verifier` subclasses we used to create our own
tests. Optionally we could add an additional utility function to make this even
easier, but I would prefer we keep consistency and not port many of the legacy
tests, since most legacy tests serve limited utility.

As an example we'll migrate the old
`quick/se/00.hello/arm/linux/simple-atomic-dummychecker` test. All paths assume
the current working directory is the gem5 base path (i.e., .../gem5/).

Here are the steps:

1. Look in the directory the old test expects a ``test.py`` file to be located in.
2. Move that file and copy it into the slightly different test location
   ``tests/gem5/se/00.hello``  and change the name to ``config.py``.
3. Move the reference files to
   ``tests/gem5/se/00.hello/ARM/simple-atomic-dummychecker``

4. Assuming that the additional config files which set up the old test are not
   ported, we need to do so.

   - To do this copy over the old config
     ``tests/configs/simple-atomic-dummychecker.py`` to
     ``tests/legacy-configs/simple-atomic-dummychecker.py`` (We know this is
     the legacy config name because it is the final name of the old test path.)

5. Create a ``test-hello.py`` file in ``quick/se/00.hello/`` and use
   ``gem5_verify_config`` and verifiers to create a suite that will compare
   gem5 execution to golden standards.

.. code:: python

    from testlib import *

    ref_path = joinpath(getcwd(), 'ARM', 'simple-atomic-dummychecker')

    verifiers = (
            verifier.MatchStdout(joinpath(ref_path, 'simout')),
            verifier.MatchStderr(joinpath(ref_path, 'simerr')),
            verifier.MatchStats(joinpath(ref_path, 'stats.txt')),
            verifier.VerifyReturncode(1),
            )

    # The test program still fits, only the path is changed from 'arm' to 'ARM'
    hello_program = TestProgram('hello', 'ARM', 'linux')

    # This is the path of legacy-configs that share the same base config.
    dummychecker = joinpath(config.base_dir,
                            'tests',
                            'legacy-configs',
                            'simple-atomic-dummychecker.py')

    gem5_verify_config(
            name='test_hello',
            fixtures=(hello_program,),
            verifiers=verifiers,

            # All legacy configs rely on using the run.py script. It has been slightly
            # updated to make it more generic with less assumptions.
            config=joinpath(config.base_dir, 'tests', 'legacy-configs', 'run.py'),

            # Notice that the legacy run.py arguments have changed. It now forces users
            # to specify config files exactly rather than making assumptions on path.
            config_args=['--executable', hello_program.path,
                '--config', dummychecker,
                '--config', joinpath(getcwd(), 'config.py')],
            valid_isas=('ARM',)
    )
