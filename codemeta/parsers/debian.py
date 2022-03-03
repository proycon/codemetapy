import sys
from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx
from codemeta.crosswalk import readcrosswalk, CWKey

PROVIDER_DEBIAN = {
    "@id": "https://www.debian.org",
    "@type": "Organization",
    "name": "The Debian Project",
    "url": "https://www.debian.org",
}

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
