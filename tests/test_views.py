import json, pytest, sys
from flask import url_for

from .datasets import *

from poliedro_donate import app as application

if sys.version_info.major == 2:
    # noinspection PyShadowingBuiltins
    bytes = str
    # noinspection PyUnresolvedReferences,PyShadowingBuiltins
    str = unicode

@pytest.fixture
def app():
    application.config["APP_MODE"] = "development"
    application.config["PAYPAL_CLIENT_ID"] = "invalid"
    application.config["PAYPAL_CLIENT_SECRET"] = "invalid"
    return application


def test_paypal_create_payment_good(client):
    r = client.post(url_for('paypal_create_payment') + "?validate_only=1",
                    data=json.dumps(JSON_SG0_GOOD),
                    content_type="application/json")

    if isinstance(r.data, bytes):
        j = json.loads(r.data.decode())
    else:
        j = json.loads(r.data)

    assert r.status_code == 200
    assert j == {"success": "Provided JSON looks good"}


def test_paypal_create_payment_bad(client):
    r = client.post(url_for('paypal_create_payment') + "?validate_only=1",
                    data=json.dumps(JSON_STRETCH_GOAL_MISSING),
                    content_type="application/json")

    if isinstance(r.data, bytes):
        j = json.loads(r.data.decode())
    else:
        j = json.loads(r.data)

    assert r.status_code == 400
    assert j["error"]["type"] == "_VALIDATION_ERROR"


def test_paypal_create_payment_paypal_error(client):
    # validate_only is not specified and auth credentials are invalid
    r = client.post(url_for('paypal_create_payment'),
                    data=json.dumps(JSON_SG0_GOOD),
                    content_type="application/json")

    if isinstance(r.data, bytes):
        j = json.loads(r.data.decode())
    else:
        j = json.loads(r.data)

    assert r.status_code == 502
    assert j["error"]["type"] == "_PAYPAL_ERROR"


def test_paypal_execute_payment_good(client):
    r = client.post(url_for('paypal_execute_payment') + "?validate_only=1",
                    data=json.dumps(JSON_EXECUTE_PAYMENT_GOOD),
                    content_type="application/json")

    if isinstance(r.data, bytes):
        j = json.loads(r.data.decode())
    else:
        j = json.loads(r.data)

    assert r.status_code == 200
    assert j == {"success": "Provided JSON looks good"}


def test_paypal_execute_payment_bad(client):
    r = client.post(url_for('paypal_execute_payment') + "?validate_only=1",
                    data=json.dumps(JSON_EXECUTE_PAYMENT_BAD),
                    content_type="application/json")

    if isinstance(r.data, bytes):
        j = json.loads(r.data.decode())
    else:
        j = json.loads(r.data)

    assert r.status_code == 400
    assert j["error"]["type"] == "_VALIDATION_ERROR"


def test_paypal_execute_payment_paypal_error(client):
    # validate_only is not specified and auth credentials are invalid
    r = client.post(url_for('paypal_execute_payment'),
                    data=json.dumps(JSON_EXECUTE_PAYMENT_GOOD),
                    content_type="application/json")

    if isinstance(r.data, bytes):
        j = json.loads(r.data.decode())
    else:
        j = json.loads(r.data)

    assert r.status_code == 502
    assert j["error"]["type"] == "_PAYPAL_ERROR"
