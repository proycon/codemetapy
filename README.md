[![Project Status: Active -- The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
[![GitHub build](https://github.com/proycon/codemetapy/actions/workflows/codemetapy.yml/badge.svg?branch=master)](https://github.com/proycon/codemetapy/actions/)
[![GitHub release](https://img.shields.io/github/release/proycon/codemetapy.svg)](https://GitHub.com/proycon/codemetapy/releases/)
[![Latest release in the Python Package Index](https://img.shields.io/pypi/v/codemetapy)](https://pypi.org/project/codemetapy/)
 
# Codemetapy

Codemetapy is a command-line tool to work with the [codemeta ](https://codemeta.github.io) software metadata standard.
Codemeta builds upon [schema.org](https://schema.org) and defines a vocabulary for describing software source code. It
maps various existing metadata standards to a unified vocabulary.

For more general information about the CodeMeta Project for defining
software metadata, see <https://codemeta.github.io>. In particular, new
users might want to start with the User Guide, while those looking to
learn more about JSON-LD and consuming existing codemeta files should
see the Developer Guide.

Using codemetapy you can generate a `codemeta.json` file, which
serialises using [JSON-LD](https://json-ld.org) , for
your software. At the moment it supports conversions from the following
existing metadata specifications:

* Python distutils/pip packages (`setup.py`/`pyproject.toml`)
* Java/Maven packages (`pom.xml`)
* NodeJS packages (`package.json`)
* Debian package (`apt show` output)
* Github API (when passed a github URL)
* GitLab API (when passed a GitLab URL)
* Web sites/services (see the section on software types and service below):
    * Simple metadata from HTML `<meta>` elements.
    * Script blocks using `application/json+ld`

It can also read and manipulate existing `codemeta.json` files as well
as parse simple AUTHORS/CONTRIBUTORS files. One of the most notable
features of codemetapy is that it allows chaining to successively update
a metadata description based on multiple sources. Codemetapy is used in
that way by the [codemeta-harvester](https://github.com/proycon/codemeta-harvester), if you
are looking for an all-in-one solution to automatically generate a
`codemeta.json` for your project, then that is the best place to start.

## Installation

`pip install codemetapy`

## Usage

Query and convert any installed python package:

`$ codemetapy somepackage`

Output will be to standard output by default, to write it to an output
file instead, do either:

`$ codemetapy somepackage > codemeta.json`

or use the `-O` parameter:

`$ codemetapy -O codemeta.json somepackage`

If you are in the current working directory of any python project and
there is a `setup.py`or `pyproject.toml`, then you can simply call `codemetapy` without
arguments to output codemeta for the project. Codemetapy will
automatically run `python setup.py egg_info` if needed and parse it's output to
facilitate this:

`$ codemetapy`

The tool also supports adding properties through parameters:

`$ codemetapy --developmentStatus active somepackage > codemeta.json`

To read an existing codemeta.json and extend it:

`$ codemetapy codemeta.json somepackage > codemeta.json`

If you want to start from scratch and build using command line parameters, use `/dev/null` as input, and make sure to pass some identifier and code repository:

`$ codemetapy --identifier some-id --codeRepository https://github.com/my/code /dev/null > codemeta.json`

This tool can also deal with debian packages by parsing the output of
`apt show` (albeit limited):

`$ apt show somepackage | codemetapy -i debian -`

Here `-` represents standard input, which enables you to use piping
solutions on a unix shell, `-i` denotes the input types, you can chain
as many as you want. The number of input types specifies must correspond
exactly to the number of input sources (the positional arguments).



## Some notes on Vocabulary

For `codemeta:developmentStatus`, codemetapy attempts to
assign full [repostatus](https://www.repostatus.org/) URIs whenever
possible For `schema:license`, full [SPDX](https://spdx.org) URIs are used where possible.

## Software Types and services

Codemetapy (since 2.0) implements an extension to codemeta that allows
linking the software source code to the actual instantiation of the
software, with explicit regard for the interface type. This is done via
the `schema:targetProduct` property, which takes as range a
`schema:SoftwareApplication`, `schema:WebAPI`,
`schema:WebSite` or any of the extra types defined in
<https://github.com/SoftwareUnderstanding/software_types/> . This was
proposed in [this issue](https://github.com/codemeta/codemeta/issues/271)

This extension is enabled by default and can be disabled by setting the
`--strict` flag.

When you pass codemetapy a URL it will assume this is where the software
is run as a service, and attempt to extract metadata from the site and
encode is via `targetProduct`. For example, here we read an
existing `codemeta.json` and extend it with some place where
it is instantiated as a service:

`$ codemetapy codemeta.json https://example.org/`

If served HTML, codemetapy will use your `<script>` block
using `application/json+ld` if it provides a valid software types (as
mentioned above). For other HTML, codemetapy will simply extract some
metadata from HTML `<meta>` elements. Content negotation will be used
and the we favour json+ld, json and even yaml and XML over HTML.

(Note: the older Entypoint Extension from before codemetapy 2.0 is now deprecated)

## Graph

You can use codemetapy to generate one big knowledge graph expressing
multiple codemeta resources using the `--graph` parameter:

`$ codemetapy --graph resource1.json resource2.json`

This will produce JSON-LD output with multiple resources in the graph.

## Github API

Codemetapy can make use of the Github API to query metdata from GitHub,
but this allows only limited anonymous requests before you hit a limit.
To allow more requests, please set the environment variable
`$GITHUB_TOKEN` to a [personal access
token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token).

## GitLab API

Codemetapy can make use of the GitLab API to query metdata from GitLab,
but this allows only limited anonymous requests before you hit a limit.
To allow more requests, please set the environment variable
`$GITLAB_TOKEN` to a [personal access
token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html).

## Integration in setup.py

You can integrate `codemeta.json` generation in your project's
`setup.py`, this will add an extra `python setup.py codemeta` command
that will generate a new metadata file or update an already existing
metadata file. Note that this must be run *after*
`python setup.py install` (or `python setup.py develop`).

To integrate this, add the following to your project's `setup.py`:

```python
try:
    from codemeta.codemeta import CodeMetaCommand
    cmdclass={
        'codemeta': CodeMetaCommand,
    }
except ImportError:
    cmdclass={}
```

And in your `setup()` call add the parameter:

```python
cmdclass=cmdclass
```

This will ensure your `setup.py` works in all cases, even if codemetapy
is not installed, and that the command will be available if codemetapy
is available.

If you want to ship your package with the generated `codemeta.json`,
then simply add a line saying `codemeta.json` to the file `MANIFEST.in`
in the root of your project.
