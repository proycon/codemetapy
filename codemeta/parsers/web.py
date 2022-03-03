import json
import requests
from codemeta.common import clean, update, AttribDict
from bs4 import BeautifulSoup


def parseweb(url, args: AttribDict):
    r = requests.get(url)
    r.raise_for_status()
    contenttype = r.headers.get('content-type')
    if contenttype == "text/html":
        soup = BeautifulSoup(r.text, 'html.parser')
        scriptblock = soup.find("script", {"type":"application/ld+json"})
        if scriptblock:
             return "".join(scriptblock.contents)
    elif contenttype in ("application/json", "application/ld+json"):
        data = json.loads(r.text)
        if "@context" in data and "@type" in data:
            value = data['@context']
            if isinstance(value,str):
                uses_schemaorg = value.find("schema.org") != -1 or value.find("codemeta") != -1
            elif isinstance(value,list):
                uses_schemaorg = any( x.find("schema.org") != -1 or x.find("codemeta") != -1 for x in value )
            else:
                uses_schemaorg = False


