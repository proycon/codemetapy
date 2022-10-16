import sys
import json
import os.path
from typing import Union, Iterator
import requests
import yaml
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, SDO, generate_uri, add_authors, get_last_component
from codemeta.parsers.jsonld import parse_jsonld_data
from bs4 import BeautifulSoup


class MiddlewareObstructionException(Exception):
    pass

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
        for value in  soup.find("head").find_all("meta", itemprop=key):
            if value.get('content'):
                return value.get('content')
        for value in  soup.find("head").find_all("meta", property=key):
            if value.get('content'):
                return value.get('content')
        for value in soup.find("head").find_all("meta", {"name": key }):
            if value.get('content'):
                return value.get('content')
    return default


def get_soup(soup,elementname, attribname=None):
    for e in soup.find_all(elementname):
        if attribname:
            v = e.get(attribname)
            return v
        elif e.text:
            return e.text
    return ""

def parse_clam(soup):
    return {
        "name": get_soup(soup,"clam","name"),
        "url": get_soup(soup, "clam", "baseurl"),
        "description": get_soup(soup, "description"),
        "author": get_soup(soup, "author"),
        "provider": get_soup(soup, "affiliation"),
        "email": get_soup(soup, "email"),
        "version": get_soup(soup, "version"),
        "license": get_soup(soup, "license")
    }

def detect_sso_middleware(r: requests.Response):
    return r.history and 'location' in r.history[-1].headers and r.history[-1].headers['location'].lower().find("shibboleth") != -1

def add_missing_url_scheme(data, original_url: str):
    """Add URL scheme when missing"""
    if isinstance(data, dict):
        return {k: add_missing_url_scheme(v, original_url) for k, v in data.items()}
    elif isinstance(data, (list,tuple)):
        return [ add_missing_url_scheme(v, original_url) for v in data ]
    elif isinstance(data, str) and data.startswith("//"):
        return original_url.split("/")[0] + data
    return data

def parse_web(g: Graph, res: Union[URIRef, BNode], url, args: AttribDict) -> Iterator[Union[URIRef,BNode,None]]:
    r = requests.get(url, headers={ "Accept": "application/json+ld;q=1.0,application/json;q=0.9,application/x-yaml;q=0.8,application/xml;q=0.7;text/html;q=0.6;text/plain;q=0.1" })
    r.raise_for_status()
    contenttype = r.headers.get('content-type',"").split(';')[0].strip()
    print(f"    Service replied with content-type {contenttype}",file=sys.stderr)
    datatype = None
    data = None


    if contenttype in ("application/json", "application/ld+json") or url.endswith(".json") or url.endswith(".jsonld"):
        print("    Parsing json...",file=sys.stderr)
        data = json.loads(r.text)
    elif contenttype in ("application/x-yaml", "text/yaml") or url.endswith(".yml") or url.endswith(".yaml"):
        print("    Parsing yaml...",file=sys.stderr)
        #may be OpenAPI
        with open(r.text,'r', encoding="utf-8") as f:
            data = yaml.load(f, yaml.Loader)
    elif contenttype == "text/html":
        if detect_sso_middleware(r):
            #we've been redirected to a login page directly
            #so we can't extract any useful metadata
            #we add a dummy entry:
            raise MiddlewareObstructionException(f"Unable to extract metadata from {url} because it immediately redirects to an external (SSO) login page rather than a proper landing page")
        #normal behaviour
        print("    Parsing html...",file=sys.stderr)
        soup = BeautifulSoup(r.text, 'html.parser')
        scriptblock = soup.find("script", {"type":"application/ld+json"})
        if scriptblock:
            #Does the site provide proper JSON-LD metadata itself?
            print("    Found a json-ld script block",file=sys.stderr)
            data = json.loads("".join(scriptblock.contents))            
        else:
            print("    Parsing site metadata",file=sys.stderr)
            name = get_meta(soup, "schema:name", "og:site_name", "og:title", "twitter:title")
            if not name and soup.title:
                name = soup.title.text
                name = name.strip()

            if args.with_stypes:
                targetres = URIRef(generate_uri(name, baseuri=args.baseuri,prefix="webapplication"))
            else:
                targetres = res
            if name:
                g.add((targetres, SDO.name, Literal(name)))

            targetrestype = SDO.WebApplication
            for e in (soup.find("head"), soup.find("html")):
                itemtype = e.get("itemtype")
                if itemtype in ("https://schema.org/WebApplication", "http://schema.org/WebApplication"):
                    targetrestype = SDO.WebApplication
                elif itemtype in ("https://schema.org/WebPage", "http://schema.org/WebPage"):
                    targetrestype = SDO.WebPage
                elif itemtype in ("https://schema.org/WebSite", "http://schema.org/WebSite"):
                    targetrestype = SDO.WebSite
                elif itemtype in ("https://schema.org/WebAPI", "http://schema.org/WebAPI"):
                    targetrestype = SDO.WebAPI
                if itemtype:
                    break

            g.add((targetres, RDF.type, targetrestype))
            g.add((targetres, SDO.url, Literal(get_meta(soup, "og:url", "url", default=url))))

            v = get_meta(soup, "schema:description", "og:description", "twitter:description", "description")
            if v: g.add((targetres, SDO.description, Literal(v)))

            v = get_meta(soup, "schema:url")
            if v: g.add((targetres, SDO.url, Literal(add_missing_url_scheme(v,url))))

            v = get_meta(soup, "schema:thumbnailUrl", "og:image", "twitter:image", "thumbnail")
            if v: g.add((targetres, SDO.thumbnailUrl, Literal(add_missing_url_scheme(v,url))))

            v = get_meta(soup, "schema:author", "author")
            if v: add_authors(g, targetres, v, baseuri=args.baseuri)

            v = get_meta(soup, "schema:keywords", "keywords")
            if v:
                for item in v.split(","):
                    item = item.strip()
                    if item: g.add((targetres, SDO.keywords, Literal(item)))

            yield targetres
            data = None
    elif contenttype in ("application/xml", "text/xml"):
        soup = BeautifulSoup(r.text, 'xml')
        if soup.find("clam") and args.with_stypes:
            print("    Parsing CLAM metadata",file=sys.stderr)
            clamdata = parse_clam(soup)
            for restype in (SDO.WebApplication, SDO.WebAPI):
                assert clamdata['name']
                targetres = URIRef(generate_uri(clamdata['name'], baseuri=args.baseuri,prefix=get_last_component(str(restype).lower())))
                g.add((targetres, RDF.type, restype))
                if clamdata['name']:
                    g.add((targetres, SDO.name, Literal(clamdata['name'])))
                if clamdata['description']:
                    g.add((targetres, SDO.description, Literal(clamdata['description'])))
                if clamdata['author']:
                    add_authors(g, targetres, clamdata['author'], baseuri=args.baseuri)
                if clamdata['email']:
                    g.add((targetres, SDO.email, Literal(clamdata['email'])))
                if clamdata['url']:
                    g.add((targetres, SDO.url, Literal(clamdata['url'])))
                    if restype == SDO.WebAPI:
                        g.add((targetres, SDO.documentation, Literal(os.path.join(clamdata['url'],"info")))) #Proposed in schemaorg/schemaorg#1423
                else:
                    g.add((targetres, SDO.url, Literal(url)))
                if clamdata['provider']:
                    g.add((targetres, SDO.provider, Literal(clamdata['provider'])))
                if clamdata['version']:
                    g.add((targetres, SDO.version, Literal(clamdata['version'])))
                yield targetres
            data = None
        else:
            print("    Remote returned unrecognized XML",file=sys.stderr)
    else:
        print(f"    Remote returned unknown contenttype: {contenttype}",file=sys.stderr)

    if data:
        datatype = detect_type(data)
        if datatype == 'schema':
            if args.with_stypes:
                targetres = URIRef(generate_uri(baseuri=args.baseuri,prefix="webapplication"))
            else:
                targetres = res
            data = add_missing_url_scheme(data, url)
            parse_jsonld_data(g, targetres, data, args)
            yield targetres
        elif datatype == 'openapi':
            raise NotImplementedError #TODO
        else:
            print(f"    Unable to detect data type of data returned by {url}",file=sys.stderr)
