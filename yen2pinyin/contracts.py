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
