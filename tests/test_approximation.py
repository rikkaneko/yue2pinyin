import pytest

from yue2pinyin.approximation import approximate


# Each expectation is the first sound entry in the proofread final table.
@pytest.mark.parametrize(
  ("final", "expected"),
  [
    ("aa", "a"), ("aai", "ai"), ("aau", "ao"), ("aam", "an"), ("aan", "an"),
    ("aang", "ang"), ("aap", "a'"), ("aat", "a'"), ("aak", "a'"),
    ("ai", "i"), ("au", "ou"), ("am", "en"), ("an", "en"), ("ang", "eng"),
    ("ap", "a'"), ("at", "a'"), ("ak", "e'"),
    ("o", "o"), ("oi", "ai"), ("ou", "ou"), ("on", "an"), ("ong", "ang"),
    ("ot", "o'"), ("ok", "o'"),
    ("e", "e"), ("ei", "ei"), ("eu", "iao"), ("em", "ian"), ("eng", "ing"),
    ("ep", "ie'"), ("ek", "ie'"),
    ("i", "i"), ("iu", "iu"), ("im", "an"), ("in", "in"), ("ing", "ing"),
    ("ip", "ie'"), ("it", "i'"), ("ik", "i'"),
    ("u", "u"), ("ui", "ui"), ("un", "un"), ("ung", "ong"), ("ut", "u'"),
    ("uk", "u'"), ("yu", "yu"), ("yun", "uan"), ("yut", "ue'"),
    ("oe", "e"), ("oeng", "iang"), ("oek", "iao'"), ("eoi", "u"),
    ("eon", "un"), ("eot", "u'"), ("m", "m"), ("ng", "wu"),
  ],
)
def test_proofread_final_defaults(final: str, expected: str) -> None:
  assert approximate(f"{final}1")[0] == f"{expected}1"


@pytest.mark.parametrize(
  ("final", "vowel", "stop_action"),
  [
    ("aap", "a", "雙唇緊閉"), ("aat", "a", "舌尖抵上齒齦"),
    ("aak", "a", "舌根抵軟腭"), ("ap", "a", "雙唇緊閉"),
    ("at", "a", "舌尖抵上齒齦"), ("ak", "e", "舌根抵軟腭"),
    ("ot", "o", "舌尖抵上齒齦"), ("ok", "o", "舌根抵軟腭"),
    ("ep", "ie", "雙唇緊閉"), ("ek", "ie", "舌根抵軟腭"),
    ("ip", "ie", "雙唇緊閉"), ("it", "i", "舌尖抵上齒齦"),
    ("ik", "i", "舌根抵軟腭"), ("ut", "u", "舌尖抵上齒齦"),
    ("uk", "u", "舌根抵軟腭"), ("yut", "ue", "舌尖抵上齒齦"),
    ("oek", "iao", "舌根抵軟腭"), ("eot", "u", "舌尖抵上齒齦"),
  ],
)
def test_checked_final_strips_coda_and_marks_cutoff(final: str, vowel: str, stop_action: str) -> None:
  for source_tone, target_tone in (("3", "1"), ("6", "4")):
    approximation, hint = approximate(f"{final}{source_tone}")
    assert approximation == f"{vowel}'{target_tone}"
    assert hint is not None
    assert "短促中斷" in hint
    assert stop_action in hint


@pytest.mark.parametrize(
  ("final", "expected"),
  [
    ("aai", "ai"), ("aau", "ao"), ("au", "ou"), ("oi", "ai"),
    ("ou", "ou"), ("ei", "ei"), ("eu", "iao"), ("iu", "iu"),
    ("ui", "ui"), ("eoi", "u"),
  ],
)
def test_diphthong_rule_defaults(final: str, expected: str) -> None:
  assert approximate(f"{final}2")[0] == f"{expected}2"


@pytest.mark.parametrize("final", ("aam", "am", "em", "im"))
def test_bilabial_nasal_final_keeps_closed_lip_hint(final: str) -> None:
  hint = approximate(f"{final}1")[1]
  assert hint is not None
  assert "韻尾雙唇緊閉，鼻腔出氣" in hint


@pytest.mark.parametrize(
  ("jyutpin", "expected"),
  [
    ("baa1", "ba1"), ("paa1", "pa1"), ("maa1", "ma1"),
    ("faa1", "fa1"), ("daa1", "da1"), ("taa1", "ta1"),
    ("naa1", "na1"), ("laa1", "la1"), ("kaa1", "ka1"),
    ("waa1", "wa1"), ("mai5", "mi2"), ("hou2", "hou2"),
    ("gwong2", "guang2"), ("kwong4", "kuang3"),
    ("si1", "xi1"), ("zi1", "ji1"), ("ci1", "qi1"),
    ("syu1", "xu1"), ("zyu1", "ju1"), ("cyu1", "qu1"),
    ("giu1", "jiu1"), ("gyu1", "ju1"), ("go1", "go1"), ("zaa1", "za1"),
    ("jaa1", "ya1"), ("jyu1", "yu1"), ("ngaa5", "a2"),
    ("m4", "m3"), ("ng5", "wu2"),
    ("goek3", "giao'1"), ("syut3", "xue'1"),
    ("maa3", "ma1"), ("maa4", "ma3"), ("maa5", "ma2"), ("maa6", "ma4"),
  ],
)
def test_initials_tones_and_literal_join(jyutpin: str, expected: str) -> None:
  assert approximate(jyutpin)[0] == expected


def test_ambiguous_lexical_examples_use_sound_defaults() -> None:
  assert approximate("si1")[0] == "xi1"
  assert approximate("bun6")[0] == "bun4"
  assert approximate("faan6")[0] == "fan4"


@pytest.mark.parametrize(
  ("syllable", "cues"),
  [
    ("si1", ("舌葉平鋪", "不捲舌")),
    ("haa1", ("聲門開啟", "喉部送氣")),
    ("ngaa5", ("舌根抵軟腭", "鼻腔出氣")),
    ("gwong2", ("聲母嘴唇收圓",)),
    ("mai5", ("縮小開口", "舌頭稍後收")),
    ("hoe1", ("韻母嘴唇收圓",)),
    ("saam1", ("韻尾雙唇緊閉", "鼻腔出氣")),
    ("m4", ("雙唇閉合", "獨立成節")),
    ("aap3", ("短促中斷", "雙唇緊閉不爆破")),
    ("aat3", ("短促中斷", "舌尖抵上齒齦不爆破")),
    ("aak3", ("短促中斷", "舌根抵軟腭不爆破")),
  ],
)
def test_action_hints(syllable: str, cues: tuple[str, ...]) -> None:
  hint = approximate(syllable)[1]
  assert hint is not None
  assert all(cue in hint for cue in cues)


@pytest.mark.parametrize("syllable", ("xyz1", "baa9", "baa", "BAA1", "baat0", "b1"))
def test_unknown_or_malformed_syllable(syllable: str) -> None:
  assert approximate(syllable) == (None, None)


def test_plain_syllable_has_empty_hint() -> None:
  assert approximate("baa1")[1] == ""
