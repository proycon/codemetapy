import sys
import importlib
import re
from typing import Union, IO
if sys.version_info.minor < 8:
    import importlib_metadata #backported
else:
    import importlib.metadata as importlib_metadata #python 3.8 and above: in standard library
from nameparser import HumanName

from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx, detect_list
from codemeta.crosswalk import readcrosswalk, CWKey

PROVIDER_PYPI = {
    "@id": "https://pypi.org",
    "@type": "Organization",
    "name": "The Python Package Index",
    "url": "https://pypi.org",
}

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
