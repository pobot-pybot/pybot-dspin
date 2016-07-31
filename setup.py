# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

import textwrap

setup(
    name='pybot-dspin',
    namespace_packages=['pybot'],
    setup_requires=['setuptools_scm'],
    use_scm_version=True,
    description='STMicro dSPIN stepper smart driver interface',
    license='LGPL',
    long_description=textwrap.dedent("""
            This sub-package contains classes for controlling stepper
            motors with dSPIN chips.
      """),
    author='Eric Pascual',
    author_email='eric@pobot.org',
    url='http://www.pobot.org',
    install_requires=['pybot-core', 'spidev', 'RPi.GPIO'],
    download_url='https://github.com/Pobot/PyBot',
    packages=find_packages("src"),
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'dspin-demo = pybot.dspin.demo.MotorDemo:main'
        ]
    }
)
