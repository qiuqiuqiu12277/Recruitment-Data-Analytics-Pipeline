from recruitment_pipeline.features import (
    ExperienceRange,
    SkillExtractor,
    extract_experience_range,
    extract_skills,
)


def test_extracts_english_experience_ranges_and_bounds():
    assert extract_experience_range("Requires 1-3 years of Python") == ExperienceRange(1, 3)
    assert extract_experience_range("At least 2 years of SQL") == ExperienceRange(2, None)
    assert extract_experience_range("Up to 4 years experience") == ExperienceRange(0, 4)
    assert extract_experience_range("5+ years building APIs") == ExperienceRange(5, None)


def test_extracts_chinese_digits_and_fresh_graduate_terms():
    assert extract_experience_range("要求三至五年数据分析经验") == ExperienceRange(3, 5)
    assert extract_experience_range("至少两年机器学习经验") == ExperienceRange(2, None)
    assert extract_experience_range("需要3年以上相关经验") == ExperienceRange(3, None)
    assert extract_experience_range("欢迎应届毕业生申请") == ExperienceRange(0, 0)


def test_skill_matching_respects_token_boundaries():
    skills = extract_skills("JavaScript developer supporting recruitment analytics")
    assert "JavaScript" in skills
    assert "Java" not in skills
    assert "R" not in skills


def test_skill_extractor_is_configurable_and_supports_chinese_aliases():
    extractor = SkillExtractor({"Data Governance": ["数据治理", "data governance"]})
    assert extractor.extract("负责数据治理与质量监控") == ["Data Governance"]
    assert extractor.extract("Build data governance controls") == ["Data Governance"]
