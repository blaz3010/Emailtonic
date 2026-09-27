import asyncio
import base64
import mimetypes

from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
def get_gmail_service(token:str):
    credentials = Credentials.from_authorized_user_info(info=token, scopes=SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        with open(token, "w") as token:
            token.write(credentials.to_json())

    return build(
        "gmail",
        "v1",
        credentials=credentials
    )
def send_email(to:str,subject:str,body:str,resume_path:str,token:str):
    service = get_gmail_service(token)
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with open(resume_path,"rb") as f:
        resume = f.read()
    message.add_attachment(resume, maintype="application", subtype="pdf", filename=mimetypes.guess_filename(resume_path))
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    response=service.users().messages().send(userId="me", body={"raw": encoded_message}).execute()
    return response

async def send_gmail_service(to:str,subject:str,body:str,resume_path:str,token:str):
    try:
        response=await asyncio.to_thread(send_email,to,subject,body,resume_path,token)
        return response["id"]
    except Exception as e:
        print("Error In Sending the Service {}")