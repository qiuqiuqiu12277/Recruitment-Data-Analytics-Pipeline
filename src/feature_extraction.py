import re

SKILLS = [
    "python", "sql", "pandas", "numpy",
    "machine learning", "deep learning",
    "pytorch", "java", "excel"
]

def extract_experience(text):
    text = str(text).lower()
    patterns = [r"(\d+)\s*years?", r"(\d+)\s*年以上"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    if "应届" in text or "fresh graduate" in text:
        return 0
    return None

def classify_experience(years):
    if years is None:
        return "unknown"
    if years == 0:
        return "entry"
    if years <= 2:
        return "junior"
    if years <= 5:
        return "mid"
    return "senior"

def extract_skills(text):
    text = str(text).lower()
    return [skill for skill in SKILLS if skill in text]

def extract_features(text):
    years = extract_experience(text)
    return {
        "years_required": years,
        "experience_level": classify_experience(years),
        "skills": extract_skills(text)
    }
