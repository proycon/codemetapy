#!/usr/bin/env python3

#This script converts software metadata
#from PyPI/distutils into a generic codemata form (https://codemeta.github.io/)
#can be extended for other input types too

# Maarten van Gompel
# CLST, Radboud University Nijmegen
# & KNAW Humanities Cluster
# GPL v3

import sys
import argparse
import json
import os.path
import csv
import glob
import importlib
import re
from collections import OrderedDict, defaultdict
from typing import Union, IO
import distutils #note: will be removed in python 3.12!
try:
    import yaml
except ImportError:
    yaml = None
if sys.version_info.minor < 8:
    import importlib_metadata #backported
else:
    import importlib.metadata as importlib_metadata #python 3.8 and above: in standard library
#pylint: disable=C0413
from nameparser import HumanName

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
    "http://schema.org/",
]

ENTRYPOINT_CONTEXT = { #these are all custom extensions not in codemeta (yet), they are proposed in https://github.com/codemeta/codemeta/issues/183 but are obsolete in favour of the newer software types (see next declaration)
    "entryPoints": { "@reverse": "schema:actionApplication" },
    "interfaceType": { "@id": "codemeta:interfaceType" }, #Type of the entrypoint's interface (e.g CLI, GUI, WUI, TUI, REST, SOAP, XMLRPC, LIB)
    "specification": { "@id": "codemeta:specification" , "@type":"@id"}, #A technical specification of the interface
    "mediatorApplication": {"@id": "codemeta:mediatorApplication", "@type":"@id" } #auxiliary software that provided/enabled this entrypoint
}

#these are all custom extensions not in codemeta/schema.org (yet), they are proposed in https://github.com/codemeta/codemeta/issues/271 and supersede the above one
SOFTWARETYPE_CONTEXT = "https://w3id.org/software-types#"




REPOSTATUS= { #maps Python development status to repostatus.org vocabulary (the mapping is debatable)
    "1 - planning": "concept",
    "2 - pre-alpha": "concept",
    "3 - alpha": "wip",
    "4 - beta": "wip",
    "5 - production/stable": "active",
    "6 - mature": "active",
    "7 - inactive": "inactive",
}

LICENSE_MAP = [ #maps some common licenses to SPDX URIs, mapped with a substring match on first come first serve basis
    ("GNU General Public License v3.0 or later", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GNU General Public License v3 or later", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GNU General Public License v3", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GNU General Public License v2.0 or later", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GNU General Public License v2 or later", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GNU General Public License v2", "http://spdx.org/licenses/GPL-2.0-only"),
    ("GNU Affero General Public License v3.0 or later", "http://spdx.org/licenses/AGPL-3.0-or-later"),
    ("GNU Affero General Public License v3 or later", "http://spdx.org/licenses/AGPL-3.0-or-later"),
    ("GNU Affero General Public License", "http://spdx.org/licenses/AGPL-3.0-only"),
    ("GNU Lesser General Public License v3.0 or later", "http://spdx.org/licenses/LGPL-3.0-or-later"),
    ("GNU Lesser General Public License v3", "http://spdx.org/licenses/LGPL-3.0-only"),
    ("GNU Lesser General Public License v2.1 or later", "http://spdx.org/licenses/LGPL-2.1-or-later"),
    ("GNU Lesser General Public License v2.1", "http://spdx.org/licenses/LGPL-2.1-only"),
    ("GNU Lesser General Public License v2 or later", "http://spdx.org/licenses/LGPL-2.0-or-later"),
    ("GNU Lesser General Public License v2", "http://spdx.org/licenses/LGPL-2.0-only"),
    ("Mozilla Public License 1.1", "http://spdx.org/licenses/MPL-1.1"),
    ("Mozilla Public License 1", "http://spdx.org/licenses/MPL-1.0"),
    ("Mozilla Public License", "http://spdx.org/licenses/MPL-2.0"),
    ("European Union Public License 1.1", "http://spdx.org/licenses/EUPL-1.1"),
    ("European Union Public License", "http://spdx.org/licenses/EUPL-1.2"),
    ("Eclipse Public License 1", "http://spdx.org/licenses/EPL-1.0"),
    ("Eclipse Public License", "http://spdx.org/licenses/EPL-2.0"),
    ("Common Public Attribution License", "http://spdx.org/licenses/CPAL-1.0"),
    ("Apache License 2", "http://spdx.org/licenses/Apache-2.0"),
    ("Apache License", "http://spdx.org/licenses/Apache-1.1"),
    ("Apache-2.0", "http://spdx.org/licenses/Apache-2.0"),
    ("Apache-1.1", "http://spdx.org/licenses/Apache-1.1"),
    ("Apache", "http://spdx.org/licenses/Apache-2.0"), #ambiguous, assume apache 2.0
    ("AGPL-3.0-or-later", "http://spdx.org/licenses/AGPL-3.0-or-later"),
    ("AGPL-3.0-only", "http://spdx.org/licenses/AGPL-3.0-only"),
    ("GPL-3.0-or-later", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GPL-3.0-only", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GPLv3+", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GPLv3", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GPL3+", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GPL3", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GPL-2.0-or-later", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GPL-2.0-only", "http://spdx.org/licenses/GPL-2.0-only"),
    ("GPLv2+", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GPLv2", "http://spdx.org/licenses/GPL-2.0-only"),
    ("GPL3+", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GPL3", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GPL2+", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GPL2", "http://spdx.org/licenses/GPL-2.0-only"),
    ("GPL", "http://spdx.org/licenses/GPL-2.0-or-later"), #rather ambiguous, assuming all that could apply
    ("BSD-3-Clause", "http://spdx.org/licenses/BSD-3-Clause"),
    ("BSD-2-Clause", "http://spdx.org/licenses/BSD-2-Clause"),
    ("Simplified BSD", "http://spdx.org/licenses/BSD-2-Clause"),
    ("FreeBSD", "http://spdx.org/licenses/BSD-2-Clause"),
    ("BSD License", "http://spdx.org/licenses/BSD-3-Clause"), #may be ambiguous, better be as restrictive
    ("BSD", "http://spdx.org/licenses/BSD-3-Clause"), #may be ambiguous, better be as restrictive
    ("MIT No Attribution", "http://spdx.org/licenses/MIT-0"),
    ("MIT", "http://spdx.org/licenses/MIT"),
    ("Creative Commons Attribution Share Alike 4.0 International", "http://spdx.org/licenses/CC-BY-SA-4.0"), #not designed for software, not OSI-approved
    ("CC-BY-SA-4.0", "http://spdx.org/licenses/CC-BY-SA-4.0"), #not designed for software, not OSI-approved
]

class AttribDict(dict):
    """Simple dictionary that is addressable via attributes"""
    def __init__(self, d):
        self.__dict__ = d

    def __getattr__(self, key):
        if key in self:
            return self[key]
        return None



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


def readcrosswalk(sourcekeys=(CWKey.PYPI,CWKey.DEBIAN)):
    """Read the crosswalk.csv as provided by codemeta into memory"""
    #pylint: disable=W0621
    crosswalk = defaultdict(dict)
    #pip may output things differently than recorded in distutils/setup.py, so we register some aliases:
    crosswalk[CWKey.PYPI]["home-page"] = "url"
    crosswalk[CWKey.PYPI]["summary"] = "description"
    props = {}
    crosswalkfile = os.path.join(os.path.dirname(__file__), 'schema','crosswalk.csv')
    with open(crosswalkfile, 'r', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            props[row[CWKey.PROP]] = {"PARENT": row[CWKey.PARENT], "TYPE": row[CWKey.TYPE], "DESCRIPTION": row[CWKey.DESCRIPTION] }
            for sourcekey in sourcekeys:
                if row[sourcekey]:
                    crosswalk[sourcekey][row[sourcekey].lower()] = row[CWKey.PROP]

    return props, crosswalk


def license_to_spdx(value: Union[str,list], args: AttribDict) -> str:
    """Attempts to converts a license name or acronym to a full SPDX URI (https://spdx.org/licenses/)"""
    if isinstance(value, list):
        return [ license_to_spdx(x, args) for x in value ]
    if not args.with_spdx: return value
    if value.startswith("http://spdx.org") or value.startswith("https://spdx.org"):
        #we're already good, nothing to do
        return value
    for substr, license_uri in LICENSE_MAP:
        if value.find(substr) != -1:
            return license_uri
    return value

def detect_list(value: Union[list,tuple,set,str]) -> Union[list,str]:
    """Tries to see if the value is a list (string of comma separated items) and then returns a list"""
    if isinstance(value, (list,tuple)):
        return value
    if isinstance(value, str) and value.count(',') >= 1:
        return [ x.strip() for x in value.split(",") ]
    return value

#pylint: disable=W0621
def parsecodemeta(file_descriptor: IO, args: AttribDict) -> dict:
    data = json.load(file_descriptor)
    for key, value in data.items():
        if key == "developmentStatus":
            if args.with_repostatus and value.strip().lower() in REPOSTATUS:
                #map to repostatus vocabulary
                data[key] = "https://www.repostatus.org/#" + REPOSTATUS[value.strip().lower()]
        elif key == "license":
            data[key] = license_to_spdx(value, args)
    return data

#pylint: disable=W0621
def parsepython(data, packagename: str, crosswalk, args: AttribDict):
    """Parses python package metadata and converts it to codemeta"""
    if crosswalk is None:
        _, crosswalk = readcrosswalk((CWKey.PYPI,))
    authorindex = []
    data["provider"] = PROVIDER_PYPI
    if args.exactplatformversion:
        data["runtimePlatform"] =  "Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro)
    else:
        data["runtimePlatform"] =  "Python 3"
    if args.with_entrypoints and not 'entryPoints' in data:
        #not in official specification!!!
        data['entryPoints'] = []
    if args.with_stypes and not 'targetProduct' in data:
        #not in official specification!!!
        data['targetProduct'] = []
    try:
        pkg = importlib_metadata.distribution(packagename)
    except importlib_metadata.PackageNotFoundError:
        #fallback if package is not installed but in local directory:
        context = importlib.metadata.DistributionFinder.Context(name=packagename,path=".")
        try:
            pkg = next(importlib_metadata.MetadataPathFinder().find_distributions(context))
        except StopIteration:
            print(f"No such python package: {packagename}",file=sys.stderr)
            sys.exit(4)
    print(f"Found metadata in {pkg._path}",file=sys.stderr) #pylint: disable=W0212
    for key, value in pkg.metadata.items():
        queue = [] #queue of key, valuepairs to add
        if key == "Classifier":
            fields = [ x.strip() for x in value.strip().split('::') ]
            pipkey = "classifiers['" + fields[0] + "']"
            pipkey = pipkey.lower()
            if pipkey in crosswalk[CWKey.PYPI]:
                key = crosswalk[CWKey.PYPI][pipkey]
                det = " :: " if key != "programmingLanguage" else " "
                value = det.join(fields[1:])
                if key == "developmentStatus":
                    if args.with_repostatus and value.strip().lower() in REPOSTATUS:
                        #map to repostatus vocabulary
                        value = "https://www.repostatus.org/#" + REPOSTATUS[value.strip().lower()]

                elif key == "license":
                    value = license_to_spdx(value, args)
                elif key == "applicationCategory":
                    value = fields[1]
                    if len(fields) > 2:
                        queue.append(("applicationSubCategory","/".join(fields[1:])))
                queue.insert(0, (key, value))
            elif fields[0].lower() in crosswalk[CWKey.PYPI]:
                key = crosswalk[CWKey.PYPI][fields[0].lower()]
                det = " :: " if key != "programmingLanguage" else " "
                value = det.join(fields[1:])
                if key == "license":
                    value = license_to_spdx(value, args)
                queue.append((key,value))
            elif fields[0] == "Intended Audience":
                if not any(( isinstance(a, dict) and 'audienceType' in a and a['audienceType'] == " :: ".join(fields[1:]) for a in data.get("audience",[]) )): #prevent duplicates
                    queue.append(("audience", {
                        "@type": "Audience",
                        "audienceType": " :: ".join(fields[1:])
                    }))
            else:
                print("NOTICE: Classifier "  + fields[0] + " has no translation",file=sys.stderr)
        else:
            if key == "Author":
                if args.single_author:
                    names = [value.strip()]
                else:
                    names = value.strip().split(",")
                for name in names:
                    humanname = HumanName(name.strip())
                    lastname = " ".join((humanname.middle, humanname.last)).strip()
                    found = False
                    for i, a in enumerate(data.get("author",[])):
                        if a['givenName'] == humanname.first and a['familyName'] == lastname:
                            authorindex.append(i)
                            found = True
                            break
                    if not found:
                        authorindex.append(len(data.get("author",[])))
                        queue.append(("author",
                            {"@type":"Person", "givenName": humanname.first, "familyName": lastname }
                        ))
                        if args.with_orcid:
                            queue[-1][1]["@id"] = "https://orcid.org/EDIT_ME!"
            elif key == "Author-email":
                if "author" in data:
                    if args.single_author:
                        data["author"][-1]["email"] = value
                    else:
                        mails = value.split(",")
                        if len(mails) == len(authorindex):
                            for i, mail in zip(authorindex, mails):
                                if isinstance(data['author'], dict) and i == 0:
                                    data["author"]["email"] = mail.strip()
                                    data["author"] = [data["author"]]
                                else:
                                    data["author"][i]["email"] = mail.strip()
                        else:
                            print("WARNING: Unable to unambiguously assign e-mail addresses to multiple authors",file=sys.stderr)
                else:
                    print("WARNING: No author provided, unable to attach author e-mail",file=sys.stderr)
            elif key == "Requires-Dist":
                for dependency in splitdependencies(value):
                    if dependency.find("extra =") != -1 and args.no_extras:
                        print("Skipping extra dependency: ",dependency,file=sys.stderr)
                        continue
                    dependency, depversion = parsedependency(dependency.strip())
                    if dependency and not any(( 'identifier' in d and d['identifier'] == dependency for d in data.get('softwareRequirements',[]) if isinstance(d,dict) )):
                        queue.append(('softwareRequirements',{
                            "@type": "SoftwareApplication",
                            "identifier": dependency,
                            "name": dependency,
                            "provider": PROVIDER_PYPI,
                            "runtimePlatform": data["runtimePlatform"]
                        }))
                        if depversion:
                            queue[-1][1]['version'] = depversion
            elif key == "Requires-External":
                for dependency in value.split(','):
                    dependency = dependency.strip()
                    if dependency and not any(( 'identifier' in d and d['identifier'] == dependency for d in data.get('softwareRequirements',[]) if isinstance(d,dict) )):
                        queue.append(('softwareRequirements', {
                            "@type": "SoftwareApplication",
                            "identifier": dependency,
                            "name": dependency,
                        }))
            elif key.lower() in crosswalk[CWKey.PYPI]:
                if key.lower() == "license":
                    value = license_to_spdx(value, args)
                elif key.lower() == "keywords":
                    value = detect_list(value)
                queue.append((crosswalk[CWKey.PYPI][key.lower()], value))
                if key == "Name" and ('identifier' not in data or data['identifier'] in ("unknown","")):
                    queue.append(("identifier",value))
            else:
                print("WARNING: No translation for distutils key " + key,file=sys.stderr)

        if queue:
            for key, value in queue:
                if key in data:
                    if isinstance(data[key],str) and data[key] != value:
                        data[key] = [ data[key], value ]
                    elif isinstance(data[key],list):
                        if value not in data[key]:
                            data[key].append(value)
                else:
                    data[key] = value

    if args.with_stypes:
        for rawentrypoint in pkg.entry_points:
            if rawentrypoint.group == "console_scripts":
                interfacetype = "CommandLineApplication"
            elif rawentrypoint.group == "gui_scripts":
                interfacetype = "DesktopApplication"
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
            targetproduct = {
                "@type": interfacetype,
                "name": rawentrypoint.name,
                "executableName": rawentrypoint.name,
                "runtimePlatform": data['runtimePlatform']
            }
            if description:
                targetproduct['description'] = description
            if targetproduct not in data['targetProduct']:
                data['targetProduct'].append(targetproduct)
        if not data['targetProduct'] or ('applicationCategory' in data and isinstance(data['applicationCategory'], (list,tuple)) and 'libraries' in ( x.lower() for x in data['applicationCategory'] if isinstance(x,str)) ):
            #no entry points defined (or explicitly marked as library), assume this is a library
            data['targetProduct'].append({
                "@type": "SoftwareLibrary",
                "name": pkg.name,
                "executableName": re.sub(r"[-_.]+", "-", pkg.name).lower(), #see https://python.github.io/peps/pep-0503/
                "runtimePlatform": data['runtimePlatform']
            })
    if args.with_entrypoints:
        #legacy!
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
        if not data['entryPoints'] or ('applicationCategory' in data and isinstance(data['applicationCategory'], (list,tuple)) and 'libraries' in ( x.lower() for x in data['applicationCategory'] if isinstance(x,str)) ):
            #no entry points defined, assume this is a library
            data['interfaceType'] = "LIB"
    return data

def splitdependencies(s: str):
    """Split a string of multiple (python) dependencies"""
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


def parsedependency(s: str):
    """Parses a pip dependency specification, returning the identifier, version"""
    identifier = s.split(" ")[0]
    begin = s.find("(")
    if begin != -1:
        end = s.find(")")
        version = s[begin+1:end].strip().replace("==","")
    else:
        version = None
    return identifier, version


def parseapt(data, lines, crosswalk, args: AttribDict):
    """Parses apt show output and converts to codemeta"""
    if crosswalk is None:
        _, crosswalk = readcrosswalk((CWKey.DEBIAN,))
    provider = PROVIDER_DEBIAN
    description = ""
    parsedescription = False
    if args.with_entrypoints and not 'entryPoints' in data:
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
                        if not 'softwareRequirements' in data:
                            data['softwareRequirements'] = []
                        data['softwareRequirements'].append({
                            "@type": "SoftwareApplication",
                            "identifier": dependency,
                            "name": dependency,
                        })
            elif key == "Section":
                if "libs" in value or "libraries" in value:
                    if args.with_entrypoints: data['interfaceType'] = "LIB"
                    data['audience'] = "Developers"
                elif "utils" in value or "text" in value:
                    if args.with_entrypoints: data['interfaceType'] = "CLI"
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
            elif key.lower() in crosswalk[CWKey.DEBIAN]:
                data[crosswalk[CWKey.DEBIAN][key.lower()]] = value
                if key == "Package":
                    data["identifier"] = value
                    data["name"] = value
            else:
                print("WARNING: No translation for APT key " + key,file=sys.stderr)
    if description:
        data["description"] = description
    return data


def clean(data: dict) -> dict:
    """Purge empty values, lowercase identifier"""
    purgekeys = []
    for k,v in data.items():
        if v == "" or v is None or (isinstance(v,(tuple, list)) and len(v) == 0):
            purgekeys.append(k)
        elif isinstance(v, (dict, OrderedDict)):
            clean(v)
        elif isinstance(v, (tuple, list)):
            data[k] = [ clean(x) if isinstance(x, (dict,OrderedDict)) else x for x in v ]
    for k in purgekeys:
        del data[k]
    if 'identifier' in data and isinstance(data['identifier'], str):
        data['identifier'] = data['identifier'].lower()
    return data

def resolve(data: dict, idmap=None) -> dict:
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

def update(data: dict, newdata: dict):
    """Recursive update a dictionary, adds values whenever possible instead of replacing"""
    for key, value in newdata.items():
        if key in data:
            if isinstance(value, dict):
                update(data[key], value)
            elif isinstance(value, (list,tuple)):
                for x in value:
                    if isinstance(data[key], dict ):
                        data[key] = [ data[key], x ]
                    elif isinstance(data[key], (list,tuple)):
                        if x not in data[key]:
                            if isinstance(data[key], list):
                                data[key].append(x)
                    elif isinstance(data[key], (str,float,int,bool) ):
                        data[key] = [ data[key], x ]
            else:
                data[key] = value
        else:
            data[key] = value

def getstream(source: str):
    """Opens an file (or use - for stdin) and returns the file descriptor"""
    if source == '-':
        return sys.stdin
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


props, crosswalk = readcrosswalk()

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
    print(args,file=sys.stderr)
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
            update(data, parsepython(data, source, crosswalk, args))
        elif inputtype == "pip":
            print("Pip output parsing is obsolete since codemetapy 0.3.0, please use input type 'python' instead",file=sys.stderr)
            sys.exit(2)
        elif inputtype in ("apt","debian","deb"):
            aptlines = getstream(source).read().split("\n")
            update(data, parseapt(data, aptlines, crosswalk, args))
        elif inputtype == "json":
            print(f"Parsing json file: {source}",file=sys.stderr)
            update(data, parsecodemeta(getstream(source), args))

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
