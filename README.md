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
that way by the [codemeta-harvester](https://github.com/proycon/codemeta-harvester). 

**Note:** If you are looking for an all-in-one solution to automatically
generate a `codemeta.json` for your project, then
*[codemeta-harvester](https://github.com/proycon/codemeta-harvester) is the
best place to start*. It is a higher-level tool that automatically invokes
codemetapy on various sources it can automatically detect, and combined those into
a single codemeta representation.

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

`$ codemetapy -O codemeta.json codemeta.json somepackage`

or even:

`$ codemetapy -O codemeta.json codemeta.json codemeta2.json codemeta3.json`

This makes use of an important characteristic of codemetapy which is *composition*. When you specify multiple input sources, they will be interpreted as referring to the same resource.
Properties (on `schema:SoftwareSourceCode`) in the later resources will *overwrite* earlier properties. So if `codemeta3.json` specifies authors, all authors that were specified in `codemeta2.json` are lost rather than merged and the end result will have the authors from `codemeta3.json`. However, if `codemeta2.json` has a property that was not in `codemeta3.json`, say `deveopmentStatus`, then that will make it to the end rsult. In other words, the latest source always takes precedence. Any non-overlapping properties will be be merged. This functionality is heavily relied on by the higher-level tool [codemeta-harvester](https://github.com/proycon/codemeta-harvester).

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

## Identifiers

We distinguish two types of identifiers, first there is the URI or [IRI](https://www.w3.org/TR/rdf11-concepts/#section-IRIs) 
that identifies RDF resources. It is a globally unique identifier and often looks like a URL. 

Codemetapy will assign new URIs for resources if and only if you pass a base URI using ``--baseuri``. Moreover, if you set this, codemetapy will *forcibly* set URIs over any existing ones, effectively assigning new identifiers. The previous identifier will then be covered via the `owl:sameAs` property instead. This allows you to ownership of all URIs.  Internally, codemetapy will create URIs for everything even if you don't specified a base URI (even for blank nodes), but these URIs are stripped again upon serialisation to JSON-LD.

The second identifier is the [schema:identifier](https://schema.org/identifier), of which there may even be multiple.
Codemetapy typically expects such an identifier to be a simple unspaced string holding a name for software. For example, a Python package name would make a good identifier. If this property is present, codemetapy will use it when generating URIs.
The `schema:identifier` property can be contrasted with `schema:name`, which is the human readable form of the name and may be more elaborate.
The identifier is typically also used for other identifiers (such as DOIs, ISBNs, etc), which should come in the following form:

```json
"identifier:" {
    "@type": "PropertyValue",
    "propertyID": "doi",
    "value": "10.5281/zenodo.6882966"
}
```

But short-hand forms such as ``doi:10.5281/zenodo.6882966`` or as a URL like `https://doi.org/10.5281/zenodo.6882966` are also recognised by this library.


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
