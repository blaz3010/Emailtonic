import os
import cloudinary
import cloudinary.uploader
import asyncio
import httpx
from dotenv import load_dotenv
load_dotenv()
cloudinary.config(cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"), api_key=os.getenv("CLOUDINARY_API_KEY"), api_secret=os.getenv("CLOUDINARY_API_SECRET"), )

async def upload_resume(file,file_name:str):
    result=cloudinary.uploader.upload(
        file,resource_type="raw",
        public_id=file_name,
        folder="resumes"
    )
    return result["secure_url"]

async def get_resume(file_url:str)->bytes:
    async with httpx.AsyncClient() as client:
        response=await client.get(file_url)
        response.raise_for_status()
        return response.content