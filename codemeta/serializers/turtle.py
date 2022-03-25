import sys
import json
from codemeta.common import SDO, get_subgraph
from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal


def serialize_to_turtle(g: Graph, res: Union[URIRef,None]) -> dict:
    """Serializes the RDF graph to Turtle"""
    if res:
        #Get the subgraph that focusses on this specific resource
        g = get_subgraph(g, res)

    g.bind('sdo', SDO)
    return g.serialize(format='turtle', auto_compact=True)
