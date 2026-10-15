import asyncio
from io import BytesIO
import fitz
import pymupdf

try:
    from docling.document_converter import DocumentConverter, DocumentStream
    converter = DocumentConverter()
except ImportError:
    converter = None


def _convert_pdf_sync(stream: BytesIO, filename: str):
    if converter is not None:
        source = DocumentStream(
            name=filename,
            stream=stream
        )
        result = converter.convert(source)
        return result.document.export_to_markdown()
        
    doc = pymupdf.open(
        stream=stream.getvalue(),
        filetype="pdf"
    )
    text = "\n".join(
        page.get_text()
        for page in doc
    )
    return text


def _convert_pdf_sync_fitz(file_bytes: bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_text = []
    for page in doc:
        text = page.get_text("text")
        pages_text.append(text)
    doc.close()
    return "\n".join(pages_text)


async def read_text_from_pdf(file):
    filename = getattr(file, "filename", "document.pdf")
    print(f"Reading PDF file: {filename}")
    pdf_bytes = await file.read()
    stream = BytesIO(pdf_bytes)
    
    markdown = await asyncio.to_thread(_convert_pdf_sync, stream, filename)
    if markdown is None:
        print(f"Converter failed for {filename}, falling back to PyMuPDF (fitz)")
        markdown = await asyncio.to_thread(_convert_pdf_sync_fitz, pdf_bytes)
        
    return markdown