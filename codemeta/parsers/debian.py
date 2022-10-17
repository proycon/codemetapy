import sys
from typing import Union
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, add_triple, CODEMETA, SOFTWARETYPES, SDO, SOFTWARETYPES, generate_uri
from codemeta.crosswalk import readcrosswalk, CWKey

def parse_debian(g: Graph, res: Union[URIRef, BNode], lines, crosswalk, args: AttribDict):
    """Parses apt show output and converts to codemeta"""
    if crosswalk is None:
        _, crosswalk = readcrosswalk((CWKey.DEBIAN,))

    name = None
    interfacetype = None
    description = ""
    parsedescription = False
    for line in lines:
        if parsedescription and line and line[0] == ' ':
            description += line[1:] + " "
        else:
            try:
                key, value = (x.strip() for x in line.split(':',1))
            except:
                continue
            if key == "Origin":
                if value == "Debian":
                    provider = URIRef("https://www.debian.org")
                    g.add((provider, RDF.type, SDO.Organization))
                    g.add((provider, SDO.name, Literal("The Debian Project")))
                    g.add((provider, SDO.url, Literal("https://www.debian.org")))
                    g.add((res,SDO.provider,provider))
                elif value == "Ubuntu":
                    provider = URIRef("https://ubuntu.com")
                    g.add((provider, RDF.type, SDO.Organization))
                    g.add((provider, SDO.name, Literal("Ubuntu")))
                    g.add((provider, SDO.url, Literal("https://ubuntu.com")))
                    g.add((res,SDO.provider,provider))
                else:
                    print(f"WARNING: Don't know how to convert Origin: {value}",file=sys.stderr)
            elif key == "Depends":
                for dependency in value.split(","):
                    dependency = dependency.strip().split(" ")[0].strip()
                    if dependency:
                        depnode = URIRef(generate_uri(dependency, baseuri=args.baseuri,prefix="dependency"))
                        g.add((depnode, RDF.type, SDO.SoftwareApplication))
                        g.add((depnode, SDO.identifier, Literal(dependency)))
                        g.add((depnode, SDO.name, Literal(dependency)))
                        g.add((res, CODEMETA.softwareRequirements, depnode))
            elif key == "Section":
                #attempt to make an educated guess for the audience and interface type
                if "libs" in value or "libraries" in value:
                    if args.with_stypes:
                        interfacetype = SOFTWARETYPES.SoftwareLibrary
                        add_triple(g, res, "audience", "Developers", args)
                elif "utils" in value or "text" in value:
                    if args.with_stypes:
                        interfacetype = SOFTWARETYPES.CommandLineApplication
                elif "devel" in value:
                    add_triple(g, res, "audience", "Developers", args)
                elif "science" in value:
                    add_triple(g, res, "audience", "Researchers", args)
            elif key == "Description":
                parsedescription = True
                description = value + "\n\n"
            elif key == "Homepage":
                g.add((res, SDO.url, Literal(value)))
            elif key == "Version":
                g.add((res, SDO.version, Literal(value)))
            elif key.lower() in crosswalk[CWKey.DEBIAN]:
                if key == "Package":
                    name = value
                else:
                    key = crosswalk[CWKey.DEBIAN][key.lower()]
                    add_triple(g, res, key, value, args)
            else:
                print("WARNING: No translation for APT key " + key,file=sys.stderr)
    if name:
        g.add((res, SDO.name, Literal(name)))
        g.add((res, SDO.identifier, Literal(name)))
    else:
        print("No name found for package, should not happen",file=sys.stderr)
        return False
    if description:
        g.add((res, SDO.description, Literal(description)))
    if interfacetype and args.with_stypes:
        sapp = URIRef(generate_uri(name, baseuri=args.baseuri,prefix=str(interfacetype).lower()))
        g.add((sapp, RDF.type, interfacetype))
        g.add((sapp, SDO.name, name))
        g.add((res, SDO.targetProduct, sapp))

