import sys
import os
import datetime
from rdflib import Graph, Namespace, URIRef, BNode, Literal
from rdflib.namespace import RDF, SH
from typing import Union, IO, Sequence, Optional, Tuple
from codemeta.common import init_graph, init_context, CODEMETA, AttribDict,  SDO,  generate_uri

from pyshacl import validate as pyshacl_validate

def validate(g: Graph, res: Union[URIRef,BNode], args: AttribDict, contextgraph: Union[Graph,None] = None) -> Tuple[bool, Graph]:
    """Validates software metadata using SHACL, generates a validation report and adds it to the SoftwareSourceCode metadata via the schema:review property"""
    shacl_file: str = args.validate
    if shacl_file.endswith("ttl"):
        shacl_format="turtle"
    elif shacl_file.endswith(("json","jsonld")):
        shacl_format="json-ld"
    else:
        raise ValueError(f"Expect ttl or json file for SHACL ({args.validate}), unable to determine from extension")
    shacl_graph = Graph()
    shacl_graph.parse(args.validate, format=shacl_format)
    conforms, results_graph, _ = pyshacl_validate(data_graph=g, shacl_graph=shacl_graph, ont_graph=contextgraph, abort_on_first=False, allow_infos=True, allow_warnings=True)
    counter = 0
    review = URIRef(generate_uri(None, args.baseuri,prefix="validation"))
    g.add((review, RDF.type, SDO.Review))
    g.add((review, SDO.author, Literal(f"codemetapy validator using {os.path.basename(shacl_file)}")))
    g.add((review, SDO.datePublished, Literal(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))))
    name = g.value(res,SDO.name)
    if not name: name = "unnamed software"
    version = g.value(res,SDO.version)
    if not version: version = "(unknown version)"
    g.add((review, SDO.name, Literal(f"Automatic software metadata validation report for {name} {version}")))
    messages = []
    warnings = 0
    violations = 0
    info = 0
    for node ,_,_ in results_graph.triples((None,SH.focusNode,res)):
        if (node, RDF.type, SH.ValidationResult) in results_graph:
            severity = ""
            if (node, SH.resultSeverity, SH.Violation) in results_graph:
                severity = "Violation"
                violations += 1
            elif (node, SH.resultSeverity, SH.Warning) in results_graph:
                severity = "Warning"
                warnings += 1
            elif (node, SH.resultSeverity, SH.Info) in results_graph:
                severity = "Info"
                info += 1
            else:
                severity = "Unknown"
            cause = ""
            if (node, SH.sourceConstraintComponent, SH.ClassConstraintComponent) in results_graph:
                cause = "The metadata does express this currently, but the wrong class is used."
            elif (node, SH.sourceConstraintComponent, SH.DatatypeConstraintComponent) in results_graph:
                cause = "The metadata does express this currently, but the wrong datatype is used"
            elif (node, SH.sourceConstraintComponent, SH.NodeKindConstraintComponent) in results_graph:
                cause = "The metadata does express this currently, but the wrong node kind is used (probably URI vs literal)"
            elif (node, SH.sourceConstraintComponent, SH.OrConstraintComponent) in results_graph:
                cause = "The metadata does express this currently, but something is wrong in the way it is expressed. Is the type/class valid?"
            elif (node, SH.sourceConstraintComponent, SH.QualifiedMinCountConstraintComponent) in results_graph:
                cause = "This is missing in the metadata"
            elif (node, SH.sourceConstraintComponent, SH.QualifiedMaxCountConstraintComponent) in results_graph:
                cause = "The metadata expresses this multiple times and is too ambiguous"
            elif (node, SH.sourceConstraintComponent, SH.MinCountConstraintComponent) in results_graph:
                cause = "This is missing in the metadata"
            elif (node, SH.sourceConstraintComponent, SH.MaxCountConstraintComponent) in results_graph:
                cause = "The metadata expresses this multiple times and is too ambiguous"
            if cause: cause = f"({cause})"

            #path = results_graph.value(node, SH.resultPath)
            msg = results_graph.value(node, SH.resultMessage)
            if msg:
                counter +=1 
                print(f"VALIDATION {str(res)} #{counter}: {severity}: {str(msg)} {cause}", file=sys.stderr)
                messages.append(f"{counter}. {severity}: {msg} {cause}")
    head = args.textv  + "\n\n" if args.textv else ""
    if messages:
        if conforms:
            if warnings:
                head += f"Validation of {name} {version} was successful (score=3/5), but there are some warnings which should be addressed:"
                g.add((review, SDO.reviewRating, Literal(3)))
            else:
                head += f"Validation of {name} {version} was successful (score=4/5), but there are some remarks which you may or may not want to address:"
                g.add((review, SDO.reviewRating, Literal(4)))
        else:
            if violations > 3:
                g.add((review, SDO.reviewRating, Literal(0)))
                score = "(score 0/5)"
            elif violations > 1 or warnings > 5:
                g.add((review, SDO.reviewRating, Literal(1)))
                score = "(score 1/5)"
            else:
                g.add((review, SDO.reviewRating, Literal(2)))
                score = "(score 2/5)"
            head += f"Validation of {name} {version} failed {score} due to one or more requirement violations:"
        g.add((review, SDO.reviewBody, Literal(head + "\n\n" + "\n".join(messages))))
    else:
        g.add((review, SDO.reviewBody, Literal("Validates perfectly, no further remarks!")))
        g.add((review, SDO.reviewRating, Literal(5)))
    g.add((res, SDO.review, review))
    return conforms, results_graph

def get_validation_report(g: Graph, res: Union[Sequence,URIRef,BNode]) -> Optional[str]:
    """Get the text of an existing validation report for the given resource"""
    if (res,RDF.type,SDO.Review):
        return g.value(res,SDO.reviewBody)
    else:
        for _,_,review in g.triples((res,SDO.review,None)):
            return g.value(review,SDO.reviewBody)

            

    
