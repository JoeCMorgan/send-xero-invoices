#!/bin/sh
import os
from dotenv import load_dotenv, set_key, find_dotenv
from functools import wraps
import logging
import json

from xero_python.accounting import AccountingApi, Invoices, Invoice, CreditNote, CreditNotes
from xero_python.api_client import ApiClient
from xero_python.api_client.configuration import Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.exceptions import AccountingBadRequestException

import smtplib
import ssl

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

dotenv_file = find_dotenv()
load_dotenv(dotenv_file)

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
TENANT_ID = os.environ["TENANT_ID"]

SMTP_SERVER = os.environ["SMTP_SERVER"]
SMTP_PORT = os.environ["SMTP_PORT"]
SMTP_SENDER_EMAIL = os.environ["SMTP_SENDER_EMAIL"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]


logging.basicConfig(level=logging.INFO, filename="invoice_mailer.log", filemode="a",
                    format="%(asctime)s %(levelname)s %(message)s")

# configure api_client for use with xero-python sdk client
api_client = ApiClient(
    Configuration(
        debug='false',
        oauth2_token=OAuth2Token(
            client_id=CLIENT_ID, client_secret=CLIENT_SECRET
        ),
    ),
    pool_threads=1,
)


@api_client.oauth2_token_saver
def store_xero_oauth2_token(token):
    os.environ["XERO_TOKEN"] = json.dumps(token)
    set_key(dotenv_file, "XERO_TOKEN", os.environ["XERO_TOKEN"])


@api_client.oauth2_token_getter
def obtain_xero_oauth2_token():
    return json.loads(os.environ["XERO_TOKEN"])


def xero_token_required(function):
    @wraps(function)
    def decorator(*args, **kwargs):
        xero_token = obtain_xero_oauth2_token()
        if not xero_token:
            return ""

        return function(*args, **kwargs)

    return decorator


@xero_token_required
def refresh_token():
    token = api_client.refresh_oauth2_token()
    store_xero_oauth2_token(token)


@xero_token_required
def get_contact(api_instance, contact_id):
    try:
        api_reponse = api_instance.get_contact(TENANT_ID, contact_id)

    except AccountingBadRequestException as e:
        print("Exception when calling AccountingApi->getContact: %s\n" % e)
        logging.error(f"Exception when calling AccountingApi->getContact:\n {e}")

    return api_reponse.contacts[0]


@xero_token_required
def get_credit_notes(api_instance):
    try:
        api_response = api_instance.get_credit_notes(
            TENANT_ID,
            where='SentToContact=Null or SentToContact=False'
        )

        logging.info(f"{len(api_response.credit_notes)} credit notes retrieved")

    except AccountingBadRequestException as e:
        print("Exception when calling AccountingApi->getCreditNotes: %s\n" % e)
        logging.error(f"Exception when calling AccountingApi->getCreditNotes:\n {e}")

    return api_response.credit_notes


@xero_token_required
def get_credit_note_pdf(api_instance, credit_note_id):
    try:
        api_reponse = api_instance.get_credit_note_as_pdf(TENANT_ID, credit_note_id)
        with open(api_reponse, 'rb') as f:
            pdf = f.read()
        os.remove(api_reponse)

    except AccountingBadRequestException as e:
        print("Exception when calling AccountingApi->getCreditNoteAsPdf: %s\n" % e)
        logging.error(f"Exception when calling AccountingApi->getCreditNoteAsPdf:\n {e}")

    return pdf


@xero_token_required
def mark_credit_note_sent(api_instance, credit_note):
    try:
        updated_credit_note = CreditNote(sent_to_contact=True)
        credit_notes = CreditNotes(credit_notes=[updated_credit_note])

        api_instance.update_credit_note(TENANT_ID, credit_note.credit_note_id, credit_notes)

    except AccountingBadRequestException as e:
        print("Exception when calling AccountingApi->updateCreditNotes: %s\n" % e)
        logging.error(f"Exception when calling AccountingApi->updateCreditNotes:\n {e}")


@xero_token_required
def get_invoices(api_instance):
    try:
        api_response = api_instance.get_invoices(
            TENANT_ID,
            where='SentToContact=Null or SentToContact=False'
        )

        logging.info(f"{len(api_response.invoices)} invoices retrieved")

    except AccountingBadRequestException as e:
        print("Exception when calling AccountingApi->getInvoices: %s\n" % e)
        logging.error(f"Exception when calling AccountingApi->getInvoices:\n {e}")

    return api_response.invoices


@xero_token_required
def get_invoice_pdf(api_instance, invoice_id):
    try:
        api_reponse = api_instance.get_invoice_as_pdf(TENANT_ID, invoice_id)
        with open(api_reponse, 'rb') as f:
            pdf = f.read()
        os.remove(api_reponse)

    except AccountingBadRequestException as e:
        print("Exception when calling AccountingApi->getInvoiceAsPdf: %s\n" % e)
        logging.error(f"Exception when calling AccountingApi->getInvoiceAsPdf:\n {e}")

    return pdf


@xero_token_required
def get_invoice_url(api_instance, invoice_id):
    try:
        api_reponse = api_instance.get_online_invoice(TENANT_ID, invoice_id)

    except AccountingBadRequestException as e:
        print("Exception when calling AccountingApi->getOnlineInvoice: %s\n" % e)
        logging.error(f"Exception when calling AccountingApi->getOnlineInvoice:\n {e}")

    return api_reponse.online_invoices[0].online_invoice_url


@xero_token_required
def mark_invoice_sent(api_instance, invoice):
    try:
        updated_invoice = Invoice(sent_to_contact=True)
        invoices = Invoices(invoices=[updated_invoice])

        api_instance.update_invoice(TENANT_ID, invoice.invoice_id, invoices)

    except AccountingBadRequestException as e:
        print("Exception when calling AccountingApi->updateInvoice: %s\n" % e)
        logging.error(f"Exception when calling AccountingApi->updateInvoice:\n {e}")


def email_pdf(type, contact, inv_pdf, inv_number, inv_reference, inv_url):
    receiver_email = contact.email_address
    subject = f"Your {type} for City Auto Paints order {inv_reference}"
    text = f"Dear {contact.name}, \n\n Thank you for shopping with City Auto Paints Ltd. A copy of your {type} for order {inv_reference} is attached. If your {type} is not attached to this email, please contact us."
    html = f"""\
        <html>
          <body>
            <p>Dear {contact.name},<br><br>
              Thank you for shopping with City Auto Paints Ltd. A copy of your {type} for order
              {inv_reference} is attached. <br> <br>
              If your {type} is not attached to this email, please contact us.
              {f'Alternatively, <a href="{inv_url}">view your {type} online</a>.' if inv_url else ''}
            </p>
          </body>
        </html>
        """

    # Create a multipart message and set headers
    message_alternative = MIMEMultipart("alternative")

    text_part = MIMEText(text, "plain")
    html_part = MIMEText(html, "html")

    # Add body to email
    message_alternative.attach(text_part)
    message_alternative.attach(html_part)

    message = MIMEMultipart('mixed')

    message["From"] = SMTP_SENDER_EMAIL
    message["To"] = receiver_email
    message["Subject"] = subject

    pdf_part = MIMEBase("application", "octet-stream")
    pdf_part.set_payload(inv_pdf)

    # Encode file in ASCII characters to send by email
    encoders.encode_base64(pdf_part)

    # Add header as key/value pair to attachment part
    pdf_part.add_header(
        "Content-Disposition",
        f"attachment; filename= {inv_number}.pdf",
    )

    # Add attachment to message and convert message to string
    message.attach(message_alternative)
    message.attach(pdf_part)

    # Try to log in to server and send email
    try:
        context = ssl.create_default_context()
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls(context=context)
        server.login(SMTP_SENDER_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_SENDER_EMAIL, receiver_email, message.as_string())

        logging.info(f"Invoice {inv_number} sent to {contact.name}")
    except Exception as e:
        logging.error(f"Exception when sending email:\n {e}")
    finally:
        server.quit()


def main():
    refresh_token()
    api_instance = AccountingApi(api_client)
    invoices = get_invoices(api_instance)
    credit_notes = get_credit_notes(api_instance)

    for invoice in invoices:
        invoice_contact = get_contact(api_instance, invoice.contact.contact_id)
        invoice_pdf = get_invoice_pdf(api_instance, invoice.invoice_id)
        invoice_url = get_invoice_url(api_instance, invoice.invoice_id)

        try:
            email_pdf('invoice', invoice_contact, invoice_pdf, invoice.invoice_number,
                      invoice.reference, invoice_url)
        except Exception as e:
            logging.error(f"Exception when sending invoice email:\n {e}")
        else:
            mark_invoice_sent(api_instance, invoice)

    for credit_note in credit_notes:
        credit_note_contact = get_contact(api_instance, credit_note.contact.contact_id)
        credit_note_pdf = get_credit_note_pdf(api_instance, credit_note.credit_note_id)

        try:
            email_pdf('credit note', credit_note_contact, credit_note_pdf,
                      credit_note.credit_note_number, credit_note.reference, "")
        except Exception as e:
            logging.error(f"Exception when sending credit note email:\n {e}")
        # API current does not handle modifying paid credit notes
        # else:
        #     mark_credit_note_sent(api_instance, credit_note)


if __name__ == "__main__":
    main()
