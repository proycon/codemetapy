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

``$ pip show -v somepackage | codemetadapy``

To pipe to an output file:

``$ pip show -v somepackage | codemetadapy > somepackage.json``

