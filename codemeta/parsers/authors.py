from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal
from codemeta.common import (
    AttribDict,
    add_authors,
    SDO
)


def parse_authors(
    g: Graph, res: Union[URIRef, BNode], file: IO, args: AttribDict, property=SDO.author
):
    """Parses a plain-text file of people, one person (author/contributor/maintainer) per line, may additionally contain e-mail addresses <> and (urls), in that order"""
    for i, line in enumerate(file.readlines()):
        line = line.strip()
        if line and line[0] != "#":
            add_authors(
                g,
                res,
                line,
                single_author=True,
                baseuri=args.baseuri,
                property=property,
                skip_duplicates=True,
                position=i + 1,
            )
