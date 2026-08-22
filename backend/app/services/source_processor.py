import io
import re
import zipfile
import json
import xml.etree.ElementTree as ET
import pymupdf as fitz
from fastapi import UploadFile
import httpx
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import logging

logger = logging.getLogger(__name__)

async def extract_text_from_pdf(file: UploadFile) -> str:
    """Extracts text from a PDF file using pymupdf."""
    content = await file.read()
    doc = fitz.open(stream=content, filetype="pdf")
    text = ""
    for i, page in enumerate(doc):
        text += f"\n--- PAGE {i+1} ---\n"
        text += page.get_text() + "\n"
    text = text.strip()
    
    if not text:
        text = "SYSTEM NOTE: The uploaded PDF could not be read because it appears to be a scanned image or has no readable text layer."
    return text

def extract_text_from_docx_bytes(content: bytes) -> str:
    """Extracts text from DOCX (Office Open XML) without external binary dependencies."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
            xml_content = docx_zip.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            # Find all text elements in the XML namespace
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            paragraphs = []
            for p in tree.iterfind('.//w:p', namespaces):
                texts = [node.text for node in p.iterfind('.//w:t', namespaces) if node.text]
                if texts:
                    paragraphs.append(''.join(texts))
            return '\n\n'.join(paragraphs)
    except Exception as e:
        logger.warning(f"Failed to parse DOCX structure: {e}")
        return content.decode('utf-8', errors='ignore')

def extract_text_from_pptx_bytes(content: bytes) -> str:
    """Extracts slide text from PPTX (PowerPoint Open XML) slides."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as pptx_zip:
            slide_texts = []
            slide_num = 1
            # PowerPoint stores slides as ppt/slides/slide1.xml, slide2.xml, etc.
            for name in sorted(pptx_zip.namelist()):
                if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                    xml_content = pptx_zip.read(name)
                    tree = ET.fromstring(xml_content)
                    namespaces = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                    texts = [node.text for node in tree.iterfind('.//a:t', namespaces) if node.text]
                    if texts:
                        slide_texts.append(f"--- SLIDE {slide_num} ---\n" + "\n".join(texts))
                        slide_num += 1
            return '\n\n'.join(slide_texts) if slide_texts else content.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"Failed to parse PPTX structure: {e}")
        return content.decode('utf-8', errors='ignore')

async def extract_text_from_file(file: UploadFile) -> str:
    """
    Universal file text extractor.
    Supports: PDF, DOCX, PPTX, TXT, MD, JSON, CSV, HTML, and all source code files.
    """
    filename = file.filename.lower()
    content = await file.read()
    
    if filename.endswith('.pdf'):
        # Rewind file for PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        text = ""
        for i, page in enumerate(doc):
            text += f"\n--- PAGE {i+1} ---\n"
            text += page.get_text() + "\n"
        return text.strip() or "SYSTEM NOTE: The uploaded PDF contains no readable text."

    elif filename.endswith('.docx') or filename.endswith('.doc'):
        return extract_text_from_docx_bytes(content)

    elif filename.endswith('.pptx') or filename.endswith('.ppt'):
        return extract_text_from_pptx_bytes(content)

    elif filename.endswith('.json'):
        try:
            parsed = json.loads(content.decode('utf-8', errors='replace'))
            return json.dumps(parsed, indent=2)
        except Exception:
            return content.decode('utf-8', errors='replace')

    else:
        # Plain text, Markdown (.md), CSV, Code (.py, .ts, .js, .java, .cpp, .c), HTML, etc.
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'utf-16']:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode('utf-8', errors='ignore')

async def extract_text_from_url(url: str) -> str:
    """Fetches a webpage and extracts clean readable text."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            script.extract()
            
        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return '\n'.join(chunk for chunk in chunks if chunk)
    except Exception as e:
        raise ValueError(f"Failed to extract text from URL: {e}")

def extract_text_from_youtube(url: str) -> str:
    """Extracts transcript from a YouTube video URL."""
    try:
        video_id = None
        if "v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
            
        if not video_id:
            raise ValueError("Invalid YouTube URL")
            
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        raise ValueError(f"Failed to fetch YouTube transcript: {e}")
