"""Public request and response contracts."""

from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr


JyutpinValue: TypeAlias = str | list[str] | None
ApproximationValue: TypeAlias = str | list[str | None] | None


class TextRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  text: StrictStr


class ApproxTextRequest(TextRequest):
  allow_invalid_pinyin: StrictBool = False


class JyutpinRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  jyutpin: list[StrictStr | list[StrictStr] | None]


class ApproxJyutpinRequest(JyutpinRequest):
  allow_invalid_pinyin: StrictBool = False


class JyutpinResponse(BaseModel):
  text: list[str]
  jyutpin: list[JyutpinValue]
  words: list[str]
  jyutpin_words: list[JyutpinValue]


class ApproxPinyinResponse(JyutpinResponse):
  approx_pinyin: list[ApproximationValue]
  approx_pinyin_words: list[ApproximationValue]
  hint: list[ApproximationValue]


class DirectApproxPinyinResponse(BaseModel):
  jyutpin: list[JyutpinValue]
  approx_pinyin: list[ApproximationValue]
  hint: list[ApproximationValue]


class Headword(BaseModel):
  model_config = ConfigDict(extra="allow")

  word: str
  readings: list[str]


class Example(BaseModel):
  model_config = ConfigDict(extra="allow")

  jyutpin: str | None = None
  yue: str | None = None


class Definition(BaseModel):
  model_config = ConfigDict(extra="allow")

  explanation: list[dict[str, str]]
  eg: list[Example]


class WordEntry(BaseModel):
  model_config = ConfigDict(extra="allow")

  headwords: list[Headword]
  pos: list[str]
  sim: list[str]
  label: list[str]
  ant: list[str]
  img: list[str]
  ref: list[str]
  definitions: list[Definition]
  reviewed: int


class WordDocument(BaseModel):
  metadata: dict[str, str | int | None]
  entries: list[WordEntry]
