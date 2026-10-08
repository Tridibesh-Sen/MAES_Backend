import json
import logging
# pyrefly: ignore [missing-import]
from openai import AsyncOpenAI
from app.config import settings
from app.services.json_utils import repair_and_parse_json

logger = logging.getLogger(__name__)

KNOWLEDGE_EXTRACTION_SYSTEM = """
You are an expert data structured extraction AI. Your goal is to compress raw document text into a highly structured JSON knowledge base.
Extract the core facts, concepts, definitions, and potential question/answer pairs from the provided text.

Return ONLY a valid JSON object with the following schema:
{
  "summary": "A 2-3 sentence high-level summary of the entire document.",
  "topics": [
    {
      "topic_name": "...",
      "key_points": ["point 1", "point 2"],
      "definitions": { "Term": "Definition" },
      "potential_qa": [
        { "q": "...", "a": "..." }
      ]
    }
  ]
}
Do NOT include any markdown formatting, backticks, or other text outside of the JSON object.
"""

async def extract_knowledge(raw_text: str) -> dict:
    """
    Takes raw document text, sends it to the LLM, and returns a structured JSON knowledge base.
    """
    if not raw_text or len(raw_text.strip()) < 50:
        return {"summary": "Document too short or empty.", "topics": []}

    client = AsyncOpenAI(api_key=settings.mistral_api_key, base_url="https://api.mistral.ai/v1")
    
    # Mistral context window is up to 131k (for mistral-large) but let's be safe.
    capped_text = raw_text[:30000]
    
    messages = [
        {"role": "system", "content": KNOWLEDGE_EXTRACTION_SYSTEM},
        {"role": "user", "content": f"Extract knowledge from this text:\n\n{capped_text}"}
    ]

    try:
        model_to_use = settings.agent_a_model or "codestral-latest"
        response = await client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=2000
        )
        
        extracted_content = response.choices[0].message.content
        structured_data = repair_and_parse_json(extracted_content)
        return structured_data
    except Exception as e:
        logger.error(f"Knowledge extraction failed: {e}")
        # Fallback if extraction fails
        return {
            "summary": "Knowledge extraction failed. Storing raw text instead.",
            "topics": [
                {
                    "topic_name": "Raw Text Segment",
                    "key_points": [capped_text[:1000] + "..."],
                    "definitions": {},
                    "potential_qa": []
                }
            ]
        }
