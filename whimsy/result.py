import abc
import collections
import time
import xml.etree.ElementTree as ET
import string

import _util
import whimsy.terminal as termcap

class InvalidResultException(Exception):
    pass

Result = _util.Enum(
    [
    'PASS',   # The test passed successfully.
    'XFAIL',  # The test ran and failed as expected.
    'SKIP',   # The test was skipped.
    'ERROR',  # There was an error during the setup of the test.
    'FAIL',   # The test failed to pass.
    ],
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
    def __init__(self, name, result=None, reason=None, *args, **kwargs):
        super(TestCaseResult, self).__init__(*args, **kwargs)
        self._result = result
        self._name = name
        self.reason = reason

    @property
    def result(self):
        return self._result

    @result.setter
    def result(self, val):
        self._result = val

    @property
    def name(self):
        return self._name


class TestSuiteResult(TestResult):
    '''
    Holds information containing one or more test cases or suites.
    '''
    def __init__(self, name, *args, **kwargs):
        super(TestSuiteResult, self).__init__(*args, **kwargs)
        self._name = name
        self.results = []

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
        return self._name

    def iter_tests(self):
        '''
        Returns an iterable over all the TestCaseResults contained in the suite

        (Pretends that this is the only suite and that it contains all tests
        directly.)
        '''
        for result in self.iter_inorder():
            if isinstance(result, TestCaseResult):
                yield result

    def iter_inorder(self):
        '''
        Iterate over all the results contained in this collection of results.
        Traverses the tree in in-order fashion.
        '''
        for result in self.results:
            if isinstance(result, TestSuiteResult):
                # yield the testsuite first
                yield result

                # Then yield that testsuite's results.
                for result in result:
                    yield result
            else:
                # Otherwise just yield the test case result
                yield result

    def __iter__(self):
        '''
        Return an iterator over the test suites and cases just in this suite.
        '''
        return iter(self.results)


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

class ConsoleFormatter(ResultFormatter):
    '''
    Formats results for a console.
    '''
    color = termcap.get_termcap()
    reset = color.Normal
    result_colormap = {
        Result.FAIL: color.Red,
        Result.ERROR: color.Red,
        Result.PASS: color.Green,
        Result.XFAIL: color.Cyan,
        Result.SKIP: color.Cyan,
    }
    sep_fmtkey = 'separator'
    sep_fmtstr = '{%s}' % sep_fmtkey
    verbosity_levels = _util.Enum([
            'FATAL',
            'INFO',
            'DEBUG',])

    def __init__(self, result, verbosity=verbosity_levels.INFO, only_testcases=True):
        super(ConsoleFormatter, self).__init__(result)
        self.only_testcases = only_testcases
        self.verbosity = verbosity

    def format_test(self, test):
        string = '{color}{result}: {name}{reset}\n'.format(
                color=self.result_colormap[test.result],
                result=test.result,
                name=test.name,
                reset=self.reset)
        if self.verbosity > self.verbosity_levels.DEBUG:
            if test.reason:
                string += '\nFailure Reason:\n\n'
                string += '%s\n' % test.reason
        return string

    def format_tests(self, suite):
        string = bytearray('')
        for testcase in suite:
            string += self.sep_fmtstr
            string += self.format_test(testcase)
        string += self.sep_fmtstr

        return str(string)

    def format_summary(self, summary):
        result_heading = 'Result'
        count_heading = 'Count'
        h_sep = ' | '
        v_sep = '-'

        summary = {name:len(results) for name, results in summary.items() }

        # First get the alignment to start/stop numbers at.
        namestrings = map(str, Result.enums)
        namestrings.append(result_heading)
        maxname = max(map(len, namestrings))

        result_strings = map(str, summary.values())
        result_strings.append(count_heading)
        maxresult = max(map(len, result_strings))

        divider = '{:-%d}' % (maxname + maxresult + len(h_sep))
        summarystring = '{result: <{maxname}}{h_sep}{count: >{maxresult}}\n'.format(
                h_sep=h_sep,
                maxname=maxname,
                maxresult=maxresult,
                result=result_heading,
                count=count_heading)
        formatstring = '{name: <{maxname}}{h_sep}{count: >{maxresult}}\n'

        # Actually start building our string now.
        string = bytearray(summarystring)
        string += len(summarystring) * '-' + '\n'
        # Iterate through the results in the specified order by the enum type.
        for key in Result.enums:
            string += formatstring.format(
                    h_sep=h_sep,
                    name=key,
                    count=summary[key],
                    maxname=maxname,
                    maxresult=maxresult)
        return str(string)

    def summarize_results(self):
        # If only_testcases don't summarize information about suites.
        summary = {enum:[] for enum in Result.enums}
        if self.only_testcases:
            for test in self.result.iter_tests():
                summary[test.result].append(test)
        return summary

    def format_separators(self, string):
        (termw, termh) = termcap.terminal_size()
        format_separators = {self.sep_fmtkey: '='*termw}
        return string.format(**format_separators)

    def __str__(self):
        string = ''
        # If we only care about printing test cases logic looks simpler.
        if self.only_testcases:
            string = self.format_tests(self.result.iter_tests())

        string += self.format_summary(self.summarize_results())
        string += self.sep_fmtstr

        return self.format_separators(string)


class JUnitFormatter(ResultFormatter):
    '''
    Formats TestResults into the JUnit XML format.
    '''

    # Results considered passing under JUnit, we have a couple extra states
    # that aren't traditionally reported under JUnit.
    passing_results = {Result.PASS, Result.XFAIL}

    def __init__(self,
                 result,
                 translate_names=True,
                 flatten=True):
        '''
        :param flatten: Flatten out heirarchical tests in order to fit the
        basic JUnit format (test suites traditionally cannot hold other test
        suites).
        '''
        super(JUnitFormatter, self).__init__(result)
        self.flatten = flatten

        if translate_names:
            self.name_table = string.maketrans("/.", ".-",)
        else:
            self.name_table = string.maketrans("", "")

    def __str__(self):
        self.root = ET.Element("testsuites")

        results = self.result
        if self.flatten:
            results = JUnitFormatter.flatten_suites(results)

        ET.ElementTree(self.convert_testsuite(self.root,
                                              results,
                                              self.flatten))
        return ET.tostring(self.root)

    @staticmethod
    def flatten_suites(toplevel_suite):
        '''
        JUnit doesn't officially have a concept of heirarchecal test suites as
        far as I can tell, so to fix this we group tests at their finest
        granularity. That is, test cases are grouped in the test suite that
        directly contains them, not a suite of a suite.

        :returns: A new toplevel_suite which contains flattened suites.
        '''

        def metadata_copy_suiteresult(suite):
            copy = TestSuiteResult(suite.name)
            copy.timer = suite.timer
            return copy

        def recurse_flatten(suite):
            # Iterate over items in the suite, if they are other suites, we need
            # to recurse and do the same.
            # If they are tests then pull them out and save them. We'll attach
            # them to us.
            flattened_suite = metadata_copy_suiteresult(suite)
            our_testcases = []
            flat_suites = []

            for result in suite:
                if isinstance(result, TestCaseResult):
                    our_testcases.append(result)
                else:
                    flat_suites.extend(recurse_flatten(result))

            if our_testcases:
                # If there were test cases held in this test suite, we should
                # reattach them to our new copy and place us in the top level
                # collection
                flattened_suite.results.extend(our_testcases)
                flat_suites.append(flattened_suite)

            return flat_suites

        # Just copy the name since we're going to update all the results.
        new_toplevel_suite = metadata_copy_suiteresult(toplevel_suite)
        flatted_results = recurse_flatten(toplevel_suite)
        if flatted_results:
            new_toplevel_suite.results.extend(flatted_results)

        return new_toplevel_suite

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
            # TODO: Use these subelements for text.
            #<system-out>
            #    I am stdout!
            #</system-out>
            #<system-err>
            #    I am stderr!
            #</system-err>
            pass


    def convert_testsuite(self, xtree, suite, _flatten=False):
        '''
        '''
        errors = 0
        failures = 0
        skipped = 0

        # Remove the topmost suite that is containing other suites.
        if _flatten:
            xsuite = xtree
            _flatten = False
        else:
            xsuite = ET.SubElement(xtree, "testsuite",
                                    name=suite.name.translate(self.name_table),
                                    time="%f" % suite.runtime)

        # Iterate over the tests and suites held in the test suite.
        for result in suite:
            # If the element is a test case attach it as such
            if isinstance(result, TestCaseResult):
                self.convert_testcase(xsuite, result)
            else:
                # Otherwise recurse
                self.convert_testsuite(xsuite, result, _flatten)

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

        if not _flatten:
            xsuite.set("errors", str(errors))
            xsuite.set("failures", str(failures))
            xsuite.set("skipped", str(skipped))
            xsuite.set("tests", str(len(suite.results)))


if __name__ == '__main__':
    import whimsy.suite as suite
    suiteresult = TestSuiteResult('Test Suite')
    parentsuiteresult = TestSuiteResult('Parent Test Suite')
    parentsuiteresult.results.append(suiteresult)

    parentsuiteresult.timer.start()
    parentsuiteresult.timer.stop()
    suiteresult.timer.start()
    suiteresult.timer.stop()


    for _ in range(2):
        testcase = TestCaseResult('testcase', result=Result.PASS)
        testcase.timer.start()
        testcase.timer.stop()
        suiteresult.results.append(testcase)

    #formatter = JUnitFormatter(parentsuiteresult, flatten=True)
    #print(formatter)
    formatter = ConsoleFormatter(parentsuiteresult)
    print(formatter)
