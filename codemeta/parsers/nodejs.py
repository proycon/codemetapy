import sys
import json
import os.path
from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, add_triple, CODEMETA, SOFTWARETYPES, add_authors, SDO, COMMON_SOURCEREPOS, SOFTWARETYPES
from codemeta.crosswalk import readcrosswalk, CWKey


def parse_sourcerepo(value):
    """npm allows some shortcuts, resolve them"""
    if value.startswith("github:"):
        value = "https://github.com/" + value[len("github:"):]
    elif value.startswith("gitlab:"):
        value = "https://gitlab.com/" + value[len("gitlab:"):]
    elif value.startswith("bitbucket:"):
        value = "https://bitbucket.com/" + value[len("bitbucket:"):]
    value = value.replace("git://","https://").replace("git+ssh://","https://") #always prefer https in URLs
    return value

def parse_nodejs(g: Graph, res: Union[URIRef, BNode], file: IO , crosswalk, args: AttribDict) -> Union[str,None]:
    data = json.load(file)
    prefuri = None
    for key, value in data.items():
        if key.lower() in crosswalk[CWKey.NODEJS]:
            if key == 'bugs':
                if isinstance(value,dict) and 'url' in value:
                    g.add((res, CODEMETA.issueTracker, Literal(value['url'])))
                    if 'email' in value:
                        g.add((res, SDO.email, Literal(value['email'])))
                elif isinstance(value, str):
                    g.add((res, CODEMETA.issueTracker, Literal(value)))
            elif key == 'license':
                if isinstance(value, dict) and 'type' in value:
                    add_triple(g, res, "license", value['type'], args)
                elif isinstance(value, (list,tuple)):
                    for item in value:
                        if isinstance(item, dict) and 'type' in item:
                            add_triple(g, res, "license", item['type'], args)
                        elif isinstance(item, str):
                            add_triple(g, res, "license", item, args)
                elif isinstance(value, str):
                    add_triple(g, res, "license", value, args)
            elif key == 'keywords':
                if isinstance(value, (list,tuple)):
                    for keyword in value:
                        add_triple(g, res, "keywords", value, args)
                else:
                    print("WARNING: keywords in package.json should be a list",file=sys.stderr)
            elif key == 'repository':
                if isinstance(value, str):
                    value = parse_sourcerepo(value)
                    add_triple(g, res, "codeRepository", value, args)
                    prefuri = value
                elif isinstance(value, dict) and 'url' in value:
                    value = parse_sourcerepo(value['url'])
                    add_triple(g, res, "codeRepository", value, args)
                    prefuri = value
            elif key == 'homepage':
                for sourcerepo in COMMON_SOURCEREPOS:
                    if value.startswith(sourcerepo) and not prefuri:
                        #catch if we're describing the source code repo instead
                        add_triple(g, res, "codeRepository", value, args)
                        prefuri = value
                        break
                add_triple(g, res, "url", value, args)
            elif key == 'author':
                #npm prescribes that author is only one person
                if isinstance(value, dict) and 'name' in value:
                    authors = add_authors(g, res, value['name'], True, value.get("email"))
                    if authors and 'url' in value:
                        g.add((authors[0], SDO.url, Literal(value['url'])))
                elif isinstance(value, str):
                    #npm allows strings like "Barney Rubble <b@rubble.com> (http://barnyrubble.tumblr.com/)"
                    #our add_authors function can handle that directly
                    add_authors(g, res, value, True)
            elif key == 'dependencies':
                if isinstance(value, dict):
                    for key, versioninfo in value.items():
                        dependency = BNode()
                        g.add((dependency, RDF.type, SDO.SoftwareApplication))
                        g.add((dependency, SDO.name, Literal(key)))
                        g.add((dependency, SDO.identifier, Literal(key)))
                        g.add((dependency, SDO.version, Literal(versioninfo)))
                        g.add((res,  CODEMETA.softwareRequirements, dependency))
            elif key in ('devDependencies','bundledDependencies','peerDependencies'):
                pass #ignore
            elif key == 'bin':
                #note: assuming CommandLineApplication may be a bit presumptuous here
                if isinstance(value, dict) and 'name' in value:
                    for progname, execname in value.items():
                        sapp = BNode()
                        g.add((sapp, RDF.type, SOFTWARETYPES.CommandLineApplication))
                        g.add((sapp, SDO.name, progname)) #from parent
                        g.add((sapp, SOFTWARETYPES.executableName, os.path.basename(execname)))
                        g.add((res, SDO.targetProduct, sapp))
                elif isinstance(value, str):
                    sapp = BNode()
                    g.add((sapp, RDF.type, SOFTWARETYPES.CommandLineApplication))
                    g.add((sapp, SDO.name, data['name'])) #from parent
                    g.add((sapp, SOFTWARETYPES.executableName, os.path.basename(value)))
                    g.add((res, SDO.targetProduct, sapp))
            elif key == 'engines':
                #TODO: map to runtimePlatform
                pass
            else:
                key = crosswalk[CWKey.NODEJS][key.lower()]
                add_triple(g, res, key, value, args)


    return prefuri
