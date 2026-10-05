"""Optional browser regression against separate static and API servers."""

import json
import os
import subprocess
from urllib.parse import urljoin

import pytest
from pydantic import AnyHttpUrl, TypeAdapter


@pytest.mark.skipif(not os.environ.get("BROWSER_TEST_URL"), reason="requires a running browser-test server")
def test_frontend_interactions() -> None:
  base_url = str(TypeAdapter(AnyHttpUrl).validate_python(os.environ["BROWSER_TEST_URL"]))
  api_url = str(TypeAdapter(AnyHttpUrl).validate_python(
    os.environ.get("BROWSER_TEST_API_URL", "http://127.0.0.1:8000"),
  )).rstrip("/")
  session = ["agent-browser", "--session", "cantonese-flashcard-layout"]
  if "BROWSER_TEST_API_URL" in os.environ:
    # Override only the static config response when the local API uses a test port.
    subprocess.run([*session, "network", "route", "**/config.js", "--body", (
      f"window.CANTONESE_TUTOR_CONFIG = Object.freeze({{ apiBaseUrl: '{api_url}' }});"
    )], check=True, capture_output=True)

  for command in (
    ["open", base_url],
    ["eval", "document.title === '粵語發音轉換' && Boolean(window.jQuery) && Boolean(window.CANTONESE_TUTOR_CONFIG)"],
  ):
    result = subprocess.run([*session, *command], capture_output=True, text=True, check=True)
    if command[0] == "eval":
      assert json.loads(result.stdout) is True

  configured = subprocess.run([*session, "eval", "window.CANTONESE_TUTOR_CONFIG.apiBaseUrl"], capture_output=True, text=True, check=True)
  assert json.loads(configured.stdout).rstrip("/") == api_url
  assets = subprocess.run([*session, "eval", "['./style.css', './config.js', './app.js'].every(path => document.querySelector(`[href=\"${path}\"], [src=\"${path}\"]`) && new URL(path, location.href).origin === location.origin)"], capture_output=True, text=True, check=True)
  assert json.loads(assets.stdout) is True

  # A blank submission uses the randomly chosen placeholder, which must be one distinct example.
  examples = ["你好，今日天氣點呀？", "唔該，幾多錢？", "我唔係好明白。", "食咗飯未呀？", "唔該幫我埋單。", "檸檬茶少甜少冰，唔該。"]
  placeholder = subprocess.run([*session, "eval", "document.querySelector('#cantonese-input').placeholder"], capture_output=True, text=True, check=True)
  selected = json.loads(placeholder.stdout)
  assert selected in examples
  subprocess.run([*session, "eval", "document.querySelector('#analyze-button').click()"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "#pronunciation-result .word-card"], check=True, capture_output=True)
  fallback = subprocess.run([*session, "eval", "Array.from(document.querySelectorAll('#pronunciation-result .word-card .word-trigger, #pronunciation-result .word-card .hanzi')).map(node => node.textContent).join('')"], capture_output=True, text=True, check=True)
  assert json.loads(fallback.stdout) == selected

  subprocess.run([*session, "eval", "document.querySelector('#cantonese-input').value = '你好，👋'; window.jQuery('#cantonese-input').trigger('input'); document.querySelector('#analyze-button').click();"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "#pronunciation-result .word-card"], check=True, capture_output=True)
  rendered = subprocess.run([*session, "eval", "Array.from(document.querySelectorAll('#pronunciation-result .word-card .word-trigger, #pronunciation-result .word-card .hanzi')).map(node => node.textContent).join('')"], capture_output=True, text=True, check=True)
  assert json.loads(rendered.stdout) == "你好，👋"
  order = subprocess.run([*session, "eval", "document.querySelector('#pronunciation-result .word-card').children[0].classList.contains('approx')"], capture_output=True, text=True, check=True)
  assert json.loads(order.stdout) is True

  subprocess.run([*session, "eval", "document.querySelector('#cantonese-input').value = 'x'.repeat(2001); document.querySelector('#analyze-button').click();"], check=True, capture_output=True)
  invalid = subprocess.run([*session, "eval", "document.querySelector('#pronunciation-status').classList.contains('error')"], capture_output=True, text=True, check=True)
  assert json.loads(invalid.stdout) is True
  subprocess.run([*session, "eval", "document.querySelector('#cantonese-input').value = '你好，👋';"], check=True, capture_output=True)

  subprocess.run([*session, "eval", "window.__spoken = null; Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: { getVoices: () => [], cancel: () => {}, speak: utterance => { window.__spoken = { text: utterance.text, lang: utterance.lang }; } } }); window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } }; document.querySelector('#speak-input').click();"], check=True, capture_output=True)
  spoken = subprocess.run([*session, "eval", "window.__spoken"], capture_output=True, text=True, check=True)
  assert json.loads(spoken.stdout) == {"text": "你好，👋", "lang": "zh-HK"}
  subprocess.run([*session, "eval", "document.querySelector('#pronunciation-result .speak-word').click()"], check=True, capture_output=True)
  word_spoken = subprocess.run([*session, "eval", "({spoken: window.__spoken, expected: document.querySelector('#pronunciation-result .word-card .word-trigger, #pronunciation-result .word-card .hanzi').textContent})"], capture_output=True, text=True, check=True)
  assert json.loads(word_spoken.stdout)["spoken"] == {"text": json.loads(word_spoken.stdout)["expected"], "lang": "zh-HK"}

  # Latin readings and hints use whole-word API text units; unknown text remains visible.
  unknown_text = "你好 龘龘world HELLO，👋"
  unknown_units = ["你", "好", " ", "龘", "龘", "world", " ", "HELLO", "，", "👋"]
  unknown = {
    "text": unknown_units,
    "words": ["你好", " ", "龘", "龘", "world", " ", "HELLO", "，", "👋"],
    "jyutpin": ["nei5", "hou2", None, None, None, None, None, ["haa1", "lou3"], None, None],
    "approx_pinyin": ["nei2", "hao2", None, None, None, None, None, ["ha1", "lao3"], None, None],
    "hint": [None, None, None, None, None, None, None, ["first sound cue", "second sound cue"], None, None],
    "jyutpin_words": ["nei5 hou2", None, None, None, None, None, ["haa1", "lou3"], None, None],
    "approx_pinyin_words": ["nei2 hao2", None, None, None, None, None, ["ha1", "lao3"], None, None],
  }
  subprocess.run([*session, "eval", (
    "window.__originalFetch = window.fetch; "
    "window.fetch = async (input, options) => new URL(input).pathname === '/approx_pinyin' "
    f"? new Response(JSON.stringify({json.dumps(unknown, ensure_ascii=False)}), {{ status: 200, headers: {{ 'Content-Type': 'application/json' }} }}) "
    ": window.__originalFetch(input, options);"
  )], check=True, capture_output=True)
  subprocess.run([*session, "eval", f"document.querySelector('#cantonese-input').value = {json.dumps(unknown_text, ensure_ascii=False)}; document.querySelector('#analyze-button').click();"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "#pronunciation-result .word-card"], check=True, capture_output=True)
  unknown_display = subprocess.run([*session, "eval", "({groups: Array.from(document.querySelectorAll('#pronunciation-result .word-card .word-trigger, #pronunciation-result .word-card .hanzi')).map(node => node.textContent), controls: Array.from(document.querySelectorAll('#pronunciation-result .word-card')).map(card => [Boolean(card.querySelector('.approx')), Boolean(card.querySelector('.jyutpin')), Boolean(card.querySelector('.speak-word'))])})"], capture_output=True, text=True, check=True)
  assert json.loads(unknown_display.stdout) == {
    "groups": ["你好", " ", "龘龘", "world", " ", "HELLO", "，", "👋"],
    "controls": [[True, True, True], *([[False, False, False]] * 4), [True, True, True], *([[False, False, False]] * 2)],
  }
  latin_reading = subprocess.run([*session, "eval", "(() => { const card = Array.from(document.querySelectorAll('#pronunciation-result .word-card')).find(node => node.querySelector('.word-trigger')?.textContent === 'HELLO'); return {word: card?.querySelector('.word-trigger')?.textContent, approx: card?.querySelector('.approx')?.textContent, jyutpin: card?.querySelector('.jyutpin')?.textContent, hints: Array.from(card?.querySelectorAll('.word-hint-content p') ?? []).map(node => ({label: node.querySelector('strong')?.textContent, cue: node.textContent}))}; })()"], capture_output=True, text=True, check=True)
  assert json.loads(latin_reading.stdout) == {"word": "HELLO", "approx": "ha1 lao3", "jyutpin": "haa1 lou3", "hints": [{"label": "ha1", "cue": "ha1first sound cue"}, {"label": "lao3", "cue": "lao3second sound cue"}]}
  subprocess.run([*session, "eval", "window.fetch = window.__originalFetch; delete window.__originalFetch;"], check=True, capture_output=True)

  subprocess.run([*session, "eval", "document.querySelector('#cantonese-input').value = '三甲'; document.querySelector('#analyze-button').click();"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "#pronunciation-result .word-trigger"], check=True, capture_output=True)
  aligned = subprocess.run([*session, "eval", "({lines: Array.from(document.querySelector('#pronunciation-result .word-card').children).filter(node => !node.hidden && !node.classList.contains('speak-word')).map(node => node.textContent), hints: Array.from(document.querySelectorAll('#pronunciation-result .word-hint-content p')).map(node => node.querySelector('strong').textContent)})"], capture_output=True, text=True, check=True)
  assert json.loads(aligned.stdout) == {"lines": ["san1 ga'1", "saam1 gaap3", "三甲"], "hints": ["三", "甲"]}
  hint_cue = subprocess.run([*session, "eval", "({underline: getComputedStyle(document.querySelector('#pronunciation-result .word-label')).textDecorationLine, icon: getComputedStyle(document.querySelector('#pronunciation-result .word-trigger'), '::after').content, inline: getComputedStyle(document.querySelector('#pronunciation-result .word-trigger'), '::after').display === 'inline-block'})"], capture_output=True, text=True, check=True)
  assert json.loads(hint_cue.stdout) == {"underline": "underline", "icon": '"ⓘ"', "inline": True}
  subprocess.run([*session, "eval", "document.querySelector('#pronunciation-result .word-trigger').click()"], check=True, capture_output=True)
  clicked_hint = subprocess.run([*session, "eval", "!document.querySelector('#active-hint-box').hidden && document.querySelector('#active-hint-box').textContent.includes('三') && document.querySelector('#active-hint-box').textContent.includes('甲')"], capture_output=True, text=True, check=True)
  assert json.loads(clicked_hint.stdout) is True
  subprocess.run([*session, "eval", "document.querySelector('#pronunciation-result .word-trigger').dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch', clientX: 10, clientY: 10 }))"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "650"], check=True, capture_output=True)
  long_press = subprocess.run([*session, "eval", "document.querySelector('#hint-dialog').open && document.querySelector('#hint-dialog-title').textContent === '三甲' && document.querySelectorAll('#hint-dialog-content p').length === 2"], capture_output=True, text=True, check=True)
  assert json.loads(long_press.stdout) is True
  subprocess.run([*session, "eval", "document.querySelector('#hint-dialog-close').click(); document.querySelector('#pronunciation-result .word-trigger').dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'F10', shiftKey: true }))"], check=True, capture_output=True)
  keyboard_popup = subprocess.run([*session, "eval", "document.querySelector('#hint-dialog').open"], capture_output=True, text=True, check=True)
  assert json.loads(keyboard_popup.stdout) is True
  subprocess.run([*session, "eval", "document.querySelector('#hint-dialog-close').click()"], check=True, capture_output=True)

  # Fix the flashcard source so language labels and omitted source readings are deterministic.
  fixture = {
    "headwords": [{"word": "三甲", "readings": ["RAW-HEADWORD-READING"]}],
    "pos": [], "sim": [], "label": [], "ant": [], "img": [], "ref": [], "reviewed": 1,
    "definitions": [{
      "explanation": [{"yue": "粵語解釋", "eng": "English definition", "other": "other definition"}],
      "eg": [{"yue": "三甲，唔該。", "eng": "Please.", "jyutpin": "RAW-EXAMPLE-READING"}],
    }],
  }
  subprocess.run([*session, "eval", (
    "window.__originalFetch = window.fetch; "
    "window.fetch = async (input, options) => new URL(input).pathname === '/word' "
    f"? new Response(JSON.stringify({json.dumps(fixture, ensure_ascii=False)}), {{ status: 200, headers: {{ 'Content-Type': 'application/json' }} }}) "
    ": window.__originalFetch(input, options);"
  )], check=True, capture_output=True)
  subprocess.run([*session, "eval", "document.querySelector('[data-view=flashcard]').click()"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "#flashcard-result article.card"], check=True, capture_output=True)
  flashcard = subprocess.run([*session, "eval", "Boolean(document.querySelector('#flashcard-result h2')?.textContent && document.querySelector('#flashcard-result .example') && document.querySelector('#flashcard-result .reading-block .word-card'))"], capture_output=True, text=True, check=True)
  assert json.loads(flashcard.stdout) is True
  language_display = subprocess.run([*session, "eval", "({headings: Array.from(document.querySelectorAll('#flashcard-result .sense h5')).map(node => node.textContent), body: document.querySelector('#flashcard-result').innerText, headword: Array.from(document.querySelectorAll('#flashcard-result .field-list dt')).find(node => node.textContent === '詞形')?.nextElementSibling.textContent, gap: document.querySelector('#flashcard-result .example .reading-block').getBoundingClientRect().top - document.querySelector('#flashcard-result .example button').getBoundingClientRect().bottom})"], capture_output=True, text=True, check=True)
  language = json.loads(language_display.stdout)
  assert language["headings"] == ["粵語", "英語", "粵語", "英語"]
  assert all(text in language["body"] for text in ("粵語解釋", "English definition", "other definition", "Please."))
  assert "RAW-HEADWORD-READING" not in language["body"]
  assert "RAW-EXAMPLE-READING" not in language["body"]
  assert language["headword"] == "三甲"
  assert language["gap"] > 0
  alignment = subprocess.run([*session, "eval", "({rows: Array.from(document.querySelectorAll('#flashcard-result .example .word-card')).filter(card => card.querySelector('.jyutpin')).slice(0, 2).map(card => Array.from(card.children).filter(node => !node.hidden).map(node => Math.round(node.getBoundingClientRect().top))), allSingleLine: getComputedStyle(document.querySelector('#flashcard-result .word-grid')).flexWrap === 'nowrap'})"], capture_output=True, text=True, check=True)
  layout = json.loads(alignment.stdout)
  assert len(layout["rows"]) == 2
  assert layout["rows"][0] == layout["rows"][1]
  assert layout["allSingleLine"] is True
  subprocess.run([*session, "eval", "window.fetch = window.__originalFetch; delete window.__originalFetch;"], check=True, capture_output=True)

  subprocess.run([*session, "set", "viewport", "390", "844"], check=True, capture_output=True)
  subprocess.run([*session, "eval", "document.querySelector('[data-view=pronunciation]').click(); document.querySelector('#cantonese-input').value = '三甲'.repeat(40); document.querySelector('#analyze-button').click();"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "#pronunciation-result .word-card"], check=True, capture_output=True)
  mobile = subprocess.run([*session, "eval", "({horizontal: getComputedStyle(document.querySelector('#pronunciation-result .word-grid')).overflowX === 'auto', scrolling: document.querySelector('#pronunciation-result .word-grid').scrollWidth > document.querySelector('#pronunciation-result .word-grid').clientWidth, noVerticalScroll: document.querySelector('#pronunciation-result .word-grid').scrollHeight === document.querySelector('#pronunciation-result .word-grid').clientHeight, noPageOverflow: document.documentElement.scrollWidth <= innerWidth})"], capture_output=True, text=True, check=True)
  assert json.loads(mobile.stdout) == {"horizontal": True, "scrolling": True, "noVerticalScroll": True, "noPageOverflow": True}
  subprocess.run([*session, "eval", "document.querySelector('#sidebar-toggle').click()"], check=True, capture_output=True)
  opened = subprocess.run([*session, "eval", "document.querySelector('#sidebar-toggle').getAttribute('aria-expanded')"], capture_output=True, text=True, check=True)
  assert json.loads(opened.stdout) == "true"
  subprocess.run([*session, "eval", "document.querySelector('[data-view=pronunciation]').click()"], check=True, capture_output=True)
  closed = subprocess.run([*session, "eval", "document.querySelector('#sidebar-toggle').getAttribute('aria-expanded')"], capture_output=True, text=True, check=True)
  assert json.loads(closed.stdout) == "false"

  subprocess.run([*session, "network", "route", "**/word", "--abort"], check=True, capture_output=True)
  subprocess.run([*session, "eval", "document.querySelector('[data-view=flashcard]').click(); document.querySelector('#next-word').click();"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "--text", "暫時無法載入詞語卡"], check=True, capture_output=True)
  error = subprocess.run([*session, "eval", "document.querySelector('#flashcard-status').classList.contains('error')"], capture_output=True, text=True, check=True)
  assert json.loads(error.stdout) is True
  subprocess.run([*session, "network", "unroute"], check=True, capture_output=True)

  subprocess.run([*session, "network", "route", "**/approx_pinyin", "--abort"], check=True, capture_output=True)
  subprocess.run([*session, "eval", "document.querySelector('[data-view=pronunciation]').click(); document.querySelector('#analyze-button').click();"], check=True, capture_output=True)
  subprocess.run([*session, "wait", "--text", "暫時無法分析發音"], check=True, capture_output=True)
  pronunciation_error = subprocess.run([*session, "eval", "document.querySelector('#pronunciation-status').classList.contains('error')"], capture_output=True, text=True, check=True)
  assert json.loads(pronunciation_error.stdout) is True
  subprocess.run([*session, "network", "unroute"], check=True, capture_output=True)

  # Both local path forms must keep each API endpoint under the configured path.
  for path in ("/api", "./api"):
    subprocess.run([*session, "network", "route", "**/config.js", "--body", (
      f"window.CANTONESE_TUTOR_CONFIG = {{ apiBaseUrl: '{path}' }};"
    )], check=True, capture_output=True)
    subprocess.run([*session, "open", base_url], check=True, capture_output=True)
    enabled = subprocess.run([*session, "eval", "!document.querySelector('#analyze-button').disabled && !document.querySelector('#next-word').disabled"], capture_output=True, text=True, check=True)
    assert json.loads(enabled.stdout) is True
    subprocess.run([*session, "eval", (
      "window.__requestedUrls = []; window.fetch = async (url) => { window.__requestedUrls.push(String(url)); "
      "return new Response('', { status: 503 }); }; "
      "document.querySelector('#cantonese-input').value = '你好'; "
      "document.querySelector('#analyze-button').click(); "
      "document.querySelector('[data-view=flashcard]').click();"
    )], check=True, capture_output=True)
    requested = subprocess.run([*session, "eval", "window.__requestedUrls"], capture_output=True, text=True, check=True)
    assert json.loads(requested.stdout) == [
      urljoin(base_url, f"{path}/approx_pinyin"),
      urljoin(base_url, f"{path}/word"),
    ]
    subprocess.run([*session, "network", "unroute"], check=True, capture_output=True)

  # Invalid schemes and URL components must leave both API actions disabled.
  for value in ("ftp://invalid.example", "//invalid.example/api", "\\\\invalid.example/api",
                "https:invalid.example/api", "https://user:pass@invalid.example/api",
                "/api?token=abc", "/api#fragment", "http://[", ""):
    subprocess.run([*session, "network", "route", "**/config.js", "--body", (
      f"window.CANTONESE_TUTOR_CONFIG = {{ apiBaseUrl: {json.dumps(value)} }};"
    )], check=True, capture_output=True)
    subprocess.run([*session, "open", base_url], check=True, capture_output=True)
    subprocess.run([*session, "wait", "--text", "API 網址設定無效"], check=True, capture_output=True)
    invalid_config = subprocess.run([*session, "eval", "document.querySelector('#analyze-button').disabled && document.querySelector('#next-word').disabled"], capture_output=True, text=True, check=True)
    assert json.loads(invalid_config.stdout) is True
    subprocess.run([*session, "network", "unroute"], check=True, capture_output=True)
  subprocess.run([*session, "close"], check=True, capture_output=True)
