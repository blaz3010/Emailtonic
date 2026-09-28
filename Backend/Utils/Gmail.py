import asyncio
import base64
from pathlib import Path
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_gmail_service(
    refresh_token: str,
    client_id: str,
    client_secret: str,
):
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    if not credentials.valid:
        credentials.refresh(Request())

    return build(
        "gmail",
        "v1",
        credentials=credentials,
    )


def send_email(
    to: str,
    subject: str,
    body: str,
    resume_path: str,
    refresh_token: str,
    client_id: str,
    client_secret: str,
):
    service = get_gmail_service(
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
    )

    message = EmailMessage()

    message["To"] = to
    message["Subject"] = subject

    message.set_content(body)

    resume_file = Path(resume_path)

    with open(resume_file, "rb") as f:
        resume = f.read()

    message.add_attachment(
        resume,
        maintype="application",
        subtype="pdf",
        filename=resume_file.name,
    )

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    response = (
        service.users()
        .messages()
        .send(
            userId="me",
            body={"raw": encoded_message},
        )
        .execute()
    )

    return response


async def send_gmail_service(
    to: str,
    subject: str,
    body: str,
    resume_path: str,
    refresh_token: str,
    client_id: str,
    client_secret: str,
):
    try:
        response = await asyncio.to_thread(
            send_email,
            to,
            subject,
            body,
            resume_path,
            refresh_token,
            client_id,
            client_secret,
        )

        return response["id"]

    except Exception as e:
        print(f"Error in sending Gmail service: {e}")
        raise