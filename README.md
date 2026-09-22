# 📄 Multimodal Resume Analyzer & Recruiter Ranking Agent

An AI-powered resume analysis application that uses **Google Gemini's multimodal document understanding** to analyze resumes as complete documents — not just extracted text. Supports PDFs, images, DOCX, and more. Built for job seekers, students, professionals, and recruiters.

## ✨ Features

### For Job Seekers & Professionals
- **Multimodal Document Analysis** — Understands text, layout, formatting, images, tables, and visual elements
- **Evidence-Based Scoring** — 8-category rubric with transparent, weighted scoring (100-point scale)
- **ATS Compatibility Check** — Analyzes how well your resume works with Applicant Tracking Systems
- **Actionable Recommendations** — Specific before/after improvement suggestions
- **Visual/Document Quality Analysis** — Evaluates layout, typography, spacing, and readability
- **Job Match Analysis** — Compare your resume against a specific job description

### For Recruiters & Hiring Teams
- **Batch Resume Analysis** — Upload and analyze up to 50 resumes simultaneously
- **Candidate Ranking** — Automated scoring and ranking based on job-relevant criteria only
- **Comparison Table** — Side-by-side candidate comparison with sortable columns
- **Filtering** — Filter by score thresholds, ATS compatibility, skills, and more
- **CSV/JSON Export** — Export comparison results for external tools
- **Fairness Enforcement** — Ranking never uses protected characteristics (gender, race, age, etc.)

### Supported File Formats
| Format | Type | Processing |
|--------|------|------------|
| PDF | Document | Native multimodal vision (preserves layout, images, charts) |
| DOCX | Document | Text + structure extraction |
| TXT | Text | Direct text processing |
| MD | Text | Markdown processing |
| RTF | Text | RTF-to-text extraction |
| PNG | Image | Multimodal vision |
| JPG/JPEG | Image | Multimodal vision |
| WebP | Image | Multimodal vision |
| BMP | Image | Multimodal vision |
| TIFF | Image | Multimodal vision |

## 🏗️ Architecture

```
app/
├── config.py                    # Configuration, env vars, scoring weights
├── models/
│   └── resume.py                # Pydantic schemas (ResumeAnalysis, JobMatch, etc.)
├── services/
│   ├── document_processor.py    # File validation, multimodal input preparation
│   ├── gemini_service.py        # Gemini API integration, structured output
│   ├── resume_analyzer.py       # Analysis orchestrator, score calculation
│   ├── job_matcher.py           # Job description matching utilities
│   └── ranking.py               # Sorting, filtering, export
├── prompts/
│   └── analysis.py              # System instructions, analysis prompts
└── ui/
    ├── components.py            # Reusable UI components
    └── main_app.py              # Streamlit application

tests/
├── conftest.py                  # Shared fixtures, mock Gemini client
├── test_document_processor.py   # File validation & processing tests
├── test_models.py               # Pydantic schema validation tests
└── test_resume_analyzer.py      # Scoring, pipeline, ranking tests
```

### Processing Pipeline

```
File Upload → Validation → Type Detection → Multimodal Processing → Gemini Analysis
    → Structured Output Parsing → Score Validation → Result Rendering
```

- **PDFs** are sent to Gemini as `document` type for native vision understanding
- **Images** are sent as `image` type for multimodal analysis
- **DOCX/RTF/Text** are extracted and sent as text content
- **Scoring** is deterministic: Gemini provides category scores, the app calculates the weighted overall

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| AI Model | Google Gemini 3.8 Flash (multimodal) |
| SDK | google-genai >= 2.3.0 |
| UI | Streamlit |
| Validation | Pydantic v2 |
| DOCX Processing | python-docx |
| Image Handling | Pillow |
| RTF Processing | striprtf |
| Testing | pytest |

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- [Google Gemini API key](https://aistudio.google.com/apikey)

### Installation

```bash
# Clone the repository
git clone https://github.com/Huzaifa-Ansari-AI/Resume-Analyzer-Agent.git
cd Resume-Analyzer-Agent

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Create your .env file from the template
copy .env.example .env     # Windows
# cp .env.example .env     # macOS/Linux

# Edit .env and add your Gemini API key
# GEMINI_API_KEY=your_key_here
```

### Run Locally

```bash
streamlit run app/ui/main_app.py
```

The app will open at `http://localhost:8501`.

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_document_processor.py -v

# Run with coverage
pytest tests/ -v --tb=short
```

Tests use mocked Gemini API calls — no API key required for testing.

## 📊 Scoring Methodology

The analyzer uses a transparent **100-point weighted rubric**:

| Category | Weight | What It Measures |
|----------|--------|------------------|
| Content Quality | 20% | Completeness, relevance, professional summary |
| Experience & Achievements | 20% | Action verbs, quantified impact, career progression |
| Skills Relevance | 15% | Breadth, relevance, organization |
| ATS Compatibility | 15% | Standard sections, text extractability, formatting |
| Structure & Readability | 10% | Organization, consistency, scanability |
| Impact & Quantification | 10% | Numbers, metrics, specific outcomes |
| Language & Communication | 5% | Grammar, tone, active voice |
| Visual/Document Quality | 5% | Layout, whitespace, typography |

**Scoring is deterministic**: Gemini provides per-category scores with evidence, then the application calculates the weighted overall score. This prevents inconsistent LLM-generated totals.

## 🔒 Privacy & Security

- **No permanent storage**: Resumes are processed in memory and not saved to disk permanently
- **API disclosure**: Documents are sent to Google's Gemini API for AI analysis
- **No logging of PII**: Resume contents, contact information, and personal data are not logged
- **Environment variables**: API keys are loaded from environment variables, never hard-coded
- **Prompt injection defense**: Resume content is treated as untrusted data; embedded instructions are ignored
- **Store=False**: Gemini interactions are not stored on Google's servers

## ⚖️ Fairness

- Candidate ranking is based **only on job-relevant resume evidence**
- The system never evaluates candidates based on gender, race, ethnicity, religion, age, disability, nationality, appearance, or other protected characteristics
- Profile photos are detected but NOT used for scoring
- The system is **decision-support software**, not an autonomous hiring tool

## 🚀 Deployment

### Streamlit Community Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repository
4. Set `GEMINI_API_KEY` in Streamlit secrets
5. Set main file path to `app/ui/main_app.py`

### Docker (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app/ui/main_app.py", "--server.port=8501"]
```

## ⚠️ Limitations

- **AI-generated analysis**: Results depend on the Gemini model and may not be perfect
- **DOCX images**: Visual elements inside DOCX files are not preserved (text-only extraction)
- **Scanned PDFs**: Quality depends on scan resolution and Gemini's OCR capability
- **Rate limits**: Batch processing is sequential to respect API rate limits
- **Cost**: Each analysis consumes Gemini API tokens
- **No offline mode**: Requires internet access for Gemini API calls

## 🔮 Future Improvements

1. **Resume builder** — Generate improved resume sections based on analysis
2. **LinkedIn import** — Direct LinkedIn profile analysis
3. **Team collaboration** — Shared recruiter workspaces with saved candidates
4. **Historical tracking** — Track resume improvements over time
5. **Custom rubrics** — User-defined scoring criteria for specific industries
6. **Async batch processing** — Parallel resume analysis for faster batch results

## 📄 License

This project is for educational and portfolio purposes.

---

Built with ❤️ using Google Gemini AI
