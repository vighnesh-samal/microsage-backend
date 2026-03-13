from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import (
    AnalyzeRequest, AnalyzeResponse, OrganismResult,
    CultureMedia, Antibiotics, SymptomsResponse, HealthResponse,
    FeedbackRequest
)
from scorer import (
    score_organisms, get_symptoms_for_site,
    fill_teach_me, calculate_confidence, ORGANISMS
)
import json, os, smtplib
from datetime import datetime
from email.mime.text import MIMEText

GMAIL_USER = "vighnesh7samal@gmail.com"
GMAIL_PASS = "tlnj elck tpxq copx"

def send_feedback_email(rating, comment):
    try:
        msg = MIMEText(f"New MicroSage Feedback\n\nRating: {rating}/5\n\nComment:\n{comment or 'No comment left.'}")
        msg["Subject"] = f"⭐ MicroSage Feedback — {rating}/5"
        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        print(f"Email error: {e}")

# In-memory feedback store
feedback_store = []

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

app = FastAPI(
    title="MicroSage API",
    description="Microbiology Decision Support System — Think Like a Microbiologist",
    version="1.0.0"
)

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    return {
        "status": "MicroSage is running",
        "version": "1.0.0",
        "total_organisms": len(ORGANISMS)
    }


# ─────────────────────────────────────────────
# GET DYNAMIC SYMPTOMS FOR A SITE
# ─────────────────────────────────────────────

@app.get("/symptoms/{site}", response_model=SymptomsResponse)
def get_symptoms(site: str):
    valid_sites = ["Respiratory", "Urinary", "Gastrointestinal", "CNS", "Skin", "Bloodstream"]
    if site not in valid_sites:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid site. Choose from: {', '.join(valid_sites)}"
        )
    return get_symptoms_for_site(site)


# ─────────────────────────────────────────────
# GET ALL ORGANISMS (reference endpoint)
# ─────────────────────────────────────────────

@app.get("/organisms")
def get_organisms():
    return {
        "total": len(ORGANISMS),
        "organisms": [
            {
                "id": org["id"],
                "name": org["name"],
                "gram": org["gram"],
                "shape": org["shape"],
                "sites": org["sites"]
            }
            for org in ORGANISMS
        ]
    }


# ─────────────────────────────────────────────
# MAIN ANALYZE ENDPOINT
# ─────────────────────────────────────────────

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):

    # Validate at least one input is provided
    request_dict = request.dict()
    has_input = any([
        request.gram,
        request.shape,
        request.arrangement,
        request.oxygen,
        request.spore is not None,
        request.capsule is not None,
        request.hemolysis,
        request.motility is not None,
        request.site,
        request.age_group,
        request.immunocompromised,
        len(request.symptoms) > 0
    ])

    if not has_input:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least one clinical or microbiological input to analyze."
        )

    # Run scoring engine
    scored_results, inputs_provided = score_organisms(request_dict)

    # Filter out zero scores
    scored_results = [r for r in scored_results if r["score"] > 0]

    if not scored_results:
        raise HTTPException(
            status_code=404,
            detail="No organisms matched the provided inputs. Please review your selections."
        )

    # Take top 3
    top_3 = scored_results[:3]
    total_score = sum(r["score"] for r in top_3)

    # Calculate max possible score for confidence
    # (rough estimate based on inputs provided)
    max_possible = inputs_provided * 4

    # Build response
    organism_results = []
    for rank, result in enumerate(top_3, start=1):
        org = result["organism"]
        score = result["score"]
        matched = result["matched"]
        mismatched = result["mismatched"]

        # Percentage of top 3 total
        percentage = round((score / total_score) * 100, 1) if total_score > 0 else 0

        # Confidence
        confidence, confidence_reason = calculate_confidence(
            score=score,
            max_possible=max_possible,
            mismatches=len(mismatched),
            inputs_provided=inputs_provided
        )

        # Fill teach me template
        teach_me_text = fill_teach_me(
            template=org.get("teach_me", ""),
            site=request.site or "",
            age_group=request.age_group or "",
            immunocompromised=request.immunocompromised,
            symptoms=request.symptoms
        )

        organism_results.append(OrganismResult(
            rank=rank,
            name=org["name"],
            score=round(score, 2),
            percentage=percentage,
            confidence=confidence,
            confidence_reason=confidence_reason,
            teach_me=teach_me_text,
            clinical_pearl=org.get("clinical_pearl", ""),
            gram_appearance=org.get("gram_appearance", ""),
            culture_media=CultureMedia(
                primary=org["culture_media"]["primary"],
                secondary=org["culture_media"]["secondary"]
            ),
            confirmatory_tests=org.get("confirmatory_tests", []),
            antibiotics=Antibiotics(
                first_line=org["antibiotics"]["first_line"],
                second_line=org["antibiotics"]["second_line"],
                resistance_warning=org["antibiotics"]["resistance_warning"]
            ),
            matched_inputs=matched,
            mismatched_inputs=mismatched
        ))

    # Build analysis note
    if inputs_provided <= 2:
        analysis_note = "Limited inputs provided — results are broad estimates. Add more clinical details for higher accuracy."
    elif inputs_provided <= 5:
        analysis_note = "Moderate inputs provided — results are reasonably narrowed. Consider adding gram stain and site details if not already included."
    else:
        analysis_note = "Good input coverage — results reflect a well-characterized clinical picture."

    return AnalyzeResponse(
        results=organism_results,
        total_organisms_scored=len(ORGANISMS),
        inputs_provided=inputs_provided,
        analysis_note=analysis_note
    )

# ─────────────────────────────────────────────
# FEEDBACK ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    entry = {
        "id": len(feedback_store) + 1,
        "rating": request.rating,
        "comment": request.comment,
        "timestamp": datetime.utcnow().isoformat()
    }
    feedback_store.append(entry)
    send_feedback_email(request.rating, request.comment)
    return {"message": "Thank you for your feedback!", "id": entry["id"]}

@app.get("/feedback")
def get_feedback(sort: str = "desc"):
    feedbacks = sorted(feedback_store, key=lambda x: x["rating"], reverse=(sort != "asc"))
    return {
        "total": len(feedbacks),
        "average_rating": round(sum(f["rating"] for f in feedbacks) / len(feedbacks), 1) if feedbacks else 0,
        "feedbacks": feedbacks
    }
