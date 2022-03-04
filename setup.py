#!/usr/bin/env python3

import os
from setuptools import setup
try:
    from codemeta.codemeta import CodeMetaCommand
    cmdclass={
        'codemeta': CodeMetaCommand,
    }
except ImportError:
    cmdclass={}

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname),'r',encoding='utf-8').read()

setup(
    name = "CodeMetaPy",
    version = "0.4.0",
    author = "Maarten van Gompel",
    author_email = "proycon@anaproy.nl",
    description = ("Generate CodeMeta metadata for Python packages"),
    license = "GPL-3.0-only",
    keywords = "software metadata codemeta doap pip pypi distutils admssw",
    url = "https://github.com/proycon/codemeta",
    packages=['codemeta', 'codemeta.parsers'],
    long_description=read('README.rst'),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Software Development",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: POSIX",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
    zip_safe=False,
    include_package_data=True,
    package_data = { 'codemeta': ['schema/crosswalk.csv', 'schema/codemeta.jsonld'] },
    install_requires=[ 'nameparser','importlib_metadata','BeautifulSoup4', 'rdflib >= 6.1.1' ],
    entry_points = {    'console_scripts': [ 'codemetapy = codemeta.codemeta:main' ] },
    cmdclass=cmdclass
)
