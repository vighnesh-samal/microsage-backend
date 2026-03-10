import json
import os
from typing import List, Dict, Tuple

# ─────────────────────────────────────────────
# LOAD ORGANISM DATA
# ─────────────────────────────────────────────

DATA_PATH = os.path.join(os.path.dirname(__file__), "microsage_organisms.json")

with open(DATA_PATH, "r") as f:
    RAW_DATA = json.load(f)

ORGANISMS = RAW_DATA["organisms"]


# ─────────────────────────────────────────────
# DYNAMIC SYMPTOMS BY SITE
# ─────────────────────────────────────────────

GENERAL_SYMPTOMS = [
    "Fever",
    "Chills and rigors",
    "Fatigue / Malaise",
    "Night sweats",
    "Weight loss"
]

SITE_SYMPTOMS = {
    "Respiratory": [
        "Cough",
        "Productive cough",
        "Hemoptysis",
        "Shortness of breath",
        "Chest pain",
        "Whooping sound"
    ],
    "Urinary": [
        "Burning urination",
        "Frequent urination",
        "Cloudy urine",
        "Flank pain",
        "Blood in urine"
    ],
    "Gastrointestinal": [
        "Diarrhea",
        "Bloody diarrhea",
        "Nausea / Vomiting",
        "Abdominal cramps",
        "Rice water stools"
    ],
    "CNS": [
        "Neck stiffness",
        "Headache",
        "Photophobia",
        "Altered consciousness",
        "Seizures"
    ],
    "Skin": [
        "Itching",
        "Rash",
        "Redness / Erythema",
        "Swelling",
        "Pus / Wound discharge",
        "Skin ulceration",
        "Burning sensation"
    ],
    "Bloodstream": [
        "Chills and rigors",
        "Altered consciousness",
        "Rash",
        "Pus / Wound discharge"
    ]
}


def get_symptoms_for_site(site: str) -> Dict:
    """Return general + site specific symptoms for a given clinical site."""
    return {
        "site": site,
        "general_symptoms": GENERAL_SYMPTOMS,
        "site_specific_symptoms": SITE_SYMPTOMS.get(site, [])
    }


# ─────────────────────────────────────────────
# SCORING WEIGHTS
# ─────────────────────────────────────────────

# How much each input category contributes to the total score
GRAM_MATCH_SCORE = 6       # Gram reaction — highest weight, most definitive
GRAM_MISMATCH_PENALTY = 8  # Heavy penalty for gram mismatch

SHAPE_MATCH_SCORE = 3
SHAPE_MISMATCH_PENALTY = 3

ARRANGEMENT_MATCH_SCORE = 2
ARRANGEMENT_MISMATCH_PENALTY = 2

OXYGEN_MATCH_SCORE = 3
OXYGEN_MISMATCH_PENALTY = 4

SPORE_MATCH_SCORE = 4
SPORE_MISMATCH_PENALTY = 5  # Spore forming vs non-spore forming is highly definitive

CAPSULE_MATCH_SCORE = 2
CAPSULE_MISMATCH_PENALTY = 1

HEMOLYSIS_MATCH_SCORE = 3
HEMOLYSIS_MISMATCH_PENALTY = 2

MOTILITY_MATCH_SCORE = 2
MOTILITY_MISMATCH_PENALTY = 1


# ─────────────────────────────────────────────
# TEACH ME TEMPLATE FILLER
# ─────────────────────────────────────────────

def fill_teach_me(template: str, site: str, age_group: str, immunocompromised: bool, symptoms: List[str]) -> str:
    """Fill in the teach me template with actual user inputs."""
    if not site:
        site = "unspecified site"
    if not age_group:
        age_group = "patient"
    else:
        age_group = f"{age_group.lower()} patient"

    if immunocompromised:
        age_group += " (immunocompromised)"

    symptom_str = ", ".join(symptoms) if symptoms else "no specific symptoms recorded"

    result = template.replace("[site]", site)
    result = result.replace("[age_group]", age_group)
    result = result.replace("[symptoms]", symptom_str)
    return result


# ─────────────────────────────────────────────
# CONFIDENCE CALCULATION
# ─────────────────────────────────────────────

def calculate_confidence(
    score: float,
    max_possible: float,
    mismatches: int,
    inputs_provided: int
) -> Tuple[str, str]:
    """
    Returns (confidence_level, confidence_reason)
    confidence_level: "High" | "Moderate" | "Low"
    """
    if max_possible == 0 or inputs_provided == 0:
        return "Low", "Insufficient inputs provided to determine confidence."

    score_ratio = score / max_possible

    if mismatches == 0 and score_ratio >= 0.65:
        return (
            "High",
            "Most provided inputs strongly match this organism's profile with no contradicting features."
        )
    elif mismatches <= 1 and score_ratio >= 0.40:
        return (
            "Moderate",
            "Several inputs match this organism however one or more features are inconsistent — consider alongside clinical picture."
        )
    else:
        return (
            "Low",
            "Multiple inputs contradict this organism's typical profile — use clinical judgment and consider alternative diagnoses."
        )


# ─────────────────────────────────────────────
# MAIN SCORING FUNCTION
# ─────────────────────────────────────────────

def score_organisms(request_data: dict) -> List[dict]:
    """
    Score all organisms against provided inputs.
    Returns sorted list of organism results.
    """
    gram = request_data.get("gram")
    shape = request_data.get("shape")
    arrangement = request_data.get("arrangement")
    oxygen = request_data.get("oxygen")
    spore = request_data.get("spore")
    capsule = request_data.get("capsule")
    hemolysis = request_data.get("hemolysis")
    motility = request_data.get("motility")
    site = request_data.get("site")
    age_group = request_data.get("age_group")
    immunocompromised = request_data.get("immunocompromised", False)
    symptoms = request_data.get("symptoms", [])

    # Count how many inputs were actually provided
    inputs_provided = sum([
        gram is not None,
        shape is not None,
        arrangement is not None,
        oxygen is not None,
        spore is not None,
        capsule is not None,
        hemolysis is not None,
        motility is not None,
        site is not None,
        age_group is not None,
        immunocompromised,
        len(symptoms) > 0
    ])

    results = []

    for org in ORGANISMS:
        score = 0
        matched = []
        mismatched = []

        # ── GRAM REACTION ──
        if gram is not None:
            org_gram = org.get("gram", "")
            if gram == org_gram:
                score += GRAM_MATCH_SCORE
                matched.append(f"Gram reaction ({gram})")
            elif org_gram in ["No Gram Reaction (Acid Fast)", "No Gram Reaction (Intracellular)"]:
                # Atypical organisms — no penalty, just no bonus
                pass
            else:
                score -= GRAM_MISMATCH_PENALTY
                mismatched.append(f"Gram reaction (selected: {gram}, organism: {org_gram})")

        # ── SHAPE ──
        if shape is not None:
            org_shape = org.get("shape", "")
            if shape == org_shape:
                score += SHAPE_MATCH_SCORE
                matched.append(f"Shape ({shape})")
            elif org_shape == "Pleomorphic" or org_shape == "Coccoid":
                # Pleomorphic organisms — partial match possible
                pass
            else:
                score -= SHAPE_MISMATCH_PENALTY
                mismatched.append(f"Shape (selected: {shape}, organism: {org_shape})")

        # ── ARRANGEMENT ──
        if arrangement is not None:
            org_arrangement = org.get("arrangement", "")
            # Handle organisms that can appear in multiple arrangements
            if arrangement in org_arrangement or org_arrangement in arrangement:
                score += ARRANGEMENT_MATCH_SCORE
                matched.append(f"Arrangement ({arrangement})")
            else:
                score -= ARRANGEMENT_MISMATCH_PENALTY
                mismatched.append(f"Arrangement (selected: {arrangement}, organism: {org_arrangement})")

        # ── OXYGEN REQUIREMENT ──
        if oxygen is not None:
            org_oxygen = org.get("oxygen", "")
            if oxygen == org_oxygen:
                score += OXYGEN_MATCH_SCORE
                matched.append(f"Oxygen requirement ({oxygen})")
            elif oxygen == "Facultative Anaerobe" and org_oxygen == "Obligate Anaerobe":
                # Partial mismatch — facultative vs obligate
                score -= 2
                mismatched.append(f"Oxygen requirement (selected: {oxygen}, organism: {org_oxygen})")
            else:
                score -= OXYGEN_MISMATCH_PENALTY
                mismatched.append(f"Oxygen requirement (selected: {oxygen}, organism: {org_oxygen})")

        # ── SPORE FORMATION ──
        if spore is not None:
            org_spore = org.get("spore", False)
            if spore == org_spore:
                score += SPORE_MATCH_SCORE
                matched.append(f"Spore formation ({'Spore forming' if spore else 'Non-spore forming'})")
            else:
                score -= SPORE_MISMATCH_PENALTY
                mismatched.append(f"Spore formation (selected: {'Yes' if spore else 'No'}, organism: {'Yes' if org_spore else 'No'})")

        # ── CAPSULE ──
        if capsule is not None:
            org_capsule = org.get("capsule", False)
            if capsule == org_capsule:
                score += CAPSULE_MATCH_SCORE
                matched.append(f"Capsule ({'Present' if capsule else 'Absent'})")
            else:
                score -= CAPSULE_MISMATCH_PENALTY
                mismatched.append(f"Capsule (selected: {'Yes' if capsule else 'No'}, organism: {'Yes' if org_capsule else 'No'})")

        # ── HEMOLYSIS ──
        if hemolysis is not None:
            org_hemolysis = org.get("hemolysis", "")
            # Handle double zone hemolysis — counts as Beta match
            org_hemolysis_normalized = "Beta" if "Beta" in org_hemolysis else org_hemolysis
            hemolysis_normalized = "Beta" if "Beta" in hemolysis else hemolysis
            if hemolysis_normalized == org_hemolysis_normalized:
                score += HEMOLYSIS_MATCH_SCORE
                matched.append(f"Hemolysis ({hemolysis})")
            else:
                score -= HEMOLYSIS_MISMATCH_PENALTY
                mismatched.append(f"Hemolysis (selected: {hemolysis}, organism: {org_hemolysis})")

        # ── MOTILITY ──
        if motility is not None:
            org_motility = org.get("motility", False)
            if motility == org_motility:
                score += MOTILITY_MATCH_SCORE
                matched.append(f"Motility ({'Motile' if motility else 'Non-motile'})")
            else:
                score -= MOTILITY_MISMATCH_PENALTY
                mismatched.append(f"Motility (selected: {'Motile' if motility else 'Non-motile'}, organism: {'Motile' if org_motility else 'Non-motile'})")

        # ── CLINICAL SITE ──
        if site is not None:
            site_weights = org.get("site_weights", {})
            if site in site_weights:
                site_score = site_weights[site]
                score += site_score
                matched.append(f"Clinical site ({site} — weight: {site_score})")
            else:
                score -= 3
                mismatched.append(f"Clinical site ({site} not typical for this organism)")

        # ── AGE GROUP ──
        if age_group is not None:
            age_weights = org.get("age_weights", {})
            age_score = age_weights.get(age_group, 0)
            if age_score > 0:
                score += age_score
                matched.append(f"Age group ({age_group} — weight: {age_score})")
            elif age_score < 0:
                score += age_score  # adds negative value
                mismatched.append(f"Age group ({age_group} atypical for this organism)")

        # ── IMMUNOCOMPROMISED ──
        if immunocompromised:
            age_weights = org.get("age_weights", {})
            immuno_score = age_weights.get("Immunocompromised", 0)
            if immuno_score > 0:
                score += immuno_score
                matched.append(f"Immunocompromised host (weight: {immuno_score})")

        # ── SYMPTOMS ──
        symptom_weights = org.get("symptom_weights", {})
        for symptom in symptoms:
            if symptom in symptom_weights:
                sym_score = symptom_weights[symptom]
                score += sym_score
                matched.append(f"Symptom: {symptom} (weight: {sym_score})")

        # ── PREVENT NEGATIVE SCORES ──
        score = max(0, score)

        results.append({
            "organism": org,
            "score": score,
            "matched": matched,
            "mismatched": mismatched,
            "inputs_provided": inputs_provided
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    return results, inputs_provided
