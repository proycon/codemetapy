<a id="v3.0.4"></a>
# v3.0.4 - 2026-03-18

* Dependency version bump for pyshacl and rdflib (thanks to [@AutumnIsilme](https://github.com/AutumnIsilme))
* Dropped Python 3.8 support

<a id="v3.0.3"></a>
# v3.0.3 - 2025-04-24

* Fixed a problem with missing authors/mails due to parsing errors ([#53](https://github.com/proycon/codemetapy/issues/53)), thanks also to [@willynilly](https://github.com/willynilly) 
* CI fixes



<a id="v3.0.2"></a>
# v3.0.2 - 2025-04-17

Minor update after 3.0.1 was mistagged; adds support for detecting "archived" repos at GitHub and derives repostatus from that (unsupported or abandoned).



<a id="v3.0.1"></a>
# v3.0.1 - 2025-04-17

Minor update, adds support for detecting "archived" repos at GitHub and derives repostatus from that (unsupported or abandoned).



<a id="v3.0.0"></a>
# v3.0.0 - 2025-03-10

This major release updates the codemeta library for use with codemeta v3. It will hence-forth output codemeta v3 data only. Codemeta v2 can still be read as input and will be automatically converted. See https://github.com/codemeta/codemeta/releases/tag/3.0 for the codemeta v3 release notes which illustrates the changes.  Some notable ones:

* We now use https://w3id.org/codemeta/3.0 as JSON-LD context, instead of https://doi.org/10.5063/schema/codemeta-2.0
* The RDF namespace has not changed between version and remains https://codemeta.github.io/terms/
* Codemeta 3 introduces a `isSourceCodeOf` property. We now use this instead of `schema:targetProduct` to link between source code and applications/services. See also: [codemeta/codemeta#271](https://github.com/codemeta/codemeta/issues/271) . 





<a id="v2.5.3"></a>
# v2.5.3 - 2024-06-14

* Remove distutils and use setuptools (needed for Python 3.12 compatibility) [#50](https://github.com/proycon/codemetapy/issues/50)
* Fixed `setup.py codemeta` command  [#50](https://github.com/proycon/codemetapy/issues/50) 



<a id="v2.5.2"></a>
# v2.5.2 - 2023-11-27

* Fix incorrect parsing of version from dependencies (closes [#48](https://github.com/proycon/codemetapy/issues/48))
* Java/Maven: translate organization from pom.xml to schema:Organization (type was missing)
* Check e-mail validity when inferring a maintainer
* Metadata update




<a id="v2.5.1"></a>
# v2.5.1 - 2023-09-18

Features:
* python: support "homepage" and "documentation" fields from pyproject.toml, limited support for "readme" too
* python:parse maintainers from pyproject.toml [#44](https://github.com/proycon/codemetapy/issues/44)
* npm: support 'maintainers' field in package.json [#44](https://github.com/proycon/codemetapy/issues/44)
* updated to latest codemeta crosswalks (proper v3 compatibility is coming in the next codemetapy release)

Bugfixes:
* python: fix incorrect parsing of versions from dependencies if e.g. extras are stated to be installed [#42](https://github.com/proycon/codemetapy/issues/42)
* npm: ensure url is retained for all contributors [#45](https://github.com/proycon/codemetapy/issues/45)
* ensure lists are always sorted in some way so output is deterministic [#39](https://github.com/proycon/codemetapy/issues/39)
* we eagerly turn literals into resources when they exist in our graph; exempt certain properties like 'url' from this behaviour [#46](https://github.com/proycon/codemetapy/issues/46)



<a id="v2.5.0"></a>
# v2.5.0 - 2023-05-15

* Split off all HTML generation code to a seperate project codemeta2html: https://github.com/proycon/codemeta2html
* prevent unnecessary URI remapping
* set pyshacl version fixed to 0.20.0, versions 0.22.0 break stuff; to be re-evaluated later
* better detection of json-ld for --addcontextgraph
* more robust URI generation
* added load function for API usage
* web: extract title from h1 if no title found in head




<a id="v2.4.1"></a>
# v2.4.1 - 2023-03-15

Bugfix release:

* Remove stub targetProducts (i.e. without url) for web applications/services if we have better ones (i.e. with url)
* Minor fix in verbose log output
* Removed some itemss from deviant context, no longer needed
* Nodejs: fix for contributors parsing
* html visualisation: fix for screenshot display
* html visualisation: also allow screenshots and references on targetproduct pages



<a id="v2.4.0"></a>
# v2.4.0 - 2023-03-02

* nodejs: fixing parsing of contributors 
* nodejs/npm: remove the scope from the name in conversion to codemeta
* Implemented support for converting Rust's Cargo.toml [#10](https://github.com/proycon/codemetapy/issues/10)
* added --addcontextgraph parameter to add information to the context graph but not to the JSON-LD context
* expand implicit id nodes also when there is a known namespace prefix (CLARIAH/tool-discovery#33, CLARIAH/tool-discovery#34)
* fix recursion problem in item embedding, and skip embedding for certain acyclic properties  
* implemented direct parsing of pyproject.toml [#28](https://github.com/proycon/codemetapy/issues/28) CLARIAH/tool-discovery#35 
* if labels have a language, always choose english (for now)
* minor style fixes for frontend
* allow merging heterogenous developmentStatus  
* java: resolve ${project.groupId} and ${project.artifactId} variables
* improved own codemeta metadata



<a id="v2.3.3"></a>
# v2.3.3 - 2022-11-21

Bugfix release:

* collide blank-nodes that have exact the same content (assume same URI), should solve issue [#36](https://github.com/proycon/codemetapy/issues/36)



<a id="v2.3.2"></a>
# v2.3.2 - 2022-11-09

New feature in html visualisation: added support for aggregation of tools in groups/suites.



<a id="v2.3.1"></a>
# v2.3.1 - 2022-11-03

Bugfixes:
* Fixed namespaces in HTML output
* Fixed template error in table view

New:
* Added richer meta tags in HTML output



<a id="v2.3.0"></a>
# v2.3.0 - 2022-10-21

This is a pretty big release with a lot of refactoring, bugfixes and various new features:

* Major refactoring and numerous bugfixes
   * schema:author and schema:contributor are now always interpreted as ordered lists (even if the context doesn't make this explicit), this has repercussions for querying (e.g. SPARQL) [#22](https://github.com/proycon/codemetapy/issues/22) 
   * Reimplemented JSON-LD object framing
   * Graphs output (--graph) now also does object framing for per SoftwareSourceCode entry and uses expanded form (= some duplication/redundancy)
   * When assigning URIs for SoftwareSourceCode and SoftwareApplication, add a version component. So each version has its own URI (requires --baseuri to be set)
* Added support for DOIs in schema:identifier, shown also in html output [#33](https://github.com/proycon/codemetapy/issues/33) 
* Use schema.org and codemeta context as officially published [#32](https://github.com/proycon/codemetapy/issues/32)
* Set TMPDIR in a more platform independent way [#31](https://github.com/proycon/codemetapy/issues/31)
* Assume input to be installed python packages when no explicit type is provided nor can be detected [#27](https://github.com/proycon/codemetapy/issues/27) 
* Reference publications didn't visualize properly yet in html output [#18](https://github.com/proycon/codemetapy/issues/18) 
* HTML output now shows a citation example for the software itself (incl DOI if set)
* Improved license mapping to SPDX vocabulary
* Do some simple license conflict detection and resolution in case multiple licenses are specified
* For the --enrich option: Consider first author as the maintainer if none was specified
* Implemented support for Technology Readiness Levels (use --trl parameters to opt-in)
* Added an --includecontext option that includes further context information in the codemeta JSON-LD output (like from the repostatus ontology, from SPDX, etc, adds redundancy but makes the information more complete)
  * Added an --addcontext option to customise extra JSON-LD context to load and add (affects --includecontext)
* Python parsing: Improved parsing of Python Project-URL labels
* Renamed parameter --toolstore to --codemetaserver, set for use with codemeta-server
* Upgrade to v14 of schema.org
* Added --interpreter option to dump the user in an interactive python environment, helps with debugging




<a id="v2.2.2"></a>
# v2.2.2 - 2022-09-12

* jsonld serialization: serialize lists alphabetically by schema:name/@id/schema:identifier if schema:position is not used ([#26](https://github.com/proycon/codemetapy/issues/26))
* fix: properly deal with ~= and != operators in python dependencies
* fix: strip leading/trailing whitespace in author names/mails/etc
* new feature: improved python Project-Url parsing



<a id="v2.2.1"></a>
# v2.2.1 - 2022-09-12

* Re-implemented ``--no-extras`` parameter to skip extra (python) dependencies (closes [#24](https://github.com/proycon/codemetapy/issues/24))
* Allow egg_info directories in subdirectories




<a id="v2.2.0"></a>
# v2.2.0 - 2022-09-05

* Many fixes and improvements
* Added unit/integration tests [#20](https://github.com/proycon/codemetapy/issues/20) 
* Added support for gitlab API ([#19](https://github.com/proycon/codemetapy/issues/19), thanks to [@xmichele](https://github.com/xmichele))
* Added support for private git repos ([#19](https://github.com/proycon/codemetapy/issues/19), thanks to [@xmichele](https://github.com/xmichele))
* Implementing support for the software-iodata profile: https://github.com/SoftwareUnderstanding/software-iodata
* Implemented ability to validate metadata against a SHACL schema ([#21](https://github.com/proycon/codemetapy/issues/21))
   * Generates automatic validation reports and adds those to the metadata
   * Visualised as a 0 to 5-star ranking in the html output
* Major updates to the html visualisation
   * Added an additional service-oriented index (showing only web applications)
* Added opt-in automatic enrichment of codemeta (based on some inferences we can make)
* Detect redirects by single-sign-on middleware that prevent us from further metadata harvesting
* Allow constructing codemeta.json from scratch without any input, merely passing command line parameters (use /dev/null as input)
* Use repostatus ontology (jantman/repostatus.org#48)



<a id="v2.1.0"></a>
# v2.1.0 - 2022-06-09

* Implemented support for handling projects with pyproject.toml [#17](https://github.com/proycon/codemetapy/issues/17) 



<a id="v2.0.1"></a>
# v2.0.1 - 2022-06-07

Bugfix release: don't trip on packages without dependencies ([#16](https://github.com/proycon/codemetapy/issues/16))



<a id="v2.0"></a>
# v2.0 - 2022-05-17

This is a major new release of codemetapy. It does introduce some backward-incompatible changes.

* Major overhaul of the entire codebase:
    * Now uses an actual RDF graph with RDF triples internally (using `rdflib`) [#12](https://github.com/proycon/codemetapy/issues/12)
    * Allows for SPARQL queries
    * Supports serialisation in JSON-LD, Turtle and HTML with [RDFa](https://www.w3.org/TR/rdfa-primer/)
* Implements codemeta 2.0 with some extensions (see the README)
* map developmentStatus to repostatus.org vocabulary [#7](https://github.com/proycon/codemetapy/issues/7)
* map licenses to SPDX vocabulary [#8](https://github.com/proycon/codemetapy/issues/8)
* The old 'entrypoints' extension to codemeta (as described in https://github.com/codemeta/codemeta#183 ) is now deprecated in favour of the newer software types extension (proposed in  https://github.com/codemeta/codemeta#271 and worked out in https://github.com/SoftwareUnderstanding/software_types ).
    * Supports `schema:targetProduct` to link software source code to instances of the software
    * Supports extended [software types](https://github.com/SoftwareUnderstanding/software_types), on top of the ones already available in schema.org.
    * See the README for more info
* Implemented support for parsing and converting Java/Maven `pom.xml` to codemeta [#9](https://github.com/proycon/codemetapy/issues/9)
* Implemented support for parsing and converting NodeJS/npm `package.json` to codemeta [#11](https://github.com/proycon/codemetapy/issues/11)
* Implemented support for parsing and converting remote webservices (via `targetProduct`) (https://github.com/CLARIAH/clariah-plus#92)
    * Can extract `<script>` blocks with `application/json+ld` from HTML
    * Parses and converts metadata in HTML `<head>` (including RDFa and microdata)
* Improved support for parsing and converting Python/setuptools/distutils to codemeta
    * use `runtimePlatform` instead of `programmingLanguage` when converting pip's 'programmingLanguage' classes
    * No longer requires software to be actually installed prior to parsing
* Implemented supported for parsing and converting from the GitHub API to codemeta
    * Set environment variable `GITHUB_TOKEN` to your personal access token if you run into rate limitations.
* Improvements in merging/reconciliating metadata that describe the same source, but from multiple perspectives
* Improvements in joining multiple sources together in one graph (``--graph`` parameter, replaces the old ``--registry`` parameter)
* Improvements in author parsing
    * Implemented support for ingesting simple textual lists of authors as is customary in files like `AUTHORS`, `CONTRIBUTORS`, `MAINTAINERS`.
* Rich HTML visualisation (with [RDFa](https://www.w3.org/TR/rdfa-primer/)!), is used primarily by [codemeta-server](https://github.com/proycon/codemeta-server) (https://github.com/CLARIAH/clariah-plus#99)
* Added a ``--strict`` option to disable codemeta extensions (the inverse of the old ``--all`` parameter that is now removed)
* Dropped support for Python 3.5 and below

This release also comes with two related projects that rely on codemetapy, together they form a powerful ensemble:

* [codemeta-server](https://github.com/proycon/codemeta-server) - Server for codemeta, in memory triple store, SPARQL endpoint and simple web-based visualisation for end-users
* [codemeta-harvester](https://github.com/proycon/codemeta-harvester) -  Harvest and aggregate codemeta from source repositories and service endpoints, automatically converting known metadata schemes in the process. Wraps around codemetapy and other codemeta software.




<a id="v0.3.5"></a>
# v0.3.5 - 2020-10-15

Added the ability to detect multiple authors [#5](https://github.com/proycon/codemetapy/issues/5) 



<a id="v0.3.4"></a>
# v0.3.4 - 2020-10-08

Previous release was a bit premature, there was a bug related to [#4](https://github.com/proycon/codemetapy/issues/4) still that has now been fixed.



<a id="v0.3.3"></a>
# v0.3.3 - 2020-10-08

* parse dependency versions and store them explicitly; don't stumble over extras (they will be processed as any other dependency, the 'extra' information bit does not get converted. [#4](https://github.com/proycon/codemetapy/issues/4)
* added a ``-no-extras`` parameter that disregards all the extras. [#4](https://github.com/proycon/codemetapy/issues/4) 





<a id="v0.3.2"></a>
# v0.3.2 - 2020-02-03

Minor bugfix release: do add duplicate entrypoints



<a id="v0.3.1"></a>
# v0.3.1 - 2019-11-20

Minor bugfix release: do not reset entrypoints when chaining



<a id="v0.3.0"></a>
# v0.3.0 - 2019-11-15

This release makes some changes to the way codemetapy works:
* Instead of parsing pip output, the tool now uses importlib.metadata to query for metadata. As metadata is read after installation, this work regardless of how the metadata was initially specified (setup.yp, setup.cfg or pyproject.toml)

New features:
* Added an output file parameter (``-O``)
* Added an integration hook for setuptools, allowing users to  add a codemeta command to setup.py

Fixes:
* Prevent duplicates in authors and other fields





<a id="v0.2.2"></a>
# v0.2.2 - 2019-09-09

Minor update to entrypoint extension: attempt to automatically read the docstring for each entrypoint and use it as a description for the entrypoint metadata



<a id="v0.2.1.1"></a>
# v0.2.1.1 - 2019-01-16

(Minor rerelease without changes just to trigger a DOI on Zenodo)



<a id="v0.2.1"></a>
# v0.2.1 - 2018-10-08

* better failure and exit code if identifier was not found in registry



<a id="v0.2.0"></a>
# v0.2.0 - 2018-09-17

* Added some simple support for converting debian package metadata from apt show to codemeta ([#1](https://github.com/proycon/codemetapy/issues/1))



<a id="v0.1.6"></a>
# v0.1.6 - 2018-08-31

Minor bugfix release



<a id="v0.1.5"></a>
# v0.1.5 - 2018-08-30

Minor update release:
* Added ``--with-orcid`` parameter to generate placeholders for ORCIDs in author details ([#2](https://github.com/proycon/codemetapy/issues/2))




<a id="v0.1.4"></a>
# v0.1.4 - 2018-05-19

* Bugfix release



<a id="v0.1.3"></a>
# v0.1.3 - 2018-05-10

* Added a ``resolve()`` function that resolves nodes that only have an ``@id`` when such a node was previously introduced (not used internally yet)



<a id="v0.1.2"></a>
# v0.1.2 - 2018-05-02

* making registry jsonld complaint
* added schema:audience property 
* Work on entrypoints, defining extra context for entrypoints (codemeta/codemeta#183) 
* lowercase all identifiers



<a id="v0.1.1"></a>
# v0.1.1 - 2018-04-23

* Minor fix: omit empty fields, use lower case identifiers in registry

