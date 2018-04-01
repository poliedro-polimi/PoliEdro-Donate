from __future__ import print_function

import sys, traceback
import warnings
import braintreehttp
from flask import request, jsonify, url_for, g, Blueprint

from .. import app, strings, database, mail
from ..database.models import Transaction
from ..validator import validate_donation_request, validate_execute_request
from ..paypal import pp_client
from ..errors import DonationError
from ..utils import get_paypal_email

import paypalrestsdk.v1.payments as payments

paypal_bp = Blueprint('paypal', __name__)


@paypal_bp.route('/create', methods=('POST',))
def create_payment():
    req = request.get_json()

    try:
        validate_donation_request(req)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        raise

    if "lang" in req:
        lang = req["lang"]
    else:
        lang = "en"
    g.lang = lang

    if int(request.args.get("validate_only", 0)) and app.config["APP_MODE"] == "development":
        return jsonify({"success": "Provided JSON looks good"})

    if app.config.get("APP_MAX_STRETCH_GOAL", None) and req["stretch_goal"] > app.config["APP_MAX_STRETCH_GOAL"]:
        raise ValueError("Selected stretch goal isn't available at the moment.")

    # Store request into database
    donation = database.register_donation(req)

    try:
        body = {
            "payer": {
                "payment_method": "paypal"
            },
            "intent": "sale",
            "transactions": [{
                "amount": {
                    "total": str(req["donation"]),
                    "currency": "EUR"
                },
                "description": strings.PP_ITEM_NAME[lang] + " - " + strings.PP_ITEM_DESC(lang, req["stretch_goal"],
                                                                                         req[
                                                                                             "items"]) + " (id: {})".format(
                    donation.pretty_id)
            }],
            "redirect_urls": {
                "cancel_url": url_for("paypal.cancel"),
                "return_url": url_for("paypal.return_")
            },
        }

        payment_create_request = payments.PaymentCreateRequest()
        payment_create_request.request_body(body)

        try:
            payment_create_response = pp_client.execute(payment_create_request)
            payment = payment_create_response.result
        except IOError as ioe:
            ioe.body = body
            raise

        # Store transaction into database
        database.add_transaction_details(donation, payment.id, body)

        return jsonify({
            "payment_id": payment.id,
            "donation_id": donation.pretty_id
        })

    except Exception as e:
        raise DonationError(donation, e)


@paypal_bp.route('/execute', methods=('POST',))
def execute_payment():
    req = request.json

    try:
        validate_execute_request(req)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        raise

    if int(request.args.get("validate_only", 0)) and app.config["APP_MODE"] == "development":
        return jsonify({"success": "Provided JSON looks good"})

    query = Transaction.query.filter_by(payment_id=req["paymentID"])
    donation = query[0].donation

    try:
        body = {
            "payer_id": req["payerID"]
        }

        payment_execute_request = payments.PaymentExecuteRequest(req["paymentID"])
        payment_execute_request.request_body(body)

        try:
            payment_execute_response = pp_client.execute(payment_execute_request, parse=False)
            r = payment_execute_response
            if r.status_code < 200 or r.status_code > 299:
                raise braintreehttp.http_error.HttpError(r.text, r.status_code, r.headers)
        except IOError as ioe:
            ioe.body = body
            raise

        jresult = r.json()

        # Store payment execution into database
        database.register_transaction(req["paymentID"], req["payerID"], jresult, jresult["state"])

        # Send confirmation email
        mail_error = False
        if app.config["APP_MAILER"] is not None:
            to_addrs = []
            if donation.reference:
                to_addrs.append(donation.reference.email)

            paypal_addr = get_paypal_email(jresult)
            if paypal_addr:
                to_addrs.append(paypal_addr)

            lang = "en"
            if "lang" in req:
                lang = req["lang"]
            elif donation.reference and donation.reference.lang:
                lang = donation.reference.lang

            if len(to_addrs) == 0:
                warnings.warn("User has no email address! Donation ID: {}".format(donation.pretty_id))
            else:
                try:
                    mail.send_confirmation_email(to_addrs, donation, lang)
                except Exception as e:
                    mail_error = True
                    app.log_exception(e)
                    app.log_exception(DonationError(donation, e))

        rjson = {
            "result": jresult["state"],
            "donation_id": donation.pretty_id
        }

        if mail_error:
            rjson["error"] = {
                "type": "_MAIL_ERROR",
                "message": "The donation has been recorded, however an error occurred while trying to send you a "
                           "confirmation email. As the email is required to pick up the gadgets, you should contact "
                           "us at info@poliedro-polimi.it and send us the donation ID ({}), so we can send it to you "
                           "manually.".format(
                    donation.pretty_id)
            }

        return jsonify(rjson)

    except Exception as e:
        raise DonationError(donation, e)


@paypal_bp.route('/cancel')
def cancel():
    return jsonify({"error": "This is a stub"})


@paypal_bp.route('/return')
def return_():
    return jsonify({"error": "This is a stub"})