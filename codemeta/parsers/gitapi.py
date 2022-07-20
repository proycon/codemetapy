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

GITAPI_REPO_BLACKLIST=["https://codeberg.org/","http://codeberg.org", "https://git.sr.ht/", "https://bitbucket.com/"]
repo_type_cache = {}

def parse(g: Graph, res: Union[URIRef, BNode], source: str, args: AttribDict) -> Union[URIRef,BNode,None]:
    source=source.strip("/")
    cleaned_url= source
    prefix=""
    if(source.startswith("https://")):
     git_address = cleaned_url.replace('https://','').split('/')[0]
     prefix="https://"
    else:
     raise ValueError(source + " source url format not recognized!!")
 
    github_suffix=cleaned_url.replace(prefix + git_address,'')[1:]
    gitlab_suffix=github_suffix.replace('/', '%2F')
    gitlab_repo_api_url = f"{prefix}{git_address}/api/v4/projects/{gitlab_suffix}"
    repo_kind = ""
    if("github.com/" in source):
     response=_rate_limit_get(source.replace(f"{cleaned_url}",f"{prefix}api.github.com/repos/"), "github")
     repo_kind = "github"
    elif("gitlab.com/" in source):
     response=_rate_limit_get(gitlab_repo_api_url, "gitlab")
     repo_kind = "gitlab"
    elif f"{prefix}{git_address}/" not in GITAPI_REPO_BLACKLIST:
      if(repo_type_cache[cleaned_url] is None):
        #Proprietary repos
        response=_rate_limit_get(gitlab_repo_api_url, "gitlab")
        if(response.status_code > 400 and response.status_code < 500):
         #if fails try with github type
         response=_rate_limit_get(source.replace(f"{cleaned_url}",f"{prefix}{git_address}/api/v3/repos/"), "github")
         if(response): repo_kind = "github" 
        else: 
         repo_kind = "gitlab"
      else:
        repo_kind = repo_type_cache[f"{prefix}{git_address}/"]
    #Populate the cache even when there is a 4xx failure
    repo_type_cache[f"{prefix}{git_address}/"] = repo_kind
    if(repo_kind == "gitlab"):
       _parse_gitlab(response, g,res,f"{prefix}{git_address}", args)  
    elif(repo_kind == "gitlab"):
       _parse_github(response, g,res,f"{prefix}{git_address}", args)
    return cleaned_url

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
def _rate_limit_get(url:str, repo_kind:str,  backoff_rate=2, initial_backoff=1, **kwargs): 
    rate_limited = True
    response = {}
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
        response = requests.get(url, **kwargs)
        data = response
        rate_limit_remaining = data.headers["RateLimit-Remaining" if repo_kind == "gitlab" else "x-ratelimit-remaining"]
        epochtime = int(data.headers["RateLimit-Reset" if repo_kind == "gitlab" else  "x-ratelimit-reset"])
        date_reset = datetime.fromtimestamp(epochtime)
        print(f"Remaining {repo_kind} API requests: " + rate_limit_remaining + " ### Next rate limit reset at: " + str(date_reset) + f" (has_token={has_token})")
        response = response.json()
        if 'message' in response and 'API rate limit exceeded' in response['message']:
            rate_limited = True
            print(f"{repo_kind} API: rate limited. Backing off for {initial_backoff} seconds (has_token={has_token})", file=sys.stderr)
            sys.stderr.flush()
            if initial_backoff > 120:
                raise Exception(f"{repo_kind} API timed out because of rate limiting, giving up... (has_token={has_token})")
            time.sleep(initial_backoff)
            # increase the backoff for next time
            initial_backoff *= backoff_rate
        else:
            rate_limited = False
    return response

def _parse_github(response, g: Graph, res: Union[URIRef, BNode], source: str, args: AttribDict):
    """Query and parse from the github API"""
    users_api_url=f"{source}/api/v3/users/"
    if("github.com/" in source):
     users_api_url=source.replace("www.github.com/", "api.github.com/").replace("github.com/", "api.github.com/") + "/users/"
    
    owner=response['owner']['login']
    #repo = response['name']
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

    if response.get('has_issues', False) and response.get("html_url"):
        g.add((res, CODEMETA.issueTracker, Literal(response['html_url'] + "/issues")))

    if 'owner' in response:
        owner_api_url = f"{users_api_url}/{owner}"
        response = _rate_limit_get(owner_api_url, "github")
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
def _parse_gitlab(response, g: Graph, res: Union[URIRef, BNode], source, args: AttribDict):
    """Query and parse from the gitlab API"""
    users_api_url = f"{source}/api/v4/users/"
    #Processing start
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

    #https://docs.gitlab.com/ee/api/users.html
    #namespace kind kind can be just group or user
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
        response_owner = _rate_limit_get(owner_api_url, "gitlab")
        owner_name=response_owner['owner']['name']
        user_url=response_owner['owner']['web_url']
        if response_owner.get('public_email'):
            public_mail = response_owner.get('public_email')
    else:  return
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
     creator_id_str=str(response['creator_id'])
     if(creator_id_str != owner_id_str):
        creator_api_url = users_api_url +  creator_id_str
        response_creator = _rate_limit_get(creator_api_url, "gitlab")
        response_creator_url_field=response_creator['web_url']
    #Object X must be an rdflib term:  g.add((URIRef(response_creator_url_field), SDO.author, response_creator_name))
    #g.add((res, SDO.maintainer, owner_res))
    #if response_owner.get('work_information'): is like company?