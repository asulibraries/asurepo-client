import setuptools
from setuptools.command.test import test as TestCommand
import sys


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


setuptools.setup(
    name='asurepo-client',
    version='0.3.0',
    packages=setuptools.find_packages(),
    install_requires=['requests>=2.0'],
    tests_require=['mock>=1.0', 'pytest'],
    cmdclass={'test': PyTest},
)
