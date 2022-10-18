import sys
import os
import json
import requests
import random
import re
from collections import Counter
from tempfile import gettempdir
from rdflib import Graph, Namespace, URIRef, BNode, Literal
from rdflib.namespace import RDF, RDFS, SKOS
from rdflib.compare import graph_diff
from typing import Union, IO, Sequence, Optional,Generator
from collections import OrderedDict
from nameparser import HumanName


PROGLANG_PYTHON = {
    "@type": "ComputerLanguage",
    "name": "Python",
    "version": str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro),
    "url": "https://www.python.org",
}

SDO = Namespace("http://schema.org/")

CODEMETA = Namespace("https://codemeta.github.io/terms/")
#Custom extensions not in codemeta/schema.org (yet), they are initially proposed in https://github.com/codemeta/codemeta/issues/271
SOFTWARETYPES = Namespace("https://w3id.org/software-types#") #See https://github.com/SoftwareUnderstanding/software_types
SOFTWAREIODATA = Namespace("https://w3id.org/software-iodata#") #See https://github.com/SoftwareUnderstanding/software-iodata
TRL = Namespace("https://w3id.org/research-technology-readiness-levels")

REPOSTATUS = Namespace("https://www.repostatus.org/#")

SPDX = Namespace("http://spdx.org/licences/")

ORCID = Namespace("http://orcid.org/")

CODEMETAPY = Namespace("https://github.com/proycon/codemetapy/") #An extra internal namespace, usually not used for any serialisations

SCHEMA_SOURCE = "https://schema.org" #even though URL is https:// the RDF IRIs are all http://!
CODEMETA_SOURCE = "https://doi.org/10.5063/schema/codemeta-2.0"
STYPE_SOURCE = "https://w3id.org/software-types"
IODATA_SOURCE = "https://w3id.org/software-iodata"

REPOSTATUS_SOURCE = "https://raw.githubusercontent.com/jantman/repostatus.org/master/badges/latest/ontology.jsonld"

TMPDIR  = os.environ.get("TMPDIR",gettempdir())

SCHEMA_LOCAL_SOURCE = "file://" + os.path.join(TMPDIR, "schemaorgcontext.jsonld")
CODEMETA_LOCAL_SOURCE = "file://" + os.path.join(TMPDIR, "codemeta.jsonld")
STYPE_LOCAL_SOURCE = "file://" + os.path.join(TMPDIR, "stype.jsonld")
IODATA_LOCAL_SOURCE = "file://" + os.path.join(TMPDIR, "iodata.jsonld")
REPOSTATUS_LOCAL_SOURCE = "file://" + os.path.join(TMPDIR, "repostatus.jsonld")

COMMON_SOURCEREPOS = ["https://github.com/","http://github.com","https://gitlab.com/","http://gitlab.com/","https://codeberg.org/","http://codeberg.org", "https://git.sr.ht/", "https://bitbucket.org/", "https://bitbucket.com/"]


ENTRYPOINT_CONTEXT = { #these are all custom extensions not in codemeta (yet), they were proposed in https://github.com/codemeta/codemeta/issues/183 but are obsolete in favour of the newer software types
    "entryPoints": { "@reverse": "schema:actionApplication" },
    "interfaceType": { "@id": "codemeta:interfaceType" }, #Type of the entrypoint's interface (e.g CLI, GUI, WUI, TUI, REST, SOAP, XMLRPC, LIB)
    "specification": { "@id": "codemeta:specification" , "@type":"@id"}, #A technical specification of the interface
    "mediatorApplication": {"@id": "codemeta:mediatorApplication", "@type":"@id" } #auxiliary software that provided/enabled this entrypoint
}


DEVIANT_CONTEXT = { #Extra *internal* context that enforces some implementation-specific differences and solves conflicts, this context is ALWAYS assumed on parsing, and ALWAYS passed to the serialiser (but NEVER propagated to final output, it is stripped again on final context rewrite) 
    "softwareRequirements":{ "@id": "schema:softwareRequirements","@type":"@id"}, #schema does not add @type=@id, codemeta does....   
    "referencePublication":{ "@id": "codemeta:referencePublication","@type":"@id"}, #schema does not add @type=@id, codemeta does....
    "author": {"@id": "schema:author", "@container": "@list" },  #we treat authors as an ordered list (rdf:list), even though schema.org does not (this is also recommended by science-on-schema.org)
    "contributor": {"@id": "schema:contributor", "@container": "@list" },  #we treat contributors as an ordered list (rdf:list), even though schema.org does not (this is also recommended by science-on-schema.org)
}


REPOSTATUS_MAP = { #maps Python development status to repostatus.org vocabulary (the mapping is debatable)
    "1 - planning": "concept",
    "2 - pre-alpha": "concept",
    "3 - alpha": "wip",
    "4 - beta": "wip", #note, if --released is set this maps to "active" instead
    "5 - production/stable": "active", #reasonable guess, but being production/stable doesn't guarantee repo is active (might be inactive)
    "6 - mature": "active", #reasonable guess, but being mature doesn't guarantee repo is active (might be inactive)
    "7 - inactive": "unsupported",
}

TRL_MAP = { #maps Python development status to technology readiness levels (the mapping is debatable)
    "1 - planning": TRL.Stage1Planning,
    "2 - pre-alpha": TRL.Stage1Planning, #we can't really distinguish between the TRL levels in stage 1
    "3 - alpha": TRL.Stage2ProofOfConcept,
    "4 - beta": TRL.Stage3Experimental,
    "5 - production/stable": TRL.Level8Complete,
    "6 - mature": TRL.Level9Proven
    #7 - inactive does not map to a TRL
}

LICENSE_MAP = [ #maps some common licenses to SPDX URIs, mapped with a substring match on first come first serve basis
    ("GNU General Public License v3.0 or later", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GNU General Public License v3 or later", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GNU General Public License v3", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GNU General Public License 3.0 or later", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GNU General Public License 3 or later", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GNU General Public License 3", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GNU General Public License v2.0 or later", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GNU General Public License v2 or later", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GNU General Public License v2", "http://spdx.org/licenses/GPL-2.0-only"),
    ("GNU General Public License 2.0 or later", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GNU General Public License 2 or later", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GNU General Public License 2", "http://spdx.org/licenses/GPL-2.0-only"),
    ("GNU Affero General Public License v3.0 or later", "http://spdx.org/licenses/AGPL-3.0-or-later"),
    ("GNU Affero General Public License v3 or later", "http://spdx.org/licenses/AGPL-3.0-or-later"),
    ("GNU Affero General Public License v3", "http://spdx.org/licenses/AGPL-3.0-only"),
    ("GNU Affero General Public License", "http://spdx.org/licenses/AGPL-3.0-only"),
    ("GNU Lesser General Public License v3.0 or later", "http://spdx.org/licenses/LGPL-3.0-or-later"),
    ("GNU Lesser General Public License v3", "http://spdx.org/licenses/LGPL-3.0-only"),
    ("GNU Lesser General Public License v2.1 or later", "http://spdx.org/licenses/LGPL-2.1-or-later"),
    ("GNU Lesser General Public License v2.1", "http://spdx.org/licenses/LGPL-2.1-only"),
    ("GNU Lesser General Public License 2.1", "http://spdx.org/licenses/LGPL-2.1-only"),
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
    ("Apache License, Version 2.0", "http://spdx.org/licenses/Apache-2.0"),
    ("Apache License", "http://spdx.org/licenses/Apache-1.1"),
    ("https://www.apache.org/licenses/LICENSE-2.0.txt", "http://spdx.org/licenses/Apache-2.0"),
    ("Apache-2.0", "http://spdx.org/licenses/Apache-2.0"),
    ("Apache-1.1", "http://spdx.org/licenses/Apache-1.1"),
    ("Apache", "http://spdx.org/licenses/Apache-2.0"), #ambiguous, assume apache 2.0
    ("AGPL-3.0-or-later", "http://spdx.org/licenses/AGPL-3.0-or-later"),
    ("AGPL-3.0-only", "http://spdx.org/licenses/AGPL-3.0-only"),
    ("AGPL-3.0", "http://spdx.org/licenses/AGPL-3.0-only"),
    ("GPL-3.0-or-later", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GPL-3.0-only", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GPL-3.0", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GPLv3+", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GPLv3", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GPL3+", "http://spdx.org/licenses/GPL-3.0-or-later"),
    ("GPL3", "http://spdx.org/licenses/GPL-3.0-only"),
    ("GPL-2.0-or-later", "http://spdx.org/licenses/GPL-2.0-or-later"),
    ("GPL-2.0-only", "http://spdx.org/licenses/GPL-2.0-only"),
    ("GPL-2.0", "http://spdx.org/licenses/GPL-2.0-only"),
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

#Maps invalid characters in URIs to something sensible (especially characters from dependency version qualifiers)
IDENTIFIER_MAP = [
   ('>=', '-ge-'),
   ('~=', '-ge-'),
   ('>=', '-le-'),
   ('==', '-eq-'),
   ('!=', '-ne-'),
   ('^', '-ge-'), #used in npm version
   ('>', '-gt-'),
   ('<', '-lt-'),
   ('=', '-eq-'),
   (' ', '-'),
   ('&', '-',),
   ('/', '-',),
   ('+', '-',),
   (':', '-',),
   (';', '-'),
   (',',''),
   ('----', '-'),
   ('---', '-'),
   ('--', '-'),
]

#keywords that may be indicative of a certain interface type
INTERFACE_CLUES = [ #order matters, only one is picked
   ("web application", SDO.WebApplication),
   ("webapp", SDO.WebApplication),
   ("web-based", SDO.WebApplication),
   ("website", SDO.WebSite),
   ("webpage", SDO.WebPage),
   ("web service", SDO.WebAPI),
   ("webservice", SDO.WebAPI),
   ("restful", SDO.WebAPI),
   ("rest service", SDO.WebAPI),
   ("web api", SDO.WebAPI),
   ("library", SOFTWARETYPES.SoftwareLibrary),
   ("module", SOFTWARETYPES.SoftwareLibrary),
   ("command-line", SOFTWARETYPES.CommandLineApplication),
   ("command line", SOFTWARETYPES.CommandLineApplication),
   ("commandline", SOFTWARETYPES.CommandLineApplication),
   ("desktop application", SOFTWARETYPES.DesktopApplication),
   ("windows application", SOFTWARETYPES.DesktopApplication),
   ("windows software", SOFTWARETYPES.DesktopApplication),
   ("mac application", SOFTWARETYPES.DesktopApplication),
   ("graphical user-interface", SOFTWARETYPES.DesktopApplication),
   ("graphical user interface", SOFTWARETYPES.DesktopApplication),
   ("gnome", SOFTWARETYPES.DesktopApplication),
   ("gtk+", SOFTWARETYPES.DesktopApplication),
   (" qt ", SOFTWARETYPES.DesktopApplication),
   (" gui", SOFTWARETYPES.DesktopApplication),
   ("desktop gui", SOFTWARETYPES.DesktopApplication),
   ("android app", SOFTWARETYPES.MobileApplication),
   ("ios app", SOFTWARETYPES.MobileApplication),
   ("mobile app", SOFTWARETYPES.MobileApplication),
   ("in a terminal", SOFTWARETYPES.CommandLineApplication),
   ("in the terminal", SOFTWARETYPES.CommandLineApplication),
   ("from the terminal", SOFTWARETYPES.CommandLineApplication),
   ("from a terminal", SOFTWARETYPES.CommandLineApplication),
   (" api ", SOFTWARETYPES.SoftwareLibrary)
]

INTERFACE_CLUES_DEPS = {
    "django": SOFTWARETYPES.WebApplication,
    "flask": SOFTWARETYPES.WebApplication,
    "clam": SOFTWARETYPES.WebApplication,
    "react": SOFTWARETYPES.WebApplication,
    "vue": SOFTWARETYPES.WebApplication,
    "jquery": SOFTWARETYPES.WebApplication,
    "gatsby": SOFTWARETYPES.WebApplication,
    "angular": SOFTWARETYPES.WebApplication,
    "laravel": SOFTWARETYPES.WebApplication,
    "drupal": SOFTWARETYPES.WebApplication,
    "wordpress": SOFTWARETYPES.WebApplication,
    "joomla": SOFTWARETYPES.WebApplication,
    "spring": SOFTWARETYPES.WebApplication,
    "fastapi": SDO.WebAPI, #the distinction webservice/webapplication on the basis of dependencies is fairly ambiguous
    "bottle": SDO.WebAPI,
    "hug": SDO.WebAPI,
    "falcon": SDO.WebAPI,
    "tornado": SDO.WebAPI,
    "cherrypy": SDO.WebAPI,
    "ncurses": SOFTWARETYPES.TerminalApplication,
    "click": SOFTWARETYPES.CommandLineApplication
}



#properties that may only occur once, last one counts
SINGULAR_PROPERTIES = ( SDO.name, SDO.version, SDO.description, SDO.dateCreated, SDO.dateModified, SDO.position )

#these will be treated as ordered lists
ORDEREDLIST_PROPERTIES = ( SDO.author, SDO.contributor )

#properties that should prefer URIRef rather than Literal **if and only if** the value is a URI
PREFER_URIREF_PROPERTIES = (SDO.url, SDO.license, SDO.codeRepository, CODEMETA.developmentStatus, CODEMETA.issueTracker, CODEMETA.contIntegration, CODEMETA.readme, CODEMETA.releaseNotes, SDO.softwareHelp)
PREFER_URIREF_PROPERTIES_SIMPLE = ('url','license', 'issueTracker', 'contIntegration', 'readme', 'releaseNotes', 'softwareHelp', 'developmentStatus', 'applicationCategory')

class AttribDict(dict):
    """Simple dictionary that is addressable via attributes"""
    def __init__(self, d: dict):
        self.__dict__ = d

    def __getattr__(self, key):
        if key in self:
            return self[key]
        return None

def init_context(args: AttribDict):
    """Initialized the context, ensures all context JSONLDs are downloaded and local filesystem references are used instead"""

    sources = [ (CODEMETA_LOCAL_SOURCE, CODEMETA_SOURCE), (SCHEMA_LOCAL_SOURCE, SCHEMA_SOURCE), (STYPE_LOCAL_SOURCE, STYPE_SOURCE), (IODATA_LOCAL_SOURCE, IODATA_SOURCE), (REPOSTATUS_LOCAL_SOURCE, REPOSTATUS_SOURCE) ]
    
    if args.addcontext:
        for remote_url in args.addcontext:
            if not remote_url.startswith("http"):
                raise Exception(f"Explicitly added context (--addcontext) must be a remote URL, got {remote_url} instead")
            local = "file://" + os.path.join(TMPDIR, os.path.basename(remote_url))
            sources.append( (local, remote_url))

    for local, remote in sources:
        localfile = local.replace("file://","")
        if remote in ("http://schema.org", "https://schema.org","http://schema.org/", "https://schema.org/"):
            #schema.org does not do content negotation properly, instead it provides a link via a HEAD request, we don't support this but fake this step manually:
            remote = "https://schema.org/docs/jsonldcontext.json"
        if not os.path.exists(localfile) or args.no_cache:
            print(f"Downloading context from {remote}", file=sys.stderr)
            if remote.find("doi.org") != -1:
                #if we use application/ld+json on doi.org URL we get metadata of the DOI resource itself rather than the jsonld it references (relevant for codemeta)
                accept = "application/json;q=0.9,text/plain;q=0.5"
            else:
                accept = "application/ld+json;q=1.0;application/json;q=0.9,text/plain;q=0.5"
            r = requests.get(remote, headers={ "Accept": accept})
            r.raise_for_status()
            with open(localfile, 'wb') as f:
                f.write(r.content)

    return sources

def bind_graph(g: Graph):
    g.bind('schema', SDO)
    g.bind('codemeta', CODEMETA)
    g.bind('stype', SOFTWARETYPES)
    g.bind('iodata', SOFTWAREIODATA)

def init_graph(args: AttribDict):
    """Initializes the RDF graph, the context and the prefixes"""

    context_sources = init_context(args)

    g = Graph()

    #The context graph loads some additional linked data we may need for interpretation (it is not related to @context!),
    #This data is not propagated to the output graph (g) unless --includecontext is set

    contextgraph = Graph()
    for x in (g, contextgraph):
        bind_graph(x)

    contextgraph.bind('rdfs', RDFS)
    contextgraph.bind('repostatus', REPOSTATUS)
    contextgraph.bind('spdx', SPDX)
    contextgraph.bind('skos', SKOS)
    contextgraph.bind('orcid', ORCID)
    contextgraph.bind('trl', TRL)

    #add license names from our license map (faster/easier than ingesting the json-ld from https://github.com/spdx/license-list-data/)
    for (label, identifier) in LICENSE_MAP:
        license = URIRef(identifier)
        if (license, SDO.name, None) not in contextgraph:
            contextgraph.add((license, SDO.name, Literal(label)))

    #Add labels for software types that are not in the software types extension but in schema.org itself (without needing to parse everythign in schema.org)
    contextgraph.add((SDO.WebApplication, RDFS.label, Literal("Web Application")))
    contextgraph.add((SDO.WebApplication, RDFS.comment, Literal("A software application served as a service over the web with an interface for human end-users")))
    contextgraph.add((SDO.WebAPI, RDFS.label, Literal("Web API")))
    contextgraph.add((SDO.WebApplication, RDFS.comment, Literal("A software application served as a service over the web with an interface for human end-users")))
    contextgraph.add((SDO.MobileApplication, RDFS.label, Literal("Mobile App")))
    contextgraph.add((SDO.MobileApplication, RDFS.comment, Literal("A software application for mobile devices")))
    contextgraph.add((SDO.WebSite, RDFS.label, Literal("Website")))
    contextgraph.add((SDO.WebSite, RDFS.comment, Literal("A set of related web pages")))
    contextgraph.add((SDO.WebPage, RDFS.label, Literal("Webpage")))
    contextgraph.add((SDO.WebPage, RDFS.comment, Literal("A very particular page on the web")))

    for local, _ in context_sources:
        with open(local.replace("file://",""),'rb') as f:
            contextgraph.parse(data=json.load(f), format="json-ld")

    return g, contextgraph


def license_to_spdx(value: Union[str,list,tuple]) -> Union[str,list]:
    """Attempts to converts a license name or acronym to a full SPDX URI (https://spdx.org/licenses/)"""
    if isinstance(value, (list,tuple)):
        return [ license_to_spdx(x) for x in value ]
    if value.startswith("http://spdx.org"):
        #we're already good, nothing to do
        return value
    if value.startswith("https://spdx.org"):
        #we consistently opt for http:// in this implementation
        return value.replace("https://","http://")
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


def value_or_uri(value: str, baseuri: Optional[str]) -> str:
    #some values formally take a URI but may also be given a literal string,
    #if we interpreted the URI locally then this is an indication we
    #want a literatal string instead. Allows for values like developmentStatus: "active"
    if baseuri and value.startswith(baseuri):
        #misinterpreted as a local URI
        return value.split("/")[-1]
    elif value.startswith("/"):
        #misinterpreted as a relative URI
        return value.split("/")[-1]
    return value

def delete_repostatus(g: Graph, res: Union[URIRef, BNode]):
    """Delete any existing developmentStatus repostatus triples before adding a new one (there may be only one)"""
    for _,_,o in g.triples((res, CODEMETA.developmentStatus, None)):
        if str(o).find("repostatus") != -1:
            g.remove((res,CODEMETA.developmentStatus, o))

def add_triple(g: Graph, res: Union[URIRef, BNode],key, value, args: AttribDict, replace=False) -> bool:
    """Maps a key/value pair to an actual triple"""

    if replace or key in ( x.split("/")[-1] for x in SINGULAR_PROPERTIES  ):
        f_add = g.set
    else:
        f_add = g.add
    if key == "developmentStatus":
        f_add = g.add
        value = value_or_uri(value, args.baseuri)
        if value.strip().lower() in REPOSTATUS_MAP.values():
            delete_repostatus(g, res)
            f_add((res, CODEMETA.developmentStatus, getattr(REPOSTATUS, value.strip().lower()) ))
        elif value.strip().lower() in REPOSTATUS_MAP:
            #map to repostatus vocabulary
            repostatus = REPOSTATUS_MAP[value.strip().lower()]
            if args.released and value.strip().lower().find("beta") and repostatus == "wip":
                #beta maps to active if --released is set
                repostatus = "active"
            delete_repostatus(g, res)
            f_add((res, CODEMETA.developmentStatus, getattr(REPOSTATUS, repostatus) ))
        else:
            delete_repostatus(g, res)
            f_add((res, CODEMETA.developmentStatus, Literal(value)))
        if args.trl:
            if value.strip().lower() in TRL_MAP:
                f_add((res, CODEMETA.developmentStatus, TRL_MAP[value.strip().lower()] ))
    elif key == "license": 
        if value == "UNKNOWN":
            #python distutils has a tendency to assign 'UNKNOWN', we don't use this value
            return True
        value = value_or_uri(value, args.baseuri)
        value = license_to_spdx(value)
        if isinstance(value, str):
            listify = lambda x: [x]
        else:
            listify = lambda x: x
        for value in listify(value):
            if value.find('spdx') != -1:
                f_add((res, SDO.license, URIRef(value)))
            else:
                f_add((res, SDO.license, Literal(value)))
    elif key == "applicationCategory":
        f_add((res, SDO.applicationCategory, Literal(value)))
    elif key == "audience":
        audience = URIRef(generate_uri(value, baseuri=args.baseuri, prefix="audience"))
        g.add((audience, RDF.type, SDO.Audience))
        g.add((audience, SDO.audienceType, Literal(value) ))
        f_add((res, SDO.audience,audience ))
    elif key == "keywords":
        value = detect_list(value)
        if isinstance(value, list):
            for item in value:
                g.add((res, SDO.keywords,Literal(item)))
        else:
            f_add((res, SDO.keywords,Literal(value)))
    elif key == "operatingSystem" and isinstance(value, str) and value.upper() in ("POSIX","UNIX"):
        #decompose into some actual operating systems that are easier to understand (Python packages often use POSIX as a group)
        f_add((res, SDO.operatingSystem, Literal("Linux")))
        f_add((res, SDO.operatingSystem, Literal("BSD")))
        f_add((res, SDO.operatingSystem, Literal("macOS")))
    elif hasattr(SDO, key):
        f_add((res, getattr(SDO, key), Literal(value)))
    elif hasattr(CODEMETA, key):
        f_add((res, getattr(CODEMETA, key), Literal(value)))
    else:
        print(f"NOTICE: Don't know how to handle key '{key}' with value '{value}'... ignoring...",file=sys.stderr)
        return False
    return True

def add_authors(g: Graph, res: Union[URIRef, BNode], value, property=SDO.author, single_author = False,  **kwargs):
    """Parse and add authors and their e-mail addresses"""
    if single_author:
        names = [value.strip()]
        mails = [ kwargs.get('mail',"") ]
        urls = [ kwargs.get('url',"") ]
        orgs = [ kwargs.get('organization',"") ]
    else:
        names = value.strip().split(",")
        mails = kwargs.get("mail","").strip().split(",")
        urls = kwargs.get('url',"").strip().split(",")
        orgs = kwargs.get('organization',"").strip().split(",")


    skip_duplicates = kwargs.get('skip_duplicates')

    authors = []
    for i, name in enumerate(names):
        if len(mails) > i:
            mail = mails[i]
        else:
            mail = None
        if len(urls) > i:
            url = urls[i]
        else:
            url = None
        if len(orgs) > i:
            org = orgs[i]
        else:
            org = None

        if not mail:
            #mails and urls may be tucked away with the name
            # npm allows strings like "Barney Rubble <b@rubble.com> (http://barnyrubble.tumblr.com/)"
            # we do the same, alternatively we allow affiliations:
            #       "Barney Rubble <b@rubble.com> (Barney's Chocolate Factory)"
            m = re.search(r'([^<]+)(?:<([^@]+@[^>]+)>)?\s*(?:(\([^\)]+\)))?',name)
            if m:
                name, mail, extra = m.groups()
                if extra:
                    if extra.startswith("http"):
                        url = extra
                    elif extra.startswith("www"):
                        url = "http://" + extra
                    else:
                        org = extra

        firstname, lastname = parse_human_name(name.strip())

        author = URIRef(generate_uri(firstname + "-" + lastname, kwargs.get('baseuri'), prefix="person"))
        if skip_duplicates:
            q = f"SELECT ?a WHERE {{ ?a a schema:Person . ?a schema:givenName \"{firstname}\" . ?a schema:familyName \"{lastname}\" . }}"
            if g.query(q, initNs={'schema': SDO }):
                #person already exists, skipping
                continue
            if mail and g.query(f"SELECT ?a WHERE {{ ?a a schema:Person . ?a schema:email \"{mail}\" . }}", initNs={ 'schema': SDO }):
                #mail already exists, skipping
                continue

        g.add((author, RDF.type, SDO.Person))
        g.add((author, SDO.givenName, Literal(firstname.strip())))
        g.add((author, SDO.familyName, Literal(lastname.strip())))
        if mail and '@' in mail:
            g.add((author, SDO.email, Literal(mail.strip())))
        if url:
            g.add((author, SDO.url, Literal(url.strip("() "))))
            #                              -------------^
            #  needed to cleanup after the regexp and to prevent other accidents
        if single_author:
            if kwargs.get('position'):
                g.add((author, SDO.position, Literal(kwargs.get('position'))))
        elif len(names) > 1:
            g.add((author, SDO.position, Literal(i+1)))
        if org:
            orgres = URIRef(generate_uri(org, kwargs.get('baseuri'), prefix="org"))
            g.add((orgres, RDF.type, SDO.Organization))
            g.add((orgres, SDO.name, Literal(org.strip())))
            g.add((author, SDO.affiliation, orgres))

        if property in ORDEREDLIST_PROPERTIES:
            add_to_ordered_list(g, res, property, author)
        else:
            g.add((res, property, author))
        authors.append(author) #return the nodes

    return authors

def add_to_ordered_list(g: Graph, subject: Union[URIRef, BNode], property: URIRef, object: Union[URIRef, BNode, Literal], identifying_properties: list = [SDO.name,SDO.email]):
    """Add an item to the end of an ordered list in RDF (rdf:first, rdf:next)"""
    collection = g.value(subject, property)

    #make an invetory of property that might identify the object, so we don't add it twice
    idpropmap = {}
    for prop in identifying_properties:
        if isinstance(object, (URIRef, BNode)):
            v = g.value(object,prop)
            if v:
                idpropmap[prop] = v

    if collection and isinstance(collection, (URIRef,BNode)) and (collection, RDF.first,None) in g:
        while True:
            if (collection, RDF.first, object) in g:
                #item already exists, nothing to add
                return False
            testobject = g.value(collection, RDF.first)
            if isinstance(testobject, (URIRef, BNode)):
                for prop, value in idpropmap.items():
                    v = g.value(testobject,prop)
                    if v and v == value:
                        #item already exists, nothing to add
                        return False
            end = g.value(collection, RDF.rest)
            if end == RDF.nil or not end:
                break
            collection = end
        if not end:
            raise Exception(f"Unable to find end of ordered list {collection}")
        g.remove((collection, RDF.rest, RDF.nil))
        newnode = BNode()
        g.add((newnode, RDF.first, object)) 
        g.add((newnode, RDF.rest, RDF.nil)) 
        g.add((collection, RDF.rest, newnode))
        return True
    elif not collection:
        collection = BNode()
        g.add((subject,property, collection))
        g.add((collection, RDF.first, object))
        g.add((collection, RDF.rest, RDF.nil))
        return True
    return False

def part_of_ordered_list(g: Graph, subject: Union[URIRef, BNode], property: URIRef, object: Union[URIRef, BNode, Literal]) -> bool:
    """Check if an item is a member of an RDF ordered list (rdf:first, rdf:rest)"""
    collection = g.value(subject, property)
    while collection and isinstance(collection, (URIRef,BNode)):
        if (collection, RDF.first, object) in g:
            return True
        collection = g.value(collection, RDF.rest)
    return False

def iter_ordered_list(g: Graph, subject: Union[URIRef, BNode], property: URIRef) -> Generator:
    """Check if an item is a member of an RDF ordered list (rdf:first, rdf:rest). Returns triples"""
    collection = g.value(subject, property)
    while collection and isinstance(collection, (URIRef,BNode)):
        object =  g.value(collection, RDF.first)
        if object:
            yield subject, property, object
        collection = g.value(collection, RDF.rest)

def parse_human_name(name):
    humanname = HumanName(name.strip())
    lastname = " ".join((humanname.middle, humanname.last)).strip()
    return humanname.first, lastname


def get_last_component(uri):
    index = max(uri.rfind('#'), uri.rfind('/'))
    if index == -1:
        return uri
    else:
        return uri[index+1:]

def reconcile(g: Graph, res: URIRef, args: AttribDict):
    """Reconcile possible conflicts in the graph and issue warnings."""
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
    if status and not status.startswith("http"):
        if status.lower() in REPOSTATUS_MAP.values():
            print(f"{HEAD} automatically converting status to repostatus URI",file=sys.stderr)
            g.set((res, CODEMETA.developmentStatus, URIRef("https://www.repostatus.org/#" + status.lower())))
        else:
            print(f"{HEAD} status is not expressed using repostatus vocabulary: {status}",file=sys.stderr)
            g.set((res, CODEMETA.developmentStatus, Literal(status)))

    license = g.value(res, SDO.license)
    if license and not license.startswith("http"):
        license = license_to_spdx(license)
        if license.startswith("http"):
            print(f"{HEAD} automatically converting license to spdx URI",file=sys.stderr)
            g.set((res, SDO.license, URIRef(license)))
        else:
            g.set((res, SDO.license, Literal(license)))



    #Convert Literal to URIRef for certain properties
    for prop in PREFER_URIREF_PROPERTIES:
        for _,_,obj in g.triples((res, prop, None)):
            if obj and isinstance(obj, Literal):
                if str(obj).startswith("http"):
                    g.set((res, prop, URIRef(str(obj))))
                elif str(obj).startswith("//"): #if absolute url is missing a schema, assume HTTPS
                    g.set((res, prop, URIRef("https:" + str(obj))))
                else:
                    continue
                g.remove((res,prop,obj))

    if (res, SDO.targetProduct, None) not in g:
        #we have no target products, that means we have no associated interface types,
        #see if we can extract some clues from the keywords or the description
        #and add a targetproduct (with only a type)
        guess_interfacetype(g,res, args)

def enrich(g: Graph, res: URIRef, args: AttribDict):
    """Do some automatic inference and enrichment of the graph"""
    IDENTIFIER = g.value(res, SDO.identifier)
    if not IDENTIFIER: IDENTIFIER = str(res)
    HEAD = f"[CODEMETA ENRICHMENT ({IDENTIFIER})]"

    if not g.value(res, SDO.programmingLanguage):
        for _,_,o in g.triples((res, SDO.runtimePlatform,None)):
            for platform in ("Python","Perl","Ruby","Julia","PHP"): #java is not added because the JVM does not necessarily mean things are written in java, NodeJS is not added because it can mean either Javascript or Typescript
                if str(o).lower().startswith(platform.lower()):
                    lang = platform
                    print(f"{HEAD} automatically adding programmingLanguage {lang} derived from runtimePlatform {platform}",file=sys.stderr)
                    g.add((res, SDO.programmingLanguage, Literal(lang)))
    elif not g.value(res, SDO.runtimePlatform):
        for _,_,o in g.triples((res, SDO.programmingLanguage,None)):
            for lang in ("Python","Perl","Ruby","Julia","PHP","Java","Kotlin","Groovy","Erlang","Elixir"):
                if str(o).lower().startswith(lang.lower()):
                    if lang in ("Kotlin","Groovy"):
                        platform = "Java"
                    elif lang in "Elixir":
                        platform = "Erlang"
                    else:
                        platform = lang
                    print(f"{HEAD} automatically adding runtimePlatform {platform} derived from programmingLanguage {lang}",file=sys.stderr)
                    g.add((res, SDO.runtimePlatform, Literal(platform)))

    if not g.value(res, SDO.contributor):
        for _,_,o in g.triples((res, SDO.author,None)):
            print(f"{HEAD} adding author {o} as contributor",file=sys.stderr)
            g.add((res, SDO.contributor, o))
    elif not g.value(res, SDO.author):
        for _,_,o in g.triples((res, SDO.contributor,None)):
            print(f"{HEAD} adding contributor {o} as author",file=sys.stderr)
            g.add((res, SDO.author, o))

    authors = len(list(g.triples((res, SDO.author,None))))
    if not g.value(res, SDO.maintainer) and authors == 1:
        print(f"{HEAD} considering sole author as maintainer",file=sys.stderr)
        author = g.value(res, SDO.author)
        g.add((res, SDO.maintainer, author))

    maintainers = list(g.triples((res, SDO.maintainer,None)))
    if not g.value(res, SDO.producer) and maintainers:
        for maintainer in maintainers:
            if isinstance(maintainer, (URIRef,BNode)):
                if (maintainer, RDF.type, SDO.Person) in g:
                    for _,_,affiliation in g.triples((maintainer, SDO.affiliation,None)):
                        print(f"{HEAD} setting maintainer's affiliation as producer",file=sys.stderr)
                        g.add((res, SDO.producer, affiliation))
                elif (maintainer, RDF.type, SDO.Organization) in g:
                    print(f"{HEAD} maintainer is organization, add as producer",file=sys.stderr)
                    g.add((res, SDO.producer, maintainer))

    if not g.value(res, SDO.producer) and authors == 1:
        for author in g.triples((res, SDO.author,None)):
            if isinstance(author, (URIRef,BNode)):
                if (author, RDF.type, SDO.Person) in g:
                    for _,_,o in g.triples((author, SDO.affiliation,None)):
                        print(f"{HEAD} adding affiliation of sole author as producer",file=sys.stderr)
                        g.add((res, SDO.producer, o))
                elif (author, RDF.type, SDO.Organization) in g:
                    print(f"{HEAD} author is organization, add as producer",file=sys.stderr)
                    g.add((res, SDO.producer, author))

        

def guess_interfacetype(g: Graph, res: Union[URIRef,BNode], args: AttribDict) -> Union[URIRef,None]:
    IDENTIFIER = g.value(res, SDO.identifier)
    if not IDENTIFIER: IDENTIFIER = str(res)
    HEAD = f"[CODEMETA VALIDATION ({IDENTIFIER})]"

    counter = Counter() #we count clues for all kinds of types we can find and pick the highest one
    keywords = [ o.lower() for _,_,o in g.triples((res, SDO.keywords, None)) ]
    for clue, interfacetype in INTERFACE_CLUES:
        for keyword in keywords:
            if keyword.find(clue) != -1:
                counter.update({interfacetype:1})
    description = g.value(res, SDO.description)
    if description:
        description = description.lower()
        for clue, interfacetype in INTERFACE_CLUES:
            if description.find(clue) != -1:
                counter.update({interfacetype:1})
    #can we infer a type from the dependencies?
    for _,_, depres in g.triples((res,SDO.softwareRequirements,None)):
        depname = g.value(depres,SDO.name)
        if depname:
            depname = depname.lower()
            if depname in INTERFACE_CLUES_DEPS:
                counter.update({INTERFACE_CLUES_DEPS[depname]:1})

    if counter:
        print(f"{HEAD} Guessing interface type {interfacetype} based on clues",file=sys.stderr)
        interfacetype = max(counter)
        targetres = URIRef(generate_uri(baseuri=args.baseuri, prefix="stub"))
        g.set((targetres, RDF.type, interfacetype))
        g.set((res, SDO.targetProduct, targetres))
        return targetres


def get_subgraph(g: Graph, reslist: Sequence[Union[URIRef,BNode]], subgraph: Union[Graph,None] = None, history: set = None ) -> Graph:
    """Add everything referenced from the specified resource to the new subgraph"""

    if subgraph is None:
        subgraph = Graph()
        bind_graph(subgraph)

    if history is None:
        history = set()

    for res in reslist:
        for pred, obj in g[res]:
            subgraph.add((res,pred,obj))
            if isinstance(obj, (URIRef, BNode)) and obj not in history:
                history.add(obj)
                get_subgraph(g, [obj], subgraph, history)
            elif isinstance(obj, Literal) and str(obj).startswith(("http","_","/")) and (URIRef(obj),None,None) in g and URIRef(obj) not in history: #incldue with things that are likely references but ended up as a Literal by mistake
                history.add(URIRef(obj))
                get_subgraph(g, [URIRef(obj)], subgraph, history)

    return subgraph


def getstream(source: str):
    """Opens an file (or use - for stdin) and returns the file descriptor"""
    if source == '-':
        return sys.stdin
    return open(source,'r',encoding='utf-8')


def remap_uri(g: Graph, from_uri, to_uri):
    """Changes URIs (in-graph)"""
    assert from_uri is not None and to_uri is not None
    if not isinstance(from_uri, URIRef):
        from_uri = URIRef(from_uri)
    if not isinstance(to_uri, URIRef):
        to_uri = URIRef(to_uri)
    for s,p,o in g.triples((from_uri,None,None)):
        g.remove((s,p,o))
        g.add((to_uri,p,o))
    for s,p,o in g.triples((None,None,from_uri)):
        g.remove((s,p,o))
        g.add((s,p,to_uri))

def merge_graphs(g: Graph ,g2: Graph, map_uri_from=None, map_uri_to=None, args: Optional[AttribDict] = None):
    """Merge two graphs (g2 into g), but taking care to replace certain properties that are known to take a single value, and mapping URIs where needed"""
    i = 0
    remapped = 0
    removed = 0
    both, first, second = graph_diff(g, g2)
    for (s,p,o) in second:
        s = handle_rel_uri(s, args.baseuri)
        p = handle_rel_uri(p, args.baseuri)
        o = handle_rel_uri(o, args.baseuri, prop=p)
        if map_uri_from and map_uri_to:
            if s == URIRef(map_uri_from):
                s = URIRef(map_uri_to)
                remapped += 1
            if o == URIRef(map_uri_from):
                remapped += 1
                o = URIRef(map_uri_to)
        if p in SINGULAR_PROPERTIES:
            #remove existing triples in the graph
            for (s2,p2,o2) in g.triples((s,p,None)):
                g.remove((s2,p2,o2))
                removed += 1
        elif p in ORDEREDLIST_PROPERTIES:
            #append items from ordered list in g2 to g (if they don't exist yet)
            for s2,p2,o2 in iter_ordered_list(g2, s, p):
                add_to_ordered_list(g,s2,p2,o2)
        elif p in (RDF.first, RDF.rest):
            continue #skip, already handled recursively by the previous block
        elif p == CODEMETA.developmentStatus and str(o).find("repostatus") != -1 and isinstance(s, (URIRef, BNode)):
            #ensure there is only one repostatus
            delete_repostatus(g, s)
        g.add((s,p,o))
        i += 1
    l = len(g2)
    print(f"    Merged {i} of {l} triples, removed {removed} superseded values, remapped {remapped} uris",file=sys.stderr)


def compose_postprocess(g: Graph, oldgraph: Graph, res: URIRef):
    #ensure there is only one repostatus item
    count = 0
    for _,_,o in g.triples((res, CODEMETA.developmentStatus, None)):
        if str(o).startswith(REPOSTATUS) or str(o).strip().lower() in REPOSTATUS_MAP.values():
            count += 1
    if count > 1:
        for _,_,o in oldgraph.triples((res, CODEMETA.developmentStatus, None)):
            if str(o).startswith(REPOSTATUS) or str(o).strip().lower() in REPOSTATUS_MAP.values():
                g.remove((res, CODEMETA.developmentStatus, o))

    #ensure there is only one TRL item
    count = 0
    for _,_,o in g.triples((res, CODEMETA.developmentStatus, None)):
        if str(o).startswith(TRL) or str(o).strip().lower() in TRL_MAP.values():
            count += 1
    if count > 1:
        for _,_,o in oldgraph.triples((res, CODEMETA.developmentStatus, None)):
            if str(o).startswith(TRL) or str(o).strip().lower() in TRL_MAP.values():
                g.remove((res, CODEMETA.developmentStatus, o))

    #when two ordered lists (rdf:List) are combined, the items of the new list need to be appended to the old list
    #instead we got two separate ordered lists, resolve this:
    q = """
    SELECT ?s ?prop ?l1 ?l2 WHERE {
        ?s ?prop ?l1 .
        ?s ?prop ?l2 .
        ?l1 rdf:first ?x .
        ?l2 rdf:first ?y .
        FILTER (?l1 != ?l2 )
    }
    """
    for result in g.query(q):
        if (result.s, result.prop, result.l1) in oldgraph:
            oldlist = result.l1
        else:
            oldlist = result.l2
        g.remove((result.s, result.prop, oldlist))
        for s,p,o in iter_ordered_list(oldgraph, result.s, result.prop):
            add_to_ordered_list(g, s,p,o)
                

def handle_rel_uri(value, baseuri: Optional[str] =None, prop = None):
    """Handle relative URIs (lacking a scheme and authority part).
       Also handles some properties that are sometimes given literal values
       rather than URIs (in violation of the codemeta specification)."""

    #if prop is set, then value is the object

    if isinstance(value, URIRef) and str(value).startswith("file:///"):
        if prop == CODEMETA.developmentStatus:
            #map to repostatus
            value = value_or_uri(value.replace("file://",""), baseuri)
            if value.strip().lower() in REPOSTATUS_MAP.values():
                return getattr(REPOSTATUS, value.strip().lower())
            elif value.strip().lower() in REPOSTATUS_MAP:
                #map to repostatus vocabulary
                repostatus = REPOSTATUS_MAP[value.strip().lower()]
                return getattr(REPOSTATUS, repostatus)
            else:
                #This is not a URI but a string literal
                return Literal(value)
        elif prop == SDO.license:
            #map to spdx
            value = value_or_uri(str(value).replace("file://",""), baseuri)
            value = license_to_spdx(value)
            if value.find('spdx') != -1:
                return URIRef(value)
            else:
                return Literal(value)
        else:
            #this is the normal case where we strip and map the file:// prefix rdflib assigns to make relative URIs absolute
            if baseuri:
                return URIRef(str(value).replace("file:///",  baseuri + ("/" if baseuri[-1] not in ("/","#") else "" )))
            else:
                return URIRef(str(value).replace("file:///","/"))
    return value


def get_doi(g: Graph, res: Union[URIRef,BNode]) -> Optional[str]:
    """Get the DOI for a resource, looks in various places"""
    #DOI in URI?
    if str(res).startswith("https://doi.org/"):
        return str(res)[len("https://doi.org/"):]
    elif str(res).startswith("http://doi.org/"):
        return str(res)[len("http://doi.org/"):]
    #DOI in schema:identifier?
    for _,_,o in g.triples((res,SDO.identifier,None)):
        #as URL
        if str(o).startswith("https://doi.org/"):
            return str(o)[len("https://doi.org/"):]
        elif str(o).startswith("http://doi.org/"):
            return str(o)[len("http://doi.org/"):]
        elif str(o).lower().startswith("doi:"):
            return str(o)[len("doi:"):]
        elif isinstance(o, (URIRef,BNode)) and (o,RDF.type,SDO.PropertyValue) in g and str(g.value(o,SDO.propertyID)) in ("doi","DOI"):
            #as PropertyValue (recommended)
            doi = g.value(o,SDO.value)
            if doi:
                return str(doi)
    return None


def urijoin(*args) -> str:
    s = ""
    for arg in args:
        if s and s[-1] != "/": s += "/"
        s += arg
    return s

def generate_uri(identifier: Union[str,None] = None, baseuri: Union[str,None] = None, prefix: str= ""):
    """Generate an URI (aka IRI)"""
    if not identifier:
        identifier = "N" + "%032x" % random.getrandbits(128)
    else:
        identifier = identifier.lower()
        for pattern, replacement in IDENTIFIER_MAP:
            identifier = identifier.replace(pattern,replacement) #not the most efficient but it'll do
        identifier = identifier.strip("-")
    if prefix and prefix[-1] not in ('/','#'):
        prefix += '/'
    if not baseuri:
        baseuri = "file:///" #relative URI! (authority part file:// to be compatible with what rdflib assumes by default)
    elif baseuri[-1] not in ('/','#'):
        baseuri += '/'
    return baseuri + prefix + identifier

def query(g: Graph, sparql_query: str, restype=SDO.SoftwareSourceCode):
    results = []
    for result in g.query(sparql_query):
        try:
            if result.res and (result.res, RDF.type, restype) in g:
                label = g.value(result.res, SDO.name)
                if label:
                    results.append((result.res, label))
        except AttributeError:
            raise ValueError("Invalid query: Expected ?res in SPARQL query")
    results.sort(key=lambda x: x[1].lower())
    return results
