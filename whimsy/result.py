import abc
import collections
import time
import xml.etree.ElementTree as ET
import string

import _util

class InvalidResultException(Exception):
    pass

Result = _util.Enum(
    {
    'PASS',   # The test passed successfully.
    'XFAIL',  # The test ran and failed as expected.
    'SKIP',   # The test was skipped.
    'FAIL',   # The test failed to pass.
    'ERROR',  # There was an error during the setup of the test.
    },
    namespace='Result'
)

Result.failfast = {Result.ERROR, Result.FAIL}

class TestResult(object):
    '''
    Base Test Result class, acts as an ABC for TestResults. Can't be
    instantiated, but __init__ should be called by subclasses.
    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        '''
        :var timer: A timer used for timing the Test.
        :var result: The Result value of the Test.
        '''
        self.timer = _util.Timer()
        # I want to be able to store all output from the test in this.
        #
        # Subclasses, such as a gem5 test result might contain more results,
        # but it's up to them to concatinate them into standard formats.

    @property
    def runtime(self):
        return self.timer.runtime()

    @abc.abstractproperty
    def result():
        '''Should return the result of the TestResult.'''
        pass

    @abc.abstractproperty
    def name():
        pass

class TestCaseResult(TestResult):
    '''
    Holds information corresponding to a single test case result.
    '''
    def __init__(self, testcase, result=None, *args, **kwargs):
        super(TestCaseResult, self).__init__(*args, **kwargs)
        self.testcase = testcase
        self._result = result

    @property
    def result(self):
        return self._result

    @result.setter
    def result(self, val):
        self._result = val

    @property
    def name(self):
        return self.testcase.name


class TestSuiteResult(TestResult):
    '''
    Holds information containing one or more test cases or suites.
    '''
    def __init__(self, testsuite, results=None, *args, **kwargs):
        super(TestSuiteResult, self).__init__(*args, **kwargs)


        self.testsuite = testsuite
        if results is None:
            results = [None] * len(testsuite)

        # Assert that if given results that they have the correct number
        # for the given test suite.
        # TODO: Change from assert to an exception.
        assert(len(testsuite) == len(results))

        self.results = results

    @property
    def result(self):
        '''
        A test suite can have the following results, they occur with the
        following priority/ordering.

        ERROR - Indicates that some error happened outside of a test case,
        likely in fixture setup.

        FAIL - Indicates that one or more tests failed.

        SKIP - Indicates that all contained tests and test suites were
        skipped.

        PASS - Indicates that all tests passed or EXFAIL'd
        '''
        failed = False
        all_skipped = True

        for result in self.results:
            result = result.result
            if result == Result.ERROR:
                return Result.ERROR
            if result != Result.SKIP:
                all_skipped = False
            if result == Result.FAIL:
                failed = True

        if failed:
            return Result.FAIL
        if all_skipped:
            return Result.SKIP
        return Result.PASS

    @property
    def name(self):
        return self.testsuite.name

    def iterate_tests(self):
        '''
        Returns an iterable over all the TestCaseResults contained in the suite

        (Pretends that this is the only suite and that it contains all tests
        directly.)
        '''
        for result in self:
            if isinstance(result, TestCaseResult):
                yield result

    def __iter__(self):
        '''
        Iterate over all the results contained in this collection of results.
        Traverses the tree in in-order fashion.
        '''
        for result in self.results:
            if isinstance(result, collections.Iterable):
                # Check other iterable collections for their results.
                for result in result:
                    yield result
            else:
                # Otherwise just yield the test case result
                yield result


class ResultFormatter(object):
    '''
    Formats TestResults into a specific output.
    '''
    __metaclass__ = abc.ABCMeta
    def __init__(self, result):
        self.result = result

    @abc.abstractmethod
    def __str__(self):
        '''
        Returns the result formatted as a string using the implemented result
        formatter.
        '''


class JUnitFormatter(ResultFormatter):
    '''
    Formats TestResults into the JUnit XML format.
    '''

    # Results considered passing under JUnit, we have a couple extra states
    # that aren't traditionally reported under JUnit.
    passing_results = {Result.PASS, Result.XFAIL}

    def __init__(self, result, translate_names=True):
        super(JUnitFormatter, self).__init__(result)

        if translate_names:
            self.name_table = string.maketrans("/.", ".-",)
        else:
            self.name_table = string.maketrans("", "")

    def __str__(self):
        self.root = ET.Element("testsuites")
        et = ET.ElementTree(self.convert_testsuite(self.root, self.result))
        return ET.tostring(self.root)

    def convert_testcase(self, xtree, testcase):
        xtest = ET.SubElement(xtree, "testcase",
                               name=testcase.name,
                               time="%f" % testcase.runtime)

        if testcase.result in self.passing_results:
            xstate = Result.PASS
        elif testcase.result == Result.SKIP:
            xstate = ET.SubElement(x_test, "skipped")
        elif testcase.result == Result.FAIL:
            xstate = ET.SubElement(x_test, "failure")
        elif testcase.result == Result.ERROR:
            xstate = ET.SubElement(x_test, "error")
        else:
            assert False, "Unknown test state"

        if xstate is not Result.PASS:
            #TODO: Add extra output to the text?
            #xstate.text = "\n".join(msg)
            pass

        return xtest


    def convert_testsuite(self, xtree, suite):
        xsuite = ET.SubElement(xtree, "testsuite",
                                name=suite.name.translate(self.name_table),
                                time="%f" % suite.runtime)
        errors = 0
        failures = 0
        skipped = 0

        # Iterate over the tests and suites held in the test suite.
        for result in suite:
            # If the element is a test case attach it as such
            if isinstance(result, TestCaseResult):
                self.convert_testcase(xtree, result)
            else:
                # Otherwise recurse
                self.convert_testsuite(xtree, result)

            # Check the return value to fill in metadata for our xsuite
            if result.result not in self.passing_results:
                if test.state == Result.SKIP:
                    skipped += 1
                elif test.state == Result.ERROR:
                    errors += 1
                elif test.state == Result.FAIL:
                    failures += 1
                else:
                    assert False, "Unknown test state"

        xsuite.set("errors", str(errors))
        xsuite.set("failures", str(failures))
        xsuite.set("skipped", str(skipped))
        xsuite.set("tests", str(len(suite.results)))

        return xsuite


if __name__ == '__main__':
    import whimsy.suite as suite
    named_object = lambda : None
    named_object.name = 'testcase'
    testsuite = suite.TestSuite('testsuite', items=[None]*2)
    suiteresult = TestSuiteResult(testsuite)

    suiteresult.timer.start()
    suiteresult.timer.stop()

    suiteresult.results[0] = TestCaseResult(named_object, result=Result.PASS)
    suiteresult.results[0].timer.start()
    suiteresult.results[0].timer.stop()

    suiteresult.results[1] = TestCaseResult(named_object, result=Result.PASS)
    suiteresult.results[1].timer.start()
    suiteresult.results[1].timer.stop()

    formatter = JUnitFormatter(suiteresult)
    print(formatter)
