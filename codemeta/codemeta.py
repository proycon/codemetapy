#!/usr/bin/env python3

"""This script converts software metadata
from PyPI/distutils into a generic codemata form (https://codemeta.github.io/)
can be extended for other input types too."""

# Maarten van Gompel
# CLST, Radboud University Nijmegen
# & KNAW Humanities Cluster
# GPL v3
import re
import sys
import argparse
import json
import os.path
import glob
import random
from collections import OrderedDict, defaultdict
from typing import Union, IO, Optional, Sequence, Tuple
import copy
import datetime
import distutils.cmd #note: will be removed in python 3.12! TODO constraint <= 3.11 in apk/apt-get in Dockerfile
#pylint: disable=C0413

from rdflib import Graph, BNode, URIRef, Literal
from rdflib.namespace import RDF, SH
from rdflib.plugins.shared.jsonld.context import Context
import rdflib.plugins.serializers.jsonld

from codemeta.common import init_graph, init_context, CODEMETA, AttribDict, getstream, CONTEXT, SDO, reconcile, add_triple, generate_uri, remap_uri, query
import codemeta.crosswalk
import codemeta.parsers.python
import codemeta.parsers.debian
import codemeta.parsers.jsonld
import codemeta.parsers.nodejs
import codemeta.parsers.java
import codemeta.parsers.web
import codemeta.parsers.gitapi
import codemeta.parsers.authors
import codemeta.validation
from codemeta.serializers.jsonld import serialize_to_jsonld
from codemeta.serializers.html import serialize_to_html
from codemeta.serializers.turtle import serialize_to_turtle


#class PostDevelopCommand(setuptools.command.develop.develop):
#    """Post development installation hook"""
#    def run(self):
#        setuptools_update(self)
#        super(PostDevelopCommand, self).run()
#
#class PostInstallCommand(setuptools.command.install.install):
#    """Post installation hook"""
#    def run(self):
#        setuptools_update(self)
#        super(PostInstallCommand, self).run()

class CodeMetaCommand(distutils.cmd.Command):
    description = "Generate a codemeta.json file or update an existing one, note that the package must be installed first for this to work!"
    user_options = [
        ('with-entrypoints','e','Generate entrypoints as well (custom codemeta extension not part of the official specification)'),
        ('with-stypes','t','Generate software types using targetProduct (custom extension not part of the official codemeta/schema.org specification yet)'),
        ('dry-run','n','Write to stdout instead of codemeta.json')
    ]
    def initialize_options(self):
        self.with_entrypoints = False
        self.dry_run = False

    def finalize_options(self):
        self.with_entrypoints = bool(self.with_entrypoints)
        self.dry_run = bool(self.dry_run)

    def run(self):
        """Updates the codemeta.json for this package during the setup process. Hook to be (indirectly) called from setuptools"""
        codemetafile = "codemeta.json"
        if self.dry_run:
            outputfile = "-"
        else:
            outputfile = codemetafile
        print("Writing codemeta metadata to " + outputfile,file=sys.stderr)
        if os.path.exists(codemetafile):
            build(input="json,python",output="json",outputfile=outputfile, inputsources=[codemetafile, self.distribution.metadata.name], with_entrypoints=self.with_entrypoints)
        else:
            build(input="python",output="json",outputfile=outputfile, inputsources=[self.distribution.metadata.name], with_entrypoints=self.with_entrypoints)


props, crosswalk = codemeta.crosswalk.readcrosswalk()

def main():
    """Main entrypoint for command-line usage"""

    parser = argparse.ArgumentParser(description="Converter for Python Distutils (PyPI) Metadata to CodeMeta (JSON-LD) converter. Also supports conversion from other metadata types such as those from Debian packages. The tool can combine metadata from multiple sources.")
    parser.add_argument('-t', '--with-stypes', dest="with_stypes", help="Convert entrypoints to targetProduct and classes reflecting software type (https://github.com/codemeta/codemeta/issues/#271), linking softwareSourceCode to softwareApplication or WebAPI. If enabled, any remote URLs passed to codemetapy will automatically be encoded via targetProduct.", action='store_true',required=False)
    parser.add_argument('--exact-python-version', dest="exactplatformversion", help="Register the exact python interpreter used to generate the metadata as the runtime platform. Will only register the major version otherwise.", action='store_true',required=False)
    parser.add_argument('--single-author', dest="single_author", help="CodemetaPy will attempt to check if there are multiple authors specified in the author field, if you want to disable this behaviour, set this flag", action='store_true',required=False)
    parser.add_argument('-b', '--baseuri',type=str,help="Base URI for resulting SoftwareSourceCode instances (make sure to add a trailing slash)", action='store',required=False)
    parser.add_argument('-B', '--baseurl',type=str,help="Base URL in HTML visualizations (make sure to add a trailing slash)", action='store',required=False)
    parser.add_argument('-o', '--outputtype', dest='output',type=str,help="Output type: json (default), turtle, html", action='store',required=False, default="json")
    parser.add_argument('-O','--outputfile',  dest='outputfile',type=str,help="Output file", action='store',required=False)
    parser.add_argument('-i','--inputtype', dest='inputtypes',type=str,help="Metadata input type: python, apt (debian packages), registry, json, yaml. May be a comma seperated list of multiple types if files are passed on the command line", action='store',required=False)
    parser.add_argument('-g','--graph', dest='graph',help="Output a knowledge graph that groups all input files together. Only JSON input files are supported.", action='store_true',required=False)
    parser.add_argument('-s','--select', type=str, help="Output only the selected resource (by URI) from the graph", action='store',required=False)
    parser.add_argument('-V','--validate', type=str, help="Validate against the provided SHACL file. Adds a review property with the condensed validation results.", action='store',required=False)
    parser.add_argument('--exitv', help="Set exit status according to validation result. Use with --validate", action='store_true',required=False)
    parser.add_argument('--css',type=str, help="Associate a CSS stylesheet (URL) with the HTML output, multiple stylesheets can be separated by a comma", action='store',  required=False)
    parser.add_argument('--no-cache',dest="no_cache", help="Do not cache context files, force redownload", action='store_true',  required=False)
    parser.add_argument('--toolstore', help="When converting to HTML, link pages together as served by the CLARIAH tool store (https://github.com/CLARIAH/tool-discovery)", action='store_true',  required=False)
    parser.add_argument('--strict', dest='strict', help="Strictly adhere to the codemeta standard and disable any extensions on top of it", action='store_true')
    parser.add_argument('--released', help="Signal that this software is released, this affects whether development status maps to either WIP or active", action='store_true')
    parser.add_argument('--title', type=str, help="Title to add when generating HTML pages", action='store')
    parser.add_argument('inputsources', nargs='*', help='Input sources, the nature of the source depends on the type, often a file (or use - for standard input), set -i accordingly with the types (must contain as many items as passed!)')

    for key, prop in sorted(props.items()):
        if key:
            parser.add_argument('--' + key,dest=key, type=str, help=prop['DESCRIPTION'] + " (Type: "  + prop['TYPE'] + ", Parent: " + prop['PARENT'] + ") [you can format the value string in json if needed]", action='store',required=False)

    args = parser.parse_args()
    if not args.strict:
        args.with_stypes = True
    if args.css:
        args.css = [ x.strip() for x in args.css.split(",") ]

    if args.baseuri and not args.baseurl:
        args.baseurl = args.baseuri

    valid = False
    if args.graph:
        #join multiple inputs into a larger graph
        g, res, args, contextgraph = read(**args.__dict__)
    else:
        #normal behaviour
        g, res, args, contextgraph = build(**args.__dict__)
    if args.validate: valid, _ = codemeta.validation.validate(g, res, args, contextgraph)
    output = serialize(g, res, args, contextgraph)
    if output:
        print(output)

    if args.exitv and args.validate:
        return 0 if valid else 1




def serialize(g: Graph, res: Union[Sequence,URIRef,BNode,None], args: AttribDict, contextgraph: Union[Graph,None] = None, sparql_query: Optional[str] = None, **kwargs) -> Graph:
    if args.output == "json":
        if sparql_query: res = [ x[0]  for x in query(g, sparql_query) ]
        doc = serialize_to_jsonld(g, res)
        if args.outputfile and args.outputfile != "-":
            with open(args.outputfile,'w',encoding='utf-8') as fp:
                fp.write(json.dumps(doc, indent=4, ensure_ascii=False, sort_keys=True))
        else:
            return json.dumps(doc, indent=4, ensure_ascii=False, sort_keys=True)
    elif args.output in ("turtle","ttl"):
        if sparql_query: res = [ x[0]  for x in query(g, sparql_query) ]
        doc = serialize_to_turtle(g, res)
        if args.outputfile and args.outputfile != "-":
            with open(args.outputfile,'wb') as fp:
                fp.write(doc)
        else:
            return doc
    elif args.output == "html":
        doc = serialize_to_html(g, res, args, contextgraph, sparql_query,  **kwargs) #note: sparql query is applied in serialization function if needed
        if args.outputfile and args.outputfile != "-":
            with open(args.outputfile,'w',encoding='utf-8') as fp:
                fp.write(doc)
        else:
            return doc
    else:
        raise Exception("No such output type: ", args.output)

def read(**kwargs) -> Tuple[Graph, Union[URIRef,None], AttribDict, Graph]:
    """Read multiple resources together in a codemeta graph, and either output it all or output a selection"""

    args = AttribDict(kwargs)

    g, contextgraph = init_graph(args.no_cache)

    if not args.inputsources:
        raise Exception("No inputsources specified")

    for source in args.inputsources:
        print(f"Adding json-ld file from {source} to graph",file=sys.stderr)
        codemeta.parsers.jsonld.parse_jsonld(g, None, getstream(source), args)

    if args.select:
        res = URIRef(args.select)
        if (res, None, None) not in g:
            raise KeyError("Selected resource does not exists")
    else:
        res = None

    return (g, res, args, contextgraph)


def build(**kwargs) -> Tuple[Graph, URIRef, AttribDict, Graph]:
    """Build a codemeta graph for a single resource"""
    args = AttribDict(kwargs)

    inputsources = []
    if args.inputsources:
        inputfiles = args.inputsources
        inputtypes = args.inputtypes.split(",") if args.inputtypes else []
        guess = False
        if len(inputtypes) != len(inputfiles):
            print(f"Passed {len(inputfiles)} files/sources but specified {len(inputtypes)} input types! Automatically guessing types...",  file=sys.stderr)
            guess = True
            for inputsource in inputfiles[len(inputtypes):]:
                if inputsource.lower().endswith("setup.py"):
                    inputtypes.append("python")
                elif inputsource.endswith("package.json"):
                    inputtypes.append("nodejs")
                elif inputsource.endswith("pyproject.toml"):
                    inputtypes.append("python")
                elif inputsource.endswith("pom.xml"):
                    inputtypes.append("java")
                elif inputsource.lower().endswith(".json") or inputsource.lower().endswith(".jsonld"):
                    inputtypes.append("json")
                elif inputsource.upper().endswith("CONTRIBUTORS"):
                    inputtypes.append("contributors")
                elif inputsource.upper().endswith("AUTHORS"):
                    inputtypes.append("authors")
                elif inputsource.upper().endswith("MAINTAINERS"):
                    inputtypes.append("maintainers")
                elif inputsource.lower().startswith("https") or inputsource.lower().startswith("git@"):
                    #test if this is a known git platform we can query via an API
                    repo_kind = codemeta.parsers.gitapi.get_repo_kind(inputsource)
                    if repo_kind:
                        inputtypes.append(repo_kind)
                    elif not inputsource.lower().startswith("git@"):
                        #otherwise it is just a website
                        inputtypes.append("web")
                elif inputsource.lower().startswith("http"):
                    inputtypes.append("web")
        inputsources = list(zip(inputfiles, inputtypes))
        if guess:
            print(f"Detected input types: {inputsources}",file=sys.stderr)
    else:
        #no input was specified
        if os.path.exists('setup.py'):
            print("No input files specified, but found python project in current dir, using that...",file=sys.stderr)
            print("Generating egg_info",file=sys.stderr)
            os.system("python3 setup.py egg_info >&2")
            for d in glob.glob("*.egg-info"):
                inputsources = [(".".join(d.split(".")[:-1]),"python")]
                break
            if not inputsources:
                raise Exception("Could not generate egg_info (is python3 pointing to the right interpreter?)")
        elif os.path.exists('pyproject.toml'):
            print("No input files specified, but found python project (pyproject.toml) in current dir, using that...",file=sys.stderr)
            inputsources = [("pyproject.toml","python")]
        else:
            raise Exception("No input files specified (use - for stdin)")

    g, contextgraph = init_graph(args.no_cache)

    seturi = False #indicates whether we have set a final URI


    if args.baseuri:
        args.baseuri = args.baseuri.strip('" ')

    if args.baseuri and args.identifier:
        #Explicit identifier and baseuri passed, authoritative
        identifier = args.identifier.strip('" ')
        uri = generate_uri(identifier, args.baseuri)
        print(f"URI set based on explicit identifier: {uri}",file=sys.stderr)
        seturi = True
    elif args.codeRepository:
        #Use the one from the codeRepository that was explicitly passed
        uri = args.codeRepository.strip('"')
        print(f"URI derived from explicitly passed codeRepository: {uri}",file=sys.stderr)
        seturi = True
    else:
        #Generate a temporary ID to use for the SoftwareSourceCode resource
        #The ID will be overwritten with a more fitting one upon serialisation
        if args.identifier:
            identifier = args.identifier.strip('"')
        else:
            identifier = os.path.basename(inputsources[0][0]).lower()
        if identifier:
            identifier = identifier.replace(".codemeta.json","").replace("codemeta.json","")
            identifier = identifier.replace(".pom.xml","").replace("pom.xml","")
            identifier = identifier.replace(".package.json","").replace("package.json","")
        uri = generate_uri(identifier, args.baseuri)
        print(f"URI automatically generated, may be overriden later: {uri}",file=sys.stderr)
        seturi = False #this URI is not authoritative and will be overwritten later

    #add the root resource
    res = URIRef(uri)
    g.add((res, RDF.type, SDO.SoftwareSourceCode))


    l = len(inputsources)
    for i, (source, inputtype) in enumerate(inputsources):
        print(f"Processing source #{i+1} of {l}",file=sys.stderr)
        prefuri = None #preferred URI returned by the parsing method
          
        if inputtype == "python":
            print(f"Obtaining python package metadata for: {source}",file=sys.stderr)
            #source is a name of a package or path to a pyproject.toml file
            prefuri = codemeta.parsers.python.parse_python(g, res, source, crosswalk, args)
        elif inputtype == "debian":
            print(f"Parsing debian package from {source}",file=sys.stderr)
            aptlines = getstream(source).read().split("\n")
            prefuri = codemeta.parsers.debian.parse_debian(g, res, aptlines, crosswalk, args)
        elif inputtype == "nodejs":
            print(f"Parsing npm package.json from {source}",file=sys.stderr)
            f = getstream(source)
            prefuri = codemeta.parsers.nodejs.parse_nodejs(g, res, f, crosswalk, args)
        elif inputtype == "java":
            print(f"Parsing java/maven pom.xml from {source}",file=sys.stderr)
            f = getstream(source)
            prefuri = codemeta.parsers.java.parse_java(g, res, f, crosswalk, args)
        elif inputtype == "json":
            print(f"Parsing json-ld file from {source}",file=sys.stderr)
            prefuri = codemeta.parsers.jsonld.parse_jsonld(g, res, getstream(source), args)
        elif inputtype == "web":
            print(f"Fallback: Obtaining metadata from remote URL {source}",file=sys.stderr)
            found = False
            for targetres in codemeta.parsers.web.parse_web(g, res, source, args):
                if targetres and args.with_stypes:
                    found = True
                    print(f"Adding service (targetProduct) {source}",file=sys.stderr)
                    g.add((res, SDO.targetProduct, targetres))
            if not found:
                print(f"(no metadata found at remote URL)",file=sys.stderr)
        elif inputtype in ("github", "gitlab"):
            #e.g. transform git@gitlab.com/X in https://gitlab.com/X
            source = re.sub(r'git@(.*):', r'https://\1/', source)
            if source.endswith(".git"): source = source[:-4]
            print(f"Querying GitAPI parser for {source}",file=sys.stderr)
            prefuri = codemeta.parsers.gitapi.parse(g, res, source, inputtype ,args)
        elif inputtype in ('authors', 'contributors','maintainers'):
            print(f"Extracting {inputtype} from {source}",file=sys.stderr)
            if inputtype == 'authors':
                prop = SDO.author
            elif inputtype == 'contributors':
                prop = SDO.contributor
            elif inputtype == 'maintainers':
                prop = CODEMETA.maintainer
            codemeta.parsers.authors.parse_authors(g, res, getstream(source), args, property=prop )
        elif inputtype is not None:
            raise ValueError(f"Unknown input type: {inputtype}")


        #Set preferred URL if we haven't found a URI yet
        if prefuri and not seturi:
            uri = prefuri
            print(f"    Setting preferred URI to {uri} based on source {source}",file=sys.stderr)
            seturi = True

    #Process command-line arguments last
    for key in props:
        if hasattr(args, key):
            value = getattr(args, key)
            if value: value = value.strip('"')
            if value:
                add_triple(g, res, key, value, args, replace=True)


    if uri != str(res):
        print(f"Remapping URI: {res} -> {uri}",file=sys.stderr)
        g = remap_uri(g, str(res), uri, args)
        res = URIRef(uri)

    #Test and fix conflicts in the graph (and report them)
    reconcile(g, res, args)

    return (g,res,args, contextgraph)



if __name__ == '__main__':
    main()
