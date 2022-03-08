import csv
import os.path
from collections import defaultdict

class CWKey:
    """Crosswalk Keys, corresponds with header label in crosswalk.csv, as
    provided by the CodeMeta project"""
    PROP = "Property"
    PARENT = "Parent Type"
    TYPE = "Type"
    DESCRIPTION = "Description"
    PYPI = "Python Distutils (PyPI)"
    DEBIAN = "Debian Package"
    R = "R Package Description"
    NODEJS = "NodeJS"
    MAVEN = "Java (Maven)"
    DOAP = "DOAP"

def readcrosswalk(sourcekeys=(CWKey.PYPI,CWKey.DEBIAN,CWKey.NODEJS, CWKey.MAVEN)):
    """Read the crosswalk.csv as provided by codemeta into memory"""
    #pylint: disable=W0621
    crosswalk = defaultdict(dict)
    #pip may output things differently than recorded in distutils/setup.py, so we register some aliases:
    crosswalk[CWKey.PYPI]["home-page"] = "url"
    crosswalk[CWKey.PYPI]["summary"] = "description"
    props = {}
    crosswalkfile = os.path.join(os.path.dirname(__file__), 'schema','crosswalk.csv')
    with open(crosswalkfile, 'r', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            props[row[CWKey.PROP]] = {"PARENT": row[CWKey.PARENT], "TYPE": row[CWKey.TYPE], "DESCRIPTION": row[CWKey.DESCRIPTION] }
            for sourcekey in sourcekeys:
                if row[sourcekey]:
                    for key in [ x.strip().lower() for x in row[sourcekey].split("/") ]:
                        crosswalk[sourcekey][key] = row[CWKey.PROP]

    return props, crosswalk
