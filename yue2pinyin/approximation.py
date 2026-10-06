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

# Standard Mandarin spellings used as the validity boundary. Entries are grouped
# by written onset so the nearest-sound choice can keep the onset when possible.
VALID_FINALS = {
  "": "a ai an ang ao e ei en eng er o ou yi ya yao ye you yan yang yin ying yong wu wa wai wan wang wei wen weng wo yu yue yuan yun",
  "b": "a ai an ang ao ei en eng i ian iao ie in ing o u",
  "p": "a ai an ang ao ei en eng i ian iao ie in ing o u",
  "m": "a ai an ang ao e ei en eng i ian iao ie in ing iu o ou u",
  "f": "a an ang ei en eng o ou u",
  "d": "a ai an ang ao e ei en eng i ia ian iao ie ing iu o ong ou u uan ui un uo",
  "t": "a ai an ang ao e eng i ian iao ie ing ong ou u uan ui un uo",
  "n": "a ai an ang ao e ei en eng i ian iang iao ie in ing iu ong ou u uan uo ü üe",
  "l": "a ai an ang ao e ei eng i ia ian iang iao ie in ing iu o ong ou u uan un uo ü üe",
  "g": "a ai an ang ao e ei en eng ong ou u ua uai uan uang ui un uo",
  "k": "a ai an ang ao e en eng ong ou u ua uai uan uang ui un uo",
  "h": "a ai an ang ao e ei en eng ong ou u ua uai uan uang ui un uo",
  "j": "i ia ian iang iao ie in ing iong iu u uan ue un",
  "q": "i ia ian iang iao ie in ing iong iu u uan ue un",
  "x": "i ia ian iang iao ie in ing iong iu u uan ue un",
  "z": "a ai an ang ao e ei en eng i ong ou u uan ui un uo",
  "c": "a ai an ang ao e en eng i ong ou u uan ui un uo",
  "s": "a ai an ang ao e en eng i ong ou u uan ui un uo",
  "y": "a an ang ao e i in ing ong ou u uan ue un",
  "w": "a ai an ang ei en eng o u",
}
VALID_SYLLABLES = {
  onset + final for onset, finals in VALID_FINALS.items() for final in finals.split()
}
SOUND_FINAL_CHOICES = {
  "a": ("a", "ia"), "ai": ("ai", "ei"), "an": ("an", "ian", "uan"),
  "ang": ("ang", "iang", "uang"), "ao": ("ao", "iao"), "e": ("e", "ie"),
  "ei": ("ei", "ie"), "en": ("en", "in", "un"), "eng": ("eng", "ing", "ong"),
  "i": ("i", "ie", "ei"), "ian": ("ian", "an"), "iang": ("iang", "ang"),
  "iao": ("iao", "ao"), "ie": ("ie", "e"), "in": ("in", "en"),
  "ing": ("ing", "eng"), "iu": ("iu", "iao", "ou"), "o": ("o", "uo"),
  "ong": ("ong", "eng"), "ou": ("ou", "ao"), "u": ("u", "ou"),
  "uan": ("uan", "an", "ian"), "ue": ("ue", "üe", "ie"),
  "ui": ("ui", "ei"), "un": ("un", "en", "in"), "yu": ("ü", "u", "i"),
  "m": ("u", "en"), "wu": ("u", "ou"),
}
SOUND_ONSET_CHOICES = {
  "": ("", "y", "w"), "b": ("b", "p", "m"), "p": ("p", "b", "f"),
  "m": ("m", "n", "w"), "f": ("f", "h", "p"), "d": ("d", "t", "j"),
  "t": ("t", "d", "q"), "n": ("n", "l", "m"), "l": ("l", "n", "r"),
  "g": ("g", "k", "j"), "k": ("k", "g", "q"), "h": ("h", "k", "x"),
  "j": ("j", "q", "x"), "q": ("q", "j", "x"), "x": ("x", "q", "s"),
  "z": ("z", "c", "j"), "c": ("c", "z", "q"), "s": ("s", "x", "c"),
  "y": ("y", "j", "w"), "w": ("w", "u", "y"),
}
ZERO_ONSET_FINALS = {
  "i": "yi", "ian": "yan", "iang": "yang", "iao": "yao", "ie": "ye",
  "in": "yin", "ing": "ying", "iu": "you", "u": "wu", "uan": "yuan",
  "ue": "yue", "ui": "wei", "un": "wen", "ong": "weng",
}


def approximate(syllable: str, allow_invalid_pinyin: bool = False) -> tuple[str | None, str | None]:
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

  if not allow_invalid_pinyin and base not in VALID_SYLLABLES:
    # Keep the sound-bearing final first; only change the onset if none of its
    # nearby final spellings form a Mandarin syllable with the original onset.
    if body == "m":
      base = "mu"
    elif not onset and mapped_final in ZERO_ONSET_FINALS:
      base = ZERO_ONSET_FINALS[mapped_final]
    else:
      choices = SOUND_FINAL_CHOICES[mapped_final]
      for candidate_onset in SOUND_ONSET_CHOICES.get(onset, (onset,)):
        for candidate_final in choices:
          candidate = candidate_onset + candidate_final
          if candidate in VALID_SYLLABLES:
            base = candidate
            break
        if base in VALID_SYLLABLES:
          break
      if base not in VALID_SYLLABLES and initial in ("gw", "kw"):
        # Rounded gw/kw spellings can introduce a medial u. Retain their
        # original velar sound when the full rounded spelling has no match.
        for candidate_onset in SOUND_ONSET_CHOICES.get(initial[0], ("g",)):
          for candidate_final in choices:
            candidate = candidate_onset + candidate_final
            if candidate in VALID_SYLLABLES:
              base = candidate
              break
          if base in VALID_SYLLABLES:
            break

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
