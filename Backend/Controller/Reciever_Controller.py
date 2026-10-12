import asyncio
import sys
import os
import re

from fastapi import Form, HTTPException, Request

async def send_the_email(user_id:str=Form(...)):
    await asyncio.sleep(1)
    return "Email sent successfully"