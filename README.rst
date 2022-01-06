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

For Python packages, codemetapy uses ``importlib.metadata`` (Python 3.8+) or its backported variant (for older Python
versions) to read the metadata of installed packages. It should therefore be compatible irregardless of whether you
specified in your metadata in ``setup.py``, ``setup.cfg``, ``pyproject.toml`` or using any other backend.

Moreover, CodeMetaPy also supports conversions from other package types, such as debian packages (APT) (but this is
limited). For R, see `codemetar <https://github.com/ropensci/codemetar>`_ instead.

One of the most notable features of this tool is that it allows chaining to successively update metadata based on
multiple sources.

Installation
----------------

``pip install codemetapy``

Usage
---------------

Query and convert any installed python package:

``$ codemetapy somepackage``

Output will be to standard output by default, to write it to an output file instead, do either:

``$ codemetapy somepackage > codemeta.json``

or use the ``-O`` parameter:

``$ codemetapy -O codemeta.json somepackage``

If you are in the current working directory of any python project, i.e. there is a ``setup.py``, then you can simply
call ``codemetapy`` without arguments to output codemeta for the project. Codemetapy will automatically run ``python
setup.py egg_info`` and parse it's output to facilitate this:

``$ codemetapy``

The tool also supports adding properties through parameters:

``$ codemetapy --developmentStatus active somepackage > codemeta.json``

To read an existing codemeta.json and extend it:

``$ codemetapy -i json,python codemeta.json somepackage > codemeta.json``

This tool can also deal with debian packages by parsing the output of ``apt show`` (albeit limited):

``$ apt show somepackage | codemetapy -i apt -``

Here ``-`` represents standard input, which enables you to use piping solutions on a unix shell, ``-i`` denotes the
input types, you can chain as many as you want. The number of input types specifies must correspond exactly to the
number of input sources (the positional arguments).

Entrypoint Extension
----------------------

Though this is not part of the codemeta specification, the tool currently supports an extra ``entryPoints`` property
with type ``EntryPoint``. This can be used to describe the entry points specified in a python package (entry points will
have use a ``file://`` url to refer to the actual entrypoints, this is a bit of a liberal use...). Because this is a
non-standard extension it has to be explicitly enabled using ``--with-entrypoints``.

Integration in setup.py
-------------------------

You can integrate ``codemeta.json`` generation in your project's ``setup.py``, this will add an extra ``python setup.py
codemeta`` command that will generate a new metadata file or update an already existing metadata file. Note that this
must be run *after* ``python setup.py install`` (or ``python setup.py develop``).

To integrate this, add the following to your project's ``setup.py``:

.. code:: python

    try:
        from codemeta.codemeta import CodeMetaCommand
        cmdclass={
            'codemeta': CodeMetaCommand,
        }
    except ImportError:
        cmdclass={}

And in your ``setup()`` call add the parameter:

.. code:: python

    cmdclass=cmdclass

This will ensure your ``setup.py`` works in all cases, even if codemetapy is not installed, and that the command will be
available if codemetapy is available.

To make use of the entrypoint extension, you need to explicitly specify ``python setup.py codemeta --with-entrypoints``.

If you want to ship your package with the generated ``codemeta.json``, then simply add a line saying ``codemeta.json`` to
the file ``MANIFEST.in`` in the root of your project.



