import sys
import json
import os.path
from typing import Union, IO, Sequence
from rdflib import Graph, URIRef, BNode, Literal
from copy import copy
from codemeta.common import AttribDict, license_to_spdx, SDO, CODEMETA_SOURCE, CODEMETA_LOCAL_SOURCE, SCHEMA_SOURCE, SCHEMA_LOCAL_SOURCE, STYPE_SOURCE, STYPE_LOCAL_SOURCE, IODATA_SOURCE, IODATA_LOCAL_SOURCE, init_context, REPOSTATUS_LOCAL_SOURCE, REPOSTATUS_SOURCE, get_subgraph, PREFER_URIREF_PROPERTIES_SIMPLE, TMPDIR

def flatten_singletons(data): #TODO: no longer used, remove
    """Recursively flattens singleton ``key: { "@id": uri }`` instances to ``key: uri``"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                if '@id' in value and len(value) == 1:
                    data[key] = value['@id']
                elif 'id' in value and len(value) == 1:
                    data[key] = value['id']
                else:
                    data[key] = flatten_singletons(data[key])
            else:
                data[key] = flatten_singletons(data[key])
        return data
    elif isinstance(data, (list,tuple)):
        return [ x['@id'] if isinstance(x, dict) and '@id' in x and len(x) == 1 else flatten_singletons(x) for x in data ]
    else:
        return data

def remove_blank_ids(data):
    """Recursively remove all blank node IDs"""
    if isinstance(data, dict):
        if '@id' in data and data['@id'].startswith("_:"):
            del data['@id']
        if 'id' in data and data['id'].startswith("_:"):
            del data['id']
        return { k: remove_blank_ids(v) for k,v in data.items() }
    elif isinstance(data, (list, tuple)):
        return [ remove_blank_ids(v) for v in data ]
    else:
        return data

def alt_sort_key(data) -> str:
    if isinstance(data, dict):
        if 'name' in data:
            return data['name']
        if '@id' in data:
            return data['@id']
        if 'identifier' in data:
            return data['identifier']
    elif isinstance(data, str):
        return data
    return "~" #just a high alphanumeric character so it ends up after normal (ascii) stuff


def sort_by_position(data):
    """If list items have a position (schema:position) index, make sure to use it for sorting. If not, sort alphabetically of name of id"""
    if isinstance(data, (list, tuple)):
        if any( isinstance(x, dict) and 'position' in x for x in data ):
            try:
                return list(sorted( ( sort_by_position(x) for x in data) , key=lambda x: x['position'] if isinstance(x, dict) and 'position' in x else 99999999 ) )
            except TypeError: #in rare cases this might fail because of some inconsistency, return unsorted then
                return [ sort_by_position(x) for x in data ]
        else:
            try:
                return list(sorted( ( sort_by_position(x) for x in data) , key=lambda x: alt_sort_key(x) ) )
            except TypeError: #in rare cases this might fail because of some inconsistency, return unsorted then
                return [ sort_by_position(x) for x in data ]
    elif isinstance(data, dict):
        for key, value in data.items():
            data[key] = sort_by_position(value)
    return data


def normalize_schema_org(g: Graph):
    #there is debate on whether to use https of http for schema.org,
    #codemeta 2.0 uses http still in their context so we force that here too
    #(https://schema.org/docs/faq.html#19)
    for s, p, o in g.triples():
        if str(s).startswith("https://schema.org"):
            g.remove((s, p, o))
            g.add((URIRef(str(s).replace("https", "http")), p, o))

        if str(p).startswith("https://schema.org"):
            g.remove((s, p, o))
            g.add((s, URIRef(str(p).replace("https", "http")), p, o))

        if str(o).startswith("https://schema.org"):
            g.remove((s, p, o))
            g.add((s, p, URIRef(str(o).replace("https", "http"))))

def cleanup(data):
    """Recursively removes namespace prefixes from dictionary keys and use @id and @type rather than the id/type aliases"""
    if isinstance(data, dict):
        if 'id' in data:
            data['@id'] = data['id']
            del data['id']
        if 'type' in data:
            data['@type'] = data['type']
            del data['type']
        return { key.replace('schema:','').replace('http://schema.org/','').replace('codemeta:','').replace('stypes:','') : cleanup(value) for key, value in data.items() }
    elif isinstance(data, (list,tuple)):
        return [ cleanup(x) for x in data ]
    else:
        return data

def find_main(data, res: Union[URIRef,None]):
    """Find the main item in the graph"""
    if '@graph' in data:
        for item in data:
            if isinstance(item, dict) and item.get("@id") == str(res):
                return item, data
        return None, None
    else:
        return data, None

def expand_implicit_id_nodes(data, idref_properties):
    """Turn nodes like `key: uri` into `key: { "@id": uri }`"""
    if isinstance(data, dict):
        for k, v in data.items():
            if k in idref_properties and isinstance(v, str) and v.startswith(("http","_","/")):
                data[k] = {"@id": v }
            elif k in idref_properties and isinstance(v, list):
                data[k] = [ {"@id": e } if isinstance(e, str) and e.startswith(("http","_","/")) else expand_implicit_id_nodes(e, idref_properties) if isinstance(e, dict) else e for e in v ]
            elif isinstance(v, dict):
                data[k] = expand_implicit_id_nodes(data[k], idref_properties)
            elif isinstance(v, list):
                data[k] = [ expand_implicit_id_nodes(e, idref_properties) if isinstance(e,dict) else e for e in v ]
    return data

def do_object_framing(data: dict, res_id: str):
    """JSON-LD object framing. Rdflib's json-ld serialiser doesn't implement this so we do this ourselves"""
    assert '@graph' in data
    itemmap = {} #mapping from ids to python dicts
    gather_items(data['@graph'], itemmap)
    #print("DEBUG itemmap", repr(itemmap))
    if res_id not in itemmap:
        raise Exception("Resource not found in tree, framing not possible")
    embed_items(itemmap[res_id], itemmap, {res_id,})
    return itemmap[res_id]
        
def gather_items(data, itemmap: dict):
    """Gather all items from a JSON-LD tree, auxiliary function for object framing"""
    if isinstance(data, list): 
        for item in data:
            gather_items(item, itemmap)
    elif isinstance(data, dict): 
        for idkey in ('@id', 'id'):
            if idkey in data and len(data) > 1 and isinstance(idkey, str):
                item_id = data[idkey]
                if idkey in itemmap:
                    #print(f"DEBUG gathered {item_id} (duplicate)")
                    itemmap[item_id].update(data)
                else:
                    #print(f"DEBUG gathered {item_id} (new)")
                    itemmap[item_id] = data
        for v in data.values():
            gather_items(v, itemmap)

def embed_items(data, itemmap: dict, history: set):
    """Replace all references with items, auxiliary function for object framing. The history prevents circular references."""
    if isinstance(data, list): 
        for i, item in enumerate(data):
            data[i], new_history = embed_items(item, itemmap, copy(history)) #recursion step
            history |= new_history
    elif isinstance(data, dict): 
        for idkey in ('@id', 'id'):
            if idkey in data and data[idkey] in itemmap and data[idkey] not in history:
                #print(f"DEBUG embedded {idkey} (explicit)")
                history.add(data[idkey])
                return embed_items(itemmap[data[idkey]], itemmap, copy(history))
        for k, v in data.items():
            data[k], new_history = embed_items(v, itemmap, copy(history)) #recursion step
            history |= new_history
    elif isinstance(data, str) and data.startswith(("http","/","_")) and data in itemmap and data not in history: #this is probably a reference even though it's not explicit
        #data is an URI reference we can resolve
        history.add(data)
        return itemmap[data], history
    return data, history
    

def rewrite_context(context, addcontext = None) -> list:
    """Rewrite local contexts to their remote counterparts"""
    if isinstance(context, list):
        for i, value in enumerate(context):
            if value == CODEMETA_LOCAL_SOURCE:
                context[i] = CODEMETA_SOURCE
            elif value == SCHEMA_LOCAL_SOURCE:
                context[i] = SCHEMA_SOURCE
            elif value == STYPE_LOCAL_SOURCE:
                context[i] = STYPE_SOURCE
            elif value == IODATA_LOCAL_SOURCE:
                context[i] = IODATA_SOURCE
            elif value == REPOSTATUS_LOCAL_SOURCE:
                context[i] = REPOSTATUS_SOURCE
            elif addcontext:
                for remote_url in addcontext:
                    if not remote_url.startswith("http"):
                        raise Exception(f"Explicitly added context (--addcontext) must be a remote URL, got {remote_url} instead")
                    local = "file://" + os.path.join(TMPDIR, os.path.basename(remote_url))
                    if value == local:
                        context[i] = remote_url
    elif isinstance(context, str):
        context = rewrite_context([context])
    return context

def serialize_to_jsonld(g: Graph, res: Union[Sequence,URIRef,None], includecontext: bool = False, addcontext = None) -> dict:
    """Serializes the RDF graph to JSON, taking care of 'object framing' for embedded nodes"""

    if res:
        #Get the subgraph that focusses on this specific resource (or multiple)
        if isinstance(res, (list,tuple)):
            g = get_subgraph(g, res)
        else:
            g = get_subgraph(g, [res])

    data = json.loads(g.serialize(format='json-ld', auto_compact=False, context=[ x[1] for x in init_context(False, addcontext)]))

    #rdflib doesn't do 'object framing' so we have to do it in this post-processing step
    #if we have a single resource, it'll be the focus object the whole frame will be built around
    if res and (not isinstance(res, (list,tuple)) or len(res) == 1):
        if includecontext:
            data = expand_implicit_id_nodes(data, PREFER_URIREF_PROPERTIES_SIMPLE)
        data = do_object_framing(data, str(res))

        root, parent = find_main(data, res)
        if parent and len(data['@graph']) == 1 and res:
            #No need for @graph if it contains only one item now:
            parent.update(root)
            del data['@graph']
            root = parent

    data = sort_by_position(data)
    if '@context' in data:
        data['@context'] = rewrite_context(data['@context'], addcontext)

    #we may have some lingering prefixes which we don't need, cleanup:
    data = cleanup(data)


    return data
