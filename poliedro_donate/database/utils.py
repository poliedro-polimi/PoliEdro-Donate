import json
import warnings
from functools import wraps
from typing import AnyStr, Union, cast

from poliedro_donate.database import db
from poliedro_donate.database._helpers import json2db_shirt, deconstruct_object
from .models import *


# JSON_SG3_GOOD = {
#     "donation": 35,
#     "stretch_goal": 3,
#     "items": 3,
#     "shirts": [
#         {"size": "XS", "type": "tank_top"},
#         {"size": "L", "type": "t-shirt"},
#         {"size": "XXL", "type": "t-shirt"}
#     ],
#     "notes": "",
#     "reference": {
#         "firstname": "Davide",
#         "lastname": "Depau",
#         "email": "email@domain.com",
#         "phone": "+393200000000",
#         "location": "leonardo"
#     },
#     "lang": "it"
# }

# https://gist.github.com/yashh/14d12595f3dfa307a354
def commit_on_success(func):
    def _commit_on_success(*args, **kw):
        db = func.func_globals['db']
        try:
            res = func(*args, **kw)
        except Exception:
            if db.session.dirty:
                db.session.rollback()
                raise
        else:
            if db.session.dirty:
                try:
                    db.session.commit()
                except:
                    db.session.rollback()
                    raise
        return res

    return wraps(func)(_commit_on_success)


@commit_on_success
def register_donation(json: dict, payment_id: str, payment_obj: AnyStr) -> Donation:
    user = register_reference(json["reference"], lang=json["lang"])
    t = Transaction(payment_id=payment_id, payment_obj=payment_obj)
    donation = Donation(
        amount=json["donation"],
        stretch_goal=json["stretch_goal"],
        items=json["items"],
        notes=json["notes"] if "notes" in json else "",
        reference=user,
        transaction=t
    )
    db.session.add(t)
    db.session.add(donation)

    if "shirts" in json:
        for s in json["shirts"]:
            dbs = Shirt(donation=donation, **(json2db_shirt(s)))
            db.session.add(dbs)

    return donation


@commit_on_success
def register_transaction(payment_id: AnyStr, payer_id: AnyStr, result, state: AnyStr):
    if type(result) != dict:
        result = deconstruct_object(result)

    query = Transaction.query.filter_by(payment_id=payment_id)
    t = cast(Transaction, query[0])

    t.payer_id = payer_id
    t.state = state
    t.payment_obj = json.dumps(result)


def register_reference(json: dict, lang: AnyStr) -> User:
    query = User.query.filter_by(lang=lang, **json)
    count = query.count()

    if count > 1:
        warnings.warn("Duplicate users found in database (last name: '{}')".format(json["lastname"]),
                      UserWarning)

    if count >= 1:
        user = query[0]
    else:
        user = User(lang=lang, **json)
        db.session.add(user)

    return user
