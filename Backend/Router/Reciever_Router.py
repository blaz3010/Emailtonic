from fastapi import APIRouter, Depends

from Backend.Controller.Reciever_Controller import send_email_draft,create_email_draft, email_history


email_router = APIRouter()
email_router.add_api_route("/send_email/draft", create_email_draft, methods=["POST"], tags=["Email"])
email_router.add_api_route("/send_email/history", email_history, methods=["GET"], tags=["Email"])
email_router.add_api_route("/send_email/{draft_id}/send", send_email_draft, methods=["POST"], tags=["Email"])

