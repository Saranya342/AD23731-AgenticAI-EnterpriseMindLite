import os
import imaplib
import email
import time
from email.header import decode_header

import requests
from dotenv import load_dotenv


load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

BACKEND_URL = "http://127.0.0.1:8000/api/incidents"
CUSTOMER_SERVICE_URL = "http://127.0.0.1:8000/api/customer-service"


def decode_text(value):
    if not value:
        return ""

    decoded_parts = decode_header(value)
    result = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(
                encoding or "utf-8",
                errors="ignore"
            )
        else:
            result += part

    return result


def extract_body(message):
    body = ""

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(
                part.get("Content-Disposition")
            )

            if (
                content_type == "text/plain"
                and "attachment" not in disposition
            ):
                payload = part.get_payload(decode=True)

                if payload:
                    charset = (
                        part.get_content_charset()
                        or "utf-8"
                    )

                    body = payload.decode(
                        charset,
                        errors="ignore"
                    )

                    break

    else:
        payload = message.get_payload(decode=True)

        if payload:
            charset = (
                message.get_content_charset()
                or "utf-8"
            )

            body = payload.decode(
                charset,
                errors="ignore"
            )

    return body.strip()


def detect_customer_and_service(subject, body):
    text = f"{subject} {body}".lower()

    customers = {
        "abc retail": {
            "customer_name": "ABC Retail",
            "customer_id": "C1",
        },
        "technova inc": {
            "customer_name": "TechNova Inc",
            "customer_id": "C2",
        },
        "global mart": {
            "customer_name": "Global Mart",
            "customer_id": "C3",
        },
        "quickship logistics": {
            "customer_name": "QuickShip Logistics",
            "customer_id": "C4",
        },
        "brightpay solutions": {
            "customer_name": "BrightPay Solutions",
            "customer_id": "C5",
        },
        "sunrise foods": {
            "customer_name": "Sunrise Foods",
            "customer_id": "C6",
        },
        "vertex systems": {
            "customer_name": "Vertex Systems",
            "customer_id": "C7",
        },
        "nimbus cloud co": {
            "customer_name": "Nimbus Cloud Co",
            "customer_id": "C8",
        },
        "coastal traders": {
            "customer_name": "Coastal Traders",
            "customer_id": "C9",
        },
    }

    services = {
        "payment gateway": "S1",
        "authentication service": "S2",
        "order management": "S3",
        "inventory service": "S4",
        "customer portal": "S5",
        "notification service": "S6",
        "ci/cd pipeline": "S7",
        "api gateway": "S8",
    }

    customer_name = None
    customer_id = None
    service_id = None

    for customer_key, customer_data in customers.items():
        if customer_key in text:
            customer_name = customer_data["customer_name"]
            customer_id = customer_data["customer_id"]
            break

    for service_name, sid in services.items():
        if service_name in text:
            service_id = sid
            break

    return customer_name, customer_id, service_id


def submit_incident_to_backend(
    subject,
    body,
    sender
):
    customer_name, customer_id, service_id = (
        detect_customer_and_service(
            subject,
            body
        )
    )

    print("\n[DETECTION RESULT]")
    print("Customer:", customer_name)
    print("Customer ID:", customer_id)
    print("Service ID:", service_id)

    if not customer_id:
        print(
            "[CUSTOMER SERVICE] Unknown customer detected."
        )

        try:
            response = requests.post(
                CUSTOMER_SERVICE_URL,
                json={
                    "sender_email": sender,
                    "subject": subject,
                    "body": body,
                    "detected_customer_name": None,
                },
                timeout=30
            )

            if response.status_code >= 400:
                print(
                    "[CUSTOMER SERVICE ERROR]",
                    response.status_code,
                    response.text
                )
                return None

            print(
                "[CUSTOMER SERVICE] Email assigned "
                "to Customer Service."
            )

            return response.json()

        except requests.exceptions.RequestException as exc:
            print(
                "[CUSTOMER SERVICE ERROR]",
                str(exc)
            )
            return None

    if not service_id:
        print(
            "[CUSTOMER SERVICE] Known customer, "
            "but service could not be detected."
        )

        try:
            response = requests.post(
                CUSTOMER_SERVICE_URL,
                json={
                    "sender_email": sender,
                    "subject": subject,
                    "body": body,
                    "detected_customer_name": customer_name,
                },
                timeout=30
            )

            if response.status_code >= 400:
                print(
                    "[CUSTOMER SERVICE ERROR]",
                    response.status_code,
                    response.text
                )
                return None

            print(
                "[CUSTOMER SERVICE] Email assigned "
                "for service identification."
            )

            return response.json()

        except requests.exceptions.RequestException as exc:
            print(
                "[CUSTOMER SERVICE ERROR]",
                str(exc)
            )
            return None

    payload = {
        "subject": subject,
        "body": body,
        "customer_name": customer_name,
        "customer_id": customer_id,
        "service_id": service_id,
    }

    print("\n[BACKEND] Preparing incident submission")
    print(f"[BACKEND] Sender: {sender}")
    print(f"[BACKEND] Customer: {customer_name}")
    print(f"[BACKEND] Customer ID: {customer_id}")
    print(f"[BACKEND] Service ID: {service_id}")

    try:
        response = requests.post(
            BACKEND_URL,
            json=payload,
            timeout=180
        )

    except requests.exceptions.ConnectionError:
        print(
            "[BACKEND ERROR] Could not connect to FastAPI."
        )
        return None

    except requests.exceptions.Timeout:
        print(
            "[BACKEND ERROR] Request timed out."
        )
        return None

    except requests.exceptions.RequestException as exc:
        print(
            f"[BACKEND ERROR] {exc}"
        )
        return None

    if response.status_code >= 400:
        print(
            "[BACKEND ERROR] Incident submission failed."
        )
        print(response.status_code)
        print(response.text)
        return None

    try:
        data = response.json()

    except ValueError:
        print(
            "[BACKEND ERROR] Invalid JSON response."
        )
        print(response.text)
        return None

    print(
        "[BACKEND] Incident submitted successfully"
    )

    print(data)

    return data


def process_email(
    mail,
    email_id
):
    """
    Read one email and send it to EnterpriseMind.
    """

    status, msg_data = mail.fetch(
        email_id,
        "(RFC822)"
    )

    if status != "OK":
        print(
            f"[GMAIL] Could not fetch email "
            f"{email_id}"
        )

        return False

    raw_email = msg_data[0][1]

    message = email.message_from_bytes(
        raw_email
    )

    subject = decode_text(
        message.get("Subject")
    )

    sender = decode_text(
        message.get("From")
    )

    body = extract_body(message)

    print("\n" + "=" * 70)

    print("FROM:")
    print(sender)

    print("\nSUBJECT:")
    print(subject)

    print("\nBODY:")
    print(body)

    print("=" * 70)

    if not subject:
        print(
            "[GMAIL] Skipping email because "
            "subject is empty."
        )

        return False

    if not body:
        print(
            "[GMAIL] Skipping email because "
            "body is empty."
        )

        return False

    result = submit_incident_to_backend(
        subject=subject,
        body=body,
        sender=sender
    )

    if not result:
        print(
            "[GMAIL] Backend processing failed."
        )

        print(
            "[GMAIL] Email will remain unread "
            "so it can be retried."
        )

        return False

    print(
        "[GMAIL] EnterpriseMind accepted "
        "the incident."
    )

    #
    # Mark the email as read ONLY after
    # successful backend submission.
    #
    mail.store(
        email_id,
        "+FLAGS",
        "\\Seen"
    )

    print(
        "[GMAIL] Email marked as processed."
    )

    return True


def read_unread_emails():
    if not GMAIL_ADDRESS:
        raise ValueError(
            "Missing GMAIL_ADDRESS in .env"
        )

    if not GMAIL_APP_PASSWORD:
        raise ValueError(
            "Missing GMAIL_APP_PASSWORD in .env"
        )

    print(
        "[GMAIL] Connecting..."
    )

    mail = imaplib.IMAP4_SSL(
        "imap.gmail.com"
    )

    try:
        mail.login(
            GMAIL_ADDRESS,
            GMAIL_APP_PASSWORD.replace(
                " ",
                ""
            )
        )

        print(
            "[GMAIL] Login successful"
        )

        status, _ = mail.select(
            "inbox"
        )

        if status != "OK":
            print(
                "[GMAIL] Could not open inbox."
            )

            return

        #
        # Process only unread emails that
        # contain INCIDENT in the subject.
        #
        status, messages = mail.search(
            None,
            '(UNSEEN)'
        )

        if status != "OK":
            print(
                "[GMAIL] Failed to search inbox."
            )

            return

        email_ids = messages[0].split()

        print(
            f"[GMAIL] Unread incident emails "
            f"found: {len(email_ids)}"
        )

        if not email_ids:
            print(
                "[GMAIL] Nothing to process."
            )

            return

        success_count = 0
        failure_count = 0

        for email_id in email_ids:
            print(
                "\n[GMAIL] Processing email "
                f"{email_id.decode()}"
            )

            try:
                success = process_email(
                    mail,
                    email_id
                )

                if success:
                    success_count += 1
                else:
                    failure_count += 1

            except Exception as exc:
                failure_count += 1

                print(
                    "[GMAIL ERROR] Failed to "
                    "process email:"
                )

                print(exc)

        print(
            "\n" + "=" * 70
        )

        print(
            "[GMAIL] Processing complete"
        )

        print(
            f"[GMAIL] Successful: "
            f"{success_count}"
        )

        print(
            f"[GMAIL] Failed: "
            f"{failure_count}"
        )

        print(
            "=" * 70
        )

    finally:
        try:
            mail.logout()

        except Exception:
            pass


if __name__ == "__main__":
    print("[SYSTEM] Gmail incident monitor started.")

    while True:
        try:
            read_unread_emails()

        except KeyboardInterrupt:
            print()
            print("[SYSTEM] Gmail incident monitor stopped.")
            break

        except Exception as exc:
            print("[SYSTEM ERROR]", str(exc))

        print("[SYSTEM] Checking again in 60 seconds...")
        print()
        time.sleep(60)
