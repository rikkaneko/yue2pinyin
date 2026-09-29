import pytest

from yen2pinyin.approximation import approximate


@pytest.mark.parametrize(
  ("jyutpin", "expected"),
  [
    ("baa1", "ba1"),
    ("si1", "xi1"),
    ("zi1", "ji1"),
    ("zaa1", "za1"),
    ("gaa2", "ga2"),
    ("maa3", "ma1"),
    ("maa4", "ma3"),
    ("maa5", "ma2"),
    ("maa6", "ma4"),
    ("sam1", "sen1"),
    ("saam1", "san1"),
    ("baat3", "ba'1"),
    ("syut3", "xue'1"),
    ("m4", "en3"),
    ("ng5", "wu2"),
    ("hoeng1", "xiang1"),
    ("fu2", "fu2"),
    ("zong1", "zong1"),
  ],
)
def test_guide_mappings(jyutpin: str, expected: str) -> None:
  assert approximate(jyutpin)[0] == expected


def test_special_sound_hints_and_unknown() -> None:
  assert "雙唇閉合" in approximate("saam1")[1]
  assert "短促中斷" in approximate("baat3")[1]
  assert "喉音" in approximate("haa1")[1]
  assert "獨立成節" in approximate("m4")[1]
  assert approximate("baa1")[1] == ""
  assert approximate("xyz1") == (None, None)
  assert approximate("baa9") == (None, None)
