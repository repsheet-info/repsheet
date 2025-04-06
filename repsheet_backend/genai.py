

from repsheet_backend.common import GCP_BILLING_PROJECT
from google import genai

GEMINI_FLASH_2 = "gemini-2.0-flash"

google_ai = genai.Client(
    vertexai=True, project=GCP_BILLING_PROJECT, location='us-central1'
)

def generate_text(prompt: str, model: str = GEMINI_FLASH_2) -> str:
    """Generate text using Google Gemini."""
    response = google_ai.models.generate_content(
        model=model,
        contents=prompt
    )
    return response.text
