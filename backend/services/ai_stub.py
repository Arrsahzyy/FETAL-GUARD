from random import uniform

from schemas.ai import SafeAIClassification


def classify_screening_stub() -> tuple[float, SafeAIClassification]:
    risk_score = uniform(0.0, 1.0)

    if risk_score < 0.34:
        classification = SafeAIClassification.within_expected_range
    elif risk_score < 0.67:
        classification = SafeAIClassification.watchful
    else:
        classification = SafeAIClassification.observation_needed

    return risk_score, classification
