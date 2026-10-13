from essay_pipeline import classify


def test_programme_extraction():
    assert classify.find_programmes("[accepted: MSc in Computer Science]") == ["MSc in Computer Science"]
    assert classify.find_programmes("offered a place on the MPhil in Economics and I was thrilled") == [
        "MPhil in Economics"]
    assert classify.find_programmes("admitted to the Master of Public Policy at the University of X") == [
        "Master of Public Policy"]
    assert classify.find_programmes("I study in MA") == []


def test_institution_detection():
    assert classify.find_institution("University of Oxford [accepted: MSc]") == "University of Oxford"
    assert classify.find_institution("an offer from Cambridge for the MPhil") == "University of Cambridge"
    # Harvard's Cambridge, Massachusetts is not the University of Cambridge
    assert classify.find_institution("Harvard Kennedy School in Cambridge, MA") != "University of Cambridge"
    assert classify.find_institution("Oxford and Cambridge both admitted me") is None


def test_level():
    assert classify.classify_level("MSc in Computer Science") == "masters"
    assert classify.classify_level("DPhil in Engineering") == "doctoral"
    assert classify.classify_level("my UCAS personal statement") == "undergraduate"
    assert classify.classify_level("MPhil then PhD") == "ambiguous"
    assert classify.classify_level("Bachelor of Civil Law") == "ambiguous"
    assert classify.classify_level("a statement") == "ambiguous"


def test_acceptance_language_rejects_hedges():
    assert classify.has_acceptance_language("I was admitted to the MSc")
    assert not classify.has_acceptance_language("I was not admitted to the MSc")
    assert not classify.has_acceptance_language("I hope to be admitted to the MSc")
    assert not classify.has_acceptance_language("I wasn't accepted")


def test_category():
    assert classify.programme_category("University of Oxford", "MPP") == "Oxford master's"
    assert classify.programme_category("University of Exampleton", "Master of Public Administration") == "MPP-MPA"
    assert classify.programme_category("University of Exampleton", "MSc in Physics") is None


def test_template_flags_and_year():
    assert classify.template_flags("This is a sample statement we wrote") == ["sample", "we wrote"]
    assert classify.find_admission_year("admitted for 2019 entry to the MSc") == "2019"
    assert classify.find_admission_year("posted in March") is None
