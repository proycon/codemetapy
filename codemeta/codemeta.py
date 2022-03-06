#!/usr/bin/env python3

"""This script converts software metadata
from PyPI/distutils into a generic codemata form (https://codemeta.github.io/)
can be extended for other input types too."""

# Maarten van Gompel
# CLST, Radboud University Nijmegen
# & KNAW Humanities Cluster
# GPL v3

import sys
import argparse
import json
import os.path
import glob
from collections import OrderedDict, defaultdict
from typing import Union, IO
import copy
import distutils.cmd #note: will be removed in python 3.12!
#pylint: disable=C0413

from rdflib import Graph, BNode, URIRef
from rdflib.namespace import RDF
from rdflib.plugins.shared.jsonld.context import Context
import rdflib.plugins.serializers.jsonld

from codemeta.common import init_graph, init_context, CODEMETA, AttribDict, getstream, CONTEXT, SDO, reconcile
import codemeta.crosswalk
import codemeta.parsers.python
import codemeta.parsers.debian
import codemeta.parsers.jsonld
from codemeta.serializers.jsonld import serialize_to_jsonld


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
    parser = argparse.ArgumentParser(description="Converter for Python Distutils (PyPI) Metadata to CodeMeta (JSON-LD) converter. Also supports conversion from other metadata types such as those from Debian packages. The tool can combine metadata from multiple sources.")
    parser.add_argument('-e', '--with-entrypoints', dest="with_entrypoints", help="Add entry points (this is not in the official codemeta specification but proposed in https://github.com/codemeta/codemeta/issues/183)", action='store_true',required=False)
    parser.add_argument('-t', '--with-stypes', dest="with_stypes", help="Convert entrypoints to targetProduct and classes reflecting software type (https://github.com/codemeta/codemeta/issues/#271), linking softwareSourceCode to softwareApplication or WebAPI", action='store_true',required=False)
    parser.add_argument('--exact-python-version', dest="exactplatformversion", help="Register the exact python interpreter used to generate the metadata as the runtime platform. Will only register the major version otherwise.", action='store_true',required=False)
    parser.add_argument('--single-author', dest="single_author", help="CodemetaPy will attempt to check if there are multiple authors specified in the author field, if you want to disable this behaviour, set this flag", action='store_true',required=False)
    parser.add_argument('--with-orcid', dest="with_orcid", help="Add placeholders for ORCID, requires manual editing of the output to insert the actual ORCIDs", action='store_true',required=False)
    parser.add_argument('-b', '--baseuri',type=str,help="Base URI for resulting SoftwareSourceCode instances (make sure to add a trailing slash)", action='store',required=False)
    parser.add_argument('-o', '--outputtype', dest='output',type=str,help="Metadata output type: json (default), yaml", action='store',required=False, default="json")
    parser.add_argument('-O','--outputfile',  dest='outputfile',type=str,help="Output file", action='store',required=False)
    parser.add_argument('-i','--inputtype', dest='inputtypes',type=str,help="Metadata input type: python, apt (debian packages), registry, json, yaml. May be a comma seperated list of multiple types if files are passed on the command line", action='store',required=False)
    parser.add_argument('-r','--registry', dest='registry',type=str,help="The given registry file groups multiple JSON-LD metadata together in one JSON file. If specified, the file will be read (or created), and updated. This is a custom extension not part of the CodeMeta specification", action='store',required=False)
    parser.add_argument('-a', '--all', dest='all', help="Enable all recommended extensions: --with-stypes", action='store_true')
    parser.add_argument('inputsources', nargs='*', help='Input sources, the nature of the source depends on the type, often a file (or use - for standard input), set -i accordingly with the types (must contain as many items as passed!)')
    parser.add_argument('--no-extras',dest="no_extras",help="Do not parse any extras in the dependency specification", action='store_true', required=False)
    for key, prop in sorted(props.items()):
        if key:
            parser.add_argument('--' + key,dest=key, type=str, help=prop['DESCRIPTION'] + " (Type: "  + prop['TYPE'] + ", Parent: " + prop['PARENT'] + ") [you can format the value string in json if needed]", action='store',required=False)
    args = parser.parse_args()
    if args.all:
        args.with_stypes = True
    else:
        print("NOTE: It is recommended to run with the --all option if you want to enable all recommended extensions upon codemeta (disabled by default)",file=sys.stderr)
    build(**args.__dict__)


def build(**kwargs):
    """Build a codemeta file"""
    args = AttribDict(kwargs)

    inputsources = []
    if args.inputsources:
        inputfiles = args.inputsources
        inputtypes = args.inputtypes.split(",") if args.inputtypes else []
        guess = False
        if len(inputtypes) != len(inputfiles):
            print(f"Passed {len(inputfiles)} files but specified {len(inputtypes)} input types! Automatically guessing types...",  file=sys.stderr)
            guess = True
            for inputsource in inputfiles[len(inputtypes):]:
                if inputsource.lower().startswith("http"):
                    inputtypes.append("web")
                elif inputsource.lower().endswith(".json"):
                    inputtypes.append("json")
                else:
                    #assume python
                    inputtypes.append("python")
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
                print("Could not generate egg_info (is python3 pointing to the right interpreter?)",file=sys.stderr)
                sys.exit(2)
        else:
            print("No input files specified (use - for stdin)",file=sys.stderr)
            sys.exit(2)

    init_context()
    g = init_graph()

    #Generate a temporary ID to use for the SoftwareSourceCode resource
    #The ID will be overwritten with a more fitting one upon serialisation
    identifier = os.path.basename(inputsources[0][0]).lower()
    if not identifier or not isinstance(identifier, str) or identifier == '-':
        if args.outputfile and args.outputfile != '-':
            identifier = os.path.basename(args.outputfile).lower()
        else:
            identifier = "unknown"
    if args.baseuri:
        uri = args.baseuri +  identifier
    else:
        uri = "undefined:" + identifier

    #add the root resource
    res = URIRef(uri)
    g.add((res, RDF.type, SDO.SoftwareSourceCode))

    founduri = False #indicates whether we found a preferred URI or not

    l = len(inputsources)
    for i, (source, inputtype) in enumerate(inputsources):
        print(f"Processing source #{i+1} of {l}",file=sys.stderr)

        prefuri = None #preferred URI returned by the parsing method
        if inputtype == "python":
            print(f"Obtaining python package metadata for: {source}",file=sys.stderr)
            #source is a name of a package
            prefuri = codemeta.parsers.python.parse_python(g, res, source, crosswalk, args)
        #elif inputtype == "debian":   #TODO: re-enable!
        #    aptlines = getstream(source).read().split("\n")
        #    update(data, codemeta.parsers.debian.parseapt(data, aptlines, crosswalk, args))
        elif inputtype == "json":
            print(f"Parsing json-ld file: {source}",file=sys.stderr)
            prefuri = codemeta.parsers.jsonld.parse_jsonld(g, res, getstream(source), args)

        #Set preferred URL
        if prefuri and not founduri:
            uri = prefuri
            founduri = True

    reconcile(g, res, args)

    if args.output == "json":
        doc = serialize_to_jsonld(g, res, uri)
        if args.outputfile and args.outputfile != "-":
            with open(args.outputfile,'w',encoding='utf-8') as fp:
                fp.write(json.dumps(doc, indent=4))
        else:
            print(json.dumps(doc, indent=4))
    else:
        raise Exception("No such output type: ", args.output)



if __name__ == '__main__':
    main()
