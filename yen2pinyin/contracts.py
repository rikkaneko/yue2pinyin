"""Public request and response contracts."""

from pydantic import BaseModel, ConfigDict, StrictStr


class TextRequest(BaseModel):
  model_config = ConfigDict(extra="forbid")

  text: StrictStr


class JyutpinResponse(BaseModel):
  text: list[str]
  jyutpin: list[str | None]
  words: list[str]
  jyutpin_words: list[str | None]


class ApproxPinyinResponse(JyutpinResponse):
  approx_pinyin: list[str | None]
  approx_pinyin_words: list[str | None]
  hint: list[str | None]


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
