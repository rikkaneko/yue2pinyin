"""Deterministic sound approximation from the proofread Jyutping guides."""

import re


# Values are the proofread table's first sound choices. Checked finals hold the
# vowel left after stripping -p/-t/-k; diphthongs include aai→ai and aau→ao.
FINAL_MAP = {
  "aa": "a", "aai": "ai", "aau": "ao", "aam": "an", "aan": "an", "aang": "ang",
  "aap": "a", "aat": "a", "aak": "a", "ai": "i", "au": "ou", "am": "en",
  "an": "en", "ang": "eng", "ap": "a", "at": "a", "ak": "e", "o": "o",
  "oi": "ai", "ou": "ou", "on": "an", "ong": "ang", "ot": "o", "ok": "o",
  "e": "e", "ei": "ei", "eu": "iao", "em": "ian", "eng": "ing", "ep": "ie", "ek": "ie",
  "i": "i", "iu": "iu", "im": "an", "in": "in", "ing": "ing", "ip": "ie",
  "it": "i", "ik": "i", "u": "u", "ui": "ui", "un": "un", "ung": "ong",
  "ut": "u", "uk": "u", "yu": "yu", "yun": "uan", "yut": "ue", "oe": "e",
  "oeng": "iang", "oek": "iao", "eoi": "u", "eon": "un", "eot": "u",
  "m": "m", "ng": "wu",
}

INITIALS = ("ng", "gw", "kw", "b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h", "z", "c", "s", "j", "w")
TONE_MAP = {"1": "1", "2": "2", "3": "1", "4": "3", "5": "2", "6": "4"}


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
  if final not in FINAL_MAP:
    return None, None
  checked_coda = final[-1] if final[-1] in ("p", "t", "k") else ""

  # Map sounds without lexical examples: a Jyutping homophone has one output.
  onset = initial
  if initial in ("g", "z", "c", "s") and (final.startswith("i") or final.startswith("yu")):
    onset = {"g": "j", "z": "j", "c": "q", "s": "x"}[initial]
  elif initial == "j":
    onset = "y"
  elif initial == "ng":
    onset = ""
  elif initial == "gw":
    onset = "gu"
  elif initial == "kw":
    onset = "ku"
  mapped_final = FINAL_MAP[final]
  if final == "yu" and onset in ("j", "q", "x", "y"):
    mapped_final = "u"
  base = onset + mapped_final

  cues: list[str] = []
  if body == "m":
    cues.append("雙唇閉合，鼻音獨立成節")
  if initial == "h":
    cues.append("聲門開啟，喉部送氣")
  if initial == "ng" or body == "ng":
    cues.append("舌根抵軟腭，鼻腔出氣")
  if initial in ("gw", "kw"):
    cues.append("聲母嘴唇收圓")
  if initial in ("z", "c", "s"):
    cues.append("舌葉平鋪，不捲舌")
  if final in ("ai", "au", "am", "an", "ang", "ap", "at", "ak"):
    cues.append("縮小開口，舌頭稍後收")
  if final.startswith(("oe", "eo", "yu")):
    cues.append("韻母嘴唇收圓")
  if final.endswith("m") and body != "m":
    cues.append("韻尾雙唇緊閉，鼻腔出氣")
  if checked_coda == "p":
    cues.append("短促中斷，雙唇緊閉不爆破")
  elif checked_coda == "t":
    cues.append("短促中斷，舌尖抵上齒齦不爆破")
  elif checked_coda == "k":
    cues.append("短促中斷，舌根抵軟腭不爆破")

  # The mapped final has no stop consonant; mark its cutoff before the tone.
  stop = "'" if checked_coda else ""
  return f"{base}{stop}{TONE_MAP[tone]}", "；".join(cues)
