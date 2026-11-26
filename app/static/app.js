/**
 * Cor ad Cor — Phase 2 Frontend Controller
 * Connects daily liturgical sources, FAISS Catechism citations, and the Companion reflections.
 */

const state = {
  date: new Date().toISOString().slice(0, 10),
  offline: false,
  hasLiveKeys: false,
  liturgy: null,
  cccCitations: [],
  reflections: {
    daily: "",
    checkin: "",
    examen: "",
    lectio: "",
  },
  speakingTarget: null,
  checkinHistory: [],
  timerSeconds: 180,
  timerRemaining: 180,
  timerInterval: null,
  rosaryDecade: 1,
  rosaryBead: 0, // 0=Our Father, 1..10=Hail Marys, 11=Glory Be
};

const els = {
  dateInput: document.getElementById("liturgy-date"),
  offlineToggle: document.getElementById("offline-toggle"),
  engineStatus: document.getElementById("engine-status"),
  themeToggle: document.getElementById("theme-toggle"),
  colorDot: document.getElementById("liturgy-color-dot"),
  season: document.getElementById("liturgy-season"),
  celebration: document.getElementById("liturgy-celebration"),
  sourceTag: document.getElementById("liturgy-source-tag"),
  readingsList: document.getElementById("readings-list"),
  saintBody: document.getElementById("saint-body"),
  cccList: document.getElementById("ccc-list"),
  rosaryWeekdayEyebrow: document.getElementById("rosary-weekday-eyebrow"),
  rosarySetTitle: document.getElementById("rosary-set-title"),
  rosaryList: document.getElementById("rosary-list"),
  prayersList: document.getElementById("prayers-list"),
  cccSearchForm: document.getElementById("ccc-search-form"),
  cccSearchInput: document.getElementById("ccc-search-input"),
  tabDaily: document.getElementById("tab-daily"),
  tabCheckin: document.getElementById("tab-checkin"),
  tabExamen: document.getElementById("tab-examen"),
  tabConfession: document.getElementById("tab-confession"),
  tabLectio: document.getElementById("tab-lectio"),
  panelDaily: document.getElementById("panel-daily"),
  panelCheckin: document.getElementById("panel-checkin"),
  panelExamen: document.getElementById("panel-examen"),
  panelConfession: document.getElementById("panel-confession"),
  panelLectio: document.getElementById("panel-lectio"),
  btnGenerateDaily: document.getElementById("btn-generate-daily"),
  btnPreviewDaily: document.getElementById("btn-preview-daily"),
  dailyTelemetry: document.getElementById("daily-telemetry"),
  dailyProviderPill: document.getElementById("daily-provider-pill"),
  dailyReflectionBody: document.getElementById("daily-reflection-body"),
  checkinForm: document.getElementById("checkin-form"),
  checkinInput: document.getElementById("checkin-input"),
  checkinRemember: document.getElementById("checkin-remember"),
  btnSubmitCheckin: document.getElementById("btn-submit-checkin"),
  btnPreviewCheckin: document.getElementById("btn-preview-checkin"),
  btnResetCheckin: document.getElementById("btn-reset-checkin"),
  checkinTelemetry: document.getElementById("checkin-telemetry"),
  checkinProviderPill: document.getElementById("checkin-provider-pill"),
  checkinReflectionBody: document.getElementById("checkin-reflection-body"),
  examenForm: document.getElementById("examen-form"),
  examenGratitude: document.getElementById("examen-gratitude"),
  examenConsolation: document.getElementById("examen-consolation"),
  examenDesolation: document.getElementById("examen-desolation"),
  examenRemember: document.getElementById("examen-remember"),
  btnSubmitExamen: document.getElementById("btn-submit-examen"),
  btnPreviewExamen: document.getElementById("btn-preview-examen"),
  examenTelemetry: document.getElementById("examen-telemetry"),
  examenProviderPill: document.getElementById("examen-provider-pill"),
  examenReflectionBody: document.getElementById("examen-reflection-body"),
  memorySummaryTitle: document.getElementById("memory-summary-title"),
  memoryThemesBar: document.getElementById("memory-themes-bar"),
  memoryEntriesList: document.getElementById("memory-entries-list"),
  btnClearMemory: document.getElementById("btn-clear-memory"),
  confessionForm: document.getElementById("confession-form"),
  confessionFocus: document.getElementById("confession-focus"),
  btnSubmitConfession: document.getElementById("btn-submit-confession"),
  btnPreviewConfession: document.getElementById("btn-preview-confession"),
  confessionTelemetry: document.getElementById("confession-telemetry"),
  confessionProviderPill: document.getElementById("confession-provider-pill"),
  confessionReflectionBody: document.getElementById("confession-reflection-body"),
  btnCopyConfession: document.getElementById("btn-copy-confession"),
  btnPrintConfession: document.getElementById("btn-print-confession"),
  lectioForm: document.getElementById("lectio-form"),
  lectioPhrase: document.getElementById("lectio-phrase"),
  btnSubmitLectio: document.getElementById("btn-submit-lectio"),
  btnPreviewLectio: document.getElementById("btn-preview-lectio"),
  lectioTelemetry: document.getElementById("lectio-telemetry"),
  lectioProviderPill: document.getElementById("lectio-provider-pill"),
  lectioReflectionBody: document.getElementById("lectio-reflection-body"),
  timerDisplay: document.getElementById("timer-display"),
  btnTimerToggle: document.getElementById("btn-timer-toggle"),
  btnTimerReset: document.getElementById("btn-timer-reset"),
  timerStatus: document.getElementById("timer-status"),
  marianAntiphonTitle: document.getElementById("marian-antiphon-title"),
  marianAntiphonText: document.getElementById("marian-antiphon-text"),
  bookmarksTitle: document.getElementById("bookmarks-title"),
  bookmarksList: document.getElementById("bookmarks-list"),
  btnListenReadings: document.getElementById("btn-listen-readings"),
  cccCountHint: document.getElementById("ccc-count-hint"),
  journalImportInput: document.getElementById("journal-import-input"),
  calendarMonthTitle: document.getElementById("calendar-month-title"),
  calendarList: document.getElementById("calendar-list"),
  beadDecadeLabel: document.getElementById("bead-decade-label"),
  beadStepLabel: document.getElementById("bead-step-label"),
  beadRow: document.getElementById("bead-row"),
  btnNextBead: document.getElementById("btn-next-bead"),
  btnResetBeads: document.getElementById("btn-reset-beads"),
  btnHourPrayer: document.getElementById("btn-hour-prayer"),
  hourPrayerDrawer: document.getElementById("hour-prayer-drawer"),
  hourCanticleEyebrow: document.getElementById("hour-canticle-eyebrow"),
  hourCanticleTitle: document.getElementById("hour-canticle-title"),
  hourCanticleText: document.getElementById("hour-canticle-text"),
  hourDevotionTitle: document.getElementById("hour-devotion-title"),
  hourDevotionText: document.getElementById("hour-devotion-text"),
};

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

/**
 * Render markdown-lite prose and convert bracketed citations like [CCC §2729], [Gospel], [First Reading], [Saint]
 * into interactive buttons that highlight the corresponding source card in the left column.
 */
function renderReflectionHtml(markdownText) {
  const escaped = escapeHtml(markdownText);
  const withCitations = escaped.replace(
    /\[(CCC\s*§?\s*\d+|First Reading|Reading 1|Second Reading|Reading 2|Responsorial Psalm|Psalm|Gospel|Saint)\]/gi,
    (match, inner) => {
      const normalized = inner.trim();
      const isCcc = /^ccc/i.test(normalized);
      const pillClass = isCcc ? "pill-ccc" : "pill-scripture";
      return `<button type="button" class="citation-pill ${pillClass}" data-cite="${escapeHtml(normalized)}">${escapeHtml(match)}</button>`;
    }
  );

  const lines = withCitations.split(/\r?\n/);
  const htmlParts = [];
  let inList = false;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      if (inList) {
        htmlParts.push("</ul>");
        inList = false;
      }
      continue;
    }

    if (line.startsWith("### ")) {
      if (inList) {
        htmlParts.push("</ul>");
        inList = false;
      }
      htmlParts.push(`<h3>${ formatInlineMarkdown(line.slice(4)) }</h3>`);
    } else if (line.startsWith("> ")) {
      if (inList) {
        htmlParts.push("</ul>");
        inList = false;
      }
      htmlParts.push(`<blockquote>${ formatInlineMarkdown(line.slice(2)) }</blockquote>`);
    } else if (line.startsWith("- ") || /^\d+\.\s+/.test(line)) {
      if (!inList) {
        htmlParts.push("<ul>");
        inList = true;
      }
      const itemText = line.replace(/^(-|\d+\.)\s+/, "");
      htmlParts.push(`<li>${ formatInlineMarkdown(itemText) }</li>`);
    } else {
      if (inList) {
        htmlParts.push("</ul>");
        inList = false;
      }
      htmlParts.push(`<p>${ formatInlineMarkdown(line) }</p>`);
    }
  }
  if (inList) {
    htmlParts.push("</ul>");
  }
  return htmlParts.join("\n");
}

function formatInlineMarkdown(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function highlightElement(targetEl) {
  if (!targetEl) return;
  if (targetEl.tagName === "DETAILS") {
    targetEl.open = true;
  }
  targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
  targetEl.classList.add("source-highlight");
  setTimeout(() => targetEl.classList.remove("source-highlight"), 2200);
}

function switchSourceTab(target) {
  document.querySelectorAll(".source-tab").forEach((btn) => {
    const active = btn.dataset.sourceTab === target;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".source-pane").forEach((pane) => {
    pane.hidden = pane.dataset.sourcePane !== target;
  });
}

async function handleCitationClick(event) {
  const pill = event.target.closest(".citation-pill");
  if (!pill) return;
  const cite = (pill.dataset.cite || "").toLowerCase();

  if (cite.startsWith("ccc")) {
    switchSourceTab("catechism");
    const numMatch = cite.match(/\d+/);
    if (numMatch) {
      const paraNum = numMatch[0];
      let card = document.getElementById(`ccc-card-${paraNum}`);
      if (!card) {
        try {
          const res = await fetch(`/api/v1/ccc/${paraNum}`);
          if (res.ok) {
            const item = await res.json();
            const merged = [
              item,
              ...state.cccCitations.filter((c) => Number(c.paragraph) !== Number(item.paragraph)),
            ];
            renderCccList(merged);
            card = document.getElementById(`ccc-card-${paraNum}`);
          }
        } catch {
          // Fall back to scrolling to Catechism card
        }
      }
      highlightElement(card || document.getElementById("source-ccc"));
      return;
    }
    highlightElement(document.getElementById("source-ccc"));
    return;
  }

  switchSourceTab("readings");
  if (cite === "saint") {
    highlightElement(document.getElementById("source-saint"));
    return;
  }

  const readingItems = document.querySelectorAll(".reading-item");
  for (const item of readingItems) {
    const label = (item.dataset.label || "").toLowerCase();
    if (
      (cite.includes("first") && (label.includes("first") || label.includes("reading 1"))) ||
      (cite.includes("second") && (label.includes("second") || label.includes("reading 2"))) ||
      (cite.includes("psalm") && label.includes("psalm")) ||
      (cite.includes("gospel") && label.includes("gospel")) ||
      label.includes(cite)
    ) {
      highlightElement(item);
      return;
    }
  }
}

function renderLiturgy(liturgy) {
  state.liturgy = liturgy;
  els.season.textContent = liturgy.season || "Ordinary Time";
  els.celebration.textContent = liturgy.celebration_title || "Daily Mass";
  els.colorDot.dataset.colour = (liturgy.colour || "white").toLowerCase();
  els.sourceTag.textContent =
    liturgy.source === "live"
      ? "Source: Vatican News & CalAPI (Live)"
      : "Source: Offline Liturgical Fixture";

  // Readings
  if (!liturgy.readings || liturgy.readings.length === 0) {
    els.readingsList.innerHTML = `<p class="muted-placeholder">No readings available for this date.</p>`;
  } else {
    els.readingsList.innerHTML = liturgy.readings
      .map(
        (r, idx) => `
        <details class="reading-item" data-label="${escapeHtml(r.label)}" ${idx === liturgy.readings.length - 1 ? "open" : ""}>
          <summary>
            <span>${escapeHtml(r.label)}</span>
            <span class="reading-citation">${escapeHtml(r.citation)}</span>
          </summary>
          <div class="reading-text">${escapeHtml(r.text)}</div>
        </details>
      `
      )
      .join("");
  }

  // Saint + optional Papal Reflection from Vatican News
  const papalHtml = liturgy.papal_reflection
    ? `<div style="margin-top:0.85rem; padding-top:0.75rem; border-top:1px solid var(--border-color);">
         <div class="panel-eyebrow" style="margin-bottom:0.25rem;">Words of the Popes (Vatican News)</div>
         <p style="margin:0; font-family:var(--font-serif); font-size:0.9rem; font-style:italic;">${escapeHtml(liturgy.papal_reflection.slice(0, 420))}${liturgy.papal_reflection.length > 420 ? "…" : ""}</p>
       </div>`
    : "";

  if (liturgy.saint && liturgy.saint.title) {
    const meta = [liturgy.saint.rank, liturgy.saint.colour ? `Color: ${liturgy.saint.colour}` : ""]
      .filter(Boolean)
      .join(" • ");
    els.saintBody.innerHTML = `
      <h3 class="saint-title">${escapeHtml(liturgy.saint.title)}</h3>
      ${meta ? `<div class="saint-meta">${escapeHtml(meta)}</div>` : ""}
      <p style="margin:0; font-size:0.93rem;">${escapeHtml(liturgy.saint.summary)}</p>
      ${papalHtml}
    `;
  } else {
    els.saintBody.innerHTML = `<p class="muted-placeholder">Ferial weekday in ${escapeHtml(liturgy.season)}.</p>${papalHtml}`;
  }
}

function renderCccList(citations) {
  state.cccCitations = citations || [];
  if (state.cccCitations.length === 0) {
    els.cccList.innerHTML = `<p class="muted-placeholder">No Catechism paragraphs matched.</p>`;
    return;
  }
  els.cccList.innerHTML = state.cccCitations
    .map(
      (item) => `
      <div class="ccc-item" id="ccc-card-${item.paragraph}">
        <div class="ccc-item-header">
          <span class="ccc-badge">${escapeHtml(item.citation)}</span>
          <span class="ccc-section-title">${escapeHtml(item.section)}</span>
        </div>
        <p class="ccc-text">${escapeHtml(item.text)}</p>
      </div>
    `
    )
    .join("");
}

function formatProviderBadge(llm, verification = null) {
  let base = "Pastoral Safety Guardrail";
  if (llm) {
    base =
      llm.provider === "preview"
        ? "Preview Mode (Citation-Grounded Template)"
        : `Served by ${llm.provider.toUpperCase()} (${llm.key_slot || llm.model})`;
  }
  if (verification && verification.cited_paragraphs && verification.cited_paragraphs.length > 0) {
    const ok = verification.verified_paragraphs.length;
    const total = verification.cited_paragraphs.length;
    const mark = verification.all_valid ? "✓" : "⚠";
    return `${base} • ${mark} ${ok}/${total} CCC citations verified`;
  }
  return base;
}

async function checkEngineHealth() {
  try {
    const res = await fetch("/health");
    const data = await res.json();
    const groqCount = data.groq_keys_configured || 0;
    const hasGemini = Boolean(data.gemini_fallback_configured);
    state.hasLiveKeys = groqCount > 0 || hasGemini;

    if (els.cccCountHint && data.ccc_paragraphs_indexed) {
      els.cccCountHint.textContent = `${data.ccc_paragraphs_indexed.toLocaleString()} paragraphs indexed`;
    }

    if (state.hasLiveKeys) {
      els.engineStatus.textContent = `Groq (${groqCount} key${groqCount === 1 ? "" : "s"})${hasGemini ? " + Gemini Fallback" : ""}`;
      els.engineStatus.classList.add("ready");
    } else {
      els.engineStatus.textContent = "Preview Mode (Add .env keys for live AI)";
      els.engineStatus.classList.remove("ready");
    }
  } catch {
    els.engineStatus.textContent = "Server unreachable";
  }
}

async function loadLiturgyContext() {
  const params = new URLSearchParams({
    date: state.date,
    offline: String(state.offline),
  });
  const [litRes, rosRes] = await Promise.all([
    fetch(`/api/v1/liturgy?${params}`),
    fetch(`/api/v1/rosary?${new URLSearchParams({ date: state.date })}`),
  ]);
  if (litRes.ok) {
    const data = await litRes.json();
    renderLiturgy(data.liturgy);
    renderSeasonGuide(data.season_guide);
    renderCccList(data.ccc_citations);
    await loadHourPrayer(data.liturgy?.season || "Ordinary Time");
  }
  if (rosRes.ok) {
    const rosary = await rosRes.json();
    renderRosary(rosary);
  }
  await loadCalendarMonth();
}

async function loadCalendarMonth() {
  if (!els.calendarList) return;
  const [y, m] = state.date.split("-").map(Number);
  try {
    const params = new URLSearchParams({
      year: String(y),
      month: String(m),
      offline: String(state.offline),
    });
    const res = await fetch(`/api/v1/calendar?${params}`);
    if (!res.ok) return;
    const data = await res.json();
    if (els.calendarMonthTitle) {
      els.calendarMonthTitle.textContent = `${data.month_name} ${data.year} — Feasts & Sundays`;
    }
    // Show Sundays, Solemnities, Feasts, and the currently selected date
    const highlights = (data.days || []).filter(
      (d) => d.is_major || d.date === state.date || d.rank === "memorial"
    );
    els.calendarList.innerHTML = highlights
      .map(
        (d) => `
        <button type="button" class="calendar-row ${d.date === state.date ? "active-day" : ""}" data-cal-date="${escapeHtml(d.date)}">
          <span class="liturgy-dot" data-colour="${escapeHtml(d.colour || "green")}"></span>
          <span class="calendar-date-label">${escapeHtml(d.weekday)} ${d.day}</span>
          <span style="flex:1;">${escapeHtml(d.title)}</span>
        </button>
      `
      )
      .join("");
  } catch {
    // Non-blocking
  }
}

function renderRosary(rosary) {
  if (!els.rosaryList || !rosary) return;
  els.rosaryWeekdayEyebrow.textContent = `${rosary.weekday} Rosary`;
  els.rosarySetTitle.textContent = rosary.mystery_set;
  els.rosaryList.innerHTML = (rosary.mysteries || [])
    .map(
      (m) => `
      <details class="reading-item">
        <summary>
          <span>${m.number}. ${escapeHtml(m.title)}</span>
          <span class="reading-citation">${escapeHtml(m.fruit)}</span>
        </summary>
        <div class="reading-text" style="font-family:var(--font-sans); font-size:0.88rem;">
          <div style="color:var(--text-muted); margin-bottom:0.35rem;">
            ${escapeHtml(m.scripture)} &bull;
            <button type="button" class="citation-pill pill-ccc" data-cite="CCC §${m.ccc_paragraph}">[CCC §${m.ccc_paragraph}]</button>
          </div>
          <div>${escapeHtml(m.intention)}</div>
        </div>
      </details>
    `
    )
    .join("");
}

async function generateDailyBriefing({ demo = false } = {}) {
  const useDemo = demo || !state.hasLiveKeys;
  els.btnGenerateDaily.disabled = true;
  els.btnPreviewDaily.disabled = true;
  els.dailyReflectionBody.innerHTML = `<p class="muted-placeholder">Preparing today's liturgical reflection...</p>`;

  const params = new URLSearchParams({
    date: state.date,
    offline: String(state.offline),
    demo: String(useDemo),
  });

  // Use Server-Sent Events (/api/v1/daily/stream) for progressive token/chunk rendering
  if (typeof EventSource !== "undefined") {
    await new Promise((resolve) => {
      let streamedText = "";
      const es = new EventSource(`/api/v1/daily/stream?${params}`);

      es.addEventListener("context", (evt) => {
        const data = JSON.parse(evt.data);
        renderLiturgy(data.liturgy);
        renderCccList(data.ccc_citations);
      });

      es.addEventListener("chunk", (evt) => {
        const data = JSON.parse(evt.data);
        streamedText += data.delta || "";
        els.dailyReflectionBody.innerHTML = renderReflectionHtml(streamedText);
      });

      es.addEventListener("done", (evt) => {
        const data = JSON.parse(evt.data);
        renderLiturgy(data.liturgy);
        renderCccList(data.ccc_citations);
        state.reflections.daily = data.reflection;
        els.dailyTelemetry.hidden = false;
        els.dailyProviderPill.textContent = formatProviderBadge(
          data.llm,
          data.citation_verification
        );
        els.dailyReflectionBody.innerHTML = renderReflectionHtml(data.reflection);
        es.close();
        resolve();
      });

      es.addEventListener("error", (evt) => {
        es.close();
        if (!streamedText) {
          let msg = "Failed to stream daily reflection.";
          try {
            if (evt.data) msg = JSON.parse(evt.data).detail || msg;
          } catch {
            // ignore
          }
          els.dailyReflectionBody.innerHTML = `<div class="empty-sanctuary-state"><p>${escapeHtml(msg)}</p></div>`;
        }
        resolve();
      });
    });

    els.btnGenerateDaily.disabled = false;
    els.btnPreviewDaily.disabled = false;
    return;
  }

  try {
    const res = await fetch(`/api/v1/daily?${params}`);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to generate daily reflection.");
    }
    renderLiturgy(data.liturgy);
    renderCccList(data.ccc_citations);
    state.reflections.daily = data.reflection;
    els.dailyTelemetry.hidden = false;
    els.dailyProviderPill.textContent = formatProviderBadge(data.llm, data.citation_verification);
    els.dailyReflectionBody.innerHTML = renderReflectionHtml(data.reflection);
  } catch (err) {
    els.dailyReflectionBody.innerHTML = `<div class="empty-sanctuary-state"><p>${escapeHtml(err.message)}</p></div>`;
  } finally {
    els.btnGenerateDaily.disabled = false;
    els.btnPreviewDaily.disabled = false;
  }
}

async function loadHourPrayer(season) {
  if (!els.btnHourPrayer) return;
  try {
    const hour = new Date().getHours();
    const params = new URLSearchParams({ hour: String(hour), season: season || "Ordinary Time" });
    const res = await fetch(`/api/v1/hours?${params}`);
    if (!res.ok) return;
    const hp = await res.json();
    els.btnHourPrayer.textContent = hp.label || "Hour Prayer";
    els.hourCanticleEyebrow.textContent = `${hp.label} • ${hp.canticle_citation}`;
    els.hourCanticleTitle.textContent = hp.canticle_title;
    els.hourCanticleText.textContent = hp.canticle_text;
    els.hourDevotionTitle.textContent = hp.marian_devotion_title;
    els.hourDevotionText.textContent = hp.marian_devotion_text;
  } catch {
    // Non-blocking
  }
}

async function submitCheckin({ demo = false } = {}) {
  const message = els.checkinInput.value.trim();
  if (message.length < 2) {
    els.checkinInput.focus();
    return;
  }
  const useDemo = demo || !state.hasLiveKeys;
  els.btnSubmitCheckin.disabled = true;
  els.btnPreviewCheckin.disabled = true;
  els.checkinReflectionBody.innerHTML = `<p class="muted-placeholder">Sitting prayerfully with what you shared and today's readings...</p>`;

  const payload = {
    message,
    date: state.date,
    offline: state.offline,
    demo: useDemo,
    remember: Boolean(els.checkinRemember && els.checkinRemember.checked),
    history: state.checkinHistory.slice(-6),
  };

  try {
    const res = await fetch("/api/v1/checkin/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok || !res.body) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Could not complete check-in.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamedText = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() || "";

      for (const block of blocks) {
        const eventMatch = block.match(/^event:\s*(\S+)/m);
        const dataMatch = block.match(/^data:\s*(.+)$/m);
        if (!eventMatch || !dataMatch) continue;
        const evtName = eventMatch[1];
        const evtData = JSON.parse(dataMatch[1]);

        if (evtName === "context") {
          renderCccList(evtData.ccc_citations);
        } else if (evtName === "chunk") {
          streamedText += evtData.delta || "";
          els.checkinReflectionBody.innerHTML = renderReflectionHtml(streamedText);
        } else if (evtName === "done") {
          renderCccList(evtData.ccc_citations);
          state.reflections.checkin = evtData.reflection;
          els.checkinTelemetry.hidden = false;
          els.checkinProviderPill.textContent = formatProviderBadge(
            evtData.llm,
            evtData.citation_verification
          );
          const rendered = renderReflectionHtml(evtData.reflection);
          if (evtData.crisis_escalated) {
            els.checkinReflectionBody.innerHTML = `<div class="crisis-alert-card">${rendered}</div>`;
          } else {
            state.checkinHistory.push({ role: "user", content: message });
            state.checkinHistory.push({ role: "assistant", content: evtData.reflection });
            if (els.btnResetCheckin) els.btnResetCheckin.hidden = false;
            els.checkinInput.value = "";
            els.checkinInput.placeholder =
              "Reply to the companion's question or share what stirred in you...";
            els.checkinReflectionBody.innerHTML = rendered;
          }
          await loadSeasonMemory();
        } else if (evtName === "error") {
          throw new Error(evtData.detail || "Streaming error.");
        }
      }
    }
  } catch (err) {
    els.checkinReflectionBody.innerHTML = `<div class="empty-sanctuary-state"><p>${escapeHtml(err.message)}</p></div>`;
  } finally {
    els.btnSubmitCheckin.disabled = false;
    els.btnPreviewCheckin.disabled = false;
  }
}

async function submitExamen({ demo = false } = {}) {
  const gratitude = (els.examenGratitude.value || "").trim() || (demo ? "Quiet moments of grace today" : "");
  const consolation = (els.examenConsolation.value || "").trim() || (demo ? "Listening patiently to a colleague" : "");
  const desolation = (els.examenDesolation.value || "").trim() || (demo ? "Feeling tired and impatient by evening" : "");

  if (!gratitude && !consolation && !desolation) {
    els.examenGratitude.focus();
    return;
  }

  const useDemo = demo || !state.hasLiveKeys;
  els.btnSubmitExamen.disabled = true;
  els.btnPreviewExamen.disabled = true;
  els.examenReflectionBody.innerHTML = `<p class="muted-placeholder">Gathering the day in stillness with today's Word...</p>`;

  try {
    const res = await fetch("/api/v1/examen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        gratitude,
        consolation,
        desolation,
        date: state.date,
        offline: state.offline,
        demo: useDemo,
        remember: Boolean(els.examenRemember && els.examenRemember.checked),
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Could not generate evening Examen.");
    }
    renderCccList(data.ccc_citations);
    state.reflections.examen = data.reflection;
    els.examenTelemetry.hidden = false;
    els.examenProviderPill.textContent = formatProviderBadge(data.llm, data.citation_verification);
    const rendered = renderReflectionHtml(data.reflection);
    els.examenReflectionBody.innerHTML = data.crisis_escalated
      ? `<div class="crisis-alert-card">${rendered}</div>`
      : rendered;
    await loadSeasonMemory();
  } catch (err) {
    els.examenReflectionBody.innerHTML = `<div class="empty-sanctuary-state"><p>${escapeHtml(err.message)}</p></div>`;
  } finally {
    els.btnSubmitExamen.disabled = false;
    els.btnPreviewExamen.disabled = false;
  }
}

async function loadSeasonMemory() {
  try {
    const res = await fetch("/api/v1/memory");
    if (!res.ok) return;
    const data = await res.json();
    const total = data.total_entries || 0;
    const days = data.distinct_days || 0;
    const rhythm = days > 0 ? ` • ${days} day${days === 1 ? "" : "s"} prayed` : "";
    els.memorySummaryTitle.textContent = `Season Memory — ${data.season || "Ordinary Time"} (${total} reflection${total === 1 ? "" : "s"}${rhythm})`;

    if (!data.top_themes || data.top_themes.length === 0) {
      els.memoryThemesBar.innerHTML = `<span class="muted-placeholder">No recurring themes recorded yet. Save a Check-In or Evening Examen to track season patterns.</span>`;
    } else {
      els.memoryThemesBar.innerHTML = data.top_themes
        .map((t) => `<span class="theme-badge">${escapeHtml(t.theme)} &times;${t.count}</span>`)
        .join("");
    }

    if (!data.recent_entries || data.recent_entries.length === 0) {
      els.memoryEntriesList.innerHTML = "";
    } else {
      els.memoryEntriesList.innerHTML = data.recent_entries
        .map((e) => {
          const summary =
            e.entry_type === "examen"
              ? `Examen: ${e.desolation || e.consolation || e.user_note}`
              : `Check-In: ${e.user_note}`;
          return `
            <div class="memory-entry-item">
              <span>${escapeHtml(summary.slice(0, 120))}</span>
              <span class="memory-entry-meta">${escapeHtml(e.liturgical_date)} &bull; ${escapeHtml(e.entry_type)}</span>
            </div>
          `;
        })
        .join("");
    }
  } catch {
    // Non-blocking
  }
}

async function clearSeasonMemory() {
  await fetch("/api/v1/memory", { method: "DELETE" });
  await loadSeasonMemory();
}

async function submitConfessionPrep({ demo = false } = {}) {
  const focus_area = (els.confessionFocus.value || "").trim();
  const useDemo = demo || !state.hasLiveKeys;
  els.btnSubmitConfession.disabled = true;
  els.btnPreviewConfession.disabled = true;
  els.confessionReflectionBody.innerHTML = `<p class="muted-placeholder">Preparing a gentle Examination of Conscience from your season patterns and the Catechism...</p>`;

  try {
    const res = await fetch("/api/v1/confession-prep", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        focus_area,
        date: state.date,
        offline: state.offline,
        demo: useDemo,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Could not generate Confession preparation.");
    }
    renderCccList(data.ccc_citations);
    els.confessionTelemetry.hidden = false;
    els.confessionProviderPill.textContent = formatProviderBadge(data.llm, data.citation_verification);
    const rendered = renderReflectionHtml(data.reflection);
    els.confessionReflectionBody.innerHTML = data.crisis_escalated
      ? `<div class="crisis-alert-card">${rendered}</div>`
      : rendered;
  } catch (err) {
    els.confessionReflectionBody.innerHTML = `<div class="empty-sanctuary-state"><p>${escapeHtml(err.message)}</p></div>`;
  } finally {
    els.btnSubmitConfession.disabled = false;
    els.btnPreviewConfession.disabled = false;
  }
}

function switchTab(target) {
  const tabs = [
    ["daily", els.tabDaily, els.panelDaily],
    ["checkin", els.tabCheckin, els.panelCheckin],
    ["examen", els.tabExamen, els.panelExamen],
    ["confession", els.tabConfession, els.panelConfession],
    ["lectio", els.tabLectio, els.panelLectio],
  ];
  for (const [name, tabEl, panelEl] of tabs) {
    if (!tabEl || !panelEl) continue;
    const active = name === target;
    tabEl.classList.toggle("active", active);
    tabEl.setAttribute("aria-selected", String(active));
    panelEl.hidden = !active;
  }
  if (target === "confession") {
    loadSeasonMemory();
  }
}

async function submitLectioDivina({ demo = false } = {}) {
  const selected_phrase = (els.lectioPhrase.value || "").trim();
  const useDemo = demo || !state.hasLiveKeys;
  els.btnSubmitLectio.disabled = true;
  els.btnPreviewLectio.disabled = true;
  els.lectioReflectionBody.innerHTML = `<p class="muted-placeholder">Preparing today's four-step Lectio Divina...</p>`;

  try {
    const res = await fetch("/api/v1/lectio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        selected_phrase,
        date: state.date,
        offline: state.offline,
        demo: useDemo,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Could not prepare Lectio Divina.");
    }
    renderCccList(data.ccc_citations);
    state.reflections.lectio = data.reflection;
    els.lectioTelemetry.hidden = false;
    els.lectioProviderPill.textContent = formatProviderBadge(data.llm, data.citation_verification);
    els.lectioReflectionBody.innerHTML = renderReflectionHtml(data.reflection);
  } catch (err) {
    els.lectioReflectionBody.innerHTML = `<div class="empty-sanctuary-state"><p>${escapeHtml(err.message)}</p></div>`;
  } finally {
    els.btnSubmitLectio.disabled = false;
    els.btnPreviewLectio.disabled = false;
  }
}

function playGentleChime() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(528, ctx.currentTime);
    gain.gain.setValueAtTime(0.001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.18, ctx.currentTime + 0.08);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 2.4);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 2.5);
  } catch {
    // Non-blocking
  }
}

function renderTimer() {
  const mins = String(Math.floor(state.timerRemaining / 60)).padStart(2, "0");
  const secs = String(state.timerRemaining % 60).padStart(2, "0");
  if (els.timerDisplay) {
    els.timerDisplay.textContent = `${mins}:${secs}`;
  }
}

function stopTimer() {
  if (state.timerInterval) {
    clearInterval(state.timerInterval);
    state.timerInterval = null;
  }
  if (els.btnTimerToggle) {
    els.btnTimerToggle.textContent = "Begin Stillness";
  }
}

function toggleTimer() {
  if (state.timerInterval) {
    stopTimer();
    els.timerStatus.textContent = "Paused in stillness.";
    return;
  }
  if (state.timerRemaining <= 0) {
    state.timerRemaining = state.timerSeconds;
  }
  playGentleChime();
  els.btnTimerToggle.textContent = "Pause Stillness";
  els.timerStatus.textContent = "Be still and know that I am God (Psalm 46:10).";
  state.timerInterval = setInterval(() => {
    state.timerRemaining -= 1;
    renderTimer();
    if (state.timerRemaining <= 0) {
      stopTimer();
      playGentleChime();
      els.timerStatus.textContent = "Stillness complete. Carry this peace gently into your day.";
    }
  }, 1000);
}

function bindEvents() {
  els.dateInput.value = state.date;
  els.dateInput.addEventListener("change", () => {
    if (els.dateInput.value) {
      state.date = els.dateInput.value;
      loadLiturgyContext();
    }
  });

  els.offlineToggle.addEventListener("change", () => {
    state.offline = els.offlineToggle.checked;
    loadLiturgyContext();
  });

  els.themeToggle.addEventListener("click", () => {
    const html = document.documentElement;
    const next = html.dataset.theme === "dark" ? "light" : "dark";
    html.dataset.theme = next;
    els.themeToggle.textContent = next === "dark" ? "Morning Light" : "Evening Vigil";
  });

  if (els.btnHourPrayer && els.hourPrayerDrawer) {
    els.btnHourPrayer.addEventListener("click", () => {
      els.hourPrayerDrawer.hidden = !els.hourPrayerDrawer.hidden;
    });
  }

  els.tabDaily.addEventListener("click", () => switchTab("daily"));
  els.tabCheckin.addEventListener("click", () => switchTab("checkin"));
  els.tabExamen.addEventListener("click", () => switchTab("examen"));
  els.tabConfession.addEventListener("click", () => switchTab("confession"));
  if (els.tabLectio) {
    els.tabLectio.addEventListener("click", () => switchTab("lectio"));
  }

  els.btnGenerateDaily.addEventListener("click", () => generateDailyBriefing({ demo: false }));
  els.btnPreviewDaily.addEventListener("click", () => generateDailyBriefing({ demo: true }));

  els.checkinForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submitCheckin({ demo: false });
  });
  els.btnPreviewCheckin.addEventListener("click", () => submitCheckin({ demo: true }));
  if (els.btnResetCheckin) {
    els.btnResetCheckin.addEventListener("click", () => {
      state.checkinHistory = [];
      els.btnResetCheckin.hidden = true;
      els.checkinInput.value = "";
      els.checkinInput.placeholder =
        "Write honestly in your own words (e.g., 'I'm exhausted today and struggling to trust God with...')";
      els.checkinReflectionBody.innerHTML = "";
      els.checkinTelemetry.hidden = true;
    });
  }

  els.examenForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submitExamen({ demo: false });
  });
  els.btnPreviewExamen.addEventListener("click", () => submitExamen({ demo: true }));

  els.confessionForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submitConfessionPrep({ demo: false });
  });
  els.btnPreviewConfession.addEventListener("click", () => submitConfessionPrep({ demo: true }));

  els.btnClearMemory.addEventListener("click", clearSeasonMemory);

  if (els.btnCopyConfession) {
    els.btnCopyConfession.addEventListener("click", async () => {
      const text = els.confessionReflectionBody.innerText.trim();
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        els.btnCopyConfession.textContent = "Copied!";
        setTimeout(() => {
          els.btnCopyConfession.textContent = "Copy for Confession";
        }, 1800);
      } catch {
        alert("Could not copy automatically. Please select and copy the text.");
      }
    });
  }

  if (els.btnPrintConfession) {
    els.btnPrintConfession.addEventListener("click", () => window.print());
  }

  if (els.lectioForm) {
    els.lectioForm.addEventListener("submit", (e) => {
      e.preventDefault();
      submitLectioDivina({ demo: false });
    });
  }
  if (els.btnPreviewLectio) {
    els.btnPreviewLectio.addEventListener("click", () => submitLectioDivina({ demo: true }));
  }

  document.querySelectorAll(".timer-preset").forEach((btn) => {
    btn.addEventListener("click", () => {
      stopTimer();
      const mins = Number(btn.dataset.minutes || "3");
      state.timerSeconds = mins * 60;
      state.timerRemaining = state.timerSeconds;
      renderTimer();
      els.timerStatus.textContent = `Ready for ${mins} minute${mins === 1 ? "" : "s"} of quiet contemplation.`;
    });
  });
  if (els.btnTimerToggle) {
    els.btnTimerToggle.addEventListener("click", toggleTimer);
  }
  if (els.btnTimerReset) {
    els.btnTimerReset.addEventListener("click", () => {
      stopTimer();
      state.timerRemaining = state.timerSeconds;
      renderTimer();
      els.timerStatus.textContent = "Set down your words and rest quietly in God's presence.";
    });
  }

  document.querySelectorAll(".chip-btn").forEach((chip) => {
    chip.addEventListener("click", () => {
      els.checkinInput.value = chip.dataset.prompt || "";
      els.checkinInput.focus();
    });
  });

  els.cccSearchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = els.cccSearchInput.value.trim();
    if (q.length < 2) return;
    const res = await fetch(`/api/v1/ccc/search?${new URLSearchParams({ q, k: "4" })}`);
    if (res.ok) {
      const data = await res.json();
      renderCccList(data.results);
    }
  });

  document.body.addEventListener("click", handleCitationClick);
  document.body.addEventListener("click", handleAudioClick);
  document.body.addEventListener("click", handleBookmarkClick);
  document.querySelectorAll(".source-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchSourceTab(btn.dataset.sourceTab));
  });

  document.querySelectorAll(".ccc-topic-chip").forEach((chip) => {
    chip.addEventListener("click", async () => {
      const q = chip.dataset.cccQuery || "";
      if (!q) return;
      els.cccSearchInput.value = chip.textContent.trim();
      const res = await fetch(`/api/v1/ccc/search?${new URLSearchParams({ q, k: "4" })}`);
      if (res.ok) {
        const data = await res.json();
        renderCccList(data.results);
      }
    });
  });

  if (els.btnNextBead) {
    els.btnNextBead.addEventListener("click", advanceRosaryBead);
  }
  if (els.btnResetBeads) {
    els.btnResetBeads.addEventListener("click", () => {
      state.rosaryDecade = 1;
      state.rosaryBead = 0;
      renderRosaryBeads();
    });
  }

  document.body.addEventListener("click", async (e) => {
    const shareBtn = e.target.closest(".btn-share");
    if (!shareBtn) return;
    const target = shareBtn.dataset.shareTarget;
    const text = (state.reflections[target] || "").trim();
    if (!text) return;
    const title = `Cor ad Cor — ${state.liturgy?.celebration_title || state.date} (${state.date})`;
    const sharePayload = `${title}\n\n${text.replace(/#{1,6}\s*/g, "").replace(/\*\*/g, "")}`;
    try {
      await navigator.clipboard.writeText(sharePayload);
      shareBtn.textContent = "Copied to Share ✓";
      setTimeout(() => {
        shareBtn.textContent = "Share";
      }, 2000);
    } catch {
      alert("Could not copy automatically. Please copy the reflection text directly.");
    }
  });

  document.body.addEventListener("click", (e) => {
    const row = e.target.closest(".calendar-row");
    if (!row || !row.dataset.calDate) return;
    state.date = row.dataset.calDate;
    els.dateInput.value = state.date;
    switchSourceTab("readings");
    loadLiturgyContext();
  });

  if (els.btnListenReadings) {
    els.btnListenReadings.addEventListener("click", () => {
      if (!("speechSynthesis" in window)) return;
      if (state.speakingTarget === "readings" && window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        state.speakingTarget = null;
        els.btnListenReadings.textContent = "Listen to Readings";
        return;
      }
      const readings = state.liturgy?.readings || [];
      if (!readings.length) return;
      const script = readings
        .map((r) => `${r.label}. ${r.citation}. ${r.text}`)
        .join("\n\n");
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(script);
      utterance.rate = 0.92;
      utterance.onend = () => {
        state.speakingTarget = null;
        els.btnListenReadings.textContent = "Listen to Readings";
      };
      state.speakingTarget = "readings";
      els.btnListenReadings.textContent = "Stop Readings";
      window.speechSynthesis.speak(utterance);
    });
  }

  if (els.journalImportInput) {
    els.journalImportInput.addEventListener("change", async () => {
      const file = els.journalImportInput.files?.[0];
      if (!file) return;
      try {
        const parsed = JSON.parse(await file.text());
        const res = await fetch("/api/v1/memory/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(parsed),
        });
        if (res.ok) {
          await loadSeasonMemory();
        }
      } catch {
        alert("Invalid journal backup JSON file.");
      } finally {
        els.journalImportInput.value = "";
      }
    });
  }

  // Keyboard shortcuts: 1-5 to switch tabs when not typing, Alt+T for Evening Vigil mode
  document.addEventListener("keydown", (e) => {
    const tag = (e.target?.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select") return;
    if (e.altKey && e.key.toLowerCase() === "t") {
      e.preventDefault();
      els.themeToggle.click();
      return;
    }
    const tabMap = { "1": "daily", "2": "checkin", "3": "examen", "4": "confession", "5": "lectio" };
    if (!e.ctrlKey && !e.metaKey && !e.altKey && tabMap[e.key]) {
      switchTab(tabMap[e.key]);
    }
  });
}

async function handleAudioClick(event) {
  const btn = event.target.closest(".btn-audio");
  if (!btn) return;
  const target = btn.dataset.audioTarget;
  const action = btn.dataset.audioAction;
  const markdownText = state.reflections[target] || "";
  if (!markdownText) return;

  if (action === "speak") {
    if (!("speechSynthesis" in window)) {
      alert("Browser speech synthesis is not supported here. Try Download MP3 instead.");
      return;
    }
    if (state.speakingTarget === target && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      state.speakingTarget = null;
      btn.textContent = "Listen (Calm Voice)";
      return;
    }

    window.speechSynthesis.cancel();
    btn.disabled = true;
    try {
      const res = await fetch("/api/v1/audio/script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: markdownText }),
      });
      const data = await res.json();
      const utterance = new SpeechSynthesisUtterance(data.spoken_script || markdownText);
      utterance.rate = 0.92;
      utterance.onend = () => {
        state.speakingTarget = null;
        btn.textContent = "Listen (Calm Voice)";
      };
      state.speakingTarget = target;
      btn.textContent = "Stop Listening";
      window.speechSynthesis.speak(utterance);
    } finally {
      btn.disabled = false;
    }
    return;
  }

  if (action === "mp3") {
    btn.disabled = true;
    const prevLabel = btn.textContent;
    btn.textContent = "Generating MP3...";
    try {
      const res = await fetch("/api/v1/audio/voice-note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: markdownText }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Could not synthesize MP3 voice-note.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const player = document.getElementById(`${target}-audio-player`);
      if (player) {
        player.src = url;
        player.hidden = false;
        player.play().catch(() => {});
      }
      const link = document.createElement("a");
      link.href = url;
      link.download = `cor_ad_cor_${target}_${state.date}.mp3`;
      link.click();
    } catch (err) {
      alert(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = prevLabel;
    }
  }
}

function renderSeasonGuide(guide) {
  if (!guide) return;
  if (els.colorDot && guide.colour_meaning) {
    els.colorDot.title = guide.colour_meaning;
  }
  if (els.season && guide.spiritual_focus) {
    els.season.title = guide.spiritual_focus;
  }
  if (els.marianAntiphonTitle && guide.marian_antiphon_title) {
    els.marianAntiphonTitle.textContent = guide.marian_antiphon_title;
  }
  if (els.marianAntiphonText && guide.marian_antiphon_text) {
    els.marianAntiphonText.textContent = guide.marian_antiphon_text;
  }
}

async function loadBookmarks() {
  if (!els.bookmarksList) return;
  try {
    const res = await fetch("/api/v1/bookmarks");
    if (!res.ok) return;
    const data = await res.json();
    const list = data.bookmarks || [];
    if (els.bookmarksTitle) {
      els.bookmarksTitle.textContent = `Saved Reflections (${list.length})`;
    }
    if (list.length === 0) {
      els.bookmarksList.innerHTML = `<p class="muted-placeholder">Click "Save Reflection" on any briefing, check-in, Examen, or Lectio Divina to keep it here.</p>`;
      return;
    }
    els.bookmarksList.innerHTML = list
      .map(
        (b) => `
        <details class="reading-item">
          <summary>
            <span>${escapeHtml(b.title)}</span>
            <span class="reading-citation">${escapeHtml(b.liturgical_date)} &bull; ${escapeHtml(b.category)}</span>
          </summary>
          <div class="reading-text">
            <div style="margin-bottom:0.6rem;">${renderReflectionHtml(b.content)}</div>
            <button type="button" class="btn-ghost btn-delete-bookmark" data-bookmark-id="${b.id}">
              Remove Bookmark
            </button>
          </div>
        </details>
      `
      )
      .join("");
  } catch {
    // Non-blocking
  }
}

async function handleBookmarkClick(event) {
  const saveBtn = event.target.closest(".btn-bookmark");
  if (saveBtn) {
    const target = saveBtn.dataset.bookmarkTarget;
    const content = (state.reflections[target] || "").trim();
    if (!content) return;
    const labelMap = {
      daily: "5 Minutes Before Mass",
      checkin: "Personal Check-In",
      examen: "Evening Ignatian Examen",
      lectio: "Lectio Divina",
    };
    const title = `${labelMap[target] || "Reflection"} — ${state.liturgy?.celebration_title || state.date}`;
    saveBtn.disabled = true;
    try {
      const res = await fetch("/api/v1/bookmarks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          liturgical_date: state.date,
          category: target,
          title,
          content,
          ccc_citations: state.cccCitations.map((c) => c.citation),
        }),
      });
      if (res.ok) {
        saveBtn.textContent = "Saved ✓";
        await loadBookmarks();
        setTimeout(() => {
          saveBtn.textContent = "Save Reflection";
        }, 2000);
      }
    } finally {
      saveBtn.disabled = false;
    }
    return;
  }

  const delBtn = event.target.closest(".btn-delete-bookmark");
  if (delBtn) {
    const id = delBtn.dataset.bookmarkId;
    await fetch(`/api/v1/bookmarks/${id}`, { method: "DELETE" });
    await loadBookmarks();
  }
}

async function loadPrayers() {
  if (!els.prayersList) return;
  try {
    const res = await fetch("/api/v1/prayers");
    if (!res.ok) return;
    const data = await res.json();
    els.prayersList.innerHTML = (data.prayers || [])
      .map(
        (p) => `
        <details class="reading-item">
          <summary>
            <span>${escapeHtml(p.title)}</span>
            <span class="reading-citation">${escapeHtml(p.moment)}</span>
          </summary>
          <div class="reading-text">
            <div style="font-family:var(--font-sans); font-size:0.78rem; color:var(--text-muted); margin-bottom:0.4rem;">
              ${escapeHtml(p.attribution)}
            </div>
            ${escapeHtml(p.text)}
          </div>
        </details>
      `
      )
      .join("");
  } catch {
    // Non-blocking
  }
}

function renderRosaryBeads() {
  if (!els.beadRow) return;
  els.beadDecadeLabel.textContent = `Decade ${state.rosaryDecade} of 5`;
  if (state.rosaryBead === 0) {
    els.beadStepLabel.textContent = "Our Father (0 / 10 Hail Marys)";
  } else if (state.rosaryBead <= 10) {
    els.beadStepLabel.textContent = `Hail Mary ${state.rosaryBead} of 10`;
  } else {
    els.beadStepLabel.textContent = "Glory Be & Fatima Prayer";
  }

  const beads = [];
  for (let i = 0; i <= 10; i += 1) {
    const cls = i === 0 ? "bead-dot bead-of" : "bead-dot";
    const prayed = state.rosaryBead > i ? " prayed" : "";
    beads.push(`<span class="${cls}${prayed}" title="${i === 0 ? "Our Father" : `Hail Mary ${i}`}"></span>`);
  }
  els.beadRow.innerHTML = beads.join("");
}

function advanceRosaryBead() {
  if (state.rosaryBead < 11) {
    state.rosaryBead += 1;
  } else if (state.rosaryDecade < 5) {
    state.rosaryDecade += 1;
    state.rosaryBead = 0;
  } else {
    playGentleChime();
    state.rosaryDecade = 1;
    state.rosaryBead = 0;
  }
  renderRosaryBeads();
}

async function init() {
  bindEvents();
  renderTimer();
  renderRosaryBeads();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  }
  await checkEngineHealth();
  await loadLiturgyContext();
  await loadSeasonMemory();
  await loadBookmarks();
  await loadPrayers();
}

init();
