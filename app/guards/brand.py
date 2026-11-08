import re

from pydantic import BaseModel

OTHER_BANKS = [
    "hnb", "hatton national", "sampath", "bank of ceylon", "boc", "people's bank", "peoples bank",
    "ndb", "dfcc", "nations trust", "seylan", "pan asia", "union bank", "amana",
]
OTHER_BANK = re.compile(r"\b(" + "|".join(re.escape(name) for name in OTHER_BANKS) + r")\b", re.IGNORECASE)
COMPARISON = re.compile(r"\b(better|worse|best|cheaper|superior|inferior|versus|vs\.?|compared (to|with)|than)\b",
                        re.IGNORECASE)
REFUSAL = re.compile(r"\b(can(no|')t|can not|won't|will not|unable to|do not|don't)\b.{0,20}\b(compare|say|rank|recommend)\b",
                     re.IGNORECASE)
ADVICE = re.compile(
    r"\b(you should (buy|sell|invest)|i (would )?recommend (buying|selling|investing)|guaranteed (return|profit)s?"
    r"|(buy|sell) (this|these) (stock|share|bond)s?)\b",
    re.IGNORECASE,
)


class BrandCheck(BaseModel):
    ok: bool
    reason: str = ""


def check_brand(text: str) -> BrandCheck:
    if OTHER_BANK.search(text) and COMPARISON.search(text) and not REFUSAL.search(text):
        return BrandCheck(ok=False, reason="The answer compares Commercial Bank with another bank (POL-BRAND-001 3.1).")
    if ADVICE.search(text):
        return BrandCheck(ok=False, reason="The answer gives personal financial advice (POL-BRAND-001 3.2).")
    return BrandCheck(ok=True)
