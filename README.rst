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

Query and convert any package installed through pip:

``$ pip show -v somepackage | codemetapy``

To pipe to an output file:

``$ pip show -v somepackage | codemetapy > codemeta.json``

The tool also supports adding properties through parameters:

``$ pip show -v somepackage | codemetapy --developmentStatus active > codemeta.json``

To read an existing codemeta.json and extend it:

``$ pip show -v somepackage | codemetapy -i json,pip codemeta.json - > codemeta.json``

Here ``-`` represents standard input and ``-i`` denotes the input types, you can chain as many as you want.

This tool can also deal with debian packages (albeit limited):

``$ apt show somepackage | codemetapy -i apt``

Entrypoint Extension
----------------------

Though this is not part of the codemeta specification, the tool currently supports an extra ``entryPoints`` property
with type ``EntryPoint``. This can be used to describe the entry points specified in a python package (entry points will
have use a ``file://`` url to refer to the actual entrypoints, this is a bit of a liberal use...). Because this is a
non-standard extension it has to be explicitly enabled using ``--with-entrypoints``.

