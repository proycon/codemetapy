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
    SDO.url: "web_url"
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
        split_arr = source.strip("/").split("/")
        repo_father_path = split_arr[len(split_arr) -2]
        repo = split_arr[len(split_arr) -1]
    except:
        raise ValueError("GitLab API sources must follow repo_father_path/repo syntax")
    
    repo_base_uri=source.strip("/")
    # Substring that need to be replaced
    str_to_replace = f"{repo_father_path}/{repo}"
    # Replacement substring
    replacement_str=''
    # Replace last occurrences of substring 
    repo_base_uri = replacement_str.join(repo_base_uri.rsplit(str_to_replace, 1))

    repo_url = source.strip("/")  
    repo_api_url = f"{repo_base_uri}/api/v4/projects/{repo_father_path}%2F{repo}"
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
    elif response.get("web_url"):
        g.add((res, SDO.url, Literal(response['web_url'])))
    if response.get('open_issues_count', False) > 0:
        g.add((res, CODEMETA.issueTracker, Literal(response['_links']['issues'])))
    
    owner_id_str=""
    owner_name=""
    user_url=""
    public_mail=""
    #https://docs.gitlab.com/ee/api/users.html
    #namespace kind kind can be just group or user

    if 'namespace' in response and response['namespace']['kind'] == 'user':
        owner_id_str=str(response['namespace']['id'])
        owner_api_url = f"{repo_base_uri}/api/v4/users/" + owner_id_str
        owner_name=response['namespace']['name']
        user_url=response['namespace']['web_url']
    elif 'owner' in response:
        owner_id_str=str(response['owner']['id'])
        owner_api_url = f"{repo_base_uri}/api/v4/users/" + owner_id_str
        response_owner = rate_limit_get(owner_api_url)
        owner_name=response_owner['owner']['name']
        user_url=response_owner['owner']['web_url']
        if response_owner.get('public_email'):
            public_mail = response_owner.get('public_email')
    else:  return repo_url
    firstname, lastname = parse_human_name(owner_name)
    owner_res = URIRef(user_url)
    g.add((owner_res, RDF.type, SDO.Person))
    g.add((owner_res, SDO.givenName, Literal(firstname)))
    g.add((owner_res, SDO.familyName, Literal(lastname)))
    g.add((owner_res, SDO.url, Literal(user_url)))
    if public_mail != "":
        g.add((owner_res, SDO.email, Literal(public_mail)))
    #Creator considerer as author
    response_creator_url_field=user_url
    response_creator_name=owner_name
    if 'creator_id' in response:
     creator_id_str=str(response['creator_id'])
     if(creator_id_str != owner_id_str):
        creator_api_url = f"{repo_base_uri}/api/v4/users/" +  creator_id_str
        response_creator = rate_limit_get(creator_api_url)
        response_creator_url_field=response_creator['web_url']
    #Object X must be an rdflib term:  g.add((URIRef(response_creator_url_field), SDO.author, response_creator_name))
    #g.add((res, SDO.maintainer, owner_res))
    #if response_owner.get('work_information'): is like company?
    return repo_url
