(() => {
  const slides = Array.from(document.querySelectorAll("[data-slide]"));
  const sceneButtons = Array.from(document.querySelectorAll("[data-scene-target]"));
  const previousButton = document.querySelector("[data-prev]");
  const nextButton = document.querySelector("[data-next]");
  const autoplayButton = document.querySelector("[data-autoplay]");
  const autoplayLabel = document.querySelector("[data-autoplay-label]");
  const autoplayIcon = document.querySelector("[data-autoplay-icon]");
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

  let activeIndex = 0;
  let playing = false;
  let autoplayTimer = null;
  let progressFrame = null;

  function queryStartIndex() {
    const requested = Number(new URLSearchParams(window.location.search).get("scene"));
    return Number.isInteger(requested) && requested >= 1 && requested <= slides.length
      ? requested - 1
      : 0;
  }

  function updateAddress(index) {
    const url = new URL(window.location.href);
    url.searchParams.set("scene", String(index + 1));
    if (!playing) url.searchParams.delete("autoplay");
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
    const duration = Number(slides[activeIndex].dataset.duration || 17000);
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
    document.title = `${sceneNames[activeIndex]} | MicroScore`;
    if (updateUrl) updateAddress(activeIndex);
    startProgress();
  }

  function setPlaying(nextPlaying) {
    playing = Boolean(nextPlaying);
    autoplayButton.setAttribute("aria-pressed", String(playing));
    autoplayLabel.textContent = playing ? "Pause tour" : "Play tour";
    autoplayIcon.textContent = playing ? "Ⅱ" : "▶";
    document.body.classList.toggle("showcase-playing", playing);
    updateAddress(activeIndex);
    startProgress();
  }

  function moveScene(offset) {
    setScene(activeIndex + offset);
  }

  previousButton.addEventListener("click", () => moveScene(-1));
  nextButton.addEventListener("click", () => moveScene(1));
  autoplayButton.addEventListener("click", () => setPlaying(!playing));
  sceneButtons.forEach((button) => {
    button.addEventListener("click", () => setScene(Number(button.dataset.sceneTarget)));
  });

  document.addEventListener("keydown", (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
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
    } else if (event.key === "Escape") {
      window.location.href = "./#/review";
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && playing) setPlaying(false);
  });

  sceneTotal.textContent = String(slides.length);
  activeIndex = queryStartIndex();
  setScene(activeIndex, { updateUrl: false });
  if (new URLSearchParams(window.location.search).get("autoplay") === "1") setPlaying(true);
})();
