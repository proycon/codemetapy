#!/usr/bin/env python3

import sys
import os
import unittest
import json
from rdflib import Graph, BNode, URIRef, Literal
from rdflib.namespace import RDF, OWL
from codemeta.common import CODEMETA, SDO, AttribDict, SOFTWARETYPES, SOFTWAREIODATA, iter_ordered_list, SCHEMA_SOURCE, CODEMETA_SOURCE
from codemeta.codemeta import build, serialize

def debugout(g: Graph, s,p=None,o=None):
    print("DEBUG OUTPUT:", file=sys.stderr)
    for s,p,o in g.triples((s,p,o)):
        print(s,p,o, file=sys.stderr)

class BuildTest_Json(unittest.TestCase):
    """Build codemeta.json from existing codemeta.json (basically a parse, validation/reconciliation and reserialisation)"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["frog.codemeta.json"])

    def test001_sanity(self):
        """Testing whether a codemeta.json was read accurately, tests some basic properties"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)

    def test002_basics(self):
        """Testing some basic identifying properties"""
        self.assertIn( (self.res, SDO.identifier, Literal("frog")), self.g)
        self.assertIn( (self.res, SDO.name, Literal("Frog")), self.g)
        self.assertIn( (self.res, SDO.description, None), self.g) #doesn't test actual value
        self.assertIn( (self.res, SDO.version, Literal("0.26")), self.g)

    def test003_urlref(self):
        """Testing some common URL References"""
        self.assertIn( (self.res, SDO.codeRepository, URIRef("https://github.com/LanguageMachines/frog")), self.g)
        self.assertIn( (self.res, SDO.license, URIRef("http://spdx.org/licenses/GPL-3.0-only")), self.g)
        self.assertIn( (self.res, SDO.url, URIRef("https://languagemachines.github.io/frog")), self.g)

    def test004_codemeta_urlref(self):
        """Testing some codemeta URL References"""
        self.assertIn( (self.res, CODEMETA.developmentStatus, URIRef("https://www.repostatus.org/#active")), self.g)
        self.assertIn( (self.res, CODEMETA.issueTracker, URIRef("https://github.com/LanguageMachines/frog/issues")), self.g)
        self.assertIn( (self.res, CODEMETA.contIntegration, URIRef("https://travis-ci.org/LanguageMachines/frog")), self.g)
        self.assertIn( (self.res, CODEMETA.readme, URIRef("https://github.com/LanguageMachines/frog/blob/master/README.md")), self.g)

    def test005_os(self):
        """Testing operatingSystem property"""
        self.assertIn( (self.res, SDO.operatingSystem, Literal("Linux")), self.g)
        self.assertIn( (self.res, SDO.operatingSystem, Literal("BSD")), self.g)
        self.assertIn( (self.res, SDO.operatingSystem, Literal("macOS")), self.g)

    def test006_keywords(self):
        """Testing keywords property (not exhausively)"""
        self.assertIn( (self.res, SDO.keywords, Literal("nlp")), self.g)
        self.assertIn( (self.res, SDO.keywords, Literal("dutch")), self.g)

    def test007_datecreated(self):
        """Testing dateCreated property"""
        self.assertIn( (self.res, SDO.dateCreated,Literal("2011-03-31T12:35:01Z+0000",datatype=URIRef('http://schema.org/Date'))), self.g)

    def test008_authors(self):
        """Testing authors (sorted rdf list!) (not exhaustively)"""
        i = 0
        for i, (_,_,o) in enumerate(iter_ordered_list(self.g, self.res, SDO.author)):
            self.assertIn( (o, RDF.type, SDO.Person), self.g, "Testing if author is a schema:Person")
            self.assertIn( (o, SDO.givenName, None), self.g, "Testing if author has a givenName") #not testing actual value
            self.assertIn( (o, SDO.familyName, None), self.g, "Testing if author has a familyName") #not testing actual value
            self.assertIn( (o, SDO.email, None), self.g, "Testing if author has an email") #not testing actual value
        self.assertEqual(i+1, 3, "Testing number of authors")

        #testing one specific author
        self.assertIn( (URIRef("https://orcid.org/0000-0002-1046-0006"), SDO.givenName, Literal("Maarten")), self.g, "Testing specific author's givenName")
        self.assertIn( (URIRef("https://orcid.org/0000-0002-1046-0006"), SDO.familyName, Literal("van Gompel")), self.g, "Testing specific author's familyName")
        self.assertIn( (URIRef("https://orcid.org/0000-0002-1046-0006"), SDO.email, Literal("proycon@anaproy.nl")), self.g, "Testing specific author's email")
        self.assertIn( (URIRef("https://orcid.org/0000-0002-1046-0006"), SDO.position, Literal(3)), self.g, "Testing specific author's position")

    def test009_producer(self):
        """Testing producer (not exhaustively)"""
        self.assertIn( (self.res,SDO.producer, URIRef("https://huc.knaw.nl")), self.g, "Testing producer")
        self.assertIn( (URIRef("https://huc.knaw.nl"), SDO.name, Literal("KNAW Humanities Cluster")), self.g, "Testing producer name")
        self.assertIn( (URIRef("https://huc.knaw.nl"), SDO.url, URIRef("https://huc.knaw.nl")), self.g, "Testing producer url")

    def test010_softwarehelp(self):
        """Testing softwareHelp (not exhaustively)"""
        self.assertIn( (self.res,SDO.softwareHelp, URIRef("https://frognlp.readthedocs.io")), self.g, "Testing softwareHelp")
        self.assertIn( (URIRef("https://frognlp.readthedocs.io"), RDF.type, SDO.WebSite), self.g, "Testing softwareHelp type")

    def test011_funder(self):
        funders = [ x[2] for x in self.g.triples((self.res, SDO.funder, None)) ]
        self.assertEqual(len(funders), 2, "Testing number of funders")
        for x in funders:
            self.assertIn( (x, RDF.type, SDO.Organization), self.g, "Testing if funder is a schema:Organization")

    def test012_proglang(self):
        """Testing programming language (not exhaustively)"""
        langs = [ x[2] for x in self.g.triples((self.res, SDO.programmingLanguage, None)) ]
        self.assertEqual(len(langs), 1, "Testing number of programming languages")
        self.assertIn( (langs[0],RDF.type, SDO.ComputerLanguage), self.g, "Testing programming language type")

    def test013_targetproduct(self):
        """Testing target product"""
        targetproducts = [ x[2] for x in self.g.triples((self.res, SDO.targetProduct, None)) ]
        self.assertEqual(len(targetproducts), 5, "Testing number of target products")
        found = set()
        for x in targetproducts:
            name = self.g.value(x, SDO.name)
            self.assertIsNotNone(name)
            if name == Literal("libfrog"):
                self.assertIn( (x,RDF.type, SOFTWARETYPES.SoftwareLibrary), self.g, "Testing target product type ")
                found.add(1)
            elif name == Literal("frog"):
                self.assertIn( (x,RDF.type, SOFTWARETYPES.CommandLineApplication), self.g, "Testing target product type")
                self.assertIn( (x,SOFTWARETYPES.executableName, Literal("frog")), self.g, "Testing executable name")
                self.assertIn( (x,SDO.description, None), self.g, "Testing description") #not testing actual value
                self.assertIn( (x,SDO.runtimePlatform, Literal("Linux")), self.g, "Testing runtimePlatform")
                self.assertIn( (x,SDO.runtimePlatform, Literal("BSD")), self.g, "Testing runtimePlatform")
                self.assertIn( (x,SDO.runtimePlatform, Literal("macOS")), self.g, "Testing runtimePlatform")
                found.add(2)
            else:
                self.assertIn( (x,RDF.type, SOFTWARETYPES.CommandLineApplication), self.g, "Testing target product type")
        self.assertIn(1, found)
        self.assertIn(2, found)

    def test014_iodata(self):
        """Testing IO data"""
        targetproducts = [ x[2] for x in self.g.triples((self.res, SDO.targetProduct, None)) ]
        self.assertEqual(len(targetproducts), 5, "Testing number of target products")
        found = False
        for x in targetproducts:
            name = self.g.value(x, SDO.name)
            if name == Literal("frog"):
                for _,_, y in self.g.triples((x, SOFTWAREIODATA.consumesData, None)):
                    self.assertIn( (y,RDF.type, SDO.TextDigitalDocument), self.g, "Testing consumesData type")
                    self.assertTrue( (y,SDO.encodingFormat, Literal("text/plain")) in self.g or (y,SDO.encodingFormat, Literal("application/folia+xml")) in self.g, "Testing encoding")
                    self.assertIn( (y, SDO.inLanguage, None), self.g, "Testing inLanguage type") #not testing actual value
                    found = True
        self.assertTrue(found)

    def test100_serialisation_json(self):
        """Test json serialisation"""
        s = serialize(self.g, self.res, AttribDict({ "output": "json" }), self.contextgraph)
        data = json.loads(s)
        self.assertIn(SCHEMA_SOURCE, data['@context'], "Testing schema.org in context")
        self.assertIn(CODEMETA_SOURCE, data['@context'], "Testing codemeta in context")
        self.assertEqual(data['name'], "Frog", "Testing schema:name")
        self.assertEqual(data['@type'], "SoftwareSourceCode", "Testing type")
        self.assertTrue('description' in data,  "Testing schema:description")
        self.assertEqual(data['url'], "https://languagemachines.github.io/frog", "Testing schema:url")
        self.assertEqual(data['codeRepository'], "https://github.com/LanguageMachines/frog", "Testing schema:codeRepository")
        self.assertIsInstance(data['author'], list, "Testing whether authors are in a list")
        self.assertTrue( all(isinstance(x, dict) and x['@type'] == "Person" for x in data['author']), "Testing whether all authors are schema:Person")
        self.assertIsInstance(data['developmentStatus'], list, "Testing whether we have two development statusses in a list")
        self.assertTrue( all(isinstance(x, dict) and x['@type'] == "SoftwareApplication" for x in data['softwareRequirements']), "Testing softwareRequirements")
        self.assertTrue( all(isinstance(x, dict) and x['@type'] in ("CommandLineApplication","SoftwareLibrary") for x in data['targetProduct']), "Testing targetProducts")
        self.assertTrue( all(isinstance(x, dict) and x['@type'] in ("ScholarlyArticle","TechArticle") and isinstance(x['author'],list) and x['isPartOf']['@type'] == "PublicationIssue" for x in data['referencePublication']), "Testing referencePublication")
        self.assertEqual(data['softwareHelp']['@id'], "https://frognlp.readthedocs.io", "Testing softwareHelp ID")
        self.assertEqual(data['softwareHelp']['url'], "https://frognlp.readthedocs.io", "Testing softwareHelp URL")


    def test100_serialisation_turtle(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "ttl" }), self.contextgraph)

    def test100_serialisation_html(self):
        """Test html serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "html" }), self.contextgraph)


class BuildTest_SetupPy(unittest.TestCase):

    def setUp(self):
        #relies on automatically guessing the type based on the directory we are inputsources
        os.chdir("fusus")
        try:
            self.g, self.res, self.args, self.contextgraph = build()
        finally:
            os.chdir("..")

    def test001_sanity(self):
        """Testing whether a the basics were converted accurately, tests some basic properties"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)

    def test002_basics(self):
        """Testing some basic identifying properties"""
        self.assertIn( (self.res, SDO.identifier, Literal("fusus")), self.g)
        self.assertIn( (self.res, SDO.name, Literal("fusus")), self.g)
        self.assertIn( (self.res, SDO.description, None), self.g) #doesn't test actual value
        self.assertIn( (self.res, SDO.version, Literal("0.0.2")), self.g)

    def test003_urlref(self):
        """Testing some common URL References"""
        self.assertIn( (self.res, SDO.codeRepository, URIRef("https://github.com/among/fusus")), self.g)
        self.assertIn( (self.res, SDO.license, URIRef("http://spdx.org/licenses/MIT")), self.g)
        self.assertIn( (self.res, SDO.url, URIRef("https://github.com/among/fusus")), self.g)

    def test004_codemeta_urlref(self):
        """Testing some codemeta URL References"""
        self.assertIn( (self.res, CODEMETA.developmentStatus, URIRef("https://www.repostatus.org/#wip")), self.g)

    def test006_keywords(self):
        """Testing keywords property (not exhaustively)"""
        self.assertIn( (self.res, SDO.keywords, Literal("arabic")), self.g)
        self.assertIn( (self.res, SDO.keywords, Literal("islam")), self.g)

    def test008_authors(self):
        """Testing authors (not exhaustively)"""
        i = 0
        for i, (_,_,o) in enumerate(iter_ordered_list(self.g, self.res, SDO.author)):
            self.assertIn( (o, RDF.type, SDO.Person), self.g, "Testing if author is a schema:Person")
            self.assertIn( (o, SDO.givenName, None), self.g, "Testing if author has a givenName") #not testing actual value
            self.assertIn( (o, SDO.familyName, None), self.g, "Testing if author has a familyName") #not testing actual value
        self.assertEqual(i+1, 2, "Testing number of authors")


    def test100_serialisation_json(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "json" }), self.contextgraph)

    def test100_serialisation_turtle(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "ttl" }), self.contextgraph)

    def test100_serialisation_html(self):
        """Test html serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "html" }), self.contextgraph)

class BuildTest_GithubAPI(unittest.TestCase):
    """Build codemeta.json from existing codemeta.json (basically a parse, validation/reconciliation and reserialisation)"""

    def setUp(self):
        #relies on automatically guessing the type
        #deliberately picked software that is end-of-life and will not change much anymore
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["https://github.com/proycon/labirinto"])

    def test001_api(self):
        """Testing github API response"""
        #this is a single combined test to save API queries
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)
        self.assertIn( (self.res, SDO.name, Literal("labirinto")), self.g)
        self.assertIn( (self.res, SDO.codeRepository, URIRef("https://github.com/proycon/labirinto")), self.g)
        self.assertIn( (self.res, CODEMETA.issueTracker, URIRef("https://github.com/proycon/labirinto/issues")), self.g)
        self.assertIn( (self.res, SDO.description, None), self.g) #doesn't test actual value
        self.assertIn( (self.res, SDO.keywords, Literal("codemeta")), self.g)

class BuildTest_JavaPomXML(unittest.TestCase):
    """Build codemeta.json from pom.xml"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["widoco.pom.xml"])

    def test001_sanity(self):
        """Testing whether a pom.xml was read accurately, tests some basic properties"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)

    def test002_basics(self):
        """Testing some basic identifying properties"""
        self.assertIn( (self.res, SDO.name, Literal("Widoco")), self.g)
        self.assertIn( (self.res, SDO.version, Literal("1.4.17")), self.g)
        self.assertIn( (self.res, SDO.runtimePlatform, Literal("Java 1.8")), self.g)

    def test100_serialisation_json(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "json" }), self.contextgraph)

    def test100_serialisation_turtle(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "ttl" }), self.contextgraph)

    def test100_serialisation_html(self):
        """Test html serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "html" }), self.contextgraph)

class BuildTest_NpmPackageJSON(unittest.TestCase):
    """Build codemeta.json from npm package json"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["labirinto.package.json"])

    def test001_sanity(self):
        """Testing whether a package.json was read accurately, tests some basic properties"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)

    def test002_basics(self):
        """Testing some basic identifying properties"""
        self.assertIn( (self.res, SDO.name, Literal("labirinto")), self.g)
        self.assertIn( (self.res, SDO.version, Literal("0.2.6")), self.g)
        self.assertIn( (self.res, SDO.runtimePlatform, Literal("npm >= 3.0.0")), self.g)
        self.assertIn( (self.res, SDO.runtimePlatform, Literal("node >= 6.0.0")), self.g)

    def test003_urlref(self):
        """Testing some common URL References"""
        self.assertIn( (self.res, SDO.codeRepository, URIRef("https://github.com/proycon/labirinto")), self.g)
        self.assertIn( (self.res, SDO.license, URIRef("http://spdx.org/licenses/AGPL-3.0-or-later")), self.g)
        self.assertIn( (self.res, SDO.url, URIRef("https://github.com/proycon/labirinto")), self.g)
        self.assertIn( (self.res, CODEMETA.issueTracker, URIRef("https://github.com/proycon/labirinto/issues")), self.g)

    def test100_serialisation_json(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "json" }), self.contextgraph)

    def test100_serialisation_turtle(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "ttl" }), self.contextgraph)

    def test100_serialisation_html(self):
        """Test html serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "html" }), self.contextgraph)

class BuildTest_Web_HTML(unittest.TestCase):
    """Build codemeta.json from webpage metadata"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["https://shebanq.ancient-data.org/"], with_stypes=True)

    def test001(self):
        """Testing basic properties"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)
        service = self.g.value(self.res, SDO.targetProduct)
        self.assertIsNotNone(service)
        self.assertIn( (service, RDF.type, SDO.WebApplication), self.g)
        self.assertIn( (service, SDO.url, Literal("https://shebanq.ancient-data.org/")), self.g)
        self.assertIn( (service, SDO.name, Literal("SHEBANQ")), self.g)
        self.assertIn( (service, SDO.description, None), self.g) #not testing value
        self.assertIn( (service, SDO.author, None), self.g) #not testing value
        self.assertIn( (service, SDO.keywords, Literal("Hebrew")), self.g)
        self.assertIn( (service, SDO.keywords, Literal("Bible")), self.g)

class BuildTest_Web_JSONLD(unittest.TestCase):
    """Build codemeta.json from webpage metadata (JSON-LD)"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["https://www.delpher.nl/"], with_stypes=True)

    def test001(self):
        """Testing basic properties"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)
        service = self.g.value(self.res, SDO.targetProduct)
        self.assertIsNotNone(service)
        self.assertIn( (service, RDF.type, SDO.WebSite), self.g)
        self.assertIn( (service, SDO.url, URIRef("https://www.delpher.nl/")), self.g)
        self.assertIn( (service, SDO.potentialAction, None), self.g) #not testing value

class BuildTest_Combine(unittest.TestCase):
    """Combine two inputs for the same resource"""

    def setUp(self):
        #relies on automatically guessing the types
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["labirinto.package.json", "labirinto.codemeta-harvest.json"])

    def test001_sanity(self):
        """Testing whether a package.json was read accurately, tests some basic properties"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)

    def test002_basics(self):
        """Testing some basic identifying properties"""
        self.assertIn( (self.res, SDO.name, Literal("labirinto")), self.g)
        self.assertIn( (self.res, SDO.version, Literal("0.2.6")), self.g)
        self.assertIn( (self.res, SDO.runtimePlatform, Literal("npm >= 3.0.0")), self.g)
        self.assertIn( (self.res, SDO.runtimePlatform, Literal("node >= 6.0.0")), self.g)

    def test003_urlref(self):
        """Testing some common URL References"""
        self.assertIn( (self.res, SDO.codeRepository, URIRef("https://github.com/proycon/labirinto")), self.g)
        self.assertIn( (self.res, SDO.license, URIRef("http://spdx.org/licenses/AGPL-3.0-or-later")), self.g)
        self.assertIn( (self.res, SDO.url, URIRef("https://github.com/proycon/labirinto")), self.g)
        self.assertIn( (self.res, CODEMETA.issueTracker, URIRef("https://github.com/proycon/labirinto/issues")), self.g)

    def test004_combined(self):
        """Testing properties that come from the second resource"""
        self.assertIn( (self.res, CODEMETA.developmentStatus, URIRef("https://www.repostatus.org/#unsupported")), self.g)
        self.assertIn( (self.res, CODEMETA.issueTracker, URIRef("https://github.com/proycon/labirinto/issues")), self.g)
        producer = self.g.value(self.res, SDO.producer)
        self.assertIsNotNone(producer)
        self.assertIn( (producer, RDF.type, SDO.Organization), self.g)
        self.assertIn( (producer, SDO.name, Literal("Centre for Language and Speech Technology")), self.g)
        parent = self.g.value(producer, SDO.parentOrganization)
        self.assertIsNotNone(parent)
        self.assertIn( (parent, RDF.type, SDO.Organization), self.g)
        self.assertIn( (parent, SDO.name, Literal("Centre for Language Studies")), self.g)
        grandparent = self.g.value(parent, SDO.parentOrganization)
        self.assertIsNotNone(grandparent)
        self.assertIn( (grandparent, RDF.type, SDO.Organization), self.g)
        self.assertIn( (grandparent, SDO.name, Literal("Radboud University")), self.g)

class BuildTest_CombineRepostatus(unittest.TestCase):
    """Combine two repostatuses for the same resource"""

    def setUp(self):
        #relies on automatically guessing the types
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["withoutid.codemeta.json", "withid.codemeta.json"])

    def test001_combine_repostatus(self):
        """Testing whether second repostatus overwrites the first one"""
        self.assertIn( (self.res, CODEMETA.developmentStatus, URIRef("https://www.repostatus.org/#active")), self.g)
        self.assertNotIn( (self.res, CODEMETA.developmentStatus, URIRef("https://www.repostatus.org/#inactive")), self.g)

class BuildTest_Enrich(unittest.TestCase):
    """Build codemeta.json from existing codemeta.json (basically a parse, validation/reconciliation and reserialisation)"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["frog.codemeta.json"], enrich=True)

    def test001_sanity(self):
        """Testing whether a codemeta.json was read accurately, tests some basic properties"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertIn( (self.res, RDF.type, SDO.SoftwareSourceCode), self.g)

class BuildTest_RetainId(unittest.TestCase):
    """Build codemeta.json from existing codemeta.json with absolute identifier (no baseuri set)"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["withid.codemeta.json"])

    def test001_maintain_id(self):
        """Testing whether ID is retained properly"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertEqual( URIRef("http://example.org/test"), self.res, "Testing whether resource is as expected")
        self.assertIn( (URIRef("http://example.org/test"), None,None), self.g)

class BuildTest_NewId(unittest.TestCase):
    """Build codemeta.json from existing codemeta.json with identifier"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["withid.codemeta.json"],baseuri="https://tools.clariah.nl/")

    def test001_new_id(self):
        """Testing whether ID is retained properly"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertEqual( URIRef("https://tools.clariah.nl/test/0.1"), self.res, "Testing whether resource is as expected")
        self.assertIn( (URIRef("https://tools.clariah.nl/test/0.1"), None,None), self.g)
        self.assertIn( (self.res,OWL.sameAs,URIRef("http://example.org/test")), self.g, "Test if old URI is referenced via owl:sameAs")

class BuildTest_NewId2(unittest.TestCase):
    """Build codemeta.json from existing codemeta.json, but do not use found identifier, force identifier from file"""

    def setUp(self):
        #relies on automatically guessing the type
        self.g, self.res, self.args, self.contextgraph = build(inputsources=["withid.codemeta.json"],baseuri="https://tools.clariah.nl/", identifier_from_file=True)

    def test001_new_id(self):
        """Testing whether ID is retained properly"""
        self.assertIsInstance( self.g, Graph )
        self.assertIsInstance( self.res, URIRef)
        self.assertEqual( URIRef("https://tools.clariah.nl/withid/0.1"), self.res, "Testing whether resource is as expected")
        self.assertIn( (URIRef("https://tools.clariah.nl/withid/0.1"), None,None), self.g)
        self.assertIn( (self.res,OWL.sameAs,URIRef("http://example.org/test")), self.g, "Test if old URI is referenced via owl:sameAs")

if __name__ == '__main__':
    unittest.main()

