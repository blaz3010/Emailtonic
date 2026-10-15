from fastapi import APIRouter

from Backend.Controller.User_Controller import (
    change_password,
    create_profile,
    create_user_new,
    delete_account,
    get_me,
    get_profile,
    login_user,
    logout_user,
    refresh_access_token,
    update_profile,
)


user_router = APIRouter()

# Auth
user_router.add_api_route("/user/signup", create_user_new, methods=["POST"], status_code=201, tags=["Auth"])
user_router.add_api_route("/user/login", login_user, methods=["POST"], tags=["Auth"])
user_router.add_api_route("/user/refresh", refresh_access_token, methods=["POST"], tags=["Auth"])
user_router.add_api_route("/user/logout", logout_user, methods=["POST"], tags=["Auth"])

# User
user_router.add_api_route("/user/me", get_me, methods=["GET"], tags=["User"])
user_router.add_api_route("/user/password", change_password, methods=["PUT"], tags=["User"])
user_router.add_api_route("/user/delete", delete_account, methods=["POST"], tags=["User"])

# Profile
user_router.add_api_route("/user/profile", get_profile, methods=["GET"], tags=["Profile"])
user_router.add_api_route("/user/profile", create_profile, methods=["POST"], status_code=201, tags=["Profile"])
user_router.add_api_route("/user/profile", update_profile, methods=["PUT"], tags=["Profile"])