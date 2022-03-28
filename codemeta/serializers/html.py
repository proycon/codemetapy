import sys
import os.path
from datetime import datetime
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF, SKOS, RDFS
from typing import Union, IO
from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx, SDO, CODEMETA, SOFTWARETYPES, SCHEMA_SOURCE, CODEMETA_SOURCE, CONTEXT, DUMMY_NS, SCHEMA_LOCAL_SOURCE, SCHEMA_SOURCE, CODEMETA_LOCAL_SOURCE, CODEMETA_SOURCE, STYPE_SOURCE, STYPE_LOCAL_SOURCE, init_context, SINGULAR_PROPERTIES, merge_graphs, get_subgraph, get_last_component
from codemeta import __path__ as rootpath
from jinja2 import Environment, FileSystemLoader

def get_triples(g: Graph, res: Union[URIRef,BNode,None], prop, labelprop=SDO.name, abcsort=False):
    results = []
    havepos = False
    for _,_, res2 in g.triples((res, prop, None)):
        if isinstance(res2, Literal):
            results.append( (res2, res2, None, _get_sortkey2(g,res2)) )
        else:
            pos = g.value(res2, SDO.position)
            if pos is not None:
                havepos = True
            label = g.value(res2, labelprop)
            if label:
                results.append((label, res2, pos, _get_sortkey2(g,res2)))
            else:
                results.append((res2, res2, pos, _get_sortkey2(g,res2)))
    if havepos:
        try:
            results.sort(key=lambda x: str(x[2]))
        except TypeError: #protection against edge cases, leave unsorted then
            pass
    if abcsort:
        try:
            results.sort(key=lambda x: (x[0].lower(), x[3]))
        except TypeError: #protection against edge cases, leave unsorted then
            pass
    return [ tuple(x[:2]) for x in results ]


def _get_sortkey2(g: Graph, res: Union[URIRef,BNode,None]):
    #set a secondary sort-key for items with the very same name
    #ensures certain interface types are listed before others in case of a tie
    if (res, RDF.type, SDO.WebApplication):
        return  0
    elif (res, RDF.type, SDO.WebSite) in g:
        return  1
    elif (res, RDF.type, SDO.WebPage) in g:
        return  3
    elif (res, RDF.type, SDO.WebAPI) in g:
        return 4
    elif (res, RDF.type, SDO.CommandLineApplication) in g:
        return 5
    else:
        return 999


def get_index(g: Graph):
    results = []
    for res,_,_ in g.triples((None, RDF.type, SDO.SoftwareSourceCode)):
        label = g.value(res, SDO.name)
        if label:
            results.append((res, label))
    results.sort(key=lambda x: x[1].lower())
    return results



def parse_github_url(s):
    if not s: return None
    if s.endswith(".git"): s = s[:-4]
    if s.startswith("https://github.com/"):
        owner, repo = s.replace("https://github.com/","").split("/")
        return owner, repo
    return None, None

def get_badge(g: Graph, res: Union[URIRef,None], key):
    owner, repo = parse_github_url(g.value(res, SDO.codeRepository))
    if owner and repo:
        #github badges
        if key == "stars":
            yield f"https://img.shields.io/github/stars/{owner}/{repo}.svg?style=flat&color=5c7297", None, "Stars are an indicator of the popularity of this project on GitHub"
        elif key == "issues":
            yield f"https://img.shields.io/github/issues/{owner}/{repo}.svg?style=flat&color=5c7297", None, "The number of open issues on the issue tracker"
            yield f"https://img.shields.io/github/issues-closed/{owner}/{repo}.svg?style=flat&color=5c7297", None, "The number of closes issues on the issue tracker"
        elif key == "lastcommits":
            yield f"https://img.shields.io/github/last-commit/{owner}/{repo}.svg?style=flat&color=5c7297", None, "Last commit (main branch). Gives an indication of project development activity and rough indication of how up-to-date the latest release is."
            yield f"https://img.shields.io/github/commits-since/{owner}/{repo}/latest.svg?style=flat&color=5c7297&sort=semver", None, "Number of commits since the last release. Gives an indication of project development activity and rough indication of how up-to-date the latest release is."

def type_label(g: Graph, res: Union[URIRef,None]):
    label = g.value(res, RDF.type)
    if label:
        label = label.split("/")[-1]
        return label
    else:
        return ""


def get_interface_types(g: Graph, res: Union[URIRef,None], contextgraph: Graph, fallback= False):
    """Returns labels and definitions (2-tuple) for the interface types that this SoftwareSourceCode resource provides"""
    types =  set()
    for _,_,res3 in g.triples((res, RDF.type, None)):
        if res3 != SDO.SoftwareSourceCode:
            stype =  contextgraph.value(res3, RDFS.label)
            comment = contextgraph.value(res3, RDFS.comment) #used for definitions
            if stype:
                types.add((stype,comment))
    for _,_,res2 in g.triples((res, SDO.targetProduct, None)):
        for _,_,res3 in g.triples((res2, RDF.type, None)):
            stype =  contextgraph.value(res3, RDFS.label)
            comment = contextgraph.value(res3, RDFS.comment) #used for definitions
            if stype:
                types.add((stype,comment))

    if not types and fallback:
        types.add(("Unknown", "Sorry, we don't know what kind of interfaces this software provides. No interface types have been specified or could be automatically extracted."))
    return list(sorted(types))



def serialize_to_html(g: Graph, res: Union[URIRef,None], args: AttribDict, contextgraph: Graph) -> dict:
    """Serialize to HTML with RDFa"""

    if res:
        #Get the subgraph that focusses on this specific resource
        g = get_subgraph(g, res)

    env = Environment( loader=FileSystemLoader(os.path.join(rootpath[0], 'templates')), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    if res:
        if (res, RDF.type, SDO.SoftwareSourceCode) in g:
            template = "page_softwaresourcecode.html"
        elif (res, RDF.type, SDO.SoftwareApplication) in g \
             or (res, RDF.type, SDO.WebPage) in g \
             or (res, RDF.type, SDO.WebSite) in g \
             or (res, RDF.type, SDO.WebAPI) in g \
             or (res, RDF.type, SOFTWARETYPES.CommandLineApplication) in g \
             or (res, RDF.type, SOFTWARETYPES.SoftwareLibrary) in g:
            template = "page_targetproduct.html"
        elif (res, RDF.type, SDO.Person) in g \
            or (res, RDF.type, SDO.Organization):
            template = "page_person_or_org.html"
        else:
            template = "page_generic.html"
        index = []
    else:
        template = "index.html"
        index = get_index(g)
    template = env.get_template(template)
    return template.render(g=g, res=res, SDO=SDO,CODEMETA=CODEMETA, RDF=RDF,RDFS=RDFS,STYPE=SOFTWARETYPES, REPOSTATUS=REPOSTATUS, SKOS=SKOS, get_triples=get_triples, type_label=type_label, css=args.css, contextgraph=contextgraph, URIRef=URIRef, get_badge=get_badge, now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), index=index, get_interface_types=get_interface_types,baseuri=args.baseuri,baseurl=args.baseurl, toolstore=args.toolstore, get_last_component=get_last_component)



