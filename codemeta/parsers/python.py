import sys
import importlib
import re
from typing import Union, IO
if sys.version_info.minor < 8:
    import importlib_metadata #backported
else:
    import importlib.metadata as importlib_metadata #python 3.8 and above: in standard library

from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF, SDO
from codemeta.common import AttribDict, add_triple, CODEMETA, SOFTWARETYPES, add_authors
from codemeta.crosswalk import readcrosswalk, CWKey

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

#pylint: disable=W0621
def parsepython(g: Graph, res: Union[URIRef, BNode], packagename: str, crosswalk, args: AttribDict):
    """Parses python package metadata and converts it to codemeta"""
    if crosswalk is None:
        _, crosswalk = readcrosswalk((CWKey.PYPI,))
    authorindex = []
    if args.exactplatformversion:
        g.add((res, SDO.runtimePlatform, Literal("Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro))))
    else:
        g.add((res, SDO.runtimePlatform, Literal("Python 3")))
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
        if key == "Classifier":
            fields = [ x.strip() for x in value.strip().split('::') ]
            classifier = fields[0]
            pipkey = f"classifiers['{classifier}']".lower()
            if pipkey in crosswalk[CWKey.PYPI]:
                key = crosswalk[CWKey.PYPI][pipkey]
                det = " > " if key != "programmingLanguage" else " "
                value = det.join(fields[1:])
                add_triple(g, res, key, value, args)
            elif classifier.lower() in crosswalk[CWKey.PYPI]:
                key = crosswalk[CWKey.PYPI][classifier.lower()]
                det = " > " if key != "programmingLanguage" else " "
                value = det.join(fields[1:])
                add_triple(g, res, key, value, args)
            elif classifier == "Intended Audience":
                add_triple(g, res, "audience", " > ".join(fields[1:]), args)
            else:
                print("NOTICE: Classifier "  + fields[0] + " has no translation",file=sys.stderr)
        else:
            if key == "Author":
                add_authors(g, res, value, args, mailvalue=pkg.metadata.get("Author-email",""))
            elif key == "Author-email":
                continue #already handled by the above
            elif key == "Requires-Dist":
                for dependency in splitdependencies(value):
                    if dependency.find("extra =") != -1 and args.no_extras:
                        print("Skipping extra dependency: ",dependency,file=sys.stderr)
                        continue
                    dependency, depversion = parsedependency(dependency.strip())
                    depres = BNode()
                    g.add((depres, RDF.type, SDO.SoftwareApplication))
                    g.add((depres, SDO.identifier, Literal(dependency)))
                    g.add((depres, SDO.name, Literal(dependency)))
                    if args.exactplatformversion:
                        g.add((depres, SDO.runtimePlatform, Literal("Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro))))
                    else:
                        g.add((depres, SDO.runtimePlatform, Literal("Python 3")))
                    if depversion:
                        g.add((depres, SDO.version, Literal(depversion)))
                    g.add((res, CODEMETA.softwareRequirements, depres))
            elif key == "Requires-External":
                for dependency in value.split(','):
                    dependency = dependency.strip()
                    depres = BNode()
                    g.add((depres, RDF.type, SDO.SoftwareApplication))
                    g.add((depres, SDO.identifier, Literal(dependency)))
                    g.add((depres, SDO.name, Literal(dependency)))
                    g.add((res, CODEMETA.softwareRequirements, depres))
            elif key.lower() in crosswalk[CWKey.PYPI]:
                add_triple(g, res, crosswalk[CWKey.PYPI][key.lower()], value, args)
            else:
                print("WARNING: No translation for distutils key " + key,file=sys.stderr)

    #ensure 'identifier' is always set
    name = g.value(res, SDO.name)
    if name and (res, SDO.identifier, None) not in g:
        g.set((res, SDO.identifier, name))


    if args.with_stypes:
        found = False
        for rawentrypoint in pkg.entry_points:
            if rawentrypoint.group == "console_scripts":
                interfacetype = SOFTWARETYPES.CommandLineApplication
            elif rawentrypoint.group == "gui_scripts":
                interfacetype = SOFTWARETYPES.DesktopApplication
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

            targetproduct = BNode()
            g.add((targetproduct, RDF.type, interfacetype))
            g.add((targetproduct, SDO.name, Literal(rawentrypoint.name)))
            g.add((targetproduct, SOFTWARETYPES.executableName, Literal(rawentrypoint.name)))
            if args.exactplatformversion:
                g.add((targetproduct, SDO.runtimePlatform, Literal("Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro))))
            else:
                g.add((targetproduct, SDO.runtimePlatform, Literal("Python 3")))
            g.add((res, SDO.targetProduct, targetproduct))
            found = True

        cat = g.value(res, SDO.applicationCategory)
        if not found or (cat and cat.lower().find("libraries") != -1):
            g.add((targetproduct, RDF.type, SOFTWARETYPES.SoftareLibrary))
            g.add((targetproduct, SDO.name, Literal(pkg.name)))
            g.add((targetproduct, SOFTWARETYPES.executableName, Literal(re.sub(r"[-_.]+", "-", pkg.name).lower()))) #see https://python.github.io/peps/pep-0503/
            if args.exactplatformversion:
                g.add((targetproduct, SDO.runtimePlatform, Literal("Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro))))
            else:
                g.add((targetproduct, SDO.runtimePlatform, Literal("Python 3")))
