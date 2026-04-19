#!/usr/bin/env python3
"""
ATS Scorer - FastAPI Backend
Refactored from the original CLI tool to serve as a REST API.
"""

import re
import io
from pathlib import Path
from collections import Counter
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pdfplumber

# ── Constants ────────────────────────────────────────────────────────────────

COMMON_SECTIONS = [
    "experience", "work experience", "employment", "professional experience",
    "education", "qualifications", "skills", "technical skills", "core competencies",
    "summary", "objective", "profile", "about",
    "projects", "certifications", "awards", "publications", "languages",
    "volunteer", "interests", "references",
]

ACTION_VERBS = [
    "achieved", "built", "created", "delivered", "designed", "developed",
    "drove", "engineered", "established", "exceeded", "executed", "generated",
    "implemented", "improved", "increased", "launched", "led", "managed",
    "optimised", "optimized", "oversaw", "produced", "reduced", "spearheaded",
    "streamlined", "transformed",
]

DATE_PATTERN = re.compile(
    r"\b(\d{4})\b|"
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b|"
    r"\bPresent\b|\bCurrent\b",
    re.IGNORECASE,
)

CONTACT_PATTERNS = {
    "email":   re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}"),
    "phone":   re.compile(r"(\+?\d[\d\s\-().]{7,}\d)"),
    "linkedin": re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE),
    "github":  re.compile(r"github\.com/[\w-]+", re.IGNORECASE),
}

METRIC_PATTERN = re.compile(
    r"\d+\s*(%|percent|x\b|times|\$|£|€|million|billion|k\b|users|customers|hours|days|weeks|months)"
)

WEIGHTS = {
    "contact":    0.15,
    "sections":   0.20,
    "formatting": 0.25,
    "keywords":   0.25,
    "length":     0.10,
    "dates":      0.05,
}

# ── Pydantic Models ───────────────────────────────────────────────────────────

class ScoreDetail(BaseModel):
    score: float
    issues: list[str]
    found: Optional[dict] = None
    pages: Optional[int] = None
    word_count: Optional[int] = None
    action_verbs: Optional[list[str]] = None
    metrics_count: Optional[int] = None
    jd_match_score: Optional[float] = None
    jd_matched: Optional[list[str]] = None
    jd_missing: Optional[list[str]] = None
    dates_found: Optional[int] = None


class ATSReport(BaseModel):
    overall_score: float
    grade: str
    contact: ScoreDetail
    sections: ScoreDetail
    formatting: ScoreDetail
    keywords: ScoreDetail
    length: ScoreDetail
    dates: ScoreDetail
    all_issues: list[str]


# ── Text Extraction ───────────────────────────────────────────────────────────

def extract_text(pdf_data: bytes) -> tuple[str, dict]:
    """Extract text from PDF bytes, return (full_text, metadata)."""
    meta = {"pages": 0, "has_columns": False, "warnings": []}
    pages_text = []

    with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
        meta["pages"] = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            text = page.extract_text(layout=True) or ""
            pages_text.append(text)

            # Detect multi-column layout
            words = page.extract_words()
            if words:
                x_positions = [w["x0"] for w in words]
                mid = (page.width or 600) / 2
                left  = sum(1 for x in x_positions if x < mid * 0.4)
                right = sum(1 for x in x_positions if x > mid * 1.6)
                if left > 10 and right > 10:
                    meta["has_columns"] = True

            # Detect very sparse pages (may be image-based)
            if len(text.strip()) < 50 and page.images:
                meta["warnings"].append(f"Page {i+1} may contain image-based text (not ATS readable)")

    return "\n".join(pages_text), meta


# ── Individual Checks ─────────────────────────────────────────────────────────

def check_contact_info(text: str) -> dict:
    found = {k: bool(p.search(text)) for k, p in CONTACT_PATTERNS.items()}
    score = sum(found.values()) / len(found) * 100
    issues = [f"Missing {k}" for k, v in found.items() if not v and k in ("email", "phone")]
    return {"score": score, "found": found, "issues": issues}

def check_sections(text: str) -> dict:
    text_lower = text.lower()
    found_sections = {s: (s in text_lower) for s in COMMON_SECTIONS}
    found_list = [s for s, present in found_sections.items() if present]
    missing_critical = [s for s in ("experience", "education", "skills") if not found_sections.get(s, False)]
    score = min(100, len(found_list) / 6 * 100)
    issues = [f"Missing critical section: '{s}'" for s in missing_critical]
    return {"score": score, "found": found_sections, "issues": issues}

def check_sections1(text: str) -> dict:
    text_lower = text.lower()
    found = [s for s in COMMON_SECTIONS if s in text_lower]
    missing_critical = [s for s in ("experience", "education", "skills") if s not in found]
    score = min(100, len(found) / 6 * 100)
    issues = [f"Missing critical section: '{s}'" for s in missing_critical]
    return {"score": score, "found": found, "issues": issues}


def check_length(text: str, pages: int) -> dict:
    word_count = len(text.split())
    issues = []
    if pages > 2:
        issues.append(f"Resume is {pages} pages — most ATS and recruiters prefer 1–2 pages")
    if word_count < 200:
        issues.append(f"Very short resume ({word_count} words) — may lack enough keywords")
    score = 100 if 1 <= pages <= 2 else max(0, 100 - (pages - 2) * 30)
    return {"score": score, "pages": pages, "word_count": word_count, "issues": issues}


def check_formatting(text: str, meta: dict) -> dict:
    issues = []
    score = 100

    if meta["has_columns"]:
        issues.append("Multi-column layout detected — many ATS parse columns left-to-right, mangling content")
        score -= 30

    for warning in meta["warnings"]:
        issues.append(warning)
        score -= 20

    # Check for excessive special characters
    non_ascii_runs = re.findall(r"[^\x00-\x7F]{4,}", text)
    if non_ascii_runs:
        issues.append(f"Non-standard characters detected ({len(non_ascii_runs)} instances) — may not parse correctly")
        score -= 10

    # Check for very long lines
    long_lines = [l for l in text.splitlines() if len(l) > 200]
    if long_lines:
        issues.append("Unusually long lines detected — possible table or text box content")
        score -= 10

    return {"score": max(0, score), "issues": issues}


def check_keywords(text: str, job_description: str = "") -> dict:
    text_lower = text.lower()

    # Action verbs
    verbs_found = [v for v in ACTION_VERBS if v in text_lower]
    verb_score = min(100, len(verbs_found) / 8 * 100)

    # Metrics / quantification
    metrics = METRIC_PATTERN.findall(text)
    metric_score = min(100, len(metrics) / 5 * 100)

    issues = []
    if len(verbs_found) < 5:
        issues.append(f"Only {len(verbs_found)} action verbs found — use more (achieved, built, led, etc.)")
    if len(metrics) < 3:
        issues.append("Few quantified achievements — add numbers/metrics (e.g. 'increased sales by 30%')")

    # Job description keyword match
    jd_score = None
    jd_matches = []
    jd_missing = []
    if job_description:
        jd_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", job_description.lower()))
        stop = {"with", "that", "this", "have", "will", "from", "they", "your",
                "their", "able", "also", "been", "some", "what", "when", "would"}
        jd_keywords = jd_words - stop
        jd_matches = [w for w in jd_keywords if w in text_lower]
        jd_missing = [w for w in jd_keywords if w not in text_lower]
        jd_score = len(jd_matches) / len(jd_keywords) * 100 if jd_keywords else 0
        if jd_score < 50:
            issues.append(f"Only {jd_score:.0f}% keyword overlap with job description")

    score = (verb_score + metric_score) / 2

    return {
        "score": score,
        "action_verbs": verbs_found,
        "metrics_count": len(metrics),
        "jd_match_score": jd_score,
        "jd_matched": jd_matches[:15],
        "jd_missing": sorted(jd_missing)[:15],
        "issues": issues,
    }


def check_dates(text: str) -> dict:
    dates = DATE_PATTERN.findall(text)
    flat = [d for group in dates for d in group if d]
    issues = []
    score = 100
    if not flat:
        issues.append("No dates found — ATS expect date ranges for each role")
        score = 30
    return {"score": score, "dates_found": len(flat), "issues": issues}


# ── Scoring ───────────────────────────────────────────────────────────────────

def overall_score(scores: dict) -> float:
    return sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)


def get_grade(score: float) -> str:
    if score >= 80:
        return "GOOD"
    if score >= 60:
        return "FAIR"
    return "POOR"


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="ATS Scorer API",
    description="Analyse resumes for ATS compatibility",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/api/analyze", response_model=ATSReport)
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str = Form("")
):
    """
    Analyse a resume PDF for ATS compatibility.
    
    Returns detailed scoring across six categories.
    """
    try:
        pdf_data = await file.read()
        text, meta = extract_text(pdf_data)

        if not text.strip():
            raise ValueError("No text could be extracted — the PDF may be image-based. Try OCR first.")

        results = {
            "contact":    check_contact_info(text),
            "sections":   check_sections(text),
            "formatting": check_formatting(text, meta),
            "keywords":   check_keywords(text, job_description),
            "length":     check_length(text, meta["pages"]),
            "dates":      check_dates(text),
        }

        scores = {k: results[k]["score"] for k in results}
        total = overall_score(scores)

        # Collect all issues
        all_issues = []
        for key in results:
            all_issues.extend(results[key].get("issues", []))

        report = ATSReport(
            overall_score=total,
            grade=get_grade(total),
            contact=ScoreDetail(**results["contact"]),
            sections=ScoreDetail(**results["sections"]),
            formatting=ScoreDetail(**results["formatting"]),
            keywords=ScoreDetail(**results["keywords"]),
            length=ScoreDetail(**results["length"]),
            dates=ScoreDetail(**results["dates"]),
            all_issues=all_issues,
        )

        return report

    except ValueError as e:
        print(results['sections'])
        raise e
        raise ValueError(f"Error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error processing PDF: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
