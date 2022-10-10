import sys
import requests
import time
from os import environ
from datetime import datetime
from io import StringIO
from typing import Union, IO, Optional, Tuple
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF
from codemeta.common import AttribDict, SDO, CODEMETA, license_to_spdx, parse_human_name, generate_uri
from codemeta.parsers.jsonld import parse_jsonld_data

GITAPI_REPO_BLACKLIST=["https://codeberg.org/","http://codeberg.org", "https://git.sr.ht/", "https://bitbucket.com/"]
#it shall be persistent because each new yaml a new invoke of codemetapy is performed and so memory reset
repo_type_cache = {}

def _parse_source(source:str) -> Tuple[str,str,str]:
    source=source.strip("/")
    cleaned_url= source
    scheme=""
    if source.startswith("https://"):
        host = cleaned_url.replace('https://','').split('/')[0]
        scheme="https://"
    else:
        raise ValueError(source + " source url format not recognized!!")
    return cleaned_url, scheme, host
 


def get_repo_kind(source: str) -> Optional[str]:
    source, scheme, host = _parse_source(source)
 
    repo_kind = None
    if "github.com/" in source:
        repo_kind = "github"
    elif "gitlab.com/" in source:
        repo_kind = "gitlab"
    elif f"{scheme}{host}/" not in GITAPI_REPO_BLACKLIST:
        #we have another URL that may or may not be a private gitlab instance, test
        if f"{scheme}{host}/" in repo_type_cache:
            repo_kind = repo_type_cache[f"{scheme}{host}/"]
        else:
            test_url = f"{scheme}{host}/-/manifest.json"  #this seems a relatively cheap way to test if it's a gitlab instance
            response = requests.get(test_url)
            if response.status_code == 200 and response.headers['Content-Type'].startswith("application/json"):
                response = response.json()
                if response['short_name'] == 'GitLab':
                    repo_kind = "gitlab"

    #Populate the cache even when there is a 4xx failure
    repo_type_cache[f"{scheme}{host}/"] = repo_kind

    return repo_kind

def parse(g: Graph, res: Union[URIRef, BNode], source: str, repo_kind:str, args: AttribDict) -> str:
    source, scheme, host = _parse_source(source)
 
    github_suffix=source.replace(scheme + host,'')[1:]
    gitlab_suffix=github_suffix.replace('/', '%2F')
    gitlab_repo_api_url = f"{scheme}{host}/api/v4/projects/{gitlab_suffix}"

    if repo_kind == "github":
        response = rate_limit_get(f"{scheme}api.github.com/repos/{github_suffix}", "github")
        _parse_github(response, g,res,f"{scheme}{host}", args)
    elif repo_kind == "gitlab":
        response = rate_limit_get(gitlab_repo_api_url, "gitlab")
        _parse_gitlab(response, g,res,f"{scheme}{host}", args)  
    else:
        raise ValueError(f"Not a git API, repo_kind={repo_kind}")

    return source

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
def rate_limit_get(url:str, repo_kind: Optional[str], backoff_rate=2, initial_backoff=1, **kwargs) -> dict: 
    rate_limited = True
    data = {}
    has_token=False
    if not kwargs: kwargs = {}
    if repo_kind == "github" and 'GITHUB_TOKEN' in environ and environ['GITHUB_TOKEN']:
        if 'headers' not in kwargs: kwargs['headers'] = {}
        kwargs['headers']["Authorization"] = "token " + environ['GITHUB_TOKEN']
        has_token = True
    elif repo_kind == "gitlab" and 'GITLAB_TOKEN' in environ and environ['GITLAB_TOKEN']:
        if 'headers' not in kwargs: kwargs['headers'] = {}
        kwargs['headers']["PRIVATE-TOKEN"] = environ['GITLAB_TOKEN']
        has_token = True
    while rate_limited:
        print(f"Querying {url}")
        response = requests.get(url, **kwargs)
        rate_limit_remaining = int(response.headers.get("RateLimit-Remaining" if repo_kind == "gitlab" else "x-ratelimit-remaining",-1))
        epochtime = int(response.headers.get("RateLimit-Reset" if repo_kind == "gitlab" else  "x-ratelimit-reset",0))
        if rate_limit_remaining > -1 and epochtime > 0:
            date_reset = datetime.fromtimestamp(epochtime)
            print(f"Remaining {repo_kind} API requests: {rate_limit_remaining} ### Next rate limit reset at: {date_reset} (has_token={has_token})")
        else:
            rate_limited = False
        data = response.json()
        if 'message' in data and 'API rate limit exceeded' in data['message']:
            rate_limited = True
            print(f"{repo_kind} API: rate limited. Backing off for {initial_backoff} seconds (has_token={has_token})", file=sys.stderr)
            sys.stderr.flush()
            if initial_backoff > 120:
                raise Exception(f"{repo_kind} API timed out because of rate limiting, giving up... (has_token={has_token})")
            time.sleep(initial_backoff)
            # increase the backoff for next time
            initial_backoff *= backoff_rate
        else:
            response.raise_for_status()
            rate_limited = False
    return data

def _parse_github(response: dict, g: Graph, res: Union[URIRef, BNode], source: str, args: AttribDict):
    """Query and parse from the github API"""
    print(f"    Parsing Github API response",file=sys.stderr)
    users_api_url=f"https://api.github.com/users/"
    
    #repo = response['name']
    for prop, github_key in github_crosswalk_table.items():
        if github_key in response and response[github_key]:
            g.add((res, prop, Literal(response[github_key])))

    if response.get('license') and response['license'].get('spdx_id'):
        g.add((res, SDO.license, Literal(license_to_spdx(response['license']['spdx_id']))))

    if response.get("topics"):
        for topic in response['topics']:
            g.add((res, SDO.keywords, Literal(topic)))

    if response.get("homepage"):
        g.add((res, SDO.url, Literal(response['homepage'])))

    if response.get('has_issues', False) and response.get("html_url"):
        g.add((res, CODEMETA.issueTracker, Literal(response['html_url'] + "/issues")))

    if 'owner' in response:
        owner = response['owner']['login']
        owner_api_url = f"{users_api_url}{owner}"
        response = rate_limit_get(owner_api_url, "github")
        owner_type = response.get("type","").lower()
        owner_res = None
        if owner_type == "user" and response.get('name'):
            firstname, lastname = parse_human_name(response['name'])
            owner_res = URIRef(generate_uri(firstname + "-" + lastname, args.baseuri, prefix="person"))
            g.add((owner_res, RDF.type, SDO.Person))
            g.add((owner_res, SDO.givenName, Literal(firstname)))
            g.add((owner_res, SDO.familyName, Literal(lastname)))
            g.add((res, SDO.author, owner_res))
            g.add((res, SDO.maintainer, owner_res))
            if response.get('company'):
                affil_res = URIRef(generate_uri(response.get('company'), args.baseuri, prefix="org"))
                g.add((affil_res, RDF.type, SDO.Organization))
                g.add((affil_res, SDO.name, Literal(response['company'])))
                g.add((owner_res, SDO.affiliation, affil_res))
        elif owner_type == "organization" and response.get('name'):
            owner_res = URIRef(generate_uri(response.get('name'), args.baseuri, prefix="org"))
            g.add((owner_res, RDF.type, SDO.Organization))
            g.add((owner_res, SDO.name, Literal(response.get('name'))))
            g.add((res, SDO.producer, owner_res))
        if owner_res:
            if response.get('email'):
                g.add((owner_res, SDO.email, Literal(response.get('email'))))
            if response.get('blog'):
                g.add((owner_res, SDO.url, Literal(response.get('blog'))))


gitlab_crosswalk_table = {
    SDO.codeRepository: "web_url",
    SDO.dateCreated: "created_at",
    SDO.dateModified: "last_activity_at",
    SDO.description: "description",
    SDO.name: "name",
    SDO.url: "web_url"
}
def _parse_gitlab(response: dict, g: Graph, res: Union[URIRef, BNode], source, args: AttribDict):
    """Query and parse from the gitlab API"""
    users_api_url = f"{source}/api/v4/users/"
    #Processing start
    for prop, gitlab_key in gitlab_crosswalk_table.items():
        if gitlab_key in response and response[gitlab_key]:
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

    #https://docs.gitlab.com/ee/api/users.html
    #namespace kind can be just group or user
    owner_id_str=""
    owner_name=""
    user_url=""
    public_mail=""
    if 'namespace' in response and response['namespace']['kind'] == 'user':
        owner_id_str=str(response['namespace']['id'])
        owner_api_url = users_api_url + owner_id_str
        owner_name=response['namespace']['name']
        user_url=response['namespace']['web_url']
    elif 'owner' in response:
        owner_id_str=str(response['owner']['id'])
        owner_api_url = users_api_url + owner_id_str
        response_owner = rate_limit_get(owner_api_url, "gitlab")
        owner_name=response_owner['owner']['name']
        user_url=response_owner['owner']['web_url']
        if response_owner.get('public_email'):
            public_mail = response_owner.get('public_email')
    else:  
        return
    firstname, lastname = parse_human_name(owner_name)
    owner_res = URIRef(user_url)
    g.add((owner_res, RDF.type, SDO.Person))
    g.add((owner_res, SDO.givenName, Literal(firstname)))
    g.add((owner_res, SDO.familyName, Literal(lastname)))
    g.add((owner_res, SDO.url, Literal(user_url)))
    if public_mail != "":
        g.add((owner_res, SDO.email, Literal(public_mail)))
    #Creator considered as author
    response_creator_url_field=user_url
    response_creator_name=owner_name
    if 'creator_id' in response:
     creator_id_str = str(response['creator_id'])
     if creator_id_str != owner_id_str:
        creator_api_url = users_api_url +  creator_id_str
        response_creator = rate_limit_get(creator_api_url, "gitlab")
        response_creator_url_field=response_creator['web_url']
    #Object X must be an rdflib term:  g.add((URIRef(response_creator_url_field), SDO.author, response_creator_name))
    #g.add((res, SDO.maintainer, owner_res))
    #if response_owner.get('work_information'): is like company?
