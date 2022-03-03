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
import distutils #note: will be removed in python 3.12!
try:
    import yaml
except ImportError:
    yaml = None
#pylint: disable=C0413
from codemeta.common import clean, update, getregistry, AttribDict, CONTEXT, SOFTWARETYPE_CONTEXT, ENTRYPOINT_CONTEXT, getstream
import codemeta.crosswalk
import codemeta.parsers.python
import codemeta.parsers.debian
import codemeta.parsers.json


if yaml is not None:
    def represent_ordereddict(dumper, data):
        """function to represent an ordered dictionary in yaml"""
        value = []

        for item_key, item_value in data.items():
            node_key = dumper.represent_data(item_key)
            node_value = dumper.represent_data(item_value)

            value.append((node_key, node_value))

        return yaml.nodes.MappingNode('tag:yaml.org,2002:map', value)

    yaml.add_representer(OrderedDict, represent_ordereddict)



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
    parser.add_argument('-o', '--outputtype', dest='output',type=str,help="Metadata output type: json (default), yaml", action='store',required=False, default="json")
    parser.add_argument('-O','--outputfile',  dest='outputfile',type=str,help="Output file", action='store',required=False)
    parser.add_argument('-i','--inputtype', dest='inputtypes',type=str,help="Metadata input type: python, apt (debian packages), registry, json, yaml. May be a comma seperated list of multiple types if files are passed on the command line", action='store',required=False)
    parser.add_argument('-r','--registry', dest='registry',type=str,help="The given registry file groups multiple JSON-LD metadata together in one JSON file. If specified, the file will be read (or created), and updated. This is a custom extension not part of the CodeMeta specification", action='store',required=False)
    parser.add_argument('--with-spdx', dest='with_spdx', help="Express license information using full SPDX URIs, attempt to convert automatically where possible", action='store_true')
    parser.add_argument('--with-repostatus', dest='with_repostatus', help="Express project status using repostatus vocabulary, using full URIs, attempt to convert automatically where possible", action='store_true')
    parser.add_argument('-a', '--all', dest='all', help="Enable all recommended extensions: --with-stypes --with-spdx --with-repostatus", action='store_true')
    parser.add_argument('inputsources', nargs='*', help='Input sources, the nature of the source depends on the type, often a file (or use - for standard input), set -i accordingly with the types (must contain as many items as passed!)')
    parser.add_argument('--no-extras',dest="no_extras",help="Do not parse any extras in the dependency specification", action='store_true', required=False)
    for key, prop in sorted(props.items()):
        if key:
            parser.add_argument('--' + key,dest=key, type=str, help=prop['DESCRIPTION'] + " (Type: "  + prop['TYPE'] + ", Parent: " + prop['PARENT'] + ") [you can format the value string in json if needed]", action='store',required=False)
    args = parser.parse_args()
    if args.all:
        args.with_spdx = True
        args.with_repostatus = True
        args.with_stypes = True
    else:
        print("NOTE: It is recommended to run with the --all option if you want to enable all recommended extensions upon codemeta (disabled by default)",file=sys.stderr)
    build(**args.__dict__)


def build(**kwargs):
    """Build a codemeta file"""
    args = AttribDict(kwargs)
    if args.with_stype:
        extracontext = [SOFTWARETYPE_CONTEXT]
    elif args.with_entrypoints:
        extracontext = [ENTRYPOINT_CONTEXT]
    else:
        extracontext = []

    if args.registry:
        if os.path.exists(args.registry):
            with open(args.registry, 'r', encoding='utf-8') as f:
                registry = json.load(f)
        else:
            print(f"Registry {args.registry} does not exist yet, creating anew...",file=sys.stderr)
            registry = {"@context": CONTEXT + extracontext, "@graph": []}
    else:
        registry = None
    if registry is not None and ('@context' not in registry or '@graph' not in registry):
        print(f"Registry {args.registry} has invalid (outdated?) format, ignoring and creating a new one...",file=sys.stderr)
        registry = {"@context": CONTEXT + extracontext, "@graph": []}

    inputsources = []
    if args.inputsources:
        inputfiles = args.inputsources
        inputtypes = args.inputtypes.split(",") if args.inputtypes else []
        if len(inputtypes) != len(inputfiles):
            if all( x.lower().endswith(".json") for x in inputfiles ):
                inputtypes = ["json"] * len(inputfiles)
            else:
                if len(inputtypes) == 0:
                    print(f"No input types specified ({len(inputfiles)} input sources), assuming python",  file=sys.stderr)
                    inputtypes = ["python"] * len(inputfiles)
                else:
                    print(f"Passed {len(inputfiles)} files but specified {len(inputtypes)} input types!",  file=sys.stderr)
        inputsources = list(zip(inputfiles, inputtypes))
    else:
        #no input was specified
        if os.path.exists('setup.py'):
            print("No input files specified, but found python project in current dir, using that...",file=sys.stderr)
            print("Generating egg_info",file=sys.stderr)
            os.system("python3 setup.py egg_info")
            for d in glob.glob("*.egg-info"):
                inputsources = [(".".join(d.split(".")[:-1]),"python")]
                break
            if not inputsources:
                print("Could not generate egg_info (is python3 pointing to the right interpreter?)",file=sys.stderr)
                sys.exit(2)
        else:
            print("No input files specified (use - for stdin)",file=sys.stderr)
            sys.exit(2)

    data = OrderedDict({
        '@context': CONTEXT + extracontext,
        "@type": "SoftwareSourceCode",
    })
    l = len(inputsources)
    for i, (source, inputtype) in enumerate(inputsources):
        print(f"Processing source #{i+1} of {l}",file=sys.stderr)
        if inputtype == "registry":
            try:
                update(data, getregistry(getstream(source), registry))
            except KeyError:
                print(f"ERROR: No such identifier in registry: {source}", file=sys.stderr)
                sys.exit(3)
        elif inputtype in ("python","distutils"):
            print(f"Obtaining python package metadata for: {source}",file=sys.stderr)
            #source is a name of a package
            update(data, codemeta.parsers.python.parsepython(data, source, crosswalk, args))
        elif inputtype == "pip":
            print("Pip output parsing is obsolete since codemetapy 0.3.0, please use input type 'python' instead",file=sys.stderr)
            sys.exit(2)
        elif inputtype in ("apt","debian","deb"):
            aptlines = getstream(source).read().split("\n")
            update(data, codemeta.parsers.debian.parseapt(data, aptlines, crosswalk, args))
        elif inputtype == "json":
            print(f"Parsing json file: {source}",file=sys.stderr)
            update(data, codemeta.parsers.json.parsecodemeta(getstream(source), args))

        for key, prop in props.items():
            if hasattr(args,key) and getattr(args,key) is not None:
                value = getattr(args, key)
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError: #not JSON, take to be a literal string
                    if '[' in value or '{' in value: #surely this was meant to be json
                        raise
                data[key] = value

    data = clean(data)

    if args.output == "json":
        if args.outputfile and args.outputfile != "-":
            with open(args.outputfile,'w',encoding='utf-8') as fp:
                json.dump(data,fp, ensure_ascii=False, indent=4)
        else:
            print(json.dumps(data, ensure_ascii=False, indent=4))
    elif args.output == "yaml":
        if not yaml:
            raise Exception("Yaml support not available", args.output)
        if args.outputfile and args.outputfile != "-":
            with open(args.outputfile,'w',encoding='utf-8') as fp:
                yaml.dump(data, fp, default_flow_style=False)
        else:
            yaml.dump(data, sys.stdout, default_flow_style=False)
    else:
        raise Exception("No such output type: ", args.output)

    if args.registry and data['identifier']:
        if '@context' in data:
            del data['@context'] #already in registry at top level
        data["@id"] = "#" + data['identifier'].lower()
        found = False
        for i, d in enumerate(registry["@graph"]):
            if d['identifier'].lower() == data['identifier'].lower():
                registry['@graph'][i] = data #overwrite existing entry
                found = True
                break
        if not found:
            registry["@graph"].append(data) #add new entry
        with open(args.registry,'w',encoding='utf-8') as f:
            print(json.dumps(registry, ensure_ascii=False, indent=4), file=f)

if __name__ == '__main__':
    main()
