#!/usr/bin/env python3

#This script converts software metadata
#from PyPI/distutils into a generic codemata form (https://codemeta.github.io/)
#can be extended for other input types too

# Maarten van Gompel
# CLST, Radboud University Nijmegen
# GPL v3

import sys
import argparse
import json
import os.path
import csv
from collections import OrderedDict, defaultdict
try:
    import yaml
except ImportError:
    yaml = None
from nameparser import HumanName

class CWKey:
    """Crosswalk Keys, correspond with header label in crosswalk.csv"""
    PROP = "Property"
    PARENT = "Parent Type"
    TYPE = "Type"
    DESCRIPTION = "Description"
    PYPI = "Python Distutils (PyPI)"

PROVIDER_PYPI = {
    "@id": "https://pypi.org",
    "@type": "Organization",
    "name": "The Python Package Index",
    "url": "https://pypi.org",
}
PROGLANG_PYTHON = {
    "@type": "ComputerLanguage",
    "name": "Python",
    "version": str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro),
    "url": "https://www.python.org",
}

CONTEXT =  [
    "https://doi.org/10.5063/schema/codemeta-2.0",
    "http://schema.org"
]


if yaml is not None:
    def represent_ordereddict(dumper, data):
        value = []

        for item_key, item_value in data.items():
            node_key = dumper.represent_data(item_key)
            node_value = dumper.represent_data(item_value)

            value.append((node_key, node_value))

        return yaml.nodes.MappingNode('tag:yaml.org,2002:map', value)

    yaml.add_representer(OrderedDict, represent_ordereddict)


def readcrosswalk(sourcekeys=(CWKey.PYPI,)):
    mapping = defaultdict(dict)
    #pip may output things differently than recorded in distutils/setup.py, so we register some aliases:
    mapping[CWKey.PYPI]["home-page"] = "url"
    mapping[CWKey.PYPI]["summary"] = "description"
    props = {}
    crosswalkfile = os.path.join(os.path.dirname(__file__), 'schema','crosswalk.csv')
    with open(crosswalkfile, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            props[row[CWKey.PROP]] = {"PARENT": row[CWKey.PARENT], "TYPE": row[CWKey.TYPE], "DESCRIPTION": row[CWKey.DESCRIPTION] }
            for sourcekey in sourcekeys:
                if row[sourcekey]:
                    mapping[sourcekey][row[sourcekey].lower()] = row[CWKey.PROP]

    return props, mapping


def parsepip(lines, mapping=None, with_entrypoints=False):
    """Parses pip -v output and converts to codemeta"""
    if mapping is None:
        _, mapping = readcrosswalk((CWKey.PYPI,))
    section = None
    data = OrderedDict({ #values are overriden/extended later
        '@context': CONTEXT,
        "@type": "SoftwareSourceCode",
        "identifier":"",
        "name":"",
        "version":"",
        "description":"",
        "license":"Unknown",
        "author": [],
        "provider": PROVIDER_PYPI,
        "runtimePlatform": "Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro),
        "softwareRequirements": [],
    })
    if with_entrypoints:
        #not in official specification!!!
        data['entryPoints'] = []
    for line in lines:
        if line.strip() == "Classifiers:":
            section = "classifiers"
        elif line.strip() == "Entry-points:":
            section = "interfaces"
        elif section == "classifiers":
            fields = [ x.strip() for x in line.strip().split('::') ]
            pipkey = "classifiers['" + fields[0] + "']"
            pipkey = pipkey.lower()
            if pipkey in mapping[CWKey.PYPI]:
                data[mapping[CWKey.PYPI][pipkey]] = " :: ".join(fields[1:])
            elif fields[0].lower() in mapping[CWKey.PYPI]:
                data[mapping[CWKey.PYPI][fields[0].lower()]] = " :: ".join(fields[1:])
            else:
                print("WARNING: Classifier "  + fields[0] + " has no translation",file=sys.stderr)
        elif section == "interfaces" and with_entrypoints:
            if line.strip() == "[console_scripts]":
                pass
            elif line.find('=') != -1:
                fields = [ x.strip() for x in line.split('=') ]
                data['entryPoints'].append({ #the entryPoints relation is not in the specification, but our own invention, it is the reverse of the EntryPoint.actionApplication property
                    "@type": "EntryPoint", #we are interpreting this a bit liberally because it's usually used with HTTP webservices
                    "name": fields[0],
                    "url": "file:///" + fields[0], #three slashes because we omit host, the 'file' is an executable/binary (rather liberal use)
                })
        else:
            try:
                key, value = (x.strip() for x in line.split(':',1))
            except:
                continue
            if key == "Author":
                humanname = HumanName(value.strip())
                data["author"].append({"@type":"Person", "givenName": humanname.first, "familyName": " ".join((humanname.middle, humanname.last)).strip() })
            elif key == "Author-email":
                data["author"][-1]["email"] = value
            elif key == "Requires":
                for dependency in value.split(','):
                    dependency = dependency.strip()
                    if dependency:
                        data['softwareRequirements'].append({
                            "@type": "SoftwareApplication",
                            "identifier": dependency,
                            "name": dependency,
                            "provider": PROVIDER_PYPI,
                            "runtimePlatform": "Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro)
                        })
            elif key == "Requires-External":
                for dependency in value.split(','):
                    dependency = dependency.strip()
                    if dependency:
                        data['softwareRequirements'].append({
                            "@type": "SoftwareApplication",
                            "identifier": dependency,
                            "name": dependency,
                        })
            elif key.lower() in mapping[CWKey.PYPI]:
                data[mapping[CWKey.PYPI][key.lower()]] = value
                if key == "Name":
                    data["identifier"] = value
            else:
                print("WARNING: No translation for pip key " + key,file=sys.stderr)
    return data

def main():
    props, mapping = readcrosswalk()
    parser = argparse.ArgumentParser(description="Python Distutils (PyPI) Metadata to CodeMeta (JSON-LD) converter")
    #parser.add_argument('--pip', help="Parse pip -v output", action='store_true',required=False)
    #parser.add_argument('--yaml', help="Read metadata from standard input (YAML format)", action='store_true',required=False)
    parser.add_argument('--with-entrypoints', dest="with_entrypoints", help="Add entry points (this is not in the official codemeta specification)", action='store_true',required=False)
    parser.add_argument('--output', type=str,help="Metadata output type: json, yaml", action='store',required=False, default="json")
    for key, prop in sorted(props.items()):
        if key:
            parser.add_argument('--' + key,dest=key, type=str, help=prop['DESCRIPTION'] + " (Type: "  + prop['TYPE'] + ", Parent: " + prop['PARENT'] + ")", action='store',required=False)
    args = parser.parse_args()

    data = parsepip(sys.stdin.read().split("\n"), mapping, args.with_entrypoints)

    for key, prop in props.items():
        if hasattr(args,key) and getattr(args,key) is not None:
            data[key] = getattr(args,key)

    if args.output == "json":
        print(json.dumps(data, ensure_ascii=False, indent=4))
    elif args.output == "yaml":
        if not yaml:
            raise Exception("Yaml support not available", args.output)
        yaml.dump(data, sys.stdout, default_flow_style=False)
    else:
        raise Exception("No such output type: ", args.output)


if __name__ == '__main__':
    main()
