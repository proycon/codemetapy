import sys
import json
import os.path
from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
import lxml.etree
from codemeta.common import AttribDict, add_triple, CODEMETA, SOFTWARETYPES, add_authors, SDO, COMMON_SOURCEREPOS, SOFTWARETYPES, license_to_spdx, generate_uri
from codemeta.crosswalk import readcrosswalk, CWKey

POM_NAMESPACE = "http://maven.apache.org/POM/4.0.0"

def parse_node(node):
    for subnode in node:
        if isinstance(subnode.tag, str) and subnode.tag.startswith("{" + POM_NAMESPACE + "}"):
            key = subnode.tag[len(POM_NAMESPACE) + 2:]
            yield key, subnode

def parse_author(g, res, node, property=SDO.author):
    author_name = ""
    author_mail = ""
    author_url = ""
    org = ""
    for key3, node3 in parse_node(node):
        if key3 == "name":
            author_name = node3.text
        elif key3 == "email":
            author_mail = node3.text
        elif key3 == "url":
            author_url = node3.text
        elif key3 == "organisation":
            org = node3.text
    return add_authors(g, res, author_name, property=property, single_author=True, mail=author_mail, url=author_url,org=org)


def parse_java(g: Graph, res: Union[URIRef, BNode], file: IO , crosswalk, args: AttribDict):
    data = lxml.etree.parse(file)

    root = data.getroot()
    if root.tag != "{" + POM_NAMESPACE + "}project":
        raise Exception(f"Expected root tag 'project' in {POM_NAMESPACE} namespace, got {root.tag} instead")

    group_id = None
    artifact_id = None

    g.add((res, SDO.runtimePlatform, Literal("Java")))
    g.add((res, SDO.programmingLanguage, Literal("Java")))

    for key, node in parse_node(root):
        if key == "licenses":
            for key2, node2 in parse_node(node):
                if key2 == "license":
                    license = ""
                    for key3, node3 in parse_node(node2):
                        if key3 == "name":
                            license = license_to_spdx(node3.text)
                        if isinstance(license, str) and license.find("spdx") == -1 and key3 == "url":
                            license = node3.text
                    if license:
                        add_triple(g,res, "license", license, args)
        elif key == "issueManagement":
            for key2, node2 in parse_node(node):
                if key2 == "url" and '$' not in node2.text: #only if there are no variables in the url!
                    add_triple(g,res, "issueTracker", node2.text, args)
        elif key == "ciManagement":
            for key2, node2 in parse_node(node):
                if key2 == "url" and '$' not in node2.text: #only if there are no variables in the url!
                    add_triple(g,res, "contIntegration", node2.text, args)
        elif key == "scm":
            for key2, node2 in parse_node(node):
                if key2 == "url" and '$' not in node2.text: #only if there are no variables in the url!
                    add_triple(g,res, "codeRepository", node2.text, args)
        elif key == "repositories":
            for key2, node2 in parse_node(node):
                if key2 == "repository":
                    for key3, node3 in parse_node(node2):
                        if key3 == "url" and '$' not in node3.text: #only if there are no variables in the url!
                            add_triple(g,res, "repository", node3.text, args)
        elif key == "properties":
            for key2, node2 in parse_node(node):
                if key2 == "java.version":
                    g.add((res, SDO.runtimePlatform, Literal("Java " + node2.text)))
        elif key == 'groupId':
            group_id = node.text
        elif key == 'artifactId':
            artifact_id = node.text
        elif key == 'dependencies':
            for key2, node2 in parse_node(node):
                if key2 == "dependency":
                    dep_group_id = dep_art_id = dep_version = ""
                    for key3, node3 in parse_node(node2):
                        if key3 == "groupId":
                            dep_group_id = node3.text
                        elif key3 == "artifactId":
                            dep_art_id = node3.text
                        elif key3 == "version" and node3.text and not node3.text.startswith('$'):
                            dep_version = node3.text

                    if dep_group_id and dep_art_id:
                        depres = URIRef(generate_uri(dep_group_id +"." + dep_art_id + "." + dep_version.replace(" ",""), baseuri=args.baseuri,prefix="dependency"))
                        g.add((depres, SDO.identifier, Literal(dep_group_id + "." + dep_art_id)))
                        g.add((depres, SDO.name, Literal(dep_art_id)))
                        if dep_version:
                            g.add((depres, SDO.version, Literal(dep_version)))
                        g.add((depres, RDF.type, SDO.SoftwareApplication))
                        g.add((res, CODEMETA.softwareRequirements, depres))
        elif key == 'developers':
            for key2, node2 in parse_node(node):
                if key2 == "developer":
                    parse_author(g, res, node2)
        elif key == 'contributors':
            for key2, node2 in parse_node(node):
                if key2 == "contributor":
                    parse_author(g, res, node2, property=SDO.contributor)
        elif key == 'mailingLists':
            for key2, node2 in parse_node(node):
                if key2 == "mailingList":
                    for key3, node3 in parse_node(node2):
                        if key3 == "post":
                            add_triple(g, res, "email", node3.text, args)
        elif key == 'organization':
            org_name = None
            org_url = None
            for key2, node2 in parse_node(node):
                if key2 == "name":
                    org_name = node2.text
                elif key2 == "url":
                    org_url = node2.text
            if org_name:
                orgres = URIRef(generate_uri(org_name, baseuri=args.baseuri, prefix="org"))
                g.add((orgres, SDO.name, Literal(org_name)))
                if org_url:
                    g.add((orgres, SDO.url, Literal(org_url)))
                g.add((res, SDO.producer, orgres))
        elif key.lower() in crosswalk[CWKey.MAVEN]:
            value = node.text
            if group_id and value.find("${project.groupId}") != -1:
                value = value.replace("${project.groupId}", group_id)
            if artifact_id and value.find("${project.artifactId}") != -1:
                value = value.replace("${project.artifactId}", artifact_id)
            key = crosswalk[CWKey.MAVEN][key.lower()]
            if key != 'identifier':
                add_triple(g, res, key, value, args)

    if group_id and artifact_id:
        add_triple(g, res, "identifier", group_id + "." + artifact_id, args)
