import sys
import json
from codemeta.common import SDO, get_subgraph
from typing import Union, IO, Sequence
from rdflib import Graph, URIRef, BNode, Literal


def serialize_to_turtle(g: Graph, res: Union[Sequence,URIRef,None]) -> str:
    """Serializes the RDF graph to Turtle"""
    if res:
        #Get the subgraph that focusses on this specific resource (may be multiple) 
        #TODO: this may not work well with ordered lists yet!!
        if isinstance(res, (list,tuple)):
            g = get_subgraph(g, res)
        else:
            g = get_subgraph(g, [res])

    g.bind('sdo', SDO)
    return g.serialize(format='turtle', auto_compact=True)
