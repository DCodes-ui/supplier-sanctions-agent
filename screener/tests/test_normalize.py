from screener.matching.normalize import normalize_name


def test_legal_forms_drop():
    assert normalize_name("Example UAB") == "example"
    assert normalize_name("Firma SIA") == "firma"
    assert normalize_name("Ettevõte OÜ") == "ettevote"


def test_diacritics_and_cyrillic_and_punctuation():
    original = "Šiaulių"
    assert normalize_name(original) == "siauliu"
    assert original == "Šiaulių"
    assert normalize_name("Газпром") == "gazprom"
    assert normalize_name("Aero-Caribbean") == "aero caribbean"
