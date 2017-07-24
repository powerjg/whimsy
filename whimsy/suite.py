# Suites should have ability to be parallelized...
# Suites should provide fixtures for their contained test cases..
# How?

import _util

class TestSuite(object):
    '''An object containing a collection of tests or other test suites.'''
    def __init__(self, name, items=None, fixtures=None, failfast=True, parallelizable=False):
        '''
        All test suites are implicitly added into the top_level TestSuite.
        This forms a DAG so test runners can traverse this running test suite
        collections.

        :param items: A list of TestCase classes or TestSuite objects.

        :param name:

        :param failfast: If True indicates the first test to fail in the test
        suite will cause the execution of the test suite to halt.

        :param paralleizable: keyword only arg - indicates that tests and
        suites contained within are parallelizable with respect to eachother.
        '''

        self.name = name
        self.items = []
        self.failfast = failfast
        self.parallelizable = parallelizable

        if isinstance(fixtures, list):
            fixtures = {fixture.name: fixture for fixture in fixtures}
        elif fixtures is None:
            fixtures = {}
        self.fixtures = fixtures

        if items is not None:
            self.add_items(*items)

    def add_items(self, *items):
        '''Add the given items (TestCases or TestSuites) to this collection'''
        self.items.extend(items)

    def require_fixture():
        '''
        Require the given fixture to run this test suite and all its
        elements.
        '''
        pass

    def _detect_cycle(self):
        '''
        Traverse the DAG looking for cycles.

        Note: Since we don\'t currently allow duplicates in test suites, this
        logic is simple and we can just check that there are no duplicates.
        '''
        collected_set = set()
        def recursive_check(test_suite):
            if type(test_suite) == TestSuite:
                for item in test_suite:
                    if item in collected_set:
                        return True
                    collected_set.add(item)
                recursive_check(item)
            return False
        return recursive_check(self)

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    iter_inorder = lambda self: _util.iter_recursively(self, inorder=True)
    iter_inorder.__doc__ = \
            '''
            Iterate over all the testsuites and testcases contained in this
            testsuite. Traverses the tree in in-order fashion.
            '''
    iter_leaves = lambda self: _util.iter_recursively(self, inorder=False)
    iter_leaves.__doc__ = \
            '''
            Recursively iterate over all the testcases contained in this
            testsuite and testsuites we contain.
            '''

    def enumerate_fixtures(self):
        '''
        Traverse all our subsuites and testcases and return a list of all
        their fixtures.
        '''
        fixtures = []
        for item in self.items:
            if isinstance(item, TestSuite):
                fixtures.extend(item.enumerate_fixtures())
            else:
                fixtures.extend(item.fixtures.values())
        return fixtures
