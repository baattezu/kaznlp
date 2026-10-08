from kaznlp.normalize import fix_mixed_script, is_mixed_script, normalize


def test_latin_letter_inside_cyrillic_word_is_fixed():
    # "Қaзақстан" with a Latin "a" in the second position
    assert normalize("Қaзақстан") == "Қазақстан"


def test_pure_latin_words_are_not_touched():
    assert normalize("Telegram арнасы") == "Telegram арнасы"


def test_kazakh_lookalike_letters_are_mapped():
    assert normalize("ҡызмет") == "қызмет"
    assert normalize("əке") == "әке"
    assert normalize("ɵнім") == "өнім"
    assert normalize("таӊ") == "таң"


def test_zero_width_and_whitespace_removed():
    assert normalize("  жаңа​​тариф \n\t өте  жақсы ") == "жаңатариф өте жақсы"


def test_nfc_composition():
    decomposed = "й"  # и + combining breve
    assert normalize(decomposed) == "й"


def test_lowercase_option():
    assert normalize("ҚАЗАҚСТАН", lowercase=True) == "қазақстан"


def test_is_mixed_script():
    assert is_mixed_script("Қaзақ")
    assert not is_mixed_script("Қазақ")
    assert not is_mixed_script("Kazakh")


def test_fix_mixed_script_keeps_punctuation():
    assert fix_mixed_script("Сәл\u0065м, әлем!") == "Сәлем, әлем!"


def test_normalize_is_idempotent():
    text = "Қaзақ  ҡызметі​ жақсы"
    once = normalize(text)
    assert normalize(once) == once
