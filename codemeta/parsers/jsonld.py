import json
from rdflib import Graph, URIRef, BNode, Literal
from typing import Union, IO
from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx, SDO, SCHEMA_SOURCE

#pylint: disable=W0621
#def parsecodemeta(g: Graph, res: Union[URIRef, BNode], file_descriptor: IO, args: AttribDict) -> dict:
#    g.parse(file=file_descriptor, format="jsonld")
#
#    """Parses a codemeta.json file (json-ld)"""
#    data = json.load(file_descriptor)
#    for key, value in data.items():
#        if key == "developmentStatus":
#            if args.with_repostatus and value.strip().lower() in REPOSTATUS:
#                #map to repostatus vocabulary
#                data[key] = "https://www.repostatus.org/#" + REPOSTATUS[value.strip().lower()]
#        elif key == "license":
#            data[key] = license_to_spdx(value, args)
#    return data

def parse_jsonld(g: Graph, res: Union[BNode, URIRef,None], file_descriptor: IO, args: AttribDict) -> Union[str,None]:
    data = json.load(file_descriptor)

    #preprocess json
    if '@context' not in data:
        raise Exception("Not a valid JSON-LD document, @context missing!")

    #schema.org doesn't do proper content negotation, patch on the fly:
    if isinstance(data['@context'], list):
        for v in ("https://schema.org/","http://schema.org/","https://schema.org","http://schema.org"):
            i = data['@context'].find(v)
            if i != -1:
                data['@context'][i] = SCHEMA_SOURCE

    prefuri = None
    if isinstance(res, URIRef):
        if '@graph' in data and len(data['@graph']) == 1:
            #force same ID as the resource (to facilitate merging), but return the preferred URI to be used on serialisation again
            for k in ('id','@id'):
                if k in data['@graph'][0]:
                    prefuri = data['@graph'][0][k]
                    data[k] = str(res)
        elif '@id' in data or 'id' in data:
            #force same ID as the resource (to facilitate merging), but return the preferred URI to be used on serialisation again
            for k in ('id','@id'):
                if k in data:
                    prefuri = data[k]
                    data[k] = str(res)

    #reserialize
    data = json.dumps(data, indent=4, encoding='utf-8')

    #and parse with rdflib
    g.parse(data=data, format="json-ld")

    return prefuri
