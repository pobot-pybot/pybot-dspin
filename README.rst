POBOT's ``pybot`` collection
============================

This package is part of POBOT's ``pybot`` packages collection, which aims
at gathering contributions created while experimenting with various technologies or
hardware in the context of robotics projects.

Although primarily focused on robotics applications (taken with its widest acceptation)
some of these contributions can be used in other contexts. Don't hesitate to keep us informed
on any usage you could have made.

Implementation note
-------------------

The collection code is organized using namespace packages, in order to group them in
a single tree rather that resulting in a invading flat collection. Please refer to the official
documentation at <https://www.python.org/dev/peps/pep-0382/> for details.

Package content
===============

Interfacing of STMicroelectronic L6470 (aja dSPIN) stepper motor smart controller.

Installation
============

::

    $ cd <PROJECT_ROOT_DIR>
    $ python setup.py install

Dependencies
============

- pybot.core

External:

- spidev
- RPi.GPIO

The dependencies are declared in `setup.py`, so they are automatically installed if needed.
pybot collection not being on PyPi, you'll have to install it manually before.
