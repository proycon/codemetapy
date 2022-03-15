import sys
import json
from rdflib import Graph, URIRef, BNode, Literal
from typing import Union, IO
from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx, SDO, SCHEMA_SOURCE, CODEMETA_SOURCE, CONTEXT, DUMMY_NS, SCHEMA_LOCAL_SOURCE, SCHEMA_SOURCE, CODEMETA_LOCAL_SOURCE, CODEMETA_SOURCE, STYPE_SOURCE, STYPE_LOCAL_SOURCE, init_context


def rewrite_context(context):
    """Rewrite remote contexts to their local counterparts"""
    if isinstance(context, list):
        for i, v in enumerate(context):
            if isinstance(v, str):
                if v.startswith("https://schema.org") or v.startswith("http://schema.org") or v == SCHEMA_SOURCE:
                    context[i] = SCHEMA_LOCAL_SOURCE
                elif v.startswith("https://doi.org/10.5063/schema") or v == CODEMETA_SOURCE:
                    context[i] = CODEMETA_LOCAL_SOURCE
                elif v.startswith(STYPE_SOURCE):
                    context[i] = STYPE_LOCAL_SOURCE
                elif v.startswith("file://") and v not in (SCHEMA_LOCAL_SOURCE, CODEMETA_LOCAL_SOURCE, STYPE_LOCAL_SOURCE):
                    raise Exception(f"Refusing to load non-authorized local context: {v}")

        #remove some legacy contexts which we may encounter but would choke on if parsed
        try:
            context.remove("https://github.com/CLARIAH/tool-metadata")
        except ValueError:
            pass

def parse_jsonld(g: Graph, res: Union[BNode, URIRef,None], file_descriptor: IO, args: AttribDict) -> Union[str,None]:
    #download schemas needed for context
    data = json.load(file_descriptor)
    return parse_jsonld_data(g,res, data, args)


def parse_jsonld_data(g: Graph, res: Union[BNode, URIRef,None], data: dict, args: AttribDict) -> Union[str,None]:
    #download schemas needed for context
    init_context()

    #preprocess json
    if '@context' not in data:
        data['@context'] = CONTEXT
        print("WARNING: Not a valid JSON-LD document, @context missing! Attempting to inject automatically...", file=sys.stderr)

    #rewrite context using the local schemas
    rewrite_context(data['@context'])

    prefuri = None
    if isinstance(res, URIRef):
        if '@graph' in data and len(data['@graph']) == 1:
            #force same ID as the resource (to facilitate merging), but return the preferred URI to be used on serialisation again
            for k in ('id','@id'):
                if k in data['@graph'][0]:
                    prefuri = data['@graph'][0][k]
            data['@graph'][0]["@id"] = str(res)
            if 'id' in data['@graph'][0]: del data['@graph'][0]['id'] #prefer @id over id
        elif '@id' in data or 'id' in data:
            #force same ID as the resource (to facilitate merging), but return the preferred URI to be used on serialisation again
            for k in ('id','@id'):
                if k in data:
                    prefuri = data[k]
            data["@id"] = str(res)
            if 'id' in data: del data['id'] #prefer @id over id
        elif '@graph' not in data:
            data["@id"] = str(res)

    #reserialize
    data = json.dumps(data, indent=4)

    #and parse with rdflib
    g.parse(data=data, format="json-ld", context=CONTEXT, publicID=DUMMY_NS)
    # ^--  We assign an a dummy namespace to items that are supposed to be an ID but aren't

    if not (isinstance(prefuri,str) and prefuri.startswith("undefined:")):
        return prefuri #return preferred uri
