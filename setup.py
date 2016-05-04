# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
from git_version import git_version

import textwrap

setup(
    name='pybot-dspin',
    namespace_packages=['pybot'],
    version=git_version(),
    description='STMicro dSPIN stepper smart driver interface',
    license='LGPL',
    long_description=textwrap.dedent("""
            This sub-package contains classes for controlling stepper
            motors with dSPIN chips.
      """),
    author='Eric Pascual',
    author_email='eric@pobot.org',
    url='http://www.pobot.org',
    install_requires=['pybot-core'],
    download_url='https://github.com/Pobot/PyBot',
    packages=find_packages("src"),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'dspin-demo = pybot.dspin.demo.MotorDemo:main'
        ]
    }
)
