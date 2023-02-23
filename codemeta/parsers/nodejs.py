import sys
import json
import os.path
from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, add_triple, CODEMETA, SOFTWARETYPES, add_authors, SDO, COMMON_SOURCEREPOS, SOFTWARETYPES, generate_uri
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

def parse_nodejs(g: Graph, res: Union[URIRef, BNode], file: IO , crosswalk, args: AttribDict):
    data = json.load(file)
    iswebapp = False
    foundrepo = False
    for key, value in data.items():
        if key.lower() in crosswalk[CWKey.NODEJS]:
            if key == 'name' and value:
                #remove the 'scope' from the name
                if value[0] == '@' and value.find('/') != -1:
                    value = value.split('/')[1]
                add_triple(g, res, key, value, args)
            elif key == 'bugs':
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
                        add_triple(g, res, "keywords", keyword, args)
                else:
                    print("WARNING: keywords in package.json should be a list",file=sys.stderr)
            elif key == 'private' and value:
                    print("WARNING: private=true was set on package.json! This package is marked not to be published!",file=sys.stderr)
            elif key == 'repository':
                if isinstance(value, str):
                    value = parse_sourcerepo(value)
                    add_triple(g, res, "codeRepository", value, args)
                    foundrepo = True
                elif isinstance(value, dict) and 'url' in value:
                    value = parse_sourcerepo(value['url'])
                    add_triple(g, res, "codeRepository", value, args)
                    foundrepo = True
            elif key == 'homepage':
                for sourcerepo in COMMON_SOURCEREPOS:
                    if value.startswith(sourcerepo) and not foundrepo:
                        #catch if we're describing the source code repo instead
                        add_triple(g, res, "codeRepository", value, args)
                        break
                add_triple(g, res, "url", value, args)
            elif key == 'author':
                #npm prescribes that author is only one person
                if isinstance(value, dict) and 'name' in value:
                    authors = add_authors(g, res, value['name'], single_author=True, mail=value.get("email"), baseuri=args.baseuri)
                    if authors and 'url' in value:
                        g.add((authors[0], SDO.url, Literal(value['url'])))
                elif isinstance(value, str):
                    #npm allows strings like "Barney Rubble <b@rubble.com> (http://barnyrubble.tumblr.com/)"
                    #our add_authors function can handle that directly
                    add_authors(g, res, value, single_author=True, baseuri=args.baseuri)
            elif key == 'contributor':
                if isinstance(value, dict) and 'name' in value:
                    authors = add_authors(g, res, value['name'], property=SDO.contributor, single_author=True, mail=value.get("email"), baseuri=args.baseuri)
                elif isinstance(value, str):
                    add_authors(g, res, value, property=SDO.contributor, baseuri=args.baseuri)
                elif isinstance(value, (list,tuple)):
                    for value in value:
                        authors = add_authors(g, res, value['name'], property=SDO.contributor, single_author=True, mail=value.get("email"), baseuri=args.baseuri)
            elif key in ('dependencies','devDependencies'):
                if isinstance(value, dict):
                    for key, versioninfo in value.items():
                        depres = URIRef(generate_uri(key+versioninfo, baseuri=args.baseuri,prefix="dependency"))
                        g.add((depres, RDF.type, SDO.SoftwareApplication))
                        g.add((depres, SDO.name, Literal(key)))
                        g.add((depres, SDO.identifier, Literal(key)))
                        g.add((depres, SDO.version, Literal(versioninfo)))
                        g.add((res,  CODEMETA.softwareRequirements, depres))
                    #detect some common web application frameworks or other
                    #dependencies that indicate this is a web-app
                    iswebapp = iswebapp or 'react' in value or 'vue' in value or 'sitemap' in value or  'gatsby' in value
            elif key in ('bundledDependencies','peerDependencies'):
                pass #ignore
            elif key == 'bin':
                #note: assuming CommandLineApplication may be a bit presumptuous here
                if isinstance(value, dict) and 'name' in value and args.with_stypes:
                    for progname, execname in value.items():
                        sapp = URIRef(generate_uri(key, baseuri=args.baseuri,prefix="commandlineapplication"))
                        g.add((sapp, RDF.type, SOFTWARETYPES.CommandLineApplication))
                        g.add((sapp, SDO.name, progname))
                        g.add((sapp, SOFTWARETYPES.executableName, os.path.basename(execname)))
                        g.add((res, SDO.targetProduct, sapp))
                elif isinstance(value, str) and args.with_stypes:
                    sapp = URIRef(generate_uri(data['name'], baseuri=args.baseuri,prefix="commandlineapplication"))
                    g.add((sapp, RDF.type, SOFTWARETYPES.CommandLineApplication))
                    g.add((sapp, SDO.name, data['name'])) #from parent
                    g.add((sapp, SOFTWARETYPES.executableName, os.path.basename(value)))
                    g.add((res, SDO.targetProduct, sapp))
            elif key == 'engines':
                if isinstance(value, dict):
                    for key, versioninfo in value.items():
                        g.add((res, SDO.runtimePlatform, Literal(key + " " + versioninfo)))
            else:
                key = crosswalk[CWKey.NODEJS][key.lower()]
                add_triple(g, res, key, value, args)

    if 'devDependencies' in data and "typescript" in data['devDependencies']:
        g.add((res, SDO.programmingLanguage, Literal("Typescript")))
    else:
        g.add((res, SDO.programmingLanguage, Literal("Javascript")))

    if args.with_stypes and 'browser' in data or 'browserslist' in data or iswebapp:
        #assume this is a web-application
        sapp = URIRef(generate_uri(data['name'], baseuri=args.baseuri,prefix="webapplication"))
        g.add((sapp, RDF.type, SDO.WebApplication))
        g.add((sapp, SDO.name, Literal(data['name']))) #from parent
        g.add((sapp, SDO.version, Literal(data['version']))) #from parent
        g.add((res, SDO.targetProduct, sapp))
