import sys
import os
import importlib
import re
from typing import Union, IO
if sys.version_info.minor < 8:
    import importlib_metadata #backported
else:
    import importlib.metadata as importlib_metadata #python 3.8 and above: in standard library

from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, add_triple, CODEMETA, SOFTWARETYPES, add_authors, SDO, COMMON_SOURCEREPOS, generate_uri, get_last_component
from codemeta.crosswalk import readcrosswalk, CWKey
import pyproject_parser
import pep517.meta



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
    end = min(
        s.find(" ") if s.find(" ") != -1 else 999999,
        s.find(";") if s.find(";") != -1 else 999999,
        s.find(">") if s.find(">") != -1 else 999999,
        s.find("!") if s.find("!") != -1 else 999999,
        s.find("~") if s.find("~") != -1 else 999999,
        s.find("=") if s.find("=") != -1 else 999999,
        s.find("^") if s.find("^") != -1 else 999999
    )
    if end != 999999:
        identifier = s[:end]
    else:
        return s, ""

    versionbegin = -1
    for i, c in enumerate(s[end:]):
        if c not in ('>','=','~','!',' '):
            versionbegin = end + i
            break
    if versionbegin != -1:
        operator = s[end:versionbegin].strip()
        if operator in ("=","=="):
            version = s[versionbegin:].strip()
        else:
            version = operator + " " + s[versionbegin:].strip()
    else:
        version = ""
    if ';' in version:
        #there may be extra qualifiers after the version which we strip (like ; sys_platform=)
        version = version.split(";")[0]
    return identifier, version.strip("[]() -.,:")


def parse_classifier(value: str, g: Graph, res: Union[URIRef, BNode], crosswalk, args: AttribDict):
    fields = [ x.strip() for x in value.strip().split('::') ]
    classifier = fields[0]
    pipkey = f"classifiers['{classifier}']".lower()
    if pipkey in crosswalk[CWKey.PYPI]:
        key = crosswalk[CWKey.PYPI][pipkey]
        det = " > " if key != "programmingLanguage" else " "
        value = det.join(fields[1:])
        add_triple(g, res, "runtimePlatform" if key == "programmingLanguage" else key, value, args)
    elif classifier.lower() in crosswalk[CWKey.PYPI]:
        key = crosswalk[CWKey.PYPI][classifier.lower()]
        det = " > " if key != "programmingLanguage" else " "
        value = det.join(fields[1:])
        add_triple(g, res, "runtimePlatform" if key == "programmingLanguage" else key, value, args)
    elif classifier == "Intended Audience":
        add_triple(g, res, "audience", " > ".join(fields[1:]), args)
    else:
        print("NOTICE: Classifier "  + fields[0] + " has no translation",file=sys.stderr)

def parse_url(label: str, url: str, g: Graph, res: Union[URIRef, BNode], crosswalk, args: AttribDict):
    #label is free so we do some educated guessed
    #(see https://packaging.python.org/en/latest/specifications/core-metadata/#project-url-multiple-use)
    label = label.lower()
    if "repository" in label or label in ('git','github','code','sourcecode',"source"):
        add_triple(g, res, "codeRepository", url, args)
    elif label in ("bug tracker","issue tracker","tracker", "issues"):
        add_triple(g, res, "issueTracker", url, args)
    elif label in ("documentation", "docs","api reference","reference"):
        add_triple(g, res, "softwareHelp", url, args)
    elif label == "readme":
        add_triple(g, res, "readme", url, args)
    elif label in ("build","build instructions","installation"):
        add_triple(g, res, "buildInstructions", url, args)
    elif label in ("release notes","releases"):
        add_triple(g, res, "releaseNotes", url, args)
    elif label in ("continous integration", "ci","tests"):
        add_triple(g, res, "contIntegration", url, args)
    else:
        add_triple(g, res, "url", url, args)

def metadata_from_pyproject(pyproject: pyproject_parser.PyProject):
    if pyproject.project and 'name' in pyproject.project:
        return pyproject.project
    if pyproject.tool and 'name' in list(pyproject.tool.values())[0]:
        return list(pyproject.tool.values())[0]
    return None

#pylint: disable=W0621
def parse_python(g: Graph, res: Union[URIRef, BNode], packagename: str, crosswalk, args: AttribDict):
    """Parses python package metadata and converts it to codemeta

    Parameters:
    * `packagename` - Either 1) a name of a package that is installed or available in the current working directory, or 2) path to a pyproject.toml file 
    """
    if crosswalk is None:
        _, crosswalk = readcrosswalk((CWKey.PYPI,))
    if args.exactplatformversion:
        g.add((res, SDO.runtimePlatform, Literal("Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro))))
    else:
        g.add((res, SDO.runtimePlatform, Literal("Python 3")))

    prevdir = None
    pkg = None
    if os.path.basename(packagename) == "pyproject.toml":
        print(f"Loading metadata from {packagename} via pyproject-parser",file=sys.stderr) #pylint: disable=W0212
        metadata = None
        try:
            pyproject = pyproject_parser.PyProject.load(packagename)
            metadata = metadata_from_pyproject(pyproject)
            if not metadata:
                print(f"Failed to find complete enough metadata in pyproject.toml",file=sys.stderr)
        except Exception as e:
            print(f"Failed to process {packagename} via pyproject-parser: {str(e)}",file=sys.stderr)
       
        if not metadata:
            print(f"Fallback: Loading metadata from {packagename} via PEP517",file=sys.stderr) #pylint: disable=W0212
            try:
                pkg = pep517.meta.load(os.path.dirname(packagename))
            except Exception as e:
                print(f"Failed to process {packagename} via PEP517: {str(e)}",file=sys.stderr)
                sys.exit(4)
            packagename = pkg.name
            metadata = pkg.metadata.items()
        else:
            metadata = metadata.items()
    else:
        print(f"Loading metadata from {packagename} via importlib.metadata",file=sys.stderr) #pylint: disable=W0212
        try:
            pkg = importlib_metadata.distribution(packagename)
        except importlib_metadata.PackageNotFoundError:
            if '/' in packagename:
                dirname = os.path.dirname(packagename)
                prevdir = os.getcwd()
                os.chdir(dirname)
                packagename = os.path.basename(packagename)
            #fallback if package is not installed but in local directory:
            context = importlib_metadata.DistributionFinder.Context(name=packagename,path='.')
            try:
                pkg = next(importlib_metadata.MetadataPathFinder().find_distributions(context))
            except StopIteration:
                print(f"No such python package: {packagename}",file=sys.stderr)
                if prevdir: os.chdir(prevdir)
                sys.exit(4)
        if isinstance(pkg._path, str):
            print(f"Found metadata in {pkg._path}",file=sys.stderr) #pylint: disable=W0212
        metadata = pkg.metadata.items()
            #if prevdir: os.chdir(prevdir)

    for key, value in metadata:
        if key == "Classifier": #importlib.metadata
            parse_classifier(value, g, res, crosswalk, args)
        elif key == "classifiers" and isinstance(value, (list,tuple)): #pyproject
            for e in value:
                parse_classifier(e, g, res, crosswalk, args)
        else:
            if key == "authors" and isinstance(value, (list,tuple)): #pyproject
                for e in value:
                    if isinstance(e, str):
                        add_authors(g, res, e, single_author=True, baseuri=args.baseuri)
                    elif isinstance(e, dict) and 'name' in e:
                        add_authors(g, res, e['name'], single_author=True, mail=e.get('mail',""), baseuri=args.baseuri)
            elif key == "Author" and pkg: #distutils
                add_authors(g, res, value, single_author=args.single_author, mail=pkg.metadata.get("Author-email",""), baseuri=args.baseuri)
            elif key == "Author-email":
                continue #already handled by the above
            elif key == "Project-URL":
                if ',' in value:
                    label, url = value.split(",",1) #according to spec
                    label = label.strip()
                    url = url.strip()
                    parse_url(label, url, g, res, crosswalk, args)
                else:
                    #input probably not according to spec
                    add_triple(g, res, "url", value, args) 
            elif key == "urls" and isinstance(value,dict): #pyproject.toml
                for label, url in value.items():
                    parse_url(label, url, g, res, crosswalk, args)
            elif key == 'repository':
                add_triple(g, res, "codeRepository", value, args)
            elif key == 'dependencies':
                if isinstance(value, dict):
                    for k,v in value.items():
                        add_dependency(g, res, f"{k} {v}", args)
                elif isinstance(value, list):
                    for e in value:
                        #                      v-- we may get a pyproject_parser.Requirement() instance here, so convert to str()
                        add_dependency(g, res, str(e), args)
            elif key == 'description' and not pkg: #pyproject.toml
                #note: in distutils this is called 'summary' and we don't want the Description field there because it contains the whole README 
                add_triple(g, res, 'description', value, args)
            elif key in ('gui_scripts','gui-scripts') and isinstance(value, dict): #pyproject.toml, flit, poetry?
                for script_name, rawentrypoint in value.items():
                    module_name = rawentrypoint.strip().split(':')[0]
                    interfacetype = SOFTWARETYPES.DesktopApplication
                    add_entrypoint(g, res, script_name, module_name, interfacetype, args)
            elif key == 'scripts' and isinstance(value, dict): #pyproject.toml, poetry
                for script_name, rawentrypoint in value.items():
                    module_name = rawentrypoint.strip().split(':')[0]
                    #we don't really know for sure if it's a CLI or GUI application, assume CLI
                    interfacetype = SOFTWARETYPES.CommandLineApplication
                    add_entrypoint(g, res, script_name, module_name, interfacetype, args)
            elif key.lower() in crosswalk[CWKey.PYPI]:
                add_triple(g, res, crosswalk[CWKey.PYPI][key.lower()], value, args)
                if crosswalk[CWKey.PYPI][key.lower()] == "url":
                    for v in COMMON_SOURCEREPOS:
                        if value.startswith(v):
                            add_triple(g, res, "codeRepository", value, args)
                            if not args.baseuri:
                                prefuri = value
                            break
            else:
                print("WARNING: No translation for distutils or pyproject.toml key " + key,file=sys.stderr)

    if pkg and pkg.requires:
        for value in pkg.requires:
            add_dependency(g, res, value, args)

    test_and_set_identifier(g, res, args)

    if args.with_stypes and pkg:
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
                add_entrypoint(g, res, rawentrypoint.name, module_name, interfacetype, args)
            else:
                add_entrypoint(g, res, rawentrypoint.name, "", interfacetype, args)
            found = True

        test_and_set_library(g, res, packagename, found, args)

    if prevdir: os.chdir(prevdir)

#pylint: disable=W0621
def add_dependency(g: Graph, res: Union[URIRef, BNode], value: str, args: AttribDict):
    for dependency in splitdependencies(value):
        if 'extra ==' in dependency and args.no_extras:
            continue
        dependency, depversion = parsedependency(dependency.strip())
        if dependency and not dependency.startswith(('<','>','=','^')):
            print(f"Found dependency {dependency} {depversion}",file=sys.stderr)
            depres = URIRef(generate_uri(dependency+depversion.replace(' ',''),args.baseuri,"dependency")) #version number is deliberately in ID here!
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

def add_entrypoint(g: Graph, res: Union[URIRef, BNode], name: str, module_name: str, interfacetype: Union[BNode,URIRef], args: AttribDict):
    """Translate an entrypoint to a targetProduct"""
    description = None
    if module_name:
        try:
            module = importlib.import_module(module_name)
            description = module.__doc__
        except:
            pass
    version = g.value(res,SDO.version) or "snapshot"
    targetproduct = URIRef(generate_uri(name, baseuri=args.baseuri,prefix=get_last_component(str(interfacetype)).lower()) + "/" + str(version))
    g.add((targetproduct, RDF.type, interfacetype))
    g.add((targetproduct, SDO.name, Literal(name)))
    if description:
        g.add((targetproduct, SDO.description, Literal(description)))
    g.add((targetproduct, SOFTWARETYPES.executableName, Literal(name)))
    if args.exactplatformversion:
        g.add((targetproduct, SDO.runtimePlatform, Literal("Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro))))
    else:
        g.add((targetproduct, SDO.runtimePlatform, Literal("Python 3")))
    g.add((res, SDO.targetProduct, targetproduct))


def test_and_set_library(g: Graph, res: Union[URIRef, BNode], packagename: str, found_entrypoints: bool, args: AttribDict):
    """Is this resource a software library? Set the necessary targetProduct if so"""
    islibrary = False
    isweb = False
    for (_,_, cat) in g.triples((res, SDO.applicationCategory,None)):
        islibrary = islibrary or str(cat).lower().find("libraries") != -1
        isweb = isweb or str(cat).lower().find("internet") != -1 or str(cat).lower().find("web") != -1 or str(cat).lower().find("www") != -1

    if (not found_entrypoints and not isweb) or islibrary:
        targetproduct = URIRef(generate_uri(packagename, baseuri=args.baseuri,prefix="softwarelibrary"))
        g.add((targetproduct, RDF.type, SOFTWARETYPES.SoftwareLibrary))
        g.add((targetproduct, SDO.name, Literal(packagename)))
        g.add((targetproduct, SOFTWARETYPES.executableName, Literal(re.sub(r"[-_.]+", "-", packagename).lower()))) #see https://python.github.io/peps/pep-0503/
        if args.exactplatformversion:
            g.add((targetproduct, SDO.runtimePlatform, Literal("Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro))))
        else:
            g.add((targetproduct, SDO.runtimePlatform, Literal("Python 3")))

def test_and_set_identifier(g: Graph, res: Union[URIRef, BNode], args: AttribDict):
    """ensure 'identifier' is always set"""
    name = g.value(res, SDO.name)
    if name and (res, SDO.identifier, None) not in g:
        g.set((res, SDO.identifier, Literal(str(name).lower())))
