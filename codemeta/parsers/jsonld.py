import sys
import json
import os
from rdflib import Graph, URIRef, BNode, Literal
from typing import Union, IO, Optional
from codemeta.common import  PREFER_URIREF_PROPERTIES, AttribDict, REPOSTATUS, license_to_spdx, SDO, CODEMETA, SCHEMA_SOURCE, CODEMETA_SOURCE, SCHEMA_LOCAL_SOURCE, SCHEMA_SOURCE, CODEMETA_LOCAL_SOURCE, CODEMETA_SOURCE, STYPE_SOURCE, STYPE_LOCAL_SOURCE, IODATA_SOURCE, IODATA_LOCAL_SOURCE, init_context, SINGULAR_PROPERTIES, generate_uri, bind_graph, DEVIANT_CONTEXT


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
        if 'id' in data['@graph'][0]: del data['@graph'][0]['id']
        print(f"    Injected (possibly temporary) URI {res}",file=sys.stderr)
    elif '@graph' in data and len(data['@graph']) == 0:
        print("    NOTE: Graph is empty!",file=sys.stderr)
    elif '@graph' not in data:
        data["@id"] = str(res)
        if 'id' in data: del data['id']
        print(f"    Injected (possibly temporary) URI {res}",file=sys.stderr)
    else:
        raise Exception("JSON-LD file does not describe a single resource (did you mean to use --graph instead?)")


def compute_hash(g: Graph, s: Union[URIRef,BNode], history: Optional[set] = None) -> int:
    """Computes a content hash for all contents in a resource"""
    values = []
    if not history: 
        history = set(s)
    else:
        history.add(s)
    if isinstance(s, URIRef):
        values.append(s)
    for s,p,o in g.triples((s,None,None)):
        values += [p,o]
        if isinstance(o, (URIRef,BNode)) and o not in history and (o,None,None) in g:
            #recursion step
            values.append( compute_hash(g, o, history) )
    return hash(tuple(values))
        


def skolemize(g: Graph, baseuri: Optional[str] = None):
    """In-place skolemization, turns blank nodes into uris"""
    #unlike Graph.skolemize, this one is in-place and edits the same graph rather than returning a copy
    #also, if blank nodes have identical content, they receive the same stub ID based on a hash of the content

    if baseuri:
        authority = baseuri
        if authority[-1] != "/": authority += "/"
        basepath = "stub/"
    else:
        authority = "file://" #for compatibility with rdflib
        basepath = "/stub/"

    hashes = {}
    for s,p,o in g.triples((None,None,None)):
        if isinstance(s, BNode) and s not in hashes:
            hashes[s] = compute_hash(g,s)

    for s,p,o in g.triples((None,None,None)):
        if isinstance(s, BNode):
            g.remove((s,p,o))
            #skolemize using hashes
            s = URIRef(authority + basepath + "H" + "%016x" % hashes[s])
            g.add((s,p,o))
        if isinstance(o, BNode):
            g.remove((s,p,o))
            if o in hashes:
                #skolemize using hashes
                o = URIRef(authority + basepath + "H" + "%016x" % hashes[o])
            else:
                o = o.skolemize(authority=authority, basepath=basepath)
            g.add((s,p,o))

def correct_wrong_uris(g:Graph, baseuri: Optional[str]):
    """Certain Literals should be URIRefs when possible, and some URIRefs are misinterpreted by rdflib and should be Literals."""
    for s,p,o in g:
        new_obj = o
        if str(o).startswith("//"):
            #we interpret this as a schemeless URL and will blatantly assume HTTPS (which is the most common source when fetching info, but this may be wrong)
            if isinstance(o, Literal):
                new_obj = Literal("https:" + o)
            elif isinstance(o, URIRef):
                new_obj = URIRef("https:" + o)
        if p in PREFER_URIREF_PROPERTIES:
            #turn Literals into URIRef for properties that prefer a URIRef
            if isinstance(o, Literal) and str(o).startswith("http"):
                new_obj =  URIRef(str(o))

            #these often get misinterpreted if they're not URIs, because rdflib prepends its baseuri
            cwd = os.getcwd()
            prefixes = [baseuri, cwd + "/", "file://" +cwd + "/", cwd, "file://" +cwd, "file://"]
            for prefix in prefixes:
                if prefix and str(o).startswith(prefix):
                    new_obj =  Literal(str(o)[len(prefix):])
                    break
        #commit the change
        if new_obj != o:
            g.remove((s,p,o))
            g.add((s,p,new_obj))


def parse_jsonld_data(g: Graph, res: Union[BNode, URIRef,None], data: dict, args: AttribDict, baseuri: Optional[str] = None) -> Union[str,None]:
    #preprocess json
    if '@context' not in data:
        data['@context'] = [ x[0] for x in init_context(args) ] + [DEVIANT_CONTEXT]
        print("    NOTE: Not a valid JSON-LD document, @context missing! Attempting to inject automatically...", file=sys.stderr)
    else:
        #rewrite context using the local schemas (also adds DEVIANT_CONTEXT)
        data['@context'] = rewrite_context(data['@context'], args)

    founduri = find_main_id(data)
    if founduri:
        print(f"    Found main resource with URI {founduri}",file=sys.stderr)
    if isinstance(res, URIRef) and founduri != str(res):
        #we're handling a single resource. Inject our own URI prior to parsing with rdflib
        inject_uri(data, res)

    #reserialize after edits
    reserialised_data: str = json.dumps(data, indent=4)

    #parse as RDF, add to main graph, and skolemize (turn blank nodes into URIs)
    skolemize(g.parse(data=reserialised_data, format="json-ld", publicID=baseuri if baseuri else args.baseuri), args.baseuri)
    correct_wrong_uris(g, args.baseuri)

    return founduri #return found uri (if any)
