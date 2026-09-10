"""Medical terminology database and pronunciation resolver for MedSpeak.

Provides verified phonetic transcriptions, IPA, syllable stress breakdowns,
and educational definitions for common and complex clinical terms.
"""

import re
from dataclasses import dataclass


@dataclass
class MedicalTerm:
    canonical_name: str
    category: str
    ipa: str
    syllables: str
    definition: str
    aliases: list[str]


# Verified clinical pronunciation dictionary
MEDICAL_TERMS: dict[str, MedicalTerm] = {
    "hydroxychloroquine": MedicalTerm(
        canonical_name="hydroxychloroquine",
        category="Antimalarial / Antirheumatic (DMARD)",
        ipa="/haɪˌdrɒksiˈklɔːrəkwɪn/",
        syllables="hy-DROK-see-KLOR-oh-kwin",
        definition=(
            "A disease-modifying medication used to prevent and treat malaria "
            "and autoimmune conditions such as lupus and rheumatoid arthritis."
        ),
        aliases=["plaquenil", "hcq", "hydro chloroquine", "hydroxy chloroquine"],
    ),
    "amoxicillin": MedicalTerm(
        canonical_name="amoxicillin",
        category="Aminopenicillin Antibiotic",
        ipa="/əˌmɒksɪˈsɪlɪn/",
        syllables="uh-MOX-i-SIL-in",
        definition=(
            "A widely prescribed penicillin-class antibiotic used to treat "
            "diverse bacterial infections."
        ),
        aliases=["amoxil", "amox"],
    ),
    "tachycardia": MedicalTerm(
        canonical_name="tachycardia",
        category="Cardiology / Arrhythmia",
        ipa="/ˌtæk.ɪˈkɑːr.di.ə/",
        syllables="TAK-i-KAR-dee-uh",
        definition="An elevated resting heart rate exceeding 100 beats per minute in adults.",
        aliases=["rapid heart rate", "fast pulse", "tacky cardia", "tachyarrhythmia"],
    ),
    "omeprazole": MedicalTerm(
        canonical_name="omeprazole",
        category="Proton Pump Inhibitor (PPI)",
        ipa="/oʊˈmɛprəzoʊl/",
        syllables="oh-MEP-ruh-zohl",
        definition=(
            "A medication that inhibits gastric acid production, commonly prescribed "
            "for GERD, acid reflux, and peptic ulcer disease."
        ),
        aliases=["prilosec"],
    ),
    "acetaminophen": MedicalTerm(
        canonical_name="acetaminophen",
        category="Analgesic / Antipyretic",
        ipa="/əˌsiː.təˈmɪn.ə.fɛn/",
        syllables="uh-SEE-tuh-MIN-oh-fen",
        definition="A medication used for fever reduction and mild-to-moderate pain relief.",
        aliases=[
            "tylenol",
            "paracetamol",
            "apap",
            "a set of amino phen",
            "a cedar minophen",
            "acetaminofen",
        ],
    ),
    "ibuprofen": MedicalTerm(
        canonical_name="ibuprofen",
        category="Nonsteroidal Anti-inflammatory Drug (NSAID)",
        ipa="/ˌaɪbjuːˈproʊfən/",
        syllables="eye-byoo-PROH-fen",
        definition=(
            "A medication that decreases pain, inflammation, and fever by "
            "inhibiting prostaglandin synthesis."
        ),
        aliases=["advil", "motrin"],
    ),
    "azithromycin": MedicalTerm(
        canonical_name="azithromycin",
        category="Macrolide Antibiotic",
        ipa="/əˌzɪθroʊˈmaɪsɪn/",
        syllables="uh-ZITH-roh-MY-sin",
        definition="An antibiotic used to treat respiratory, skin, and other bacterial infections.",
        aliases=["zithromax", "z-pack"],
    ),
    "metformin": MedicalTerm(
        canonical_name="metformin",
        category="Biguanide Antidiabetic",
        ipa="/mɛtˈfɔːrmɪn/",
        syllables="met-FOR-min",
        definition="A first-line medication for blood glucose management in type 2 diabetes.",
        aliases=["glucophage"],
    ),
    "clopidogrel": MedicalTerm(
        canonical_name="clopidogrel",
        category="Antiplatelet Agent",
        ipa="/kloʊˈpɪdəɡrɛl/",
        syllables="kloh-PID-oh-grel",
        definition=(
            "An antiplatelet agent used to prevent blood clots in coronary artery "
            "disease and peripheral vascular disease."
        ),
        aliases=["plavix"],
    ),
    "dexamethasone": MedicalTerm(
        canonical_name="dexamethasone",
        category="Corticosteroid",
        ipa="/ˌdɛksəˈmɛθəsoʊn/",
        syllables="DEK-suh-METH-uh-sohn",
        definition=(
            "A glucocorticoid medication providing potent anti-inflammatory "
            "and immunosuppressant effects."
        ),
        aliases=["decadron"],
    ),
    "levothyroxine": MedicalTerm(
        canonical_name="levothyroxine",
        category="Thyroid Hormone Replacement",
        ipa="/ˌliːvoʊθaɪˈrɒksiːn/",
        syllables="LEE-voh-thye-ROX-een",
        definition="A synthetic thyroid hormone (T4) used in the management of hypothyroidism.",
        aliases=["synthroid"],
    ),
    "sternocleidomastoid": MedicalTerm(
        canonical_name="sternocleidomastoid",
        category="Musculoskeletal Anatomy",
        ipa="/ˌstɜːrnoʊˌklaɪdoʊˈmæstɔɪd/",
        syllables="STUR-noh-KLYE-doh-MAS-toyd",
        definition=(
            "A major paired muscle in the neck that assists in flexing the cervical "
            "spine and rotating the head."
        ),
        aliases=["scm muscle"],
    ),
    "epiglottis": MedicalTerm(
        canonical_name="epiglottis",
        category="Respiratory Anatomy",
        ipa="/ˌɛpɪˈɡlɒtɪs/",
        syllables="ep-i-GLOT-is",
        definition=(
            "A flap of elastic cartilage at the root of the tongue that protects "
            "the larynx during swallowing."
        ),
        aliases=[],
    ),
    "esophagus": MedicalTerm(
        canonical_name="esophagus",
        category="Digestive Anatomy",
        ipa="/ɪˈsɒfəɡəs/",
        syllables="ee-SOF-uh-guhs",
        definition=(
            "The muscular tube that transports food and liquids from the pharynx to the stomach."
        ),
        aliases=["gullet"],
    ),
    "electroencephalography": MedicalTerm(
        canonical_name="electroencephalography",
        category="Diagnostic Neurophysiology",
        ipa="/ɪˌlɛktroʊɛnˌsɛfəˈlɒɡrəfi/",
        syllables="ee-LEK-troh-en-SEF-uh-LOG-ruh-fee",
        definition=(
            "An electrophysiological test measuring the electrical activity of the cerebral cortex."
        ),
        aliases=["eeg"],
    ),
    "echocardiography": MedicalTerm(
        canonical_name="echocardiography",
        category="Diagnostic Cardiology",
        ipa="/ˌɛkoʊkɑːrdiˈɒɡrəfi/",
        syllables="EK-oh-kar-dee-OG-ruh-fee",
        definition=(
            "A diagnostic cardiac ultrasound imaging test assessing heart chamber "
            "morphology and valvular hemodynamics."
        ),
        aliases=["echo", "cardiac ultrasound"],
    ),
    "mri": MedicalTerm(
        canonical_name="mri",
        category="Diagnostic Radiology",
        ipa="/ˌɛm.ɑːrˈaɪ/",
        syllables="em-ahr-EYE",
        definition=(
            "Magnetic resonance imaging; a noninvasive diagnostic imaging technology "
            "producing detailed three-dimensional anatomical images."
        ),
        aliases=["magnetic resonance imaging"],
    ),
    "ecg": MedicalTerm(
        canonical_name="ecg",
        category="Diagnostic Cardiology",
        ipa="/ˌiː.siːˈdʒiː/",
        syllables="ee-see-JEE",
        definition=(
            "Electrocardiogram; a diagnostic clinical recording tracing the electrical "
            "depolarization and repolarization of heart myocardium."
        ),
        aliases=["ekg", "electrocardiogram"],
    ),
    "copd": MedicalTerm(
        canonical_name="copd",
        category="Pulmonology / Chronic Respiratory Disease",
        ipa="/ˌsiː.oʊ.piːˈdiː/",
        syllables="see-oh-pee-DEE",
        definition=(
            "Chronic obstructive pulmonary disease; a progressive inflammatory disease "
            "causing airflow limitation and breathing difficulty."
        ),
        aliases=["chronic obstructive pulmonary disease"],
    ),
    "sars-cov-2": MedicalTerm(
        canonical_name="sars-cov-2",
        category="Virology / Infectious Disease",
        ipa="/ˌsɑːrz.koʊˈviː.tuː/",
        syllables="SARZ-koh-vee-TOO",
        definition=(
            "Severe acute respiratory syndrome coronavirus 2; the betacoronavirus strain "
            "causing COVID-19 respiratory infections."
        ),
        aliases=["sars cov 2", "covid 19 virus", "coronavirus"],
    ),
    "10 mg": MedicalTerm(
        canonical_name="10 mg",
        category="Clinical Pharmacology / Dosage Unit",
        ipa="/tɛn ˈmɪlɪɡræmz/",
        syllables="ten MIL-i-gramz",
        definition=(
            "A metric dosage measurement equal to ten milligrams (0.010 grams) of "
            "an active pharmaceutical ingredient."
        ),
        aliases=["10 milligrams", "ten milligrams", "10mg"],
    ),
    "0.5 ml": MedicalTerm(
        canonical_name="0.5 ml",
        category="Clinical Pharmacology / Volume Unit",
        ipa="/ˈzɪroʊ pɔɪnt faɪv ˈmɪlɪliːtərz/",
        syllables="ZEER-oh poynt fyv MIL-i-lee-terz",
        definition=(
            "A volumetric liquid dosage measure equal to one-half milliliter (500 microliters)."
        ),
        aliases=["0.5 milliliters", "half a milliliter", "0.5ml"],
    ),
    "2.5 mg": MedicalTerm(
        canonical_name="2.5 mg",
        category="Clinical Pharmacology / Dosage Unit",
        ipa="/tuː pɔɪnt faɪv ˈmɪlɪɡræmz/",
        syllables="too poynt fyv MIL-i-gramz",
        definition=(
            "A metric dosage measurement equal to two and a half milligrams (0.0025 grams)."
        ),
        aliases=["2.5 milligrams", "two point five milligrams", "2.5mg"],
    ),
    "hypertension": MedicalTerm(
        canonical_name="hypertension",
        category="Cardiovascular Pathology",
        ipa="/ˌhaɪ.pərˈtɛn.ʃən/",
        syllables="HY-per-TEN-shun",
        definition="Chronically elevated systemic arterial blood pressure exceeding normal limits.",
        aliases=["high blood pressure", "htn"],
    ),
    "hypotension": MedicalTerm(
        canonical_name="hypotension",
        category="Cardiovascular Pathology",
        ipa="/ˌhaɪ.poʊˈtɛn.ʃən/",
        syllables="HY-poh-TEN-shun",
        definition="Abnormally low arterial blood pressure below expected physiologic baseline.",
        aliases=["low blood pressure"],
    ),
    "myocardial infarction": MedicalTerm(
        canonical_name="myocardial infarction",
        category="Acute Cardiovascular Disease",
        ipa="/ˌmaɪ.oʊˈkɑːr.di.əl ɪnˈfɑːrk.ʃən/",
        syllables="MY-oh-KAR-dee-uhl in-FARK-shun",
        definition=(
            "Ischemic necrosis of myocardial heart tissue caused by abrupt coronary "
            "artery occlusion."
        ),

        aliases=["heart attack", "mi"],
    ),
    "gastroesophageal reflux disease": MedicalTerm(
        canonical_name="gastroesophageal reflux disease",
        category="Gastroenterology",
        ipa="/ˌɡæs.troʊ.ɪˌsɒf.əˈdʒiː.əl ˈriː.flʌks dɪˈziːz/",
        syllables="GAS-troh-ee-SOF-uh-JEE-uhl REE-fluks dih-ZEEZ",
        definition=(
            "A chronic digestive condition in which stomach acid flows backward into the esophagus."
        ),
        aliases=["gerd", "acid reflux disease", "reflux"],
    ),
    "electrocardiogram": MedicalTerm(
        canonical_name="electrocardiogram",
        category="Diagnostic Cardiology",
        ipa="/ɪˌlɛk.troʊˈkɑːr.di.oʊ.ɡræm/",
        syllables="ee-LEK-troh-KAR-dee-oh-gram",
        definition=(
            "A clinical recording tracing the electrical depolarization and "
            "repolarization waves of the heart myocardium."
        ),
        aliases=["ecg", "ekg"],
    ),
    "pneumonia": MedicalTerm(
        canonical_name="pneumonia",
        category="Pulmonology / Infectious Disease",
        ipa="/njuːˈmoʊ.ni.ə/",
        syllables="noo-MOH-nee-uh",
        definition=(
            "An inflammatory infection of pulmonary alveoli that impairs gas exchange "
            "and causes consolidation."
        ),
        aliases=["lung infection", "pneumonitis"],
    ),
    "diabetes mellitus": MedicalTerm(
        canonical_name="diabetes mellitus",
        category="Endocrinology / Metabolic Disorder",
        ipa="/ˌdaɪ.əˈbiː.tiːz məˈlaɪ.təs/",
        syllables="dy-uh-BEE-teez meh-LY-tus",
        definition=(
            "A chronic metabolic disease characterized by elevated blood glucose due to defects "
            "in insulin secretion, insulin action, or both."
        ),
        aliases=["diabetes", "type 2 diabetes", "type 1 diabetes", "dm"],
    ),
    "metoprolol": MedicalTerm(
        canonical_name="metoprolol",
        category="Beta-1 Selective Adrenergic Blocker",
        ipa="/mɛˈtoʊ.prə.lɒl/",
        syllables="meh-TOH-pruh-lol",
        definition=(
            "A cardioselective beta-blocker used to treat hypertension, angina, and tachycardia."
        ),
        aliases=["lopressor", "toprol xl"],
    ),
    "atorvastatin": MedicalTerm(
        canonical_name="atorvastatin",
        category="HMG-CoA Reductase Inhibitor (Statin)",
        ipa="/əˌtɔːr.vəˈstæt.ɪn/",
        syllables="uh-TOR-vuh-STAT-in",
        definition=(
            "A lipid-lowering medication that inhibits cholesterol biosynthesis in the liver."
        ),
        aliases=["lipitor"],
    ),
    "corticosteroid": MedicalTerm(
        canonical_name="corticosteroid",
        category="Endocrine Pharmacology / Steroid Hormone",
        ipa="/ˌkɔːr.tɪ.koʊˈstɪr.ɔɪd/",
        syllables="KOR-ti-koh-STEER-oyd",
        definition=(
            "A class of steroid hormones used clinically for powerful anti-inflammatory and "
            "immunosuppressive therapy."
        ),
        aliases=["steroid", "corticoids", "glucocorticoid"],
    ),
}

# Alias lookup index
ALIAS_MAP: dict[str, str] = {}
for name in MEDICAL_TERMS:
    ALIAS_MAP[name.lower()] = name
for name, term in MEDICAL_TERMS.items():
    for alias in term.aliases:
        if alias.lower() not in ALIAS_MAP:
            ALIAS_MAP[alias.lower()] = name


# Generic category phrases that must never be treated as specific clinical terms
GENERIC_CATEGORY_PHRASES: set[str] = {
    "clinical terms",
    "clinical term",
    "medical words",
    "medical word",
    "medical terms",
    "medical term",
    "medical vocabulary",
    "clinical vocabulary",
    "medical pronunciation",
    "clinical pronunciation",
    "terms",
    "words",
    "vocabulary",
    "pronunciation",
    "medicine",
    "clinical words",
    "clinical word",
}


def is_generic_category(query: str | None) -> bool:
    """Check if query refers to generic terminology categories rather than a specific term."""
    if not query:
        return False
    clean = query.lower().strip().rstrip("?.!")
    if clean in GENERIC_CATEGORY_PHRASES:
        return True
    clean_no_art = re.sub(r"^(the|a|an)\s+", "", clean).strip()
    return clean_no_art in GENERIC_CATEGORY_PHRASES


def resolve_term(query: str | None) -> MedicalTerm | None:
    """Look up a medical term by exact match or alias."""
    if not query:
        return None
    clean = query.lower().strip().rstrip("?.!")
    if is_generic_category(clean):
        return None

    # Check exact match
    if clean in ALIAS_MAP:
        return MEDICAL_TERMS[ALIAS_MAP[clean]]

    # Search for known term as a substring in query
    for candidate, canonical in ALIAS_MAP.items():
        pattern = rf"\b{re.escape(candidate)}\b"
        if re.search(pattern, clean):
            return MEDICAL_TERMS[canonical]

    return None


def extract_potential_term(text: str) -> str | None:
    """Extract candidate medical term from user questions like 'How do I pronounce X?'."""
    clean = text.strip().rstrip("?.!")

    # Pattern: How do I pronounce / say / break down X
    patterns = [
        (
            r"(?:how (?:do (?:you|i)|to) (?:pronounce|say)|pronunciation of|pronounce|say)\s+"
            r"([a-zA-Z0-9\- ]+)"
        ),
        r"(?:break down|syllables of|syllable breakdown for)\s+([a-zA-Z0-9\- ]+)",
        r"(?:what is|what does)\s+([a-zA-Z0-9\- ]+)(?:\s+mean)?",
    ]

    for pat in patterns:
        match = re.search(pat, clean, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # filter out trailing words like "please"
            candidate = re.sub(
                r"\b(please|correctly|slowly)\b", "", candidate, flags=re.IGNORECASE
            ).strip()
            if candidate and is_generic_category(candidate):
                return None
            if candidate:
                return candidate

    # If no leading phrase, check if the query is a direct word
    words = clean.split()
    if len(words) <= 3 and not is_generic_category(clean):
        return clean

    return None
