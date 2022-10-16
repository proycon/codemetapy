import sys
import json
from rdflib import Graph, URIRef, BNode, Literal
from typing import Union, IO, Optional
from codemeta.common import PREFER_URIREF_PROPERTIES_SIMPLE, AttribDict, REPOSTATUS, license_to_spdx, SDO, SCHEMA_SOURCE, CODEMETA_SOURCE, SCHEMA_LOCAL_SOURCE, SCHEMA_SOURCE, CODEMETA_LOCAL_SOURCE, CODEMETA_SOURCE, STYPE_SOURCE, STYPE_LOCAL_SOURCE, IODATA_SOURCE, IODATA_LOCAL_SOURCE, init_context, SINGULAR_PROPERTIES, merge_graphs, generate_uri, bind_graph, DEVIANT_CONTEXT, remap_uri


def rewrite_context(context: Union[list,str], args: AttribDict) -> list:
    """Rewrite remote contexts to their local counterparts"""
    local_contexts = [ x[0] for x in init_context(args) ]
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
                elif v.startswith(("file://","//")) and v not in local_contexts:
                    raise Exception(f"Refusing to load non-authorized local context: {v}")

        #remove some legacy contexts which we may encounter but would choke on if parsed
        try:
            context.remove("https://github.com/CLARIAH/tool-metadata")
        except ValueError:
            pass
    elif isinstance(context, str):
        context = rewrite_context([context], args)
    #ammend context
    if SCHEMA_LOCAL_SOURCE not in context:
        context.append(SCHEMA_LOCAL_SOURCE)
    if STYPE_LOCAL_SOURCE not in context:
        context.append(STYPE_LOCAL_SOURCE)
    if IODATA_LOCAL_SOURCE not in context:
        context.append(IODATA_LOCAL_SOURCE)

    for key,value in DEVIANT_CONTEXT.items():
        if {key:value} not in context:
            context.append({key:value})
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


def skolemize(g: Graph, baseuri: Optional[str] = None):
    """In-place skolemization, turns blank nodes into uris"""
    #unlike Graph.skolemize, this one is in-place and edits the same graph rather than returning a copy
    if baseuri:
        authority = baseuri
        if authority[-1] != "/": authority += "/"
        basepath = "stub/"
    else:
        authority = "file://" #for compatibility with rdflib
        basepath = "/stub/"
    for s,p,o in g.triples((None,None,None)):
        if isinstance(s, BNode):
            g.remove((s,p,o))
            s = s.skolemize(authority=authority, basepath=basepath)
            g.add((s,p,o))
        if isinstance(o, BNode):
            g.remove((s,p,o))
            o = o.skolemize(authority=authority, basepath=basepath)
            g.add((s,p,o))


def parse_jsonld_data(g: Graph, res: Union[BNode, URIRef,None], data: dict, args: AttribDict) -> Union[str,None]:
    #preprocess json
    if '@context' not in data:
        data['@context'] = [ x[0] for x in init_context(args) ] + [DEVIANT_CONTEXT]
        print("    NOTE: Not a valid JSON-LD document, @context missing! Attempting to inject automatically...", file=sys.stderr)
    else:
        #rewrite context using the local schemas (also adds DEVIANT_CONTEXT)
        data['@context'] = rewrite_context(data['@context'], args)

    founduri = find_main_id(data)
    if not founduri and isinstance(res, URIRef):
        #JSON-LD doesn't specify an ID at all, inject one prior to parsing with rdflib
        inject_uri(data, res)
    if founduri:
        print(f"    Found main resource with URI {founduri}",file=sys.stderr)

    #reserialize after edits
    reserialised_data: str = json.dumps(data, indent=4)

    #parse as RDF, add to main graph, and skolemize (turn blank nodes into URIs)
    skolemize(g.parse(data=reserialised_data, format="json-ld", publicID=args.baseuri), args.baseuri)

    if not founduri and (res, SDO.identifier, None) in g and args.baseuri:
        return generate_uri(g.value(res, SDO.identifier), args.baseuri)
    elif founduri and not founduri.startswith("undefined:"):
        return founduri #return preferred uri
