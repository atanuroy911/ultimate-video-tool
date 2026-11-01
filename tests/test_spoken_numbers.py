"""Numbers said in words reach the screen as said: "eighty four percent" is 84 %, never "4 %" under the word "Eighty" (video lab round 1)."""
from vt.planner.rules import _number_items
from vt.schema import Word


def _ws(text: str) -> list[Word]:
    return [Word(id=f"w{i}", text=t, start=i * 0.3, end=i * 0.3 + 0.25) for i, t in enumerate(text.split())]


def test_compound_numbers_percent_money_and_scale():
    got = lambda text: [(n["disp"], n["kind"]) for n in _number_items(_ws(text), "en")]   # noqa: E731
    assert got("Eighty four percent of that was clothing.") == [("84%", "percent")]
    assert got("Bangladesh exported forty seven billion dollars last year.") == [("$47 billion", "money")]
    assert got("clothing was seventy-eight percent, so") == [("78%", "percent")]
    assert got("it costs twenty dollars") == [("$20", "money")]
    assert got("under two percent.") == [("2%", "percent")]


def test_a_comma_keeps_two_numbers_apart():
    assert [n["disp"] for n in _number_items(_ws("we tried twenty, five failed"), "en")] == ["20", "5"]
