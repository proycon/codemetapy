import sys
import json
import requests
import yaml
from io import StringIO
from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, SDO
from codemeta.parsers.jsonld import parse_jsonld_data
from bs4 import BeautifulSoup

def detect_type(data):
    if "@context" in data and "@type" in data:
        value = data['@context']
        if isinstance(value,str):
            if value.find("schema.org") != -1 or value.find("codemeta") != -1:
                return  "schema"
        elif isinstance(value,list):
            if any( x.find("schema.org") != -1 or x.find("codemeta") != -1 for x in value ):
                return "schema"
    elif isinstance(data, dict) and 'openapi' in data:
        return "openapi"
    return None

def get_meta(soup, *keys, default=""):
    for key in keys:
        value = soup.find("meta", property=key, content=True)
        if value and value.content:
            return value.content
        value = soup.find("meta", {"name": key }, content=True)
        if value and value.content:
            return value.content
    return default

def parse_web(g: Graph, res: Union[URIRef, BNode], url, args: AttribDict) -> Union[URIRef,BNode,None]:
    r = requests.get(url, headers={ "Accept": "application/json+ld;q=1.0,application/json;q=0.9,application/x-yaml;q=0.8,application/xml;q=0.7;text/html;q=0.6;text/plain;q=0.1" })
    r.raise_for_status()
    contenttype = r.headers.get('content-type').split(';')[0].strip()
    datatype = None
    data = None

    if args.with_stypes:
        targetres = BNode()
    else:
        targetres = res

    if contenttype in ("application/json", "application/ld+json") or url.endswith(".json") or url.endswith(".jsonld"):
        print("Parsing json...",file=sys.stderr)
        data = json.loads(r.text)
    elif contenttype in ("application/x-yaml", "text/yaml") or url.endswith(".yml") or url.endswith(".yaml"):
        print("Parsing yaml...",file=sys.stderr)
        #may be OpenAPI
        with open(r.text,'r', encoding="utf-8") as f:
            data = yaml.load(f, yaml.Loader)
    elif contenttype == "text/html":
        print("Parsing html...",file=sys.stderr)
        soup = BeautifulSoup(r.text, 'html.parser')
        scriptblock = soup.find("script", {"type":"application/ld+json"})
        if scriptblock:
            #Does the site provide proper JSON-LD metadata itself?
            data = json.loads("".join(scriptblock.contents))
        else:
            g.add((targetres, RDF.type, SDO.WebApplication))
            g.add((targetres, SDO.url, Literal(get_meta(soup, "og:url", "url", default=url))))

            v = get_meta(soup, "og:site_name", "og:title", "twitter:title")
            if v: g.add((targetres, SDO.name, Literal(v)))

            v = get_meta(soup, "og:description", "twitter:description", "description")
            if v: g.add((targetres, SDO.description, Literal(v)))

            v = get_meta(soup, "og:image", "twitter:image", "thumbnail")
            if v: g.add((targetres, SDO.thumbnailUrl, Literal(v)))

            v = get_meta(soup, "author")
            if v: g.add((targetres, SDO.author, Literal(v)))

            v = get_meta(soup, "keywords")
            if v:
                for item in v.split(","):
                    if item: g.add((targetres, SDO.keywords, Literal(v)))

            return targetres
    else:
        print(f"Remote returned unknown contenttype: {contenttype}",file=sys.stderr)

    if data:
        datatype = detect_type(data)
        if datatype == 'schema':
            parse_jsonld_data(g, targetres, data, args)
            return targetres
        elif datatype == 'openapi':
            raise NotImplementedError #TODO
        else:
            print(f"Unable to detect data type of data returned by {url}",file=sys.stderr)

    return None
