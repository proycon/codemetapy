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
import importlib
import distutils
import setuptools
from collections import OrderedDict, defaultdict
from nameparser import HumanName
try:
    import yaml
except ImportError:
    yaml = None
if sys.version_info.minor < 8:
    import importlib_metadata #backported
else:
    import importlib.metadata as importlib_metadata #python 3.8 and above: in standard library


class CWKey:
    """Crosswalk Keys, correspond with header label in crosswalk.csv"""
    PROP = "Property"
    PARENT = "Parent Type"
    TYPE = "Type"
    DESCRIPTION = "Description"
    PYPI = "Python Distutils (PyPI)"
    DEBIAN = "Debian Package"
    R = "R Package Description"
    NODEJS = "NodeJS"
    MAVEN = "Java (Maven)"
    DOAP = "DOAP"

PROVIDER_PYPI = {
    "@id": "https://pypi.org",
    "@type": "Organization",
    "name": "The Python Package Index",
    "url": "https://pypi.org",
}
PROVIDER_DEBIAN = {
    "@id": "https://www.debian.org",
    "@type": "Organization",
    "name": "The Debian Project",
    "url": "https://www.debian.org",
}
PROGLANG_PYTHON = {
    "@type": "ComputerLanguage",
    "name": "Python",
    "version": str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro),
    "url": "https://www.python.org",
}

CONTEXT =  [
    "https://doi.org/10.5063/schema/codemeta-2.0",
    "http://schema.org",
]

ENTRYPOINT_CONTEXT = { #these are all custom extensions not in codemeta (yet), they are proposed in https://github.com/codemeta/codemeta/issues/183
    "entryPoints": { "@reverse": "schema:actionApplication" },
    "interfaceType": { "@id": "codemeta:interfaceType" }, #Type of the entrypoint's interface (e.g CLI, GUI, WUI, TUI, REST, SOAP, XMLRPC, LIB)
    "specification": { "@id": "codemeta:specification" , "@type":"@id"}, #A technical specification of the interface
    "mediatorApplication": {"@id": "codemeta:mediatorApplication", "@type":"@id" } #auxiliary software that provided/enabled this entrypoint
}


if yaml is not None:
    def represent_ordereddict(dumper, data):
        value = []

        for item_key, item_value in data.items():
            node_key = dumper.represent_data(item_key)
            node_value = dumper.represent_data(item_value)

            value.append((node_key, node_value))

        return yaml.nodes.MappingNode('tag:yaml.org,2002:map', value)

    yaml.add_representer(OrderedDict, represent_ordereddict)


def readcrosswalk(sourcekeys=(CWKey.PYPI,CWKey.DEBIAN)):
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

def parsepython(data, packagename, mapping=None, with_entrypoints=False, orcid_placeholder=False, exactplatformversion=False,extras=True, multi_author=True):
    """Parses python package metadata and converts it to codemeta"""
    if mapping is None:
        _, mapping = readcrosswalk((CWKey.PYPI,))
    authorindex = []
    data["provider"] = PROVIDER_PYPI
    if exactplatformversion:
        data["runtimePlatform"] =  "Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro)
    else:
        data["runtimePlatform"] =  "Python 3"
    if with_entrypoints and not 'entryPoints' in data:
        #not in official specification!!!
        data['entryPoints'] = []
    pkg = importlib_metadata.distribution(packagename)
    print("Found metadata in " , pkg._path,file=sys.stderr)
    for key, value in pkg.metadata.items():
        if key == "Classifier":
            fields = [ x.strip() for x in value.strip().split('::') ]
            pipkey = "classifiers['" + fields[0] + "']"
            pipkey = pipkey.lower()
            if pipkey in mapping[CWKey.PYPI]:
                key = mapping[CWKey.PYPI][pipkey]
                det = " :: " if key != "programmingLanguage" else " "
                value = det.join(fields[1:])
                if key in data:
                    if isinstance(data[key],str):
                        if not any( x.strip() == value for x in data[key].split(",") ):
                            data[key] += ", " + value
                    elif isinstance(data[key],list):
                        if value not in data[key]:
                            data[key].append(value)
                else:
                    data[key] = value
            elif fields[0].lower() in mapping[CWKey.PYPI]:
                key = mapping[CWKey.PYPI][fields[0].lower()]
                det = " :: " if key != "programmingLanguage" else " "
                value = det.join(fields[1:])
                if key in data:
                    if not any( x.strip() == value for x in data[key].split(",") ):
                        data[key] += ", " + value
                else:
                    data[key] = value
            elif fields[0] == "Intended Audience":
                if not any(( 'audienceType' in a and a['audienceType'] == " :: ".join(fields[1:]) for a in data["audience"] )):
                    data["audience"].append({
                        "@type": "Audience",
                        "audienceType": " :: ".join(fields[1:])
                    })
            else:
                print("NOTICE: Classifier "  + fields[0] + " has no translation",file=sys.stderr)
        else:
            if key == "Author":
                if multi_author:
                    names = value.strip().split(",")
                else:
                    names = [value.strip()]
                for name in names:
                    humanname = HumanName(name.strip())
                    lastname = " ".join((humanname.middle, humanname.last)).strip()
                    found = False
                    for i, a in enumerate(data["author"]):
                        if a['givenName'] == humanname.first and a['familyName'] == lastname:
                            authorindex.append(i)
                            found = True
                            break
                    if not found:
                        authorindex.append(len(data["author"]))
                        data["author"].append(
                            {"@type":"Person", "givenName": humanname.first, "familyName": lastname }
                        )
                        if orcid_placeholder:
                            data["author"][-1]["@id"] = "https://orcid.org/EDIT_ME!"
            elif key == "Author-email":
                if data["author"]:
                    if multi_author:
                        mails = value.split(",")
                        if len(mails) == len(authorindex):
                            for i, mail in zip(authorindex, mails):
                                data["author"][i]["email"] = mail.strip()
                        else:
                            print("WARNING: Unable to unambiguously assign e-mail addresses to multiple authors",file=sys.stderr)
                    else:
                        data["author"][-1]["email"] = value
                else:
                    print("WARNING: No author provided, unable to attach author e-mail",file=sys.stderr)
            elif key == "Requires-Dist":
                for dependency in splitdeps(value):
                    if dependency.find("extra =") != -1 and not extras:
                        print("Skipping extra dependency: ",dependency,file=sys.stderr)
                        continue
                    dependency, depversion = parsedependency(dependency.strip())
                    if dependency and not any(( 'identifier' in d and d['identifier'] == dependency for d in data['softwareRequirements'])):
                        data['softwareRequirements'].append({
                            "@type": "SoftwareApplication",
                            "identifier": dependency,
                            "name": dependency,
                            "provider": PROVIDER_PYPI,
                            "runtimePlatform": data["runtimePlatform"]
                        })
                        if depversion:
                            data['softwareRequirements'][-1]['version'] = depversion
            elif key == "Requires-External":
                for dependency in value.split(','):
                    dependency = dependency.strip()
                    if dependency and not any(( 'identifier' in d and d['identifier'] == dependency for d in data['softwareRequirements'])):
                        data['softwareRequirements'].append({
                            "@type": "SoftwareApplication",
                            "identifier": dependency,
                            "name": dependency,
                        })
            elif key.lower() in mapping[CWKey.PYPI]:
                data[mapping[CWKey.PYPI][key.lower()]] = value
                if key == "Name" and ('identifier' not in data or data['identifier'] in ("unknown","")):
                    data["identifier"] = value
            else:
                print("WARNING: No translation for distutils key " + key,file=sys.stderr)
    if with_entrypoints:
        for rawentrypoint in pkg.entry_points:
            if rawentrypoint.group == "console_scripts":
                interfacetype = "CLI"
            elif rawentrypoint.group == "gui_scripts":
                interfacetype = "GUI"
            else:
                continue
            if rawentrypoint.value:
                module_name = rawentrypoint.value.strip().split(':')[0]
                try:
                    module = importlib.import_module(module_name)
                    description = module.__doc__
                except:
                    description = ""
            else:
                description = ""
            entrypoint = {
                "@type": "EntryPoint", #we are interpreting this a bit liberally because it's usually used with HTTP webservices
                "name": rawentrypoint.name,
                "urlTemplate": "file:///" + rawentrypoint.name, #three slashes because we omit host, the 'file' is an executable/binary (rather liberal use)
                "interfaceType": interfacetype, #custom property, this needs to be moved to a more formal vocabulary  at some point
            }
            if description:
                entrypoint['description'] = description
            if entrypoint not in data['entryPoints']:
                data['entryPoints'].append(entrypoint) #the entryPoints relation is not in the specification, but our own invention, it is the reverse of the EntryPoint.actionApplication property
        if not data['entryPoints'] or ('applicationCategory' in data and 'libraries' in data['applicationCategory'].lower()):
            #no entry points defined, assume this is a library
            data['interfaceType'] = "LIB"
    return data

def splitdeps(s):
    """Split a string of multiple dependencies into a list"""
    begin = 0
    depth = 0
    for i, c in enumerate(s):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        if c == ',' and depth == 0:
            yield s[begin:i].strip()
            begin = i + 1
    if s[begin:].strip():
        yield s[begin:].strip()


def parsedependency(s):
    """Parses a pip dependency specification, returning the identifier, version"""
    identifier = s.split(" ")[0]
    begin = s.find("(")
    if begin != -1:
        end = s.find(")")
        version = s[begin+1:end].strip().replace("==","")
    else:
        version = None
    return identifier, version


def parseapt(data, lines, mapping=None, with_entrypoints=False, orcid_placeholder=False):
    """Parses apt show output and converts to codemeta"""
    if mapping is None:
        _, mapping = readcrosswalk((CWKey.DEBIAN,))
    provider = PROVIDER_DEBIAN
    description = ""
    parsedescription = False
    if with_entrypoints and not 'entryPoints' in data:
        #not in official specification!!!
        data['entryPoints'] = []
    for line in lines:
        if parsedescription and line and line[0] == ' ':
            description += line[1:] + " "
        else:
            try:
                key, value = (x.strip() for x in line.split(':',1))
            except:
                continue
            if key == "Origin":
                data["provider"] = value
            elif key == "Depends":
                for dependency in value.split(","):
                    dependency = dependency.strip().split(" ")[0].strip()
                    if dependency:
                        data['softwareRequirements'].append({
                            "@type": "SoftwareApplication",
                            "identifier": dependency,
                            "name": dependency,
                        })
            elif key == "Section":
                if "libs" in value or "libraries" in value:
                    if with_entrypoints: data['interfaceType'] = "LIB"
                    data['audience'] = "Developers"
                elif "utils" in value or "text" in value:
                    if with_entrypoints: data['interfaceType'] = "CLI"
                elif "devel" in value:
                    data['audience'] = "Developers"
                elif "science" in value:
                    data['audience'] = "Researchers"
            elif key == "Description":
                parsedescription = True
                description = value + "\n\n"
            elif key == "Homepage":
                data["url"] = value
            elif key == "Version":
                data["version"] = value
            elif key.lower() in mapping[CWKey.DEBIAN]:
                data[mapping[CWKey.DEBIAN][key.lower()]] = value
                if key == "Package":
                    data["identifier"] = value
                    data["name"] = value
            else:
                print("WARNING: No translation for APT key " + key,file=sys.stderr)
    if description:
        data["description"] = description
    return data


def clean(data):
    """Purge empty values, lowercase identifier"""
    purgekeys = []
    for k,v in data.items():
        if v is "" or v is None or (isinstance(v,(tuple, list)) and len(v) == 0):
            purgekeys.append(k)
        elif isinstance(v, (dict, OrderedDict)):
            clean(v)
        elif isinstance(v, (tuple, list)):
            data[k] = [ clean(x) if isinstance(x, (dict,OrderedDict)) else x for x in v ]
    for k in purgekeys:
        del data[k]
    if 'identifier' in data:
        data['identifier'] = data['identifier'].lower()
    return data

def resolve(data, idmap=None):
    """Resolve nodes that refer to an ID mentioned earlier"""
    if idmap is None: idmap = {}
    for k,v in data.items():
        if isinstance(v, (dict, OrderedDict)):
            if '@id' in v:
                if len(v) > 1:
                    #this is not a reference, register in idmap (possibly overwriting earlier definition!)
                    idmap[v['@id']] = v
                elif len(v) == 1:
                    #this is a reference
                    if v['@id'] in idmap:
                        data[k] = idmap[v['@id']]
                    else:
                        print("NOTICE: Unable to resolve @id " + v['@id'] ,file=sys.stderr)
            resolve(v, idmap)
        elif isinstance(v, (tuple, list)):
            data[k] = [ resolve(x,idmap) if isinstance(x, (dict,OrderedDict)) else x for x in v ]
    return data

def getregistry(identifier, registry):
    for tool in registry['@graph']:
        if tool['identifier'].lower() == identifier.lower():
            return tool
    raise KeyError(identifier)

def update(data, newdata):
    """recursive update, adds values whenever possible instead of replacing"""
    if isinstance(data, dict):
        for key, value in newdata.items():
            if key in data:
                if isinstance(value, dict):
                    update(data[key], value)
                elif isinstance(value, list):
                    for x in value:
                        if isinstance(data[key], dict ):
                            data[key] = [ data[key], x ]
                        elif x not in data[key]:
                            if isinstance(data[key], list):
                               data[key].append(x)
                else:
                    data[key] = value
            else:
                data[key] = value

def getstream(source):
    if source == '-':
        return sys.stdin
    else:
        return open(source,'r',encoding='utf-8')




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
        ('with-entrypoints','e','Generate entrypoints as well (custom codemeta extension not part of the official specification'),
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


props, mapping = readcrosswalk()

def main():
    parser = argparse.ArgumentParser(description="Converter for Python Distutils (PyPI) Metadata to CodeMeta (JSON-LD) converter. Also supports conversion from other metadata types such as those from Debian packages. The tool can combine metadata from multiple sources.")
    parser.add_argument('-e','--with-entrypoints', dest="with_entrypoints", help="Add entry points (this is not in the official codemeta specification)", action='store_true',required=False)
    parser.add_argument('--exact-python-version', dest="exactplatformversion", help="Register the exact python interpreter used to generate the metadata as the runtime platform. Will only register the major version otherwise.", action='store_true',required=False)
    parser.add_argument('--single-author', dest="single_author", help="CodemetaPy will attempt to check if there are multiple authors specified in the author field, if you want to disable this behaviour, set this flag", action='store_true',required=False)
    parser.add_argument('--with-orcid', dest="with_orcid", help="Add placeholders for ORCID, requires manual editing of the output to insert the actual ORCIDs", action='store_true',required=False)
    parser.add_argument('-o', '--outputtype', dest='output',type=str,help="Metadata output type: json (default), yaml", action='store',required=False, default="json")
    parser.add_argument('-O','--outputfile',  dest='outputfile',type=str,help="Output file", action='store',required=False)
    parser.add_argument('-i','--inputtype', dest='input',type=str,help="Metadata input type: python, apt (debian packages), registry, json, yaml. May be a comma seperated list of multiple types if files are passed on the command line", action='store',required=False, default="python")
    parser.add_argument('-r','--registry', dest='registry',type=str,help="The given registry file groups multiple JSON-LD metadata together in one JSON file. If specified, the file will be read (or created), and updated. This is a custom extension not part of the CodeMeta specification", action='store',required=False)
    parser.add_argument('inputsources', nargs='*', help='Input sources, the nature of the source depends on the type, often a file (or use - for standard input), set -i accordingly with the types (must contain as many items as passed!)')
    parser.add_argument('--no-extras',dest="no_extras",help="Do not parse any extras in the dependency specification", action='store_true', required=False)
    for key, prop in sorted(props.items()):
        if key:
            parser.add_argument('--' + key,dest=key, type=str, help=prop['DESCRIPTION'] + " (Type: "  + prop['TYPE'] + ", Parent: " + prop['PARENT'] + ") [you can format the value string in json if needed]", action='store',required=False)
    args = parser.parse_args()
    build(**args.__dict__)


class AttribDict(dict):
    def __init__(self, d):
        self.__dict__ = d

    def __getattr__(self, key):
        if key in self:
            return self[key]
        else:
            return None

def build(**kwargs):
    """Build a codemeta file"""
    args = AttribDict(kwargs)
    if args.with_entrypoints:
        extracontext = [ENTRYPOINT_CONTEXT]
    else:
        extracontext = []

    if args.registry:
        if os.path.exists(args.registry):
            with open(args.registry, 'r', encoding='utf-8') as f:
                registry = json.load(f)
        else:
            print("Registry " + args.registry + " does not exist yet, creating anew...",file=sys.stderr)
            registry = {"@context": CONTEXT + extracontext, "@graph": []}
    else:
        registry = None
    if registry is not None and ('@context' not in registry or '@graph' not in registry):
        print("Registry " + args.registry + " has invalid (outdated?) format, ignoring and creating a new one...",file=sys.stderr)
        registry = {"@context": CONTEXT + extracontext, "@graph": []}

    inputsources = []
    if args.inputsources:
        if len(args.input.split(",")) != len(args.inputsources):
            print("Passed " + str(len(args.inputsources)) + " files but specified " + str(len(args.input.split(','))) + " input types!",file=sys.stderr)
        inputsources = list(zip(args.inputsources, args.input.split(',')))
    else:
        print("No input files specified (use - for stdin)",file=sys.stderr)
        sys.exit(2)

    data = OrderedDict({ #values are overriden/extended later
        '@context': CONTEXT + extracontext,
        "@type": "SoftwareSourceCode",
        "identifier":"unknown",
        "name":"unknown",
        "version":"unknown",
        "description":"",
        "license":"unknown",
        "author": [],
        "softwareRequirements": [],
        "audience": []
    })
    l = len(inputsources)
    for i, (source, inputtype) in enumerate(inputsources):
        print("Processing source #%d of %d" % (i+1,l),file=sys.stderr)
        if inputtype == "registry":
            try:
                update(data, getregistry(getstream(source), registry))
            except KeyError as e:
                print("ERROR: No such identifier in registry: ", source,file=sys.stderr)
                sys.exit(3)
        elif inputtype in ("python","distutils"):
            print("Obtaining python package metadata for: " + source,file=sys.stderr)
            #source is a name of a package
            update(data, parsepython(data, source, mapping, args.with_entrypoints, args.with_orcid, args.exactplatformversion, not args.no_extras, not args.single_author))
        elif inputtype == "pip":
            print("Pip output parsing is obsolete since codemetapy 0.3.0, please use input type 'python' instead",file=sys.stderr)
            sys.exit(2)
        elif inputtype in ("apt","debian","deb"):
            aptlines = getstream(source).read().split("\n")
            update(data, parseapt(data, aptlines, mapping, args.with_entrypoints))
        elif inputtype == "json":
            print("Parsing json file: " + source,file=sys.stderr)
            update(data, json.load(getstream(source)))

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

    if args.registry:
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
