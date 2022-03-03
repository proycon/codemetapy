import json
from typing import IO
from codemeta.common import AttribDict, REPOSTATUS, license_to_spdx

#pylint: disable=W0621
def parsecodemeta(file_descriptor: IO, args: AttribDict) -> dict:
    """Parses a codemeta.json file"""
    data = json.load(file_descriptor)
    for key, value in data.items():
        if key == "developmentStatus":
            if args.with_repostatus and value.strip().lower() in REPOSTATUS:
                #map to repostatus vocabulary
                data[key] = "https://www.repostatus.org/#" + REPOSTATUS[value.strip().lower()]
        elif key == "license":
            data[key] = license_to_spdx(value, args)
    return data
