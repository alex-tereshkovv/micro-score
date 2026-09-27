(() => {
  const slides = Array.from(document.querySelectorAll("[data-slide]"));
  const sceneButtons = Array.from(document.querySelectorAll("[data-scene-target]"));
  const modeButtons = Array.from(document.querySelectorAll("[data-tour-mode]"));
  const guideArticles = Array.from(document.querySelectorAll("[data-guide-scene]"));
  const previousButton = document.querySelector("[data-prev]");
  const nextButton = document.querySelector("[data-next]");
  const autoplayButton = document.querySelector("[data-autoplay]");
  const autoplayLabel = document.querySelector("[data-autoplay-label]");
  const autoplayIcon = document.querySelector("[data-autoplay-icon]");
  const guideButton = document.querySelector("[data-guide-toggle]");
  const guideCloseButton = document.querySelector("[data-guide-close]");
  const guidePanel = document.querySelector("[data-guide-panel]");
  const guideTitle = document.querySelector("[data-guide-title]");
  const tourLabel = document.querySelector("[data-tour-label]");
  const modeDuration = document.querySelector("[data-mode-duration]");
  const sceneLabel = document.querySelector("[data-scene-label]");
  const sceneCurrent = document.querySelector("[data-scene-current]");
  const sceneTotal = document.querySelector("[data-scene-total]");

  const sceneNames = [
    "01 · The problem",
    "02 · Research evidence",
    "03 · Product workflow",
    "04 · Monte Carlo",
    "05 · Systems engineering",
    "06 · Responsible-use boundary",
    "07 · Evidence and next steps",
  ];
  const guideTitles = [
    "01 · Frame the problem",
    "02 · Defend the research choice",
    "03 · Trace the workflow",
    "04 · Explain the simulation",
    "05 · Defend the architecture",
    "06 · State the boundary",
    "07 · Close with evidence",
  ];
  const tourModes = {
    overview: {
      label: "Two-minute overview",
      durationLabel: "2 min",
      sceneDuration: 17000,
    },
    technical: {
      label: "Five-minute technical defense",
      durationLabel: "5 min",
      sceneDuration: 40000,
    },
  };

  let activeIndex = 0;
  let tourMode = "overview";
  let guideOpen = false;
  let playing = false;
  let autoplayTimer = null;
  let progressFrame = null;

  function queryStartIndex() {
    const requested = Number(new URLSearchParams(window.location.search).get("scene"));
    return Number.isInteger(requested) && requested >= 1 && requested <= slides.length
      ? requested - 1
      : 0;
  }

  function queryTourMode() {
    return new URLSearchParams(window.location.search).get("mode") === "technical"
      ? "technical"
      : "overview";
  }

  function updateAddress(index = activeIndex) {
    const url = new URL(window.location.href);
    url.searchParams.set("scene", String(index + 1));
    if (playing) url.searchParams.set("autoplay", "1");
    else url.searchParams.delete("autoplay");
    if (tourMode === "technical") url.searchParams.set("mode", "technical");
    else url.searchParams.delete("mode");
    if (guideOpen) url.searchParams.set("guide", "1");
    else url.searchParams.delete("guide");
    window.history.replaceState(null, "", url);
  }

  function stopProgress() {
    window.clearTimeout(autoplayTimer);
    window.cancelAnimationFrame(progressFrame);
    autoplayTimer = null;
    progressFrame = null;
    sceneButtons.forEach((button) => {
      const fill = button.querySelector("i");
      fill.style.transition = "none";
      fill.style.width = Number(button.dataset.sceneTarget) < activeIndex ? "100%" : "0%";
    });
  }

  function startProgress() {
    stopProgress();
    if (!playing) return;
    const duration = tourModes[tourMode].sceneDuration;
    const fill = sceneButtons[activeIndex].querySelector("i");
    progressFrame = window.requestAnimationFrame(() => {
      fill.style.transition = `width ${duration}ms linear`;
      fill.style.width = "100%";
    });
    autoplayTimer = window.setTimeout(() => {
      if (activeIndex >= slides.length - 1) {
        setPlaying(false);
        return;
      }
      setScene(activeIndex + 1);
    }, duration);
  }

  function updateGuide(index) {
    guideArticles.forEach((article, articleIndex) => {
      article.hidden = articleIndex !== index;
    });
    guideTitle.textContent = guideTitles[index];
  }

  function setScene(index, { updateUrl = true } = {}) {
    const nextIndex = Math.max(0, Math.min(slides.length - 1, Number(index) || 0));
    slides.forEach((slide, slideIndex) => {
      const active = slideIndex === nextIndex;
      slide.classList.toggle("is-active", active);
      slide.setAttribute("aria-hidden", String(!active));
    });
    sceneButtons.forEach((button, buttonIndex) => {
      const active = buttonIndex === nextIndex;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", String(active));
    });
    activeIndex = nextIndex;
    sceneLabel.textContent = sceneNames[activeIndex];
    sceneCurrent.textContent = String(activeIndex + 1);
    previousButton.disabled = activeIndex === 0;
    nextButton.disabled = activeIndex === slides.length - 1;
    document.title = `${sceneNames[activeIndex]} | MicroScore ${tourMode === "technical" ? "Technical Defense" : "Walkthrough"}`;
    updateGuide(activeIndex);
    if (updateUrl) updateAddress(activeIndex);
    startProgress();
  }

  function setPlaying(nextPlaying) {
    playing = Boolean(nextPlaying);
    autoplayButton.setAttribute("aria-pressed", String(playing));
    autoplayLabel.textContent = playing ? "Pause tour" : `Play ${tourModes[tourMode].durationLabel} tour`;
    autoplayIcon.textContent = playing ? "Ⅱ" : "▶";
    document.body.classList.toggle("showcase-playing", playing);
    updateAddress(activeIndex);
    startProgress();
  }

  function setTourMode(nextMode, { updateUrl = true } = {}) {
    tourMode = Object.hasOwn(tourModes, nextMode) ? nextMode : "overview";
    const config = tourModes[tourMode];
    modeButtons.forEach((button) => {
      const active = button.dataset.tourMode === tourMode;
      button.setAttribute("aria-pressed", String(active));
    });
    document.body.classList.toggle("showcase-technical-mode", tourMode === "technical");
    tourLabel.textContent = config.label;
    modeDuration.textContent = config.durationLabel;
    if (!playing) autoplayLabel.textContent = `Play ${config.durationLabel} tour`;
    if (updateUrl) updateAddress(activeIndex);
    startProgress();
  }

  function setGuide(nextOpen, { updateUrl = true } = {}) {
    guideOpen = Boolean(nextOpen);
    if (guideOpen && playing) setPlaying(false);
    document.body.classList.toggle("showcase-guide-open", guideOpen);
    guidePanel.setAttribute("aria-hidden", String(!guideOpen));
    guidePanel.inert = !guideOpen;
    guideButton.setAttribute("aria-expanded", String(guideOpen));
    if (updateUrl) updateAddress(activeIndex);
    if (guideOpen) guideCloseButton.focus({ preventScroll: true });
    else guideButton.focus({ preventScroll: true });
  }

  function moveScene(offset) {
    setScene(activeIndex + offset);
  }

  previousButton.addEventListener("click", () => moveScene(-1));
  nextButton.addEventListener("click", () => moveScene(1));
  autoplayButton.addEventListener("click", () => setPlaying(!playing));
  guideButton.addEventListener("click", () => setGuide(!guideOpen));
  guideCloseButton.addEventListener("click", () => setGuide(false));
  modeButtons.forEach((button) => {
    button.addEventListener("click", () => setTourMode(button.dataset.tourMode));
  });
  sceneButtons.forEach((button) => {
    button.addEventListener("click", () => setScene(Number(button.dataset.sceneTarget)));
  });

  document.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const interactiveTarget = event.target.closest("input, textarea, select");
    if (interactiveTarget) return;
    if (event.key === "ArrowRight" || event.key === "PageDown") {
      event.preventDefault();
      moveScene(1);
    } else if (event.key === "ArrowLeft" || event.key === "PageUp") {
      event.preventDefault();
      moveScene(-1);
    } else if (event.key === "Home") {
      event.preventDefault();
      setScene(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setScene(slides.length - 1);
    } else if (event.key === " " && !event.target.closest("a, button")) {
      event.preventDefault();
      setPlaying(!playing);
    } else if (event.key.toLowerCase() === "g" && !event.target.closest("a, button")) {
      event.preventDefault();
      setGuide(!guideOpen);
    } else if (event.key === "Escape" && guideOpen) {
      event.preventDefault();
      setGuide(false);
    } else if (event.key === "Escape") {
      window.location.href = "./#/review";
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && playing) setPlaying(false);
  });

  sceneTotal.textContent = String(slides.length);
  tourMode = queryTourMode();
  activeIndex = queryStartIndex();
  setTourMode(tourMode, { updateUrl: false });
  setScene(activeIndex, { updateUrl: false });
  setGuide(new URLSearchParams(window.location.search).get("guide") === "1", { updateUrl: false });
  if (new URLSearchParams(window.location.search).get("autoplay") === "1") setPlaying(true);
})();
