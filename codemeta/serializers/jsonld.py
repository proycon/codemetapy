import sys
import json
from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal
from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx, SDO, CONTEXT

def flatten_singletons(data):
    """Recursively flattens singleton ``key: { "@id": url }`` instances to ``key: url``"""
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                if '@id' in value and len(value) == 1:
                    data[key] = value['@id']
                else:
                    data[key] = flatten_singletons(data[key])
            else:
                data[key] = flatten_singletons(data[key])
        return data
    elif isinstance(data, (list,tuple)):
        return [ x['@id'] if isinstance(x, dict) and '@id' in x and len(x) == 1 else flatten_singletons(x) for x in data ]
    else:
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

def serialize_to_jsonld(g: Graph, uri: str) -> dict:
    """Serializes the RDF graph to JSON, taking care of 'framing' for embedded nodes"""
    data = json.loads(g.serialize(format='json-ld', auto_compact=True, context=CONTEXT))

    #rdflib doesn't do 'framing' so we have to do it in this post-processing step:
    #source: a Niklas Lindström, https://groups.google.com/g/rdflib-dev/c/U9Czox7kQL0?pli=1
    #added patch: 'id' may be aliased to '@id' so check both
    if '@graph' in data:
        items, refs = {}, {}
        for item in data['@graph']:
            itemid = item.get('@id', item.get('id'))
            if itemid:
                items[itemid] = item
            for vs in item.values():
                for v in [vs] if not isinstance(vs, list) else vs:
                    if isinstance(v, dict):
                        refid = v.get('@id', v.get('id'))
                        if refid and refid.startswith('_:'):
                            refs.setdefault(refid, (v, []))[1].append(item)
        for ref, subjects in refs.values():
            if len(subjects) == 1:
                for k in ('@id','id'):
                    if k in ref:
                        ref.update(items.pop(ref[k]))
                        del ref[k]
        data['@graph'] = list(items.values())
        #<end snippet>


        #No need for @graph if it contains only one item now:
        if isinstance(data['@graph'], list) and len(data['@graph']) == 1:
            graph = data['@graph'][0]
            data.update(graph)
            del data['@graph']
        elif uri and data['@graph']:
            if 'id' in data['@graph'][0]:
                del data['@graph'][0]['id']
            data['@graph'][0]['@id'] = uri


    #flatten singletons (contains only @id)
    data = flatten_singletons(data)

    #we have some lingering prefixes which we don't need, cleanup:
    data = cleanup(data)

    if '@graph' not in data and uri:
        if 'id' in data:
            del data['id']
        data['@id'] = uri

    return data
