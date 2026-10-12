from fastapi import APIRouter, Depends

from Backend.Controller.Reciever_Controller import send_the_email


email_router = APIRouter()
email_router.add_api_route("/send_email", send_the_email, methods=["POST"], tags=["Email"])

