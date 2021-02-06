"""
This module simply contains a few common Languages with their language-codes
and QIDs for easier use.
"""
from dataclasses import dataclass


@dataclass
class Language:
    """Dataclass representing a language"""

    short: str
    qid: str


# feel free to add more languages
en = Language("en", "Q1860")
de = Language("de", "Q188")
fr = Language("fr", "Q150")
ru = Language("ru", "Q7737")
et = Language("et", "Q9072")
la = Language("la", "Q397")
he = Language("he", "Q9288")
sv = Language("sv", "Q9027")
eu = Language("eu", "Q8752")
cs = Language("cs", "Q9056")
sk = Language("sk", "Q9058")
da = Language("da", "Q9035")
