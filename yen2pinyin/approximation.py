"""Deterministic pronunciation approximation from the two project guides."""

import re


FINAL_MAP = {
  "aa": "a", "aai": "ai", "aau": "ao", "aam": "an", "aan": "an", "aang": "ang",
  "aap": "a", "aat": "a", "aak": "a", "ai": "ai", "au": "ou", "am": "en",
  "an": "en", "ang": "eng", "ap": "e", "at": "e", "ak": "e", "e": "ie",
  "ei": "ei", "eng": "eng", "ek": "ie", "i": "i", "iu": "iao", "im": "ian",
  "in": "ian", "ing": "ing", "ip": "ie", "it": "ie", "ik": "i", "o": "o",
  "oi": "ai", "ou": "ao", "on": "an", "ot": "e", "ok": "e", "ui": "ui",
  "un": "uan", "ung": "ong", "ut": "uo", "uk": "u", "oe": "ue", "oeng": "iang",
  "oek": "iao", "eoi": "ui", "eon": "un", "eot": "u", "yu": "u", "yun": "uan",
  "yut": "ue", "u": "u", "ong": "ong",
}

INITIALS = ("ng", "gw", "kw", "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "z", "c", "s", "j", "w")
TONE_MAP = {"1": "1", "2": "2", "3": "1", "4": "3", "5": "2", "6": "4"}

# These whole-syllable choices follow explicit example outputs in the preferred guide.
EXAMPLE_BASES = {
  "bong": "bang", "pong": "pang", "mong": "mang", "fong": "fang",
  "dong": "dang", "tong": "tang", "nong": "nang", "long": "lang",
  "gong": "gang", "hong": "hang", "sau": "shou", "sik": "shi",
  "gam": "jin", "san": "xin", "gap": "ji", "sat": "shi", "hak": "hei",
  "se": "xie", "geng": "jing", "sek": "shi", "sei": "si", "go": "ge",
  "gou": "gao", "fui": "hui", "fun": "huan", "hoe": "xue", "hoeng": "xiang",
  "goek": "jiao", "geoi": "ju", "seon": "xin", "ceot": "chu", "syu": "shu",
  "syun": "sun", "syut": "xue", "ngaa": "wa", "ngong": "ang",
  "gwong": "guang", "kwong": "kuang", "wong": "wang", "jip": "ye",
  "ng": "wu", "m": "en",
}


def approximate(syllable: str) -> tuple[str | None, str | None]:
  """Convert one standard Jyutping syllable to pinyin and a brief sound cue."""
  match = re.fullmatch(r"([a-z]+)([1-6])", syllable)
  if match is None:
    return None, None
  body, tone = match.groups()
  initial = ""
  final = body
  if body not in ("m", "ng"):
    for candidate in INITIALS:
      if body.startswith(candidate):
        initial = candidate
        final = body[len(candidate):]
        break
  if final not in FINAL_MAP and body not in EXAMPLE_BASES:
    return None, None

  # Prefer explicit guide examples; otherwise use its final table and initial rule.
  if body in EXAMPLE_BASES:
    base = EXAMPLE_BASES[body]
  else:
    onset = initial
    if initial in ("z", "c", "s") and (final.startswith("i") or final.startswith("yu")):
      onset = {"z": "j", "c": "q", "s": "x"}[initial]
    elif initial == "j":
      onset = "y"
    elif initial == "ng":
      onset = ""
    elif initial == "gw":
      onset = "gu"
    elif initial == "kw":
      onset = "ku"
    base = onset + FINAL_MAP[final]

  cues: list[str] = []
  if body == "m":
    cues.append("雙唇鼻音獨立成節")
  if initial == "h":
    cues.append("喉音起聲")
  if initial == "ng" or body == "ng":
    cues.append("舌根鼻音起聲")
  if initial in ("gw", "kw"):
    cues.append("聲母雙唇收圓")
  if initial in ("z", "c", "s"):
    cues.append("舌葉音起聲")
  if final.startswith(("oe", "eo", "yu")):
    cues.append("韻母雙唇收圓")
  if final.endswith("m") and body != "m":
    cues.append("韻尾雙唇閉合")
  if final.endswith(("p", "t", "k")):
    cues.append("短促中斷" + ("，雙唇閉合" if final.endswith("p") else ""))

  # The apostrophe remains attached to the pinyin base before the tone digit.
  stop = "'" if final.endswith(("p", "t", "k")) else ""
  return f"{base}{stop}{TONE_MAP[tone]}", "；".join(cues)
