#!/usr/bin/env python3
"""
ATS (Applicant Tracking System) Resume Checker
Analyses a PDF resume and scores it for ATS compatibility.

Usage:
    python ats_checker.py resume.pdf
    python ats_checker.py resume.pdf --job-description "job desc text here"
    python ats_checker.py resume.pdf --job-file job.txt
"""

import sys
import re
import argparse
from pathlib import Path
from collections import Counter

try:
    import pdfplumber
except ImportError:
    print("Error: pdfplumber not installed. Run: pip install pdfplumber")
    sys.exit(1)


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

BAD_PATTERNS = {
    "tables":        r"<table|\\begin\{tabular\}",
    "headers_footers": None,   # detected via pdfplumber bbox
    "images_as_text": None,    # detected via low text-to-page ratio
    "special_chars": r"[^\x00-\x7F]{5,}",  # long runs of non-ASCII
}

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

METRIC_PATTERN = re.compile(r"\d+\s*(%|percent|x\b|times|\$|£|€|million|billion|k\b|users|customers|hours|days|weeks|months)")


# ── Text Extraction ───────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> tuple[str, dict]:
    """Extract text from PDF, return (full_text, metadata)."""
    meta = {"pages": 0, "has_columns": False, "warnings": []}
    pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        meta["pages"] = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            text = page.extract_text(layout=True) or ""
            pages_text.append(text)

            # Detect multi-column layout (common ATS problem)
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

    # Check for very long lines (could indicate tables pasted as text)
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


# ── Scoring & Report ──────────────────────────────────────────────────────────

WEIGHTS = {
    "contact":    0.15,
    "sections":   0.20,
    "formatting": 0.25,
    "keywords":   0.25,
    "length":     0.10,
    "dates":      0.05,
}

def overall_score(scores: dict) -> float:
    return sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)


def print_report(pdf_path: str, results: dict, overall: float):
    W = 60
    PASS = "✓"
    FAIL = "✗"
    WARN = "⚠"

    def bar(score):
        filled = int(score / 5)
        return f"[{'█' * filled}{'░' * (20 - filled)}] {score:.0f}%"

    def grade(score):
        if score >= 80: return "GOOD"
        if score >= 60: return "FAIR"
        return "POOR"

    print()
    print("=" * W)
    print(f"  ATS COMPATIBILITY REPORT")
    print(f"  File: {Path(pdf_path).name}")
    print("=" * W)
    print()
    print(f"  OVERALL SCORE  {bar(overall)}  [{grade(overall)}]")
    print()
    print("-" * W)

    sections = [
        ("Contact Info",  "contact"),
        ("Section Headers", "sections"),
        ("Formatting",    "formatting"),
        ("Keywords",      "keywords"),
        ("Length",        "length"),
        ("Date Formats",  "dates"),
    ]

    for label, key in sections:
        r = results[key]
        s = r["score"]
        icon = PASS if s >= 70 else (WARN if s >= 40 else FAIL)
        print(f"  {icon} {label:<20} {bar(s)}")
        for issue in r.get("issues", []):
            print(f"      → {issue}")
        print()

    # Keywords detail
    kw = results["keywords"]
    print("-" * W)
    print(f"  ACTION VERBS FOUND ({len(kw['action_verbs'])}):")
    if kw["action_verbs"]:
        print("    " + ", ".join(kw["action_verbs"]))
    print()
    print(f"  QUANTIFIED ACHIEVEMENTS: {kw['metrics_count']} found")

    if kw["jd_match_score"] is not None:
        print()
        print(f"  JOB DESCRIPTION MATCH: {kw['jd_match_score']:.0f}%")
        if kw["jd_matched"]:
            print(f"  Matched keywords: {', '.join(kw['jd_matched'])}")
        if kw["jd_missing"]:
            print(f"  Missing keywords: {', '.join(kw['jd_missing'])}")

    # Summary recommendations
    all_issues = []
    for key in results:
        all_issues.extend(results[key].get("issues", []))

    if all_issues:
        print()
        print("-" * W)
        print("  TOP RECOMMENDATIONS:")
        for i, issue in enumerate(all_issues[:8], 1):
            print(f"  {i}. {issue}")

    print()
    print("=" * W)
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ATS Resume Checker")
    parser.add_argument("pdf", help="Path to resume PDF")
    parser.add_argument("--job-description", "-j", default="", help="Job description text for keyword matching")
    parser.add_argument("--job-file", "-f", default="", help="Path to a text file containing the job description")
    args = parser.parse_args()

    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    if not pdf_path.lower().endswith(".pdf"):
        print("Error: Input must be a PDF file")
        sys.exit(1)

    job_desc = args.job_description
    if args.job_file:
        jf = Path(args.job_file)
        if not jf.exists():
            print(f"Error: Job file not found: {args.job_file}")
            sys.exit(1)
        job_desc = jf.read_text(encoding="utf-8")

    print(f"\nAnalysing {pdf_path}...")
    text, meta = extract_text(pdf_path)

    if not text.strip():
        print("Error: No text could be extracted — the PDF may be image-based. Try OCR first.")
        sys.exit(1)

    results = {
        "contact":    check_contact_info(text),
        "sections":   check_sections(text),
        "formatting": check_formatting(text, meta),
        "keywords":   check_keywords(text, job_desc),
        "length":     check_length(text, meta["pages"]),
        "dates":      check_dates(text),
    }

    scores = {k: results[k]["score"] for k in results}
    total = overall_score(scores)

    print_report(pdf_path, results, total)


if __name__ == "__main__":
    main()