# ATS Resume Checker

A command-line tool that analyses a PDF resume for compatibility with Applicant Tracking Systems (ATS) and scores it across six categories.

## Requirements

- Python 3.10+
- [pdfplumber](https://github.com/jsvine/pdfplumber)

```bash
pip install pdfplumber
```

## Usage

```bash
# Basic check
python ats_checker.py resume.pdf

# With inline job description for keyword matching
python ats_checker.py resume.pdf --job-description "We need a Python developer with AWS experience..."

# With a job description text file
python ats_checker.py resume.pdf --job-file job.txt
```

## What It Checks

| Category | Weight | What's Analysed |
|---|---|---|
| **Formatting** | 25% | Multi-column layouts, image-based text, non-standard characters |
| **Keywords** | 25% | Action verbs, quantified achievements, job description keyword overlap |
| **Section Headers** | 20% | Presence of standard sections (experience, education, skills, etc.) |
| **Contact Info** | 15% | Email, phone, LinkedIn, GitHub |
| **Length** | 10% | Page count and word count |
| **Dates** | 5% | Date ranges present for roles |

## Sample Output

```
============================================================
  ATS COMPATIBILITY REPORT
  File: resume.pdf
============================================================

  OVERALL SCORE  [████████████░░░░░░░░] 61%  [FAIR]

------------------------------------------------------------
  ✓ Contact Info        [████████████████░░░░] 75%
  ⚠ Section Headers     [████████████░░░░░░░░] 60%
  ✗ Formatting          [████████░░░░░░░░░░░░] 40%
      → Multi-column layout detected — many ATS parse columns left-to-right, mangling content
  ✓ Keywords            [██████████████░░░░░░] 70%
  ✓ Length              [████████████████████] 100%
  ✓ Date Formats        [████████████████████] 100%

------------------------------------------------------------
  ACTION VERBS FOUND (7):
    developed, led, managed, improved, delivered, built, launched

  QUANTIFIED ACHIEVEMENTS: 4 found

  JOB DESCRIPTION MATCH: 68%
  Matched keywords: python, cloud, agile, docker, experience, team...
  Missing keywords: kubernetes, terraform, monitoring, scala...

------------------------------------------------------------
  TOP RECOMMENDATIONS:
  1. Multi-column layout detected — many ATS parse columns left-to-right, mangling content
  2. Only 7 action verbs found — use more (achieved, built, led, etc.)
  3. Few quantified achievements — add numbers/metrics (e.g. 'increased sales by 30%')
```

## Scoring

Each category is scored 0–100 and combined into an overall weighted score.

| Grade | Score |
|---|---|
| GOOD | 80–100 |
| FAIR | 60–79 |
| POOR | 0–59 |

## Common ATS Issues

- **Multi-column layouts** — ATS often read left-to-right across columns, mixing up content from separate sections. Use a single-column layout.
- **Image-based text** — Text embedded in images cannot be parsed. Ensure all text is selectable in the PDF.
- **Missing keywords** — ATS filter resumes by keyword match against the job description. Tailor each application.
- **Lack of metrics** — Quantified achievements (e.g. "reduced costs by 25%") score higher with both ATS and human reviewers.
- **Non-standard characters** — Decorative fonts or symbols may not parse correctly. Stick to standard ASCII.

## Limitations

- Does not perform OCR — image-based PDFs will return no text. Use a tool like `tesseract` to convert first.
- Job description keyword matching is based on word frequency, not semantic similarity.
- ATS behaviour varies by vendor; this tool targets general best practices rather than any specific system.