import sys
import os.path
from datetime import datetime
import codemeta.parsers.gitapi
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF, SKOS, RDFS
from typing import Union, IO, Optional, Sequence
from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx, SDO, CODEMETA, SOFTWARETYPES, CODEMETAPY, SCHEMA_SOURCE, CODEMETA_SOURCE, CONTEXT, SCHEMA_LOCAL_SOURCE, SCHEMA_SOURCE, CODEMETA_LOCAL_SOURCE, CODEMETA_SOURCE, STYPE_SOURCE, STYPE_LOCAL_SOURCE, init_context, SINGULAR_PROPERTIES, merge_graphs, get_subgraph, get_last_component, query
from codemeta import __path__ as rootpath
import codemeta.parsers.gitapi
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


def get_index(g: Graph, restype=SDO.SoftwareSourceCode):
    results = []
    for res,_,_ in g.triples((None, RDF.type, restype)):
        label = g.value(res, SDO.name)
        if label:
            results.append((res, label))
    results.sort(key=lambda x: x[1].lower())
    return results



def is_resource(res) -> bool:
    return isinstance(res, (URIRef,BNode))


def get_badge(g: Graph, res: Union[URIRef,None], key):
    source =g.value(res, SDO.codeRepository).strip("/")
    cleaned_url = source
    prefix = ""
    if source.startswith("https://"):
        repo_kind = codemeta.parsers.gitapi.get_repo_kind(source)
        git_address = cleaned_url.replace('https://','').split('/')[0]
        prefix="https://"
        git_suffix=cleaned_url.replace(prefix + git_address,'')[1:]
        if "github" == repo_kind:
            #github badges
            if key == "stars":
                yield f"https://img.shields.io/github/stars/{git_suffix}.svg?style=flat&color=5c7297", None, "Stars are an indicator of the popularity of this project on GitHub"
            elif key == "issues":
                #https://shields.io/category/issue-tracking
                yield f"https://img.shields.io/github/issues/{git_suffix}.svg?style=flat&color=5c7297", None, "The number of open issues on the issue tracker"
                yield f"https://img.shields.io/github/issues-closed/{git_suffix}.svg?style=flat&color=5c7297", None, "The number of closes issues on the issue tracker"
            elif key == "lastcommits":
                yield f"https://img.shields.io/github/last-commit/{git_suffix}.svg?style=flat&color=5c7297", None, "Last commit (main branch). Gives an indication of project development activity and rough indication of how up-to-date the latest release is."
                yield f"https://img.shields.io/github/commits-since/{git_suffix}/latest.svg?style=flat&color=5c7297&sort=semver", None, "Number of commits since the last release. Gives an indication of project development activity and rough indication of how up-to-date the latest release is."
        elif "gitlab" == repo_kind:
            # https://docs.gitlab.com/ee/api/project_badges.html
            # https://github.com/Naereen/badges
            if key == "lastcommits":
                #append all found badges at the end
                encoded_git_suffix=git_suffix.replace('/', '%2F')
                response = codemeta.parsers.gitapi.rate_limit_get(f"{prefix}{git_address}/api/v4/projects/{encoded_git_suffix}/badges", "gitlab")
                if response:
                    response = response.json()
                    for badge in response:
                       if badge['kind'] == 'project': 
                        #or rendered_image_url field?
                        image_url=badge['image_url'] 
                        name=badge['name']
                        yield f"{image_url}", f"{name}", f"{name}"  
     


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



def serialize_to_html( g: Graph, res: Union[Sequence,URIRef,None], args: AttribDict, contextgraph: Graph, sparql_query: Optional[str] = None,  **kwargs) -> dict:
    """Serialize to HTML with RDFa"""
    if res and not isinstance(res, (list,tuple)):
        #Get the subgraph that focusses on this specific resource
        g = get_subgraph(g, [res])

    env = Environment( loader=FileSystemLoader(os.path.join(rootpath[0], 'templates')), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    if res and not isinstance(res, (list,tuple)):
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
        template = kwargs.get("indextemplate","index.html")
        if isinstance(res, (list,tuple)):
            index = [ (x, g.value(x, SDO.name)) for x in res ]
            res = None
        elif sparql_query:
            index = query(g, sparql_query)
        else:
            index = get_index(g)
    template = env.get_template(template)
    return template.render(g=g,res=res, SDO=SDO,CODEMETA=CODEMETA, CODEMETAPY=CODEMETAPY, RDF=RDF,RDFS=RDFS,STYPE=SOFTWARETYPES, REPOSTATUS=REPOSTATUS, SKOS=SKOS, get_triples=get_triples, type_label=type_label, css=args.css, contextgraph=contextgraph, URIRef=URIRef, get_badge=get_badge, now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), index=index, get_interface_types=get_interface_types,baseuri=args.baseuri,baseurl=args.baseurl, toolstore=args.toolstore, get_last_component=get_last_component, is_resource=is_resource, int=int, range=range, **kwargs)



