"""Medical safety boundary service for MedSpeak.

MedSpeak is strictly an educational pronunciation tutor.
It must never provide clinical diagnosis, prescriptions, or patient-specific advice.
"""

import re

# Regex patterns detecting medical advice, diagnosis, or dosage inquiries
DOSAGE_PATTERNS = [
    r"\b(how much|what dose|what dosage|how many (mg|milligrams|tablets|pills))\b",
    r"\b(dosage recommendations?|can i take|should i take|how often (to|should i) take|overdose)\b",
]

DIAGNOSIS_PATTERNS = [
    r"\b(do i have|diagnose me|is this (a symptom of|cancer|covid)|what disease do i have)\b",
    r"\b(am i sick with|my symptoms are|i have pain in|why does my .* hurt)\b",
]

TREATMENT_PATTERNS = [
    r"\b(how to (treat|cure)|treatment recommendations?|what cures?|prescribe me)\b",
    r"\b(can you prescribe|what should i do for (my|this)|home remedies for)\b",
]

SAFETY_BOUNDARY_MESSAGE = (
    "I can help explain or pronounce medical terminology, but I can't provide "
    "diagnosis, treatment, or dosage advice. Please consult a qualified healthcare provider "
    "for patient-specific medical guidance."
)


def check_medical_safety(text: str) -> tuple[bool, str]:
    """Check whether a user prompt requests clinical diagnosis, treatment, or dosage advice.

    Returns:
        (is_violation, response_message)
    """
    clean = text.lower().strip()

    for pat in DOSAGE_PATTERNS + DIAGNOSIS_PATTERNS + TREATMENT_PATTERNS:
        if re.search(pat, clean):
            return True, SAFETY_BOUNDARY_MESSAGE

    return False, ""
