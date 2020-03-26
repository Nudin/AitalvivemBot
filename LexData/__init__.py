# -*-coding:utf-8-*
import json
import logging
from typing import Any, Dict, List, Optional

import requests

name = "LexData"
version = "0.1.13"
user_agent = "%s %s" % (name, version)


class WikidataSession:
    """Wikidata network and authentication session. Needed for everything this
    framework does.


    """

    URL = "https://www.wikidata.org/w/api.php"
    assertUser = None

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        auth: Optional[str] = None,
        user_agent=user_agent,
    ):
        """
        Create a wikidata session by logging in and getting the token
        """
        self.username = username
        self.password = password
        self.auth = auth
        self.headers = {"User-Agent": user_agent}
        self.S = requests.Session()
        if username is not None and password is not None:
            self.login()
        if token is not None:
            self.CSRF_TOKEN = token
        # After logging in enable 'assertUser'-feature of the Mediawiki-API to
        # make sure to never edit accidentally as IP
        if username is not None:
            self.assertUser = username

    def login(self):
        # Ask for a token
        PARAMS_1 = {
            "action": "query",
            "meta": "tokens",
            "type": "login",
            "format": "json",
        }
        DATA = self.get(PARAMS_1)
        LOGIN_TOKEN = DATA["query"]["tokens"]["logintoken"]

        # connexion request
        PARAMS_2 = {
            "action": "login",
            "lgname": self.username,
            "lgpassword": self.password,
            "format": "json",
            "lgtoken": LOGIN_TOKEN,
        }
        self.post(PARAMS_2)

        PARAMS_3 = {"action": "query", "meta": "tokens", "format": "json"}
        DATA = self.get(PARAMS_3)
        self.CSRF_TOKEN = DATA["query"]["tokens"]["csrftoken"]

    def post(self, data: Dict[str, str]) -> Any:
        """Send data to wikidata by POST request. The CSRF token is automatically
        filled in if __AUTO__ is given instead.

        :param data: Parameters to send via POST
        :type  data: Dict[str, str])
        :returns: Answer form the server as Objekt
        :rtype: Any

        """
        if data.get("token") == "__AUTO__":
            data["token"] = self.CSRF_TOKEN
        if "assertuser" not in data and self.assertUser is not None:
            data["assertuser"] = self.assertUser
        R = self.S.post(self.URL, data=data, headers=self.headers, auth=self.auth)
        if R.status_code != 200:
            raise Exception(
                "POST was unsuccessfull ({}): {}".format(R.status_code, R.text)
            )
        DATA = R.json()
        if "error" in DATA:
            raise PermissionError("API returned error: " + str(DATA["error"]))
        return DATA

    def get(self, data: Dict[str, str]) -> Any:
        """Send a GET request to wikidata

        :param data: Parameters to send via GET
        :type  data: Dict[str, str]
        :returns: Answer form the server as Objekt
        :rtype: Any

        """
        R = self.S.get(self.URL, params=data, headers=self.headers)
        if R.status_code != 200:
            raise Exception(
                "GET was unsuccessfull ({}): {}".format(R.status_code, R.text)
            )
        return R.json()


class Language:
    """Dataclass representing a language"""

    def __init__(self, short: str, qid: str):
        self.short = short
        self.qid = qid


class Claim(dict):
    """Wrapper around a dict to represent a Claim"""

    # Hack needed to define a property called property
    property_decorator = property

    def __init__(self, claim: Dict):
        super().__init__()
        self.update(claim)

    @property_decorator
    def value(self):
        """
        Return the value of the claim. The type depends on the data type.
        """
        return self["mainsnak"]["datavalue"]["value"]

    @property_decorator
    def type(self):
        """
        Return the data type of the claim.

        :rtype: str
        """
        return self["mainsnak"]["datavalue"]["type"]

    @property_decorator
    def property(self):
        """
        Return the property of the claim.

        :rtype: str
        """
        return self["mainsnak"]["property"]

    @property_decorator
    def rank(self):
        """
        Return the rank of the claim.

        :rtype: str
        """
        return self["rank"]

    @property_decorator
    def numeric_rank(self):
        """
        Return the rank of the claim as integer.

        :rtype: int
        """
        if self.rank == "normal":
            return 0
        elif self.rank == "preferred":
            return 1
        elif self.rank == "deprecated":
            return -1
        raise NotImplementedError("Unknown or invalid rank {}".format(self.rank))

    @property_decorator
    def pure_value(self):
        """
        Return just the 'pure' value, what this is depends on the type of the value:
        - wikibase-entity: the id, including 'L/Q/P'-prefix
        - string: the string
        - manolingualtext: the text as string
        - quantity: the amount as float
        - time: the timestamp as string in format ISO 8601
        - globecoordinate: tuple of latitude and longitude as floats

        Be aware that for most types this is not the full information stored in
        the value.
        """
        value = self.value
        vtype = self.type
        if vtype == "wikibase-entityid":
            return value["id"]
        if vtype == "string":
            return value
        if vtype == "monolingualtext":
            return value["text"]
        if vtype == "quantity":
            return float(value["amount"])
        if vtype == "time":
            return value["time"]
        if vtype == "globecoordinate":
            return (float(value["latitude"]), float(value["longitude"]))
        raise NotImplementedError

    def __repr__(self) -> str:
        return "<Claim '{}'>".format(repr(self.value))

    def __str__(self) -> str:
        return super().__repr__()


class Form(dict):
    """Wrapper around a dict to represent a From"""

    def __init__(self, form: Dict):
        super().__init__()
        self.update(form)

    def form(self) -> str:
        """
        String of the form value ("representation")

        :rtype: str
        """
        return list(self["representations"].values())[0]["value"]

    def claims(self) -> Dict[str, List[Claim]]:
        """
        All the claims of the Form

        :rtype: Dict[str, List[Claim]]
        """
        return {k: [Claim(c) for c in v] for k, v in self["claims"].items()}

    def __repr__(self) -> str:
        return "<Form '{}'>".format(self.form())

    def __str__(self) -> str:
        return super().__repr__()


class Sense(dict):
    """Wrapper around a dict to represent a Sense"""

    def __init__(self, form: Dict):
        super().__init__()
        self.update(form)

    def glosse(self, lang="en") -> str:
        """
        The gloss of the text in the specified language is available, otherwise
        in englisch, and if that's not set too in an arbitrary set language

        :param lang: language code of the wished language
        :type  lang: str
        :rtype: str
        """
        if lang not in self["glosses"]:
            if "en" in self["glosses"]:
                lang = "en"
            else:
                lang = list(self["glosses"].keys())[0]
        return self["glosses"][lang]["value"]

    def claims(self) -> Dict[str, List[Claim]]:
        """
        All the claims of the Sense

        :rtype: Dict[str, List[Claim]]
        """
        if self["claims"]:
            return {k: [Claim(c) for c in v] for k, v in self["claims"].items()}
        else:
            return {}

    def __repr__(self) -> str:
        return "<Sense '{}'>".format(self.glosse())

    def __str__(self) -> str:
        return super().__repr__()


class Lexeme(dict):
    """Wrapper around a dict to represent a Lexeme"""

    def __init__(self, repo: WikidataSession, idLex: str):
        super().__init__()
        self.repo = repo
        self.getLex(idLex)

    def getLex(self, idLex: str):
        """this function gets and returns the data of a lexeme for a given id

        :param idLex: Lexeme identifier (example: "L2")
        :type  idLex: str
        :returns: Simplified object representation of Lexeme

        """

        PARAMS = {"action": "wbgetentities", "format": "json", "ids": idLex}

        DATA = self.repo.get(PARAMS)

        self.update(DATA["entities"][idLex])

    @property
    def lemma(self) -> str:
        """
        the lemma of the lexeme as string

        :rtype: str
        """
        return list(self["lemmas"].values())[0]["value"]

    @property
    def language(self) -> str:
        """
        the language code of the lexeme as string

        :rtype: str
        """
        return list(self["lemmas"].values())[0]["language"]

    @property
    def claims(self) -> Dict[str, List[Claim]]:
        """
        All the claims of the lexeme

        :rtype: Dict[str, List[Claim]]
        """
        return {k: [Claim(c) for c in v] for k, v in super().get("claims", {}).items()}

    @property
    def forms(self) -> List[Form]:
        """
        List of all forms

        :rtype: List[Form]
        """
        return [Form(f) for f in super().get("forms", [])]

    @property
    def senses(self) -> List[Sense]:
        """
        List of all senses

        :rtype: List[Sense]
        """
        return [Sense(s) for s in super().get("senses", [])]

    def createSense(self, glosses: Dict[str, str], claims=None) -> str:
        """Create a sense for the lexeme

        :param glosses: glosses for the sense
        :type  glosses: Dict[str, str]
        :param claims: claims to add to the new form (Default value = None) -> st)
        :rtype: str

        """
        # Create the json with the sense's data
        data_sense = {"glosses": {}}
        for lang, gloss in glosses.items():
            data_sense["glosses"][lang] = {"value": gloss, "language": lang}

        # send a post to add sense to lexeme
        PARAMS = {
            "action": "wbladdsense",
            "format": "json",
            "lexemeId": self["id"],
            "token": "__AUTO__",
            "bot": "1",
            "data": json.dumps(data_sense),
        }
        DATA = self.repo.post(PARAMS)
        idSense = DATA["sense"]["id"]
        logging.info("---Created sense: idsense = %s", idSense)

        # Add the claims
        if claims:
            self.__setClaims__(idSense, claims)

        self.getLex(self["id"])
        return idSense

    def createForm(
        self, form: str, infosGram: List[str], language: Language = None, claims=None
    ) -> str:
        """Create a form for the lexeme

        :param form: the new form to add
        :type  form: str
        :param infosGram: grammatical features
        :type  infosGram: List[str]
        :param language: the language of the form
        :type  language: Optional[Language]
        :param claims: claims to add to the new form (Default value = None) -> st)
        :returns: The id of the form
        :rtype: str

        """

        if language is None:
            languagename = self.language
        else:
            languagename = language.short

        # Create the json with the forms's data
        data_form = json.dumps(
            {
                "representations": {
                    languagename: {"value": form, "language": languagename}
                },
                "grammaticalFeatures": infosGram,
            }
        )

        # send a post to add form to lexeme
        PARAMS = {
            "action": "wbladdform",
            "format": "json",
            "lexemeId": self["id"],
            "token": "__AUTO__",
            "bot": "1",
            "data": data_form,
        }
        DATA = self.repo.post(PARAMS)
        idForm = DATA["form"]["id"]
        logging.info("---Created form: idForm = %s", idForm)

        # Add the claims
        if claims:
            self.__setClaims__(idForm, claims)

        self.getLex(self["id"])
        return idForm

    def createClaims(self, claims):
        """Add claims to the Lexeme

        :param claims: The set of claims to be added

        """
        self.__setClaims__(self["id"], claims)

    def __setClaims__(self, parent: str, claims):
        """
        Add claims to a Lexeme, Form or Sense

        :type  parent: string
        :param parent: the id of the Lexeme/Form/Sense
        :type  claims: dict(List[dict()])
        :param claims: The set of claims to be added
        """
        for cle, values in claims.items():
            for value in values:
                self.__setClaim__(parent, cle, value)
        self.getLex(self["id"])

    def __setClaim__(self, parent: str, idProp: str, idItem: str):
        """
        Add a claim to an existing lexeme/form/sense

        :type  parent: string
        :param parent: the id of the Lexeme/Form/Sense
        :param idProp: id of the property
        :param idItem: id of the Item
        """

        claim_value = json.dumps({"entity-type": "item", "numeric-id": idItem[1:]})

        PARAMS = {
            "action": "wbcreateclaim",
            "format": "json",
            "entity": parent,
            "snaktype": "value",
            "bot": "1",
            "property": idProp,
            "value": claim_value,
            "token": "__AUTO__",
        }

        try:
            DATA = self.repo.post(PARAMS)
            assert "claim" in DATA
            logging.info("---claim added")
        except Exception as e:
            raise Exception("Unknown error adding claim", e)


def get_or_create_lexeme(repo, lemma: str, lang: Language, catLex: str) -> Lexeme:
    """Search for a lexeme in wikidata if not found, create it

    :param repo: Wikidata Session
    :type  repo: WikidataSession
    :param lemma: the lemma of the lexeme
    :type  lemma: str
    :param lang: language of the lexeme
    :type  lang: Language
    :param catLex: lexical Category of the lexeme
    :type  catLex: str
    :returns: Lexeme with the specified properties (created or found)
    :rtype: Lexeme

    """

    # the language we search in actually doesn't really matter
    # set it nevertheless, except if it is a Language without ISO code
    if lang.short[:3] == "mis":
        searchlang = "en"
    else:
        searchlang = lang.short

    PARAMS = {
        "action": "wbsearchentities",
        "language": searchlang,
        "type": "lexeme",
        "search": lemma,
        "format": "json",
    }

    DATA = repo.get(PARAMS)

    if "error" in DATA:
        raise Exception(DATA["error"])

    for item in DATA["search"]:
        # if the lexeme exists
        if item["label"] == lemma:
            idLex = item["id"]
            lexeme = Lexeme(repo, idLex)
            if lexeme["language"] == lang.qid and lexeme["lexicalCategory"] == catLex:
                logging.info("--Found lexeme, id = %s", idLex)
                return lexeme

    # Not found, create the lexeme
    return create_lexeme(repo, lemma, lang, catLex)


def create_lexeme(repo, lemma: str, lang: Language, catLex: str, claims=None) -> Lexeme:
    """Creates a lexeme

    :param repo: Wikidata Session
    :type  repo: WikidataSession
    :param lemma: value of the lexeme
    :type  lemma: str
    :param lang: language
    :type  lang: Language
    :param catLex: lexicographical category
    :param claims: claims to add to the lexeme (Default value = None) -> Lexem)
    :type  catLex: str
    :returns: The created Lexeme
    :rtype: Lexeme

    """

    # Create the json with the lexeme's data
    data_lex = json.dumps(
        {
            "type": "lexeme",
            "lemmas": {lang.short: {"value": lemma, "language": lang.short}},
            "language": lang.qid,
            "lexicalCategory": catLex,
            "forms": [],
        }
    )

    # Send a post to edit a lexeme
    PARAMS = {
        "action": "wbeditentity",
        "format": "json",
        "bot": "1",
        "new": "lexeme",
        "token": "__AUTO__",
        "data": data_lex,
    }

    DATA = repo.post(PARAMS)
    # Get the id of the new lexeme
    idLex = DATA["entity"]["id"]

    logging.info("--Created lexeme : idLex = %s", idLex)
    lexeme = Lexeme(repo, idLex)

    if claims:
        lexeme.createClaims(claims)

    return lexeme
