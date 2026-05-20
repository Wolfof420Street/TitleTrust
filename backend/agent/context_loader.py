import os
import glob
import datetime
from typing import Optional

# Unified Google GenAI SDK
from google import genai
from google.genai import types

from config import settings

def cache_legal_context(
    ttl_minutes: int = 60,
    cache_name: str = "kenya-land-laws-v1"
) -> Optional[str]:
    """
    Scans 'knowledgebase/' for PDFs, uploads them to Vertex AI, 
    and returns a CachedContent Resource Name via Google GenAI SDK.
    """
    # Initialize Unified Client
    # Using API Key for standard Gemini Developer access (supports file upload methods)
    client = genai.Client(
        api_key=settings.GEMINI_API_KEY
    )

    # 1. Gather Files
    pdf_files = glob.glob(os.path.join(settings.KNOWLEDGEBASE_DIR, "*.pdf"))
    
    if not pdf_files:
        print(f"⚠️ No PDFs found in {settings.KNOWLEDGEBASE_DIR}. Skipping Cache.")
        return None

    print(f"📚 Found {len(pdf_files)} legal documents. Uploading to Gemini Storage...")

    uploaded_files = []

    # 2. Upload Files
    for path in pdf_files:
        try:
            file_size = os.path.getsize(path)
            print(f"   - Uploading: {os.path.basename(path)} ({file_size/1024:.2f} KB)...")
            
            # Using File API for robust long-context handling
            with open(path, "rb") as f:
                uploaded_file = client.files.upload(
                    file=f,
                    config=dict(mime_type='application/pdf', display_name=os.path.basename(path))
                )
            
            # TODO: If video, wait for processing. defaults for PDF usually immediate or acceptable for cache creation.
            uploaded_files.append(uploaded_file)
            print(f"     ✅ Uploaded as {uploaded_file.name}")

        except Exception as e:
            print(f"   ❌ Error uploading {path}: {e}")

    if not uploaded_files:
        print("❌ No files uploaded successfully.")
        return None

    # 3. Create Cache
    system_instruction = """
    You are an expert on Kenyan Land Law. 
    Use the provided cached PDF documents (Constitution, Land Act, Registration Act) 
    as your primary source of truth for legal definitions and procedures.
    Use Chain of Verification (CoVe): extract the legal claim, verify it against the cached sources, and only then summarize.
    """

    try:
        print("💾 Creating Context Cache...")
        # Create cache using the new SDK
        cached_content = client.caches.create(
            model=settings.FORENSIC_MODEL_NAME,
            config=types.CreateCachedContentConfig(
                system_instruction=system_instruction,
                contents=[file for file in uploaded_files], 
                ttl=f"{ttl_minutes * 60}s",
                display_name=cache_name,
            )
        )
        print(f"✅ Cache Created Successfully: {cached_content.name}")
        return cached_content.name

    except Exception as e:
        print(f"❌ Failed to create Context Cache: {e}")
        return None
