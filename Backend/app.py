import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from Backend.DBhelper.db import close_db
from Backend.Router.Oauth_Router import oauth_router
from Backend.Router.Reciever_Router import email_router
from Backend.Router.User_Router import user_router
from Backend.Utils.Groq import redis_client

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # shutdown: release DB pool and Redis connection
    await close_db()
    try:
        await redis_client.aclose()
    except Exception:
        logger.warning("Redis client did not close cleanly")


app = FastAPI(title="Emailtonic API", version="1.0.0", lifespan=lifespan)

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
origins = list({
    frontend_url,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost",
})

# allow_credentials is required so the browser sends/receives the
# refresh_token cookie; with it, allow_origins must be explicit (no "*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The routers already define full paths (/user/..., /oauth/..., /send_email),
# so no extra prefix here, otherwise you'd get /user/user/login.
app.include_router(user_router)
app.include_router(oauth_router)
app.include_router(email_router)


@app.get("/", tags=["Health"])
def health_check():
    return {"message": "Emailtonic API running"}