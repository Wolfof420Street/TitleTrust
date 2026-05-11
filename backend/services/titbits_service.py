from __future__ import annotations

import json
import logging
from typing import Dict, List

try:
    from backend.config import settings
except ModuleNotFoundError:
    from config import settings

logger = logging.getLogger("TitleTrust-TitbitsService")

DEFAULT_TITBITS: List[str] = [
    "A Green Card is stronger registry evidence than the printed title deed alone.",
    "A valid transfer can still fail if the root title was void from the start.",
    "Mutation forms are a common weak point in fraudulent subdivision chains.",
    "Public land and trust land histories often hide the highest litigation risk.",
    "A clean document scan does not prove clean registry provenance.",
]


class TitbitsService:
    def generate(self) -> Dict[str, List[str]]:
        if not settings.GEMINI_API_KEY:
            return {"titbits": DEFAULT_TITBITS}

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            response = client.models.generate_content(
                model=settings.FORENSIC_MODEL_NAME,
                contents=(
                    "Generate 5 short facts about Kenyan land law, title verification, "
                    "or fraud prevention. Keep each under 20 words."
                ),
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    response_mime_type="application/json",
                    response_schema={"type": "ARRAY", "items": {"type": "STRING"}},
                ),
            )
            if response.text:
                return {"titbits": json.loads(response.text)}
        except Exception:
            logger.exception("Titbits generation failed")

        return {"titbits": DEFAULT_TITBITS}


titbits_service = TitbitsService()
