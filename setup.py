#! /usr/bin/env python
# -*- coding: utf8 -*-

from __future__ import print_function

import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname),'r',encoding='utf-8').read()

setup(
    name = "CodeMetaPy",
    version = "0.1",
    author = "Maarten van Gompel",
    author_email = "proycon@anaproy.nl",
    description = ("Generate CodeMeta metadata for Python packages"),
    license = "GPL",
    keywords = "nlp computational_linguistics entities wikipedia dbpedia linguistics tramooc",
    url = "https://github.com/proycon/codemeta",
    packages=['codemeta'],
    long_description=read('README.rst'),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Software Development",
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
    zip_safe=False,
    include_package_data=True,
    package_data = { 'codemeta': 'schema/*' },
    install_requires=[ 'nameparser', 'pyyaml'  ],
    entry_points = {    'console_scripts': [ 'codemetapy = codemeta.codemeta:main' ] }
)
