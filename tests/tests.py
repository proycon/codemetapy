#!/usr/bin/env python3

import sys
import os
import unittest
from rdflib import Graph, BNode, URIRef, Literal
from rdflib.namespace import RDF
from codemeta.common import CODEMETA, SDO, AttribDict
from codemeta.codemeta import build, serialize

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
        self.assertIn( (self.res, SDO.license, URIRef("https://spdx.org/licenses/GPL-3.0-only")), self.g)
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
        """Testing authors (not exhaustively)"""
        authors = [ x[2] for x in self.g.triples((self.res, SDO.author, None)) ]
        self.assertEqual(len(authors), 3, "Testing number of authors")
        for x in authors:
            self.assertIn( (x, RDF.type, SDO.Person), self.g, "Testing if author is a schema:Person")
            self.assertIn( (x, SDO.givenName, None), self.g, "Testing if author has a givenName") #not testing actual value
            self.assertIn( (x, SDO.familyName, None), self.g, "Testing if author has a familyName") #not testing actual value
            self.assertIn( (x, SDO.email, None), self.g, "Testing if author has an email") #not testing actual value

        #testing one specific author
        self.assertIn( (self.res,SDO.author, URIRef("https://orcid.org/0000-0002-1046-0006")), self.g, "Testing specific author")
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

    def test100_serialisation_json(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "json" }), self.contextgraph)

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
        self.g, self.res, self.args, self.contextgraph = build()
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
        """Testing keywords property (not exhausively)"""
        self.assertIn( (self.res, SDO.keywords, Literal("arabic")), self.g)
        self.assertIn( (self.res, SDO.keywords, Literal("islam")), self.g)

    def test008_authors(self):
        """Testing authors (not exhaustively)"""
        authors = [ x[2] for x in self.g.triples((self.res, SDO.author, None)) ]
        self.assertEqual(len(authors), 2, "Testing number of authors")
        for x in authors:
            self.assertIn( (x, RDF.type, SDO.Person), self.g, "Testing if author is a schema:Person")
            self.assertIn( (x, SDO.givenName, None), self.g, "Testing if author has a givenName") #not testing actual value
            self.assertIn( (x, SDO.familyName, None), self.g, "Testing if author has a familyName") #not testing actual value


    def test100_serialisation_json(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "json" }), self.contextgraph)

    def test100_serialisation_turtle(self):
        """Test json serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "ttl" }), self.contextgraph)

    def test100_serialisation_html(self):
        """Test html serialisation"""
        serialize(self.g, self.res, AttribDict({ "output": "html" }), self.contextgraph)

if __name__ == '__main__':
    unittest.main()

