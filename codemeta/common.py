import sys
from typing import Union, IO
from collections import OrderedDict


PROGLANG_PYTHON = {
    "@type": "ComputerLanguage",
    "name": "Python",
    "version": str(sys.version_info.major) + "." + str(sys.version_info.minor) + "." + str(sys.version_info.micro),
    "url": "https://www.python.org",
}

CONTEXT =  [
    "https://doi.org/10.5063/schema/codemeta-2.0",
    "http://schema.org/",
]

ENTRYPOINT_CONTEXT = { #these are all custom extensions not in codemeta (yet), they are proposed in https://github.com/codemeta/codemeta/issues/183 but are obsolete in favour of the newer software types (see next declaration)
    "entryPoints": { "@reverse": "schema:actionApplication" },
    "interfaceType": { "@id": "codemeta:interfaceType" }, #Type of the entrypoint's interface (e.g CLI, GUI, WUI, TUI, REST, SOAP, XMLRPC, LIB)
    "specification": { "@id": "codemeta:specification" , "@type":"@id"}, #A technical specification of the interface
    "mediatorApplication": {"@id": "codemeta:mediatorApplication", "@type":"@id" } #auxiliary software that provided/enabled this entrypoint
}

#these are all custom extensions not in codemeta/schema.org (yet), they are proposed in https://github.com/codemeta/codemeta/issues/271 and supersede the above one
SOFTWARETYPE_CONTEXT = "https://w3id.org/software-types#"




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

class AttribDict(dict):
    """Simple dictionary that is addressable via attributes"""
    def __init__(self, d):
        self.__dict__ = d

    def __getattr__(self, key):
        if key in self:
            return self[key]
        return None

def license_to_spdx(value: Union[str,list], args: AttribDict) -> str:
    """Attempts to converts a license name or acronym to a full SPDX URI (https://spdx.org/licenses/)"""
    if isinstance(value, list):
        return [ license_to_spdx(x, args) for x in value ]
    if not args.with_spdx: return value
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

def clean(data: dict) -> dict:
    """Purge empty values, lowercase identifier"""
    purgekeys = []
    for k,v in data.items():
        if v == "" or v is None or (isinstance(v,(tuple, list)) and len(v) == 0):
            purgekeys.append(k)
        elif isinstance(v, (dict, OrderedDict)):
            clean(v)
        elif isinstance(v, (tuple, list)):
            data[k] = [ clean(x) if isinstance(x, (dict,OrderedDict)) else x for x in v ]
    for k in purgekeys:
        del data[k]
    if 'identifier' in data and isinstance(data['identifier'], str):
        data['identifier'] = data['identifier'].lower()
    return data

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

def update(data: dict, newdata: dict):
    """Recursive update a dictionary, adds values whenever possible instead of replacing"""
    for key, value in newdata.items():
        if key in data:
            if isinstance(value, dict):
                update(data[key], value)
            elif isinstance(value, (list,tuple)):
                for x in value:
                    if isinstance(data[key], dict ):
                        data[key] = [ data[key], x ]
                    elif isinstance(data[key], (list,tuple)):
                        if x not in data[key]:
                            if isinstance(data[key], list):
                                data[key].append(x)
                    elif isinstance(data[key], (str,float,int,bool) ):
                        data[key] = [ data[key], x ]
            else:
                data[key] = value
        else:
            data[key] = value

def getstream(source: str):
    """Opens an file (or use - for stdin) and returns the file descriptor"""
    if source == '-':
        return sys.stdin
    return open(source,'r',encoding='utf-8')

