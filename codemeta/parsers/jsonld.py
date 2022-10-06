import sys
import json
from rdflib import Graph, URIRef, BNode, Literal
from typing import Union, IO
from codemeta.common import PREFER_URIREF_PROPERTIES_SIMPLE, AttribDict, REPOSTATUS, license_to_spdx, SDO, SCHEMA_SOURCE, CODEMETA_SOURCE, SCHEMA_LOCAL_SOURCE, SCHEMA_SOURCE, CODEMETA_LOCAL_SOURCE, CODEMETA_SOURCE, STYPE_SOURCE, STYPE_LOCAL_SOURCE, IODATA_SOURCE, IODATA_LOCAL_SOURCE, init_context, SINGULAR_PROPERTIES, merge_graphs, generate_uri, bind_graph


def rewrite_context(context: Union[list,str]) -> list:
    """Rewrite remote contexts to their local counterparts"""
    if isinstance(context, list):
        for i, v in enumerate(context):
            if isinstance(v, str):
                if v.startswith(("https://schema.org", "http://schema.org", "//schema.org")) or v == SCHEMA_SOURCE:
                    context[i] = SCHEMA_LOCAL_SOURCE
                elif v.startswith("https://doi.org/10.5063/schema") or v == CODEMETA_SOURCE:
                    context[i] = CODEMETA_LOCAL_SOURCE
                elif v.startswith(STYPE_SOURCE):
                    context[i] = STYPE_LOCAL_SOURCE
                elif v.startswith(IODATA_LOCAL_SOURCE):
                    context[i] = IODATA_LOCAL_SOURCE
                elif v.startswith(("file://","//")) and v not in (SCHEMA_LOCAL_SOURCE, CODEMETA_LOCAL_SOURCE, STYPE_LOCAL_SOURCE, IODATA_LOCAL_SOURCE):
                    raise Exception(f"Refusing to load non-authorized local context: {v}")

        #remove some legacy contexts which we may encounter but would choke on if parsed
        try:
            context.remove("https://github.com/CLARIAH/tool-metadata")
        except ValueError:
            pass
    elif isinstance(context, str):
        context = rewrite_context([context])
    #ammend context
    if SCHEMA_LOCAL_SOURCE not in context:
        context.append(SCHEMA_LOCAL_SOURCE)
    if STYPE_LOCAL_SOURCE not in context:
        context.append(STYPE_LOCAL_SOURCE)
    if IODATA_LOCAL_SOURCE not in context:
        context.append(IODATA_LOCAL_SOURCE)
    return context

def rewrite_schemeless_uri(data: dict) -> dict:
    for key, value in data.items():
        if key in PREFER_URIREF_PROPERTIES_SIMPLE:
            if isinstance(value, dict):
                data[key] = rewrite_schemeless_uri(value)
            elif isinstance(value, list):
                data[key] = [ "https:" + x if isinstance(x,str) and x.startswith("//") else x for x in value ]
            elif isinstance(value, str) and value.startswith("//"):
                data[key] = "https:" + data[key]
    return data


def parse_jsonld(g: Graph, res: Union[BNode, URIRef,None], file_descriptor: IO, args: AttribDict) -> Union[str,None]:
    data = json.load(file_descriptor)
    return parse_jsonld_data(g,res, data, args)


def find_main_id(data: dict)  -> Union[str,None]:
    """Find the main URI in the JSON-LD resource, if there is only one, return None otherwise"""
    if '@graph' in data and len(data['@graph']) == 1:
        root = data['@graph'][0]
    else:
        root = data

    for k in ('@id','id'):
        if k in root:
            return root[k]

    return None


def inject_uri(data: dict, res: URIRef):
    if '@graph' in data and len(data['@graph']) == 1:
        data['@graph'][0]["@id"] = str(res)
        print(f"    Injected URI {res}",file=sys.stderr)
    elif '@graph' in data and len(data['@graph']) == 0:
        print("    NOTE: Graph is empty!",file=sys.stderr)
    elif '@graph' not in data:
        data["@id"] = str(res)
        print(f"    Injected URI {res}",file=sys.stderr)
    else:
        raise Exception("JSON-LD file does not describe a single resource (did you mean to use --graph instead?)")



def parse_jsonld_data(g: Graph, res: Union[BNode, URIRef,None], data: dict, args: AttribDict) -> Union[str,None]:
    #download schemas needed for context
    init_context()

    #preprocess json
    if '@context' not in data:
        data['@context'] = [ x[0] for x in init_context(False, args.addcontext) ]
        print("    NOTE: Not a valid JSON-LD document, @context missing! Attempting to inject automatically...", file=sys.stderr)

    #rewrite context using the local schemas
    data['@context'] = rewrite_context(data['@context'])

    #convert schemeless *absolute* URLs (//, otherwise rdflib will interpret them as local). URLs starting with a single slash will be left untouched
    data = rewrite_schemeless_uri(data)


    founduri = find_main_id(data)
    if not founduri and isinstance(res, URIRef):
        #JSON-LD doesn't specify an ID at all, inject one prior to parsing with rdflib
        inject_uri(data, res)
    else:
        print(f"    Found main resource with URI {founduri}",file=sys.stderr)

    #reserialize
    data: str = json.dumps(data, indent=4)

    g2 = Graph()
    #and parse with rdflib
    g2.parse(data=data, format="json-ld", context=[ x[0] for x in init_context(False, args.addcontext) ])

    #give all blank nodes a stub URI (i.e. skolemize) to facilitate merging
    g3 = Graph()
    bind_graph(g3)
    if args.baseuri:
        authority = args.baseuri
        if authority[-1] != "/": authority += "/"
        basepath = "stub/"
    else:
        authority = "/"
        basepath = "stub/"
    g3 = g2.skolemize(authority=authority, basepath=basepath)

    merge_graphs(g,g3, map_uri_from=founduri, map_uri_to=str(res) if res else None, args=args)

    if not founduri and (res, SDO.identifier, None) in g and args.baseuri:
        return generate_uri(g.value(res, SDO.identifier), args.baseuri)
    elif founduri and not founduri.startswith("undefined:"):
        return founduri #return preferred uri
