import { z } from 'https://cdn.jsdelivr.net/npm/zod@4.4.3/+esm';

const $ = window.jQuery;
const configSchema = z.object({ apiBaseUrl: z.string().trim().min(1) });
const parsedConfig = configSchema.safeParse(window.CANTONESE_TUTOR_CONFIG);
let apiBaseUrl = null;
const configuredUrl = parsedConfig.success ? parsedConfig.data.apiBaseUrl : '';
const fullUrl = /^https?:\/\//i.test(configuredUrl);
const relativePath = !/^[a-z][a-z\d+.-]*:/i.test(configuredUrl) &&
  !configuredUrl.startsWith('//') && !configuredUrl.startsWith('\\');
if (parsedConfig.success && (fullUrl || relativePath)) {
  try {
    // Resolve local API paths from the page while keeping endpoint names under the configured base path.
    const candidate = new URL(configuredUrl, window.location.href);
    if (['http:', 'https:'].includes(candidate.protocol) && !candidate.username && !candidate.password &&
        !candidate.search && !candidate.hash && (fullUrl || candidate.origin === window.location.origin)) {
      apiBaseUrl = new URL(candidate.href.endsWith('/') ? candidate.href : `${candidate.href}/`);
    }
  } catch {
    // Malformed configuration leaves API actions disabled below.
  }
}

const textSchema = z.object({ text: z.string().trim().min(1).max(2000) });
const exampleSentences = [
  '你好，今日天氣點呀？',
  '唔該，幾多錢？',
  '我唔係好明白。',
  '食咗飯未呀？',
  '唔該幫我埋單。',
  '檸檬茶少甜少冰，唔該。',
];
const jyutpinReadingSchema = z.union([z.string(), z.array(z.string())]).nullable();
const approximationReadingSchema = z.union([z.string(), z.array(z.string().nullable())]).nullable();
const approximationSchema = z.object({
  text: z.array(z.string()),
  words: z.array(z.string()),
  jyutpin: z.array(jyutpinReadingSchema),
  jyutpin_words: z.array(jyutpinReadingSchema),
  approx_pinyin: z.array(approximationReadingSchema),
  approx_pinyin_words: z.array(approximationReadingSchema),
  hint: z.array(approximationReadingSchema),
}).refine((value) =>
  value.text.length === value.jyutpin.length &&
  value.text.length === value.approx_pinyin.length &&
  value.text.length === value.hint.length &&
  value.words.length === value.jyutpin_words.length &&
  value.words.length === value.approx_pinyin_words.length &&
  value.text.every((_, index) => {
    const jyutpin = value.jyutpin[index];
    const approx = value.approx_pinyin[index];
    const hint = value.hint[index];
    return Array.isArray(jyutpin)
      ? Array.isArray(approx) && Array.isArray(hint) && jyutpin.length === approx.length && jyutpin.length === hint.length
      : !Array.isArray(approx) && !Array.isArray(hint);
  }) &&
  value.words.every((_, index) => {
    const jyutpin = value.jyutpin_words[index];
    const approx = value.approx_pinyin_words[index];
    return Array.isArray(jyutpin)
      ? Array.isArray(approx) && jyutpin.length === approx.length
      : !Array.isArray(approx);
  }) &&
  value.words.join('') === value.text.join(''),
);
const wordSchema = z.object({
  headwords: z.array(z.object({ word: z.string(), readings: z.array(z.string()) }).passthrough()),
  pos: z.array(z.string()),
  sim: z.array(z.string()),
  label: z.array(z.string()),
  ant: z.array(z.string()),
  img: z.array(z.string()),
  ref: z.array(z.string()),
  definitions: z.array(z.object({
    explanation: z.array(z.record(z.string(), z.string())),
    eg: z.array(z.object({ jyutpin: z.string().nullable().optional(), yue: z.string().optional() }).passthrough()),
  }).passthrough()),
  reviewed: z.number().int(),
}).passthrough();

// The same grouped rendering is used for free text, a headword, and each example.
function renderPronunciation(result) {
  const grid = $('<div class="word-grid d-flex flex-nowrap align-items-start gap-2 border rounded-3 p-3" tabindex="0" aria-label="發音分析字詞"></div>');
  const displayGroups = [];
  let offset = 0;
  result.words.forEach((word, index) => {
    const hints = [];
    let remaining = word;
    // A Latin word is one API text unit, while Cantonese words contain character units.
    while (remaining) {
      const unit = result.text[offset];
      if (!unit || !remaining.startsWith(unit)) {
        throw new Error('Pronunciation text units do not align with words');
      }
      const unitHint = result.hint[offset];
      const unitApprox = result.approx_pinyin[offset];
      const latinUnit = /^[\p{Script=Latin}\p{M}\p{N}]+$/u.test(unit);
      if (Array.isArray(unitHint)) {
        unitHint.forEach((hint, syllableIndex) => {
          if (hint) {
            const approximation = Array.isArray(unitApprox) ? unitApprox[syllableIndex] : unitApprox;
            hints.push({ character: latinUnit ? approximation || unit : unit, text: hint });
          }
        });
      } else if (unitHint) {
        const approximation = Array.isArray(unitApprox) ? unitApprox[0] : unitApprox;
        hints.push({ character: latinUnit ? approximation || unit : unit, text: unitHint });
      }
      remaining = remaining.slice(unit.length);
      offset += 1;
    }
    const jyutpin = result.jyutpin_words[index];
    const mergeable = !(Array.isArray(jyutpin) ? jyutpin.some(Boolean) : jyutpin?.trim()) &&
      /^[\p{L}\p{N}\p{M}]+$/u.test(word);
    const latin = /^[\p{Script=Latin}\p{M}\p{N}]+$/u.test(word);
    const previous = displayGroups.at(-1);
    if (mergeable && previous?.mergeable && previous.latin === latin) {
      previous.word += word;
      previous.hints.push(...hints);
    } else {
      displayGroups.push({ word, jyutpin, approx: result.approx_pinyin_words[index], hints, mergeable, latin });
    }
  });

  displayGroups.forEach(({ word, jyutpin, approx, hints }) => {
    const card = $('<div class="word-card position-relative text-center px-1"></div>');
    const displayedJyutpin = Array.isArray(jyutpin) ? jyutpin.filter(Boolean).join(' ') : jyutpin;
    const displayedApprox = Array.isArray(approx) ? approx.filter(Boolean).join(' ') : approx;
    if (displayedJyutpin?.trim()) {
      if (displayedApprox?.trim()) {
        card.append($('<span class="approx small text-primary fw-semibold"></span>').text(displayedApprox));
      }
      card.append($('<span class="jyutpin small text-body-secondary"></span>').text(displayedJyutpin));
    }
    if (hints.length) {
      const trigger = $('<button class="word-trigger btn btn-link text-body fw-semibold p-0" type="button" aria-expanded="false" aria-controls="active-hint-box" aria-keyshortcuts="Shift+F10"></button>')
        .attr('aria-label', `${word}，顯示發音提示`)
        .append($('<span class="word-label"></span>').text(word));
      const hintBox = $('<div class="word-hint-content" hidden></div>');
      hints.forEach(({ character, text: hint }) => {
        hintBox.append($('<p class="small mb-1"></p>').append(
          $('<strong class="me-2"></strong>').text(character), document.createTextNode(hint),
        ));
      });
      card.append(trigger, hintBox);
    } else {
      card.append($('<span class="hanzi fw-semibold"></span>').text(word));
    }
    if (displayedJyutpin?.trim() && word.trim()) {
      card.append($('<button class="btn btn-sm btn-link speak-word p-0" type="button">播放</button>')
        .attr('data-speak', word).attr('aria-label', `播放 ${word}`));
    }
    grid.append(card);
  });
  return grid;
}

// Validate each pronunciation response before using its parallel arrays in the UI.
async function requestApproximation(text) {
  const payload = textSchema.parse({ text });
  const response = await fetch(new URL('approx_pinyin', apiBaseUrl), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Pronunciation request failed: ${response.status}`);
  }
  return approximationSchema.parse(await response.json());
}

$(function () {
  let flashcardLoaded = false;
  const example = exampleSentences[Math.floor(Math.random() * exampleSentences.length)];
  $('#cantonese-input').attr('placeholder', example);
  let pressTimer = null;
  let pressedTrigger = null;
  let pressStartX = 0;
  let pressStartY = 0;
  if (!apiBaseUrl) {
    $('#pronunciation-status, #flashcard-status').addClass('error')
      .text('API 網址設定無效，請檢查 config.js。');
    $('#analyze-button, #next-word').prop('disabled', true);
  }

  $('[data-view]').on('click', function () {
    const view = $(this).attr('data-view');
    $('[data-view]').removeClass('active').removeAttr('aria-current');
    $(this).addClass('active').attr('aria-current', 'page');
    $('#pronunciation-view').prop('hidden', view !== 'pronunciation');
    $('#flashcard-view').prop('hidden', view !== 'flashcard');
    $('#sidebar').removeClass('is-open');
    $('#sidebar-toggle').attr('aria-expanded', 'false');
    if (view === 'flashcard' && !flashcardLoaded && apiBaseUrl) {
      flashcardLoaded = true;
      $('#next-word').trigger('click');
    }
  });

  $('#sidebar-toggle').on('click', function () {
    const opened = $('#sidebar').toggleClass('is-open').hasClass('is-open');
    $(this).attr('aria-expanded', String(opened));
  });

  $('#cantonese-input').on('input', function () {
    $('#speak-input').prop('disabled', !$(this).val().trim());
  });

  $('#analyze-button').on('click', async function () {
    const status = $('#pronunciation-status').removeClass('error');
    const entered = String($('#cantonese-input').val());
    const text = entered.trim() ? entered : example;
    if (!textSchema.safeParse({ text }).success) {
      status.addClass('error').text('請輸入 1 至 2000 個字元嘅廣東話文字。');
      return;
    }
    $(this).prop('disabled', true);
    status.text('正在分析發音…');
    $('#pronunciation-result').empty();
    try {
      const result = await requestApproximation(text);
      $('#pronunciation-result').append($('<h2 class="h5 fw-bold mb-3">發音分析</h2>'), renderPronunciation(result));
      status.text('');
    } catch (error) {
      status.addClass('error').text('暫時無法分析發音，請稍後再試。');
    } finally {
      $(this).prop('disabled', false);
    }
  });

  $('#next-word').on('click', async function () {
    const status = $('#flashcard-status').removeClass('error').text('正在抽取詞語卡…');
    const result = $('#flashcard-result').empty();
    $(this).prop('disabled', true);
    try {
      const response = await fetch(new URL('word', apiBaseUrl));
      if (!response.ok) {
        throw new Error(`Flashcard request failed: ${response.status}`);
      }
      const entry = wordSchema.parse(await response.json());
      const primary = entry.headwords[0]?.word ?? '';
      const card = $('<article class="card shadow-sm"><div class="card-body p-4"></div></article>');
      const body = card.find('.card-body');
      const heading = $('<div class="flashcard-head d-flex flex-wrap justify-content-between align-items-start gap-3 border-bottom pb-3"></div>');
      heading.append($('<div></div>').append(
        $('<p class="small fw-bold text-primary mb-2">CANTONESE FLASHCARD</p>'),
        $('<h2 class="display-6 fw-bold mb-0"></h2>').text(primary || '未命名詞條'),
      ));
      if (primary.trim()) {
        heading.append($('<button class="btn btn-outline-primary" type="button">播放詞語</button>')
          .attr('data-speak', primary));
      }
      body.append(heading);

      const fields = $('<section class="border-top pt-3 mt-3"></section>');
      fields.append($('<h3 class="h6 fw-bold">詞條資料</h3>'));
      const list = $('<dl class="field-list"></dl>');
      const fieldValues = {
        headwords: entry.headwords.map((item) => item.word).join('；'),
        pos: entry.pos.join('、'),
        sim: entry.sim.join('、'),
        label: entry.label.join('、'),
        ant: entry.ant.join('、'),
        img: entry.img.join('、'),
        ref: entry.ref.join('、'),
        reviewed: entry.reviewed === 1 ? '已覆核（1）' : `未覆核（${entry.reviewed}）`,
      };
      const fieldLabels = {
        headwords: '詞形', pos: '詞性', sim: '近義詞', label: '標籤',
        ant: '反義詞', img: '圖片資料', ref: '參考資料', reviewed: '覆核狀態',
      };
      Object.entries(fieldValues).forEach(([key, value]) => {
        list.append($('<dt></dt>').text(fieldLabels[key]), $('<dd></dd>').text(value || '—'));
      });
      Object.entries(entry).filter(([key]) => !(key in fieldValues) && key !== 'definitions').forEach(([key, value]) => {
        list.append($('<dt></dt>').text(key), $('<dd></dd>').text(JSON.stringify(value)));
      });
      fields.append(list);
      body.append(fields);

      const targets = [];
      if (primary.trim()) {
        const section = $('<section class="border-top pt-3 mt-3 reading-block"></section>');
        section.append($('<h3 class="h6 fw-bold">詞語發音</h3>'));
        const slot = $('<div></div>');
        section.append(slot);
        body.append(section);
        targets.push({ text: primary, slot });
      }

      const definitions = $('<section class="border-top pt-3 mt-3"></section>');
      definitions.append($('<h3 class="h6 fw-bold">解釋與例句</h3>'));
      if (!entry.definitions.length) {
        definitions.append($('<p class="placeholder"></p>').text('暫無解釋。'));
      }
      entry.definitions.forEach((definition, definitionIndex) => {
        const sense = $('<div class="sense bg-body-tertiary rounded-3 p-3 mt-3"></div>');
        sense.append($('<h4 class="h6 fw-bold"></h4>').text(`解釋 ${definitionIndex + 1}`));
        definition.explanation.forEach((explanation) => {
          Object.entries(explanation).forEach(([language, value]) => {
            if (language === 'yue' || language === 'eng') {
              sense.append($('<div class="mb-3"></div>').append(
                $('<h5 class="h4 fw-semibold mb-1"></h5>').text(language === 'yue' ? '粵語' : '英語'),
                $('<p class="language-line mb-0"></p>').text(value),
              ));
            } else {
              sense.append($('<p class="language-line"></p>').append(
                $('<strong></strong>').text(`${language}:`), document.createTextNode(value),
              ));
            }
          });
        });
        if (!definition.explanation.length) {
          sense.append($('<p class="placeholder"></p>').text('暫無解釋文字。'));
        }
        definition.eg.forEach((example, exampleIndex) => {
          const sample = $('<div class="example border-top py-3"></div>');
          sample.append($('<p class="fw-semibold mb-2"></p>').text(`例句 ${exampleIndex + 1}`));
          Object.entries(example).forEach(([language, value]) => {
            if (language === 'jyutpin') {
              return;
            }
            if (language === 'yue' || language === 'eng') {
              sample.append($('<div class="mb-3"></div>').append(
                $('<h5 class="h4 fw-semibold mb-1"></h5>').text(language === 'yue' ? '粵語' : '英語'),
                $('<p class="language-line mb-0"></p>').text(value ?? '—'),
              ));
            } else {
              sample.append($('<p class="language-line"></p>').append(
                $('<strong></strong>').text(`${language}:`), document.createTextNode(value ?? '—'),
              ));
            }
          });
          if (example.yue?.trim() && example.yue.trim().toUpperCase() !== 'X') {
            sample.append($('<button class="btn btn-sm btn-outline-primary" type="button">播放例句</button>')
              .attr('data-speak', example.yue));
            const slot = $('<div class="reading-block mt-2"></div>');
            sample.append(slot);
            targets.push({ text: example.yue, slot });
          }
          sense.append(sample);
        });
        Object.entries(definition).filter(([key]) => key !== 'explanation' && key !== 'eg').forEach(([key, value]) => {
          sense.append($('<p class="language-line"></p>').append(
            $('<strong></strong>').text(`${key}:`), document.createTextNode(JSON.stringify(value)),
          ));
        });
        definitions.append(sense);
      });
      body.append(definitions);
      result.append(card);

      // A record remains readable even if one pronunciation request fails.
      const pronunciations = await Promise.allSettled(targets.map(async ({ text }) => requestApproximation(text)));
      let failed = false;
      pronunciations.forEach((outcome, index) => {
        if (outcome.status === 'fulfilled') {
          targets[index].slot.append(renderPronunciation(outcome.value));
        } else {
          failed = true;
          targets[index].slot.addClass('placeholder').text('暫時無法載入讀音。');
        }
      });
      status.toggleClass('error', failed).text(failed ? '部分讀音暫時無法載入。' : '');
    } catch (error) {
      status.addClass('error').text('暫時無法載入詞語卡，請稍後再試。');
    } finally {
      $(this).prop('disabled', false);
    }
  });

  // Keep a clicked hint beside its word, while a long press opens the same hints in a dialog.
  $(document).on('click', '.word-trigger', function (event) {
    if ($(this).data('suppressClick')) {
      $(this).removeData('suppressClick');
      return;
    }
    event.stopPropagation();
    const hintBox = $('#active-hint-box');
    const open = hintBox.prop('hidden') || $(this).attr('aria-expanded') === 'false';
    hintBox.prop('hidden', true);
    $('.word-trigger').attr('aria-expanded', 'false');
    if (open) {
      const bounds = this.getBoundingClientRect();
      hintBox.empty().append($(this).siblings('.word-hint-content').children().clone()).prop('hidden', false);
      const left = Math.max(8, Math.min(bounds.left, window.innerWidth - hintBox.outerWidth() - 8));
      const top = bounds.bottom + hintBox.outerHeight() + 8 <= window.innerHeight
        ? bounds.bottom + 4 : Math.max(8, bounds.top - hintBox.outerHeight() - 4);
      hintBox.css({ left, top });
      $(this).attr('aria-expanded', 'true');
    }
  });

  $(document).on('pointerdown', '.word-trigger', function (event) {
    if (event.pointerType === 'mouse' && event.button !== 0) {
      return;
    }
    pressedTrigger = this;
    pressStartX = event.clientX;
    pressStartY = event.clientY;
    pressTimer = window.setTimeout(() => {
      const trigger = $(pressedTrigger);
      $('#hint-dialog-title').text(trigger.text());
      $('#hint-dialog-content').empty().append(trigger.siblings('.word-hint-content').children().clone());
      $('#active-hint-box').prop('hidden', true);
      $('.word-trigger').attr('aria-expanded', 'false');
      document.querySelector('#hint-dialog').showModal();
      trigger.data('suppressClick', true);
      window.setTimeout(() => trigger.removeData('suppressClick'), 750);
      pressTimer = null;
    }, 550);
  });

  $(document).on('pointermove', '.word-trigger', function (event) {
    if (Math.abs(event.clientX - pressStartX) > 10 || Math.abs(event.clientY - pressStartY) > 10) {
      window.clearTimeout(pressTimer);
      pressTimer = null;
    }
  });

  $(document).on('pointerup pointercancel pointerleave', '.word-trigger', function () {
    window.clearTimeout(pressTimer);
    pressTimer = null;
    pressedTrigger = null;
  });

  $(document).on('keydown', '.word-trigger', function (event) {
    if (event.shiftKey && event.key === 'F10') {
      event.preventDefault();
      $('#hint-dialog-title').text($(this).text());
      $('#hint-dialog-content').empty().append($(this).siblings('.word-hint-content').children().clone());
      $('#active-hint-box').prop('hidden', true);
      document.querySelector('#hint-dialog').showModal();
    }
  });

  $(document).on('contextmenu', '.word-trigger', function (event) {
    event.preventDefault();
  });

  $(document).on('click', function () {
    $('#active-hint-box').prop('hidden', true);
    $('.word-trigger').attr('aria-expanded', 'false');
  });

  $('#hint-dialog-close').on('click', function () {
    document.querySelector('#hint-dialog').close();
  });

  $(document).on('click', '[data-speak], #speak-input', function () {
    const entered = String($('#cantonese-input').val());
    const text = $(this).is('#speak-input') ? (entered.trim() ? entered : example) : $(this).attr('data-speak');
    if (!text?.trim()) {
      return;
    }
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      $('#pronunciation-status').addClass('error').text('呢個瀏覽器未提供語音播放。');
      return;
    }
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.lang = 'zh-HK';
    const voice = window.speechSynthesis.getVoices().find((item) => item.lang.toLowerCase() === 'zh-hk');
    if (voice) {
      utterance.voice = voice;
    }
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
});
