from pydantic import BaseModel
from typing import List, Optional


# ─────────────────────────────────────────────
# INPUT MODEL
# ─────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    gram: Optional[str] = None           # "Gram Positive" | "Gram Negative" | "No Gram Reaction"
    shape: Optional[str] = None          # "Cocci" | "Bacilli" | "Coccobacilli" | "Pleomorphic" | "Coccoid"
    arrangement: Optional[str] = None   # "Clusters" | "Chains" | "Pairs / Diplococci" | "Single" | "Pairs / Chains"
    oxygen: Optional[str] = None        # "Obligate Aerobe" | "Obligate Anaerobe" | "Facultative Anaerobe" | "Microaerophilic" | "Obligate Intracellular"
    spore: Optional[bool] = None        # True | False
    capsule: Optional[bool] = None      # True | False
    hemolysis: Optional[str] = None     # "Alpha" | "Beta" | "Gamma" | "Double zone (Beta)"
    motility: Optional[bool] = None     # True | False
    site: Optional[str] = None          # "Respiratory" | "Urinary" | "Gastrointestinal" | "CNS" | "Skin" | "Bloodstream"
    age_group: Optional[str] = None     # "Neonate" | "Child" | "Adult" | "Elderly"
    immunocompromised: bool = False
    symptoms: List[str] = []


# ─────────────────────────────────────────────
# OUTPUT MODELS
# ─────────────────────────────────────────────

class CultureMedia(BaseModel):
    primary: str
    secondary: str


class Antibiotics(BaseModel):
    first_line: str
    second_line: str
    resistance_warning: str


class OrganismResult(BaseModel):
    rank: int
    name: str
    score: float
    percentage: float
    confidence: str          # "High" | "Moderate" | "Low"
    confidence_reason: str
    teach_me: str
    clinical_pearl: str
    gram_appearance: str
    culture_media: CultureMedia
    confirmatory_tests: List[str]
    antibiotics: Antibiotics
    matched_inputs: List[str]    # which inputs drove the score up
    mismatched_inputs: List[str] # which inputs contradicted this organism


class AnalyzeResponse(BaseModel):
    results: List[OrganismResult]
    total_organisms_scored: int
    inputs_provided: int         # how many inputs the user gave
    analysis_note: str           # general note about the analysis


class SymptomsResponse(BaseModel):
    site: str
    general_symptoms: List[str]
    site_specific_symptoms: List[str]


class HealthResponse(BaseModel):
    status: str
    version: str
    total_organisms: int
