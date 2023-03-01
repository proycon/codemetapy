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
    version = "2.4.0", #also adapt in codemeta.json
    author = "Maarten van Gompel",
    author_email = "proycon@anaproy.nl",
    description = ("Generate and manage CodeMeta software metadata"),
    license = "GPL-3.0-only",
    keywords = [ "software metadata", "codemeta", "schema.org", "rdf", "linked data"],
    url = "https://github.com/proycon/codemetapy",
    packages=['codemeta', 'codemeta.parsers','codemeta.serializers'],
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Topic :: Software Development",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: POSIX",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
    zip_safe=False,
    include_package_data=True,
    package_data = { 'codemeta': ['schema/crosswalk.csv', 'schema/codemeta.jsonld', 'templates/*.html','resources/*.css', 'resources/fa-*' ] },
    install_requires=[ 'nameparser','importlib_metadata','BeautifulSoup4', 'rdflib >= 6.1.1','pyshacl', 'requests','lxml','pyyaml','Jinja2','pep517','tomlkit','pyproject_parser'],
    entry_points = {    'console_scripts': [ 'codemetapy = codemeta.codemeta:main' ] },
    cmdclass=cmdclass
)
