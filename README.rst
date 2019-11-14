.. image:: https://travis-ci.com/proycon/codemetapy.svg?branch=master
    :target: https://travis-ci.com/proycon/codemetapy

.. image:: http://applejack.science.ru.nl/lamabadge.php/codemetapy
   :target: http://applejack.science.ru.nl/languagemachines/

.. image:: https://www.repostatus.org/badges/latest/active.svg
   :alt: Project Status: Active – The project has reached a stable, usable state and is being actively developed.
   :target: https://www.repostatus.org/#active

.. image:: https://img.shields.io/pypi/v/codemetapy
   :alt: Latest release in the Python Package Index
   :target: https://pypi.org/project/codemetapy/

CodeMetaPy
=================

The goal of CodeMetaPy is to generate the JSON-LD file, codemeta.json containing software metadata describing a Python
package. For more general information about the CodeMeta Project for defining software metadata, see
https://codemeta.github.io. In particular, new users might want to start with the User Guide, while those looking to
learn more about JSON-LD and consuming existing codemeta files should see the Developer Guide.

Installation
----------------

``pip install codemetapy``

Usage
---------------

Query and convert any install python package:

``$ codemetapy somepackage``

Output will be to standard output by defualt, to write it to an output file, do:

``$ codemetapy somepackage > codemeta.json``

or use the ``-O`` parameter:

``$ codemetapy -O codemeta.json somepackage``

The tool also supports adding properties through parameters:

``$ codemetapy --developmentStatus active somepackage > codemeta.json``

To read an existing codemeta.json and extend it:

``$ codemetapy -i json,python codemeta.json somepackage > codemeta.json``

This tool can also deal with debian packages (albeit limited):

``$ apt show somepackage | codemetapy -i apt -``

Here ``-`` represents standard input,  ``-i`` denotes the input types, you can chain as many as you want. The number of
input types specifies must correspond exactly to the number of input sources (the positional arguments).

Entrypoint Extension
----------------------

Though this is not part of the codemeta specification, the tool currently supports an extra ``entryPoints`` property
with type ``EntryPoint``. This can be used to describe the entry points specified in a python package (entry points will
have use a ``file://`` url to refer to the actual entrypoints, this is a bit of a liberal use...). Because this is a
non-standard extension it has to be explicitly enabled using ``--with-entrypoints``.

