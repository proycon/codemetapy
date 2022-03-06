import sys
import json
from rdflib import Graph, Namespace, URIRef, BNode, Literal
from rdflib.namespace import RDF
from typing import Union, IO
from collections import OrderedDict
from nameparser import HumanName


PROGLANG_PYTHON = {
    "@type": "ComputerLanguage",
    "name": "Python",
    "version": str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro),
    "url": "https://www.python.org",
}

#A dummy namespace that will be used if the RDF parser expects a namespace but can't find any
DUMMY_NS = "http://unknown/"

SDO = Namespace("http://schema.org/")

CODEMETA = Namespace("https://codemeta.github.io/terms/")
#Custom extensions not in codemeta/schema.org (yet), they are proposed in https://github.com/codemeta/codemeta/issues/271 and supersede the above one
SOFTWARETYPES = Namespace("https://w3id.org/software-types#")

SCHEMA_SOURCE = "https://raw.githubusercontent.com/schemaorg/schemaorg/main/data/releases/13.0/schemaorgcontext.jsonld" #schema.org itself doesn't seem to do proper content negotation (or rdflib chokes on it), so we grab the 'latest' release from github instead
CODEMETA_SOURCE = "https://raw.githubusercontent.com/codemeta/codemeta/2.0/codemeta.jsonld"
#^-- target of https://doi.org/10.5063/schema/codemeta-2.0, prefer github because that at least serves things reliably for both rdflib and the JsonLD playground

COMMON_SOURCEREPOS = ["https://github.com/","http://github.com","https://gitlab.com/","http://gitlab.com/","https://codeberg.org/","http://codeberg.org", "https://git.sr.ht/", "https://bitbucket.com/"]

CONTEXT = [
    CODEMETA_SOURCE, #redirects to https://raw.githubusercontent.com/codemeta/codemeta/2.0/codemeta.jsonld
    SCHEMA_SOURCE, #schema.org doesn't have proper content negotiation so we add this explicitly
    str(SOFTWARETYPES),
]


ENTRYPOINT_CONTEXT = { #these are all custom extensions not in codemeta (yet), they are proposed in https://github.com/codemeta/codemeta/issues/183 but are obsolete in favour of the newer software types (see next declaration)
    "entryPoints": { "@reverse": "schema:actionApplication" },
    "interfaceType": { "@id": "codemeta:interfaceType" }, #Type of the entrypoint's interface (e.g CLI, GUI, WUI, TUI, REST, SOAP, XMLRPC, LIB)
    "specification": { "@id": "codemeta:specification" , "@type":"@id"}, #A technical specification of the interface
    "mediatorApplication": {"@id": "codemeta:mediatorApplication", "@type":"@id" } #auxiliary software that provided/enabled this entrypoint
}


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


def init_graph():
    """Initializes the RDF graph, the context and the prefixes"""
    #context = Context(CONTEXT)
    g = Graph()
    g.bind('schema', SDO)
    g.bind('codemeta', CODEMETA)
    g.bind('stype', SOFTWARETYPES)

    return g

class AttribDict(dict):
    """Simple dictionary that is addressable via attributes"""
    def __init__(self, d):
        self.__dict__ = d

    def __getattr__(self, key):
        if key in self:
            return self[key]
        return None

def license_to_spdx(value: Union[str,list,tuple]) -> Union[str,list]:
    """Attempts to converts a license name or acronym to a full SPDX URI (https://spdx.org/licenses/)"""
    if isinstance(value, (list,tuple)):
        return [ license_to_spdx(x) for x in value ]
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


def add_triple(g: Graph, res: Union[URIRef, BNode],key, value, args: AttribDict) -> bool:
    """Maps a key/value pair to an actual triple"""
    if key == "developmentStatus":
        if value.strip().lower() in REPOSTATUS:
            #map to repostatus vocabulary
            value = "https://www.repostatus.org/#" + REPOSTATUS[value.strip().lower()]
            g.add((res, CODEMETA.developmentStatus, URIRef(value)))
        else:
            g.add((res, CODEMETA.developmentStatus, Literal(value)))
    elif key == "license":
        value = license_to_spdx(value)
        if value.find('spdx') != -1:
            g.add((res, SDO.license, URIRef(value)))
        else:
            g.add((res, SDO.license, Literal(value)))
    elif key == "applicationCategory":
        g.add((res, SDO.applicationCategory, Literal(value)))
    elif key == "audience":
        audience = BNode()
        g.add((audience, RDF.type, SDO.Audience))
        g.add((audience, SDO.audienceType, Literal(value) ))
        g.add((res, SDO.audience,audience ))
    elif key == "keywords":
        value = detect_list(value)
        if isinstance(value, list):
            for item in value:
                g.add((res, SDO.keywords,Literal(item)))
        else:
            g.add((res, SDO.keywords,Literal(value)))
    elif hasattr(SDO, key):
        g.add((res, getattr(SDO, key), Literal(value)))
    elif hasattr(CODEMETA, key):
        g.add((res, getattr(CODEMETA, key), Literal(value)))
    else:
        print(f"NOTICE: Don't know how to handle key '{key}' with value '{value}'... ignoring...",file=sys.stderr)
        return False
    return True

def add_authors(g: Graph, res: Union[URIRef, BNode], value, args: AttribDict, mailvalue = ""):
    """Parse and add authors and their e-mail addresses"""
    if args.single_author:
        names = [value.strip()]
        mails = [mailvalue]
    else:
        names = value.strip().split(",")
        mails = mailvalue.strip().split(",")

    for i, name in enumerate(names):
        if len(mails) > i:
            mail = mails[i]
        else:
            mail = None
        humanname = HumanName(name.strip())
        lastname = " ".join((humanname.middle, humanname.last)).strip()

        author = BNode()
        g.add((author, RDF.type, SDO.Person))
        g.add((author, SDO.givenName, Literal(humanname.first)))
        g.add((author, SDO.familyName, Literal(lastname)))
        if mail:
            g.add((author, SDO.email, Literal(mail)))
        g.add((res, SDO.author, author))

def reconcile(g: Graph, res: URIRef, args: AttribDict):
    """Reconcile possible conflicts in the graph and issue warnings"""
    IDENTIFIER = g.value(res, SDO.identifier)
    if not IDENTIFIER: IDENTIFIER = str(res)
    HEAD = f"[CODEMETA VALIDATION ({IDENTIFIER})]"

    if (res, SDO.codeRepository, None) not in g:
        print(f"{HEAD} codeRepository not set",file=sys.stderr)
    if (res, SDO.author, None) not in g:
        print(f"{HEAD} author not set",file=sys.stderr)
    if (res, SDO.license, None) not in g:
        print(f"{HEAD} license not set",file=sys.stderr)

    status = g.value(res, CODEMETA.developmentStatus)
    if status and status.startswith(DUMMY_NS):
        status = status[len(DUMMY_NS):]
        if status.lower() in REPOSTATUS.values():
            print(f"{HEAD} automatically converting status to repostatus URI",file=sys.stderr)
            g.set((res, CODEMETA.developmentStatus, URIRef("https://www.repostatus.org/#" + status.lower())))
        else:
            g.set((res, CODEMETA.developmentStatus, Literal(status)))

    license = g.value(res, SDO.license)
    if license and license.startswith(DUMMY_NS):
        license = license_to_spdx(license[len(DUMMY_NS):])
        if license.startswith("http"):
            print(f"{HEAD} automatically converting license to spdx URI",file=sys.stderr)
            g.set((res, SDO.license, URIRef(license)))
        else:
            g.set((res, SDO.license, Literal(license)))

#        if key == "developmentStatus":
#            if args.with_repostatus and value.strip().lower() in REPOSTATUS:
#                #map to repostatus vocabulary
#                data[key] = "https://www.repostatus.org/#" + REPOSTATUS[value.strip().lower()]
#        elif key == "license":
#            data[key] = license_to_spdx(value, args)

def getstream(source: str):
    """Opens an file (or use - for stdin) and returns the file descriptor"""
    if source == '-':
        return sys.stdin
    return open(source,'r',encoding='utf-8')
