import sys
import tomlkit
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from typing import Union, IO
from codemeta.common import AttribDict, add_triple, CODEMETA, SOFTWARETYPES, add_authors, SDO, COMMON_SOURCEREPOS, SOFTWARETYPES, generate_uri


def parse_rust(g: Graph, res: Union[URIRef, BNode], file: IO ,  args: AttribDict):
    data = tomlkit.parse(file.read())
    if 'package' in data:
        for key, value in data['package'].items():
            if key == 'repository':
                add_triple(g, res, 'codeRepository', value, args)
            elif key == 'authors':
                if isinstance(value, str):
                    add_authors(g, res, value, single_author=False, baseuri=args.baseuri)
                elif isinstance(value, list):
                    for value in value:
                        add_authors(g, res, value, single_author=True, baseuri=args.baseuri)
            elif key == 'keywords':
                if isinstance(value, (list,tuple)):
                    for keyword in value:
                        add_triple(g, res, "keywords", keyword, args)
                else:
                    print("WARNING: keywords in Cargo.toml should be a list",file=sys.stderr)
            elif key == 'homepage':
                for sourcerepo in COMMON_SOURCEREPOS:
                    if value.startswith(sourcerepo) and 'repository' not in data['package']:
                        #catch if we're describing the source code repo instead
                        add_triple(g, res, "codeRepository", value, args)
                        break
                add_triple(g, res, "url", value, args)
            elif key == 'documentation':
                add_triple(g, res, "softwareHelp", value, args)
            elif key == 'categories':
                add_triple(g, res, "applicationCategory", value, args)
            elif key in ('name','description','readme','license','version'):
                add_triple(g, res, key, value, args)
    if 'dependencies' in data:
        for key, value in data['dependencies'].items():
            if isinstance(value, dict) and 'version' in value:
                add_dependency(g, res, key, value['version'], args)
            elif isinstance(value, str):
                add_dependency(g, res, key, value, args)
            
    g.add((res, SDO.programmingLanguage, Literal("Rust")))

#pylint: disable=W0621
def add_dependency(g: Graph, res: Union[URIRef, BNode], name: str, version: str, args: AttribDict):
    if version and version[0].isalnum():
        version_id = "-" + version
    else:
        version_id = version
    depres = URIRef(generate_uri(name+version_id.replace(' ',''),args.baseuri,"dependency")) #version number is deliberately in ID here!
    g.add((depres, RDF.type, SDO.SoftwareApplication))
    g.add((depres, SDO.identifier, Literal(name)))
    g.add((depres, SDO.name, Literal(name)))
    g.add((depres, SDO.version, Literal(version)))
    g.add((res, CODEMETA.softwareRequirements, depres))
