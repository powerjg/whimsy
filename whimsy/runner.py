import tempfile
import sys
import logging

import whimsy.logger as logger
import whimsy.test as test
import whimsy.suite as suite
import whimsy.result
from whimsy.result import Result
import whimsy.terminal as terminal

class Runner(object):
    '''
    The default runner class used for running test suites and cases.
    '''

    def run_suite(self, test_suite, results=None, fixtures={}):
        '''
        Run all tests/suites. From the given test_suite.

        1. Handle setup for all fixtures in the test_suite
        2. Run child tests and test_suites passing them their required
           fixtures.
           - Collect results as tests are performed.
        3. Handle teardown for all fixtures in the test_suite.
        '''
        if results is None:
            results = whimsy.result.TestSuiteResult(test_suite.name)

        for name, fixture in test_suite.fixtures.items():
            fixture.setup()

        # We'll use a local shallow copy of fixtures to make it easier to
        # cleanup and override local fixtures.
        fixtures = fixtures.copy()
        fixtures.update(test_suite.fixtures)

        suite_iterator = enumerate(test_suite)

        for (idx, item) in suite_iterator:
            logger.log.info(terminal.separator())

            if isinstance(item, suite.TestSuite):
                result = self.run_suite(item, fixtures=fixtures)
            elif isinstance(item, test.TestCase):
                result = self.run_test(item, fixtures=fixtures)
            else:
                assert(False)

            # Add the result of the test or suite to our test_suite results.
            results.results.append(result)

            if test_suite.failfast \
                    and result.result in Result.failfast:
                logger.log.inform('Previous test failed in a failfast suite,'
                                  ' skipping remaining tests.')
                self._generate_skips(results, suite_iterator)
                break

        for fixture in test_suite.fixtures.values():
            fixture.teardown()

        return results

    def run_test(self, test, fixtures={}, result=None):
        '''
        Run the given test.

        This performs the bulkwork of the testing framework.
        1. Handle setup for all fixtures required for the specific test.
        2. Run the test.
        3. Teardown the fixtures for the test which are tied locally to the
           test?
        '''
        if result is None:
            result = whimsy.result.TestCaseResult(test.name)

        for name, fixture in test.fixtures.items():
            fixture.setup()

        # We'll use a local shallow copy of fixtures to make it easier to
        # cleanup and override local fixtures.
        fixtures = fixtures.copy()
        fixtures.update(test.fixtures)

        logger.log.info('Starting TestCase: %s' % test.name)
        result.timer.start()
        try:
            test.test(result=result, fixtures=fixtures)
        except:
            result.result = whimsy.result.Result.FAIL
        result.timer.stop()

        if result.result is None:
            result.result = whimsy.result.Result.PASS
        logger.log.info(terminal.insert_separator(' %s '%result.result))

        for name in test.fixtures:
            fixtures[name].teardown()

        return result

    def _generate_skips(self, results, remaining_iterator):
        '''
        Generate SKIP for all remaining tests (for use with the failfast
        suite option)
        '''
        for (idx, item) in remaining_iterator:
            if isinstance(item, suite.TestSuite):
                result = whimsy.result.TestSuiteResult(item.name)
            elif isinstance(item, test.TestCase):
                result = whimsy.result.TestCaseResult(item.name)
                result.result = Result.SKIP
            else:
                assert(False)
            results.results.append(result)
