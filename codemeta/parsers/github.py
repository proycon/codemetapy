import sys
import requests
import time
from datetime import datetime
from io import StringIO
from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, SDO, CODEMETA, license_to_spdx, parse_human_name
from codemeta.parsers.jsonld import parse_jsonld_data

github_crosswalk_table = {
    SDO.codeRepository: "html_url",
    SDO.dateCreated: "created_at",
    SDO.dateModified: "pushed_at",
    SDO.description: "description",
    SDO.name: "name",
}

#"owner": ["owner", "login"],
#"ownerType": ["owner", "type"],  # used to determine if owner is User or Organization

# the same as requests.get(args).json(), but protects against rate limiting
# Adapted from source: https://github.com/KnowledgeCaptureAndDiscovery/somef (MIT licensed)
def rate_limit_get(*args, backoff_rate=2, initial_backoff=1, **kwargs):
    rate_limited = True
    response = {}
    while rate_limited:
        response = requests.get(*args, **kwargs)
        data = response
        rate_limit_remaining = data.headers["x-ratelimit-remaining"]
        epochtime = int(data.headers["x-ratelimit-reset"])
        date_reset = datetime.fromtimestamp(epochtime)
        print("Remaining GitHub API requests: " + rate_limit_remaining + " ### Next rate limit reset at: " + str(date_reset))
        response = response.json()
        if 'message' in response and 'API rate limit exceeded' in response['message']:
            rate_limited = True
            print(f"Github API: rate limited. Backing off for {initial_backoff} seconds")
            time.sleep(initial_backoff)

            # increase the backoff for next time
            initial_backoff *= backoff_rate
        else:
            rate_limited = False

    return response

def parse_github(g: Graph, res: Union[URIRef, BNode], source, args: AttribDict) -> Union[URIRef,BNode,None]:
    """Query and parse from the github API"""

    try:
        owner, repo = source.split("/")
    except:
        raise ValueError("Github API sources must follow owner/repo syntax")

    repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_url = f"https://github.com/{owner}/{repo}"

    response = rate_limit_get(repo_api_url)

    for prop, github_key in github_crosswalk_table.items():
        if github_key in response:
            g.add((res, prop, Literal(response[github_key])))

    if response.get('license') and response['license'].get('spdx_id'):
        g.add((res, SDO.license, Literal(license_to_spdx(response['license']['spdx_id']))))

    if response.get("topics"):
        for topic in response['topics']:
            g.add((res, SDO.keywords, Literal(topic)))

    if response.get("homepage"):
        g.add((res, SDO.url, Literal(response['homepage'])))

    if response.get('has_issues', False):
        g.add((res, CODEMETA.issueTracker, Literal(f"https://github.com/{owner}/{repo}/issues")))

    if 'owner' in response:
        owner_api_url = f"https://api.github.com/users/{owner}"
        response = rate_limit_get(owner_api_url)
        owner_type = response.get("type","").lower()
        owner_res = BNode()
        if owner_type == "user" and response.get('name'):
            firstname, lastname = parse_human_name(response['name'])
            g.add((owner_res, RDF.type, SDO.Person))
            g.add((owner_res, SDO.givenName, Literal(firstname)))
            g.add((owner_res, SDO.familyName, Literal(lastname)))
            g.add((res, SDO.author, owner_res))
            g.add((res, SDO.maintainer, owner_res))
            if response.get('company'):
                affil_res = BNode()
                g.add((affil_res, RDF.type, SDO.Organization))
                g.add((affil_res, SDO.name, Literal(response['company'])))
                g.add((owner_res, SDO.affiliation, affil_res))
        elif owner_type == "organization" and response.get('name'):
            g.add((owner_res, SDO.name, Literal(response.get('name'))))
            g.add((res, SDO.producer, owner_res))
        if response.get('email'):
            g.add((owner_res, SDO.email, Literal(response.get('email'))))
        if response.get('blog'):
            g.add((owner_res, SDO.url, Literal(response.get('blog'))))

    return repo_url
