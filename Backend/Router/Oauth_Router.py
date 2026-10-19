from fastapi import APIRouter, Query
from uuid import UUID

from Backend.Controller.Oauth_controller import (
    oauth_connect,
    oauth_callback,
    list_accounts,
    disconnect_account,
)

oauth_router = APIRouter()
oauth_router.add_api_route("/oauth/{provider}/connect",oauth_connect,methods=["GET"],tags=["OAuth"],)
oauth_router.add_api_route("/oauth/{provider}/callback",oauth_callback,methods=["GET"],tags=["OAuth"],)
oauth_router.add_api_route("/oauth/accounts",list_accounts,methods=["GET"],tags=["OAuth"],)
oauth_router.add_api_route("/oauth/accounts/{account_id}",disconnect_account,methods=["DELETE"],tags=["OAuth"],)