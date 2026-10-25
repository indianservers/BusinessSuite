"""AI-powered resume parser using Anthropic Claude."""
import json
from typing import Optional
from app.core.config import settings


RESUME_PARSE_PROMPT = """Extract the following information from this resume and return it as a JSON object:
{
  "full_name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "total_experience_years": number,
  "current_company": "string",
  "current_designation": "string",
  "skills": ["list", "of", "skills"],
  "education": [
    {
      "degree": "string",
      "institution": "string",
      "year": number
    }
  ],
  "experience": [
    {
      "company": "string",
      "designation": "string",
      "from_date": "string",
      "to_date": "string",
      "description": "string"
    }
  ],
  "summary": "2-3 sentence professional summary",
  "key_highlights": ["notable achievements or skills"]
}

Return ONLY valid JSON, no other text."""


async def parse_resume(resume_text: str) -> dict:
    """Parse resume text using Claude AI."""
    if not settings.ANTHROPIC_API_KEY:
        return _basic_parse(resume_text)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": f"{RESUME_PARSE_PROMPT}\n\nResume:\n{resume_text[:8000]}"
            }],
        )

        result_text = response.content[0].text.strip()
        # Clean potential markdown code blocks
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        return json.loads(result_text)
    except json.JSONDecodeError:
        return _basic_parse(resume_text)
    except Exception:
        return _basic_parse(resume_text)


async def score_resume_for_job(resume_data: dict, job_description: str, required_skills: list) -> dict:
    """Score a resume against a job description."""
    if not settings.ANTHROPIC_API_KEY:
        return {"score": 50.0, "reasoning": "AI scoring not configured", "matched_skills": [], "missing_skills": []}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        prompt = f"""Score this candidate for the job and return JSON:
{{
  "score": (0-100 number),
  "reasoning": "brief explanation",
  "matched_skills": ["skills that match"],
  "missing_skills": ["required skills not found"],
  "recommendation": "Strongly Recommend / Recommend / Neutral / Not Recommend"
}}

Job Description: {job_description[:2000]}
Required Skills: {', '.join(required_skills)}
Candidate Profile: {json.dumps(resume_data, indent=2)[:3000]}

Return ONLY JSON."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        return json.loads(result_text)
    except Exception:
        return {"score": 50.0, "reasoning": "Scoring failed", "matched_skills": [], "missing_skills": [], "recommendation": "Neutral"}


def _basic_parse(text: str) -> dict:
    """Very basic resume parsing as fallback."""
    import re
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    phones = re.findall(r'[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}', text)

    return {
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "summary": "Resume parsed with basic extractor. Please review manually.",
        "skills": [],
        "experience": [],
        "education": [],
        "key_highlights": [],
    }


async def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF or DOCX resume file."""
    ext = file_path.rsplit(".", 1)[-1].lower()

    try:
        if ext == "pdf":
            import pypdf
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                return " ".join(page.extract_text() or "" for page in reader.pages)
        elif ext in ["doc", "docx"]:
            from docx import Document
            doc = Document(file_path)
            return " ".join(para.text for para in doc.paragraphs)
        elif ext == "txt":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception:
        pass
    return ""
