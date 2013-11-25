#!/usr/bin/env python
import setuptools
from asurepo_client import __version__ as version
setuptools.setup(
    name='asurepo-client',
    version=version,
    packages=setuptools.find_packages(),
    install_requires=['requests>=2.0'],
    tests_require=['mock>=1.0']
)

