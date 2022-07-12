import sys
import requests
import time
from os import environ
from datetime import datetime
from io import StringIO
from typing import Union, IO
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, SDO, CODEMETA, license_to_spdx, parse_human_name, generate_uri
from codemeta.parsers.jsonld import parse_jsonld_data

gitlab_crosswalk_table = {
    SDO.codeRepository: "web_url",
    SDO.dateCreated: "created_at",
    SDO.dateModified: "last_activity_at",
    SDO.description: "description",
    SDO.name: "name",
}

# the same as requests.get(args).json(), but protects against rate limiting
# Adapted from github.py
def rate_limit_get(*args, backoff_rate=2, initial_backoff=1, **kwargs):
    rate_limited = True
    response = {}
    if not kwargs: kwargs = {}
    if 'GITLAB_TOKEN' in environ and environ['GITLAB_TOKEN']:
        if 'headers' not in kwargs: kwargs['headers'] = {}
        kwargs['headers']["Authorization"] = "token " + environ['GITLAB_TOKEN']
        has_token = True
    else:
        has_token = False
    while rate_limited:
        response = requests.get(*args, **kwargs)
        data = response
        rate_limit_remaining = data.headers["RateLimit-Remaining"]
        epochtime = int(data.headers["RateLimit-Reset"])
        date_reset = datetime.fromtimestamp(epochtime)
        print("Remaining GitLab API requests: " + rate_limit_remaining + " ### Next rate limit reset at: " + str(date_reset) + f" (has_token={has_token})")
        response = response.json()
        #OR http return code is 429
        if 'message' in response and 'Retry later' in response['message']:
            rate_limited = True
            print(f"GitLab API: rate limited. Backing off for {initial_backoff} seconds (has_token={has_token})", file=sys.stderr)
            sys.stderr.flush()
            if initial_backoff > 120:
                raise Exception("GitLab API timed out because of rate limiting, giving up... (has_token={has_token})")
            time.sleep(initial_backoff)

            # increase the backoff for next time
            initial_backoff *= backoff_rate
        else:
            rate_limited = False

    return response

def parse_gitlab(g: Graph, res: Union[URIRef, BNode], source, args: AttribDict) -> Union[URIRef,BNode,None]:
    """Query and parse from the gitlab API"""
    # https://docs.gitlab.com/ee/api/projects.html    GET /projects/:id
    try:
        repo_father_path, repo = source.strip("/").split("/")
    except:
        raise ValueError("GitLab API sources must follow repo_father_path/repo syntax")

    repo_api_url = f"https://gitlab.com/api/v4/projects/{repo_father_path}%2F{repo}"
    repo_url = f"https://gitlab.com/{repo_father_path}/{repo}"

    response = rate_limit_get(repo_api_url)

    for prop, gitlab_key in gitlab_crosswalk_table.items():
        if gitlab_key in response:
            g.add((res, prop, Literal(response[gitlab_key])))

    if response.get('license') and response['license'].get('nickname'):
        g.add((res, SDO.license, Literal(license_to_spdx(response['license']['nickname']))))
    if response.get("topics"):
        for topic in response['topics']:
            g.add((res, SDO.keywords, Literal(topic)))
    if response.get("homepage"):
        g.add((res, SDO.url, Literal(response['homepage'])))
    if response.get('open_issues_count', False) > 0:
        g.add((res, CODEMETA.issueTracker, Literal(response['_links']['issues'])))
        
    #https://docs.gitlab.com/ee/api/users.html
    if 'owner' in response:
        owner_api_url = "https://gitlab.com/api/v4/users/" + str(response['owner']['id'])
        response_owner = rate_limit_get(owner_api_url)
        #owner_type not exists for gitlab (just user)
        if  response_owner.get('owner'):
            firstname, lastname = parse_human_name(response_owner['owner']['name'])
            #owner_res = URIRef(generate_uri(firstname + "-" + lastname, args.baseuri, prefix="person"))
            g.add((owner_api_url, RDF.type, SDO.Person))
            g.add((owner_api_url, SDO.givenName, Literal(firstname)))
            g.add((owner_api_url, SDO.familyName, Literal(lastname)))
            #creator_api_url = "https://gitlab.com/api/v4/users/" + str(response['creator_id']) + GET + g.add((resFROM get creator_api_url , SDO.author, fullNameFromcreator_api_url))
            #g.add((res, SDO.maintainer, owner_res))
            #if response_owner.get('work_information'): is like company 
                #affil_res = URIRef(generate_uri(response_owner.get('company'), args.baseuri, prefix="org"))
                #g.add((affil_res, RDF.type, SDO.Organization))
                #g.add((affil_res, SDO.name, Literal(response_owner['company'])))
                #g.add((owner_res, SDO.affiliation, affil_res))
        #if response_owner.get('organization'):
        #    g.add((owner_res, SDO.name, Literal(response_owner.get('organization'))))
        #    g.add((res, SDO.producer, null))
            if response_owner.get('public_email'):
                g.add((owner_api_url, SDO.email, Literal(response_owner.get('public_email'))))
            if response_owner.get('web_url'):
                g.add((owner_api_url, SDO.url, Literal(response_owner.get('website_url'))))

    return repo_url
