import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet
load_dotenv()
FERNET_KEY=os.getenv("FERNET_KEY")
cipher=Fernet(FERNET_KEY)

async def encrypt(text:str):
    return cipher.encrypt(text.encode()).decode()

async def decrypt(text:str):
    return cipher.decrypt(text).decode()