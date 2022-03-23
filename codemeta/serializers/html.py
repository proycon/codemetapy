import sys
import os.path
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF, SKOS
from typing import Union, IO
from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx, SDO, CODEMETA, SOFTWARETYPES, SCHEMA_SOURCE, CODEMETA_SOURCE, CONTEXT, DUMMY_NS, SCHEMA_LOCAL_SOURCE, SCHEMA_SOURCE, CODEMETA_LOCAL_SOURCE, CODEMETA_SOURCE, STYPE_SOURCE, STYPE_LOCAL_SOURCE, init_context, SINGULAR_PROPERTIES, merge_graphs
from codemeta import __path__ as rootpath
from jinja2 import Environment, FileSystemLoader

def get_triples(g: Graph, res: Union[URIRef,BNode,None], prop, labelprop=SDO.name, abcsort=False):
    results = []
    havepos = False
    for _,_, res2 in g.triples((res, prop, None)):
        if isinstance(res2, Literal):
            results.append( (res2, res2, None) )
        else:
            pos = g.value(res2, SDO.position)
            if pos is not None:
                havepos = True
            label = g.value(res2, labelprop)
            if label:
                results.append((label, res2, pos))
            else:
                results.append((res2, res2, pos))
    if havepos:
        results.sort(key=lambda x: x[2])
    if abcsort:
        results.sort()
    return [ tuple(x[:2]) for x in results ]

def type_label(g: Graph, res: Union[URIRef,None]):
    label = g.value(res, RDF.type)
    if label:
        label = label.split("/")[-1]
        return label
    else:
        return ""

def serialize_to_html(g: Graph, res: Union[URIRef,None], args: AttribDict, contextgraph: Graph) -> dict:
    """Serialize to HTML with RDFa"""

    env = Environment( loader=FileSystemLoader(os.path.join(rootpath[0], 'templates')))
    if res:
        template = env.get_template("softwaresourcecode.html")
        return template.render(g=g, res=res, SDO=SDO,CODEMETA=CODEMETA, RDF=RDF, STYPE=SOFTWARETYPES, REPOSTATUS=REPOSTATUS, SKOS=SKOS, get_triples=get_triples, type_label=type_label, css=args.css, contextgraph=contextgraph, URIRef=URIRef)



