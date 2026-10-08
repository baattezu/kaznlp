import pytest

from kaznlp.pii import count_pii, find_pii, is_valid_iin, scrub

VALID_IIN = "950512300457"


def test_valid_iin_checksum():
    assert is_valid_iin(VALID_IIN)
    assert is_valid_iin("880215401233")
    assert is_valid_iin("950512300107")  # needs the second set of weights


@pytest.mark.parametrize("value", ["950512300450", "12345", "abcdefghijkl", "9505123004571"])
def test_invalid_iin(value):
    assert not is_valid_iin(value)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Хабарласыңыз: +7 701 123 45 67", "Хабарласыңыз: <PHONE>"),
        ("номер 8(701)123-45-67 жазыңыз", "номер <PHONE> жазыңыз"),
        ("пошта: aidos.k@example.com", "пошта: <EMAIL>"),
        ("толығы https://example.kz/news/1 сілтемеде", "толығы <URL> сілтемеде"),
        ("карта 4400 4301 2345 6789 бұғатталды", "карта <CARD> бұғатталды"),
        (f"ЖСН {VALID_IIN} дұрыс па?", "ЖСН <IIN> дұрыс па?"),
        ("@aidos_k сізге жауап берді", "<USER> сізге жауап берді"),
    ],
)
def test_scrub_replaces_each_type(text, expected):
    assert scrub(text) == expected


def test_order_number_with_invalid_checksum_is_kept():
    assert scrub("тапсырыс нөмірі 950512300450") == "тапсырыс нөмірі 950512300450"
    assert scrub("тапсырыс нөмірі 950512300450", check_iin=False) == "тапсырыс нөмірі <IIN>"


def test_email_is_not_split_into_username():
    matches = find_pii("жазыңыз a.b@mail.kz")
    assert [m.kind for m in matches] == ["EMAIL"]


def test_text_without_pii_is_unchanged():
    text = "Банктің жаңа қолданбасы өте ыңғайлы."
    assert scrub(text) == text


def test_count_pii():
    counts = count_pii(["+7 701 123 45 67 және a@b.kz", "@user_name", "таза мәтін"])
    assert counts == {"PHONE": 1, "EMAIL": 1, "USER": 1}
