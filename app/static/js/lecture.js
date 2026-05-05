// Phase 1I: initialize Reveal.js, presenter controls, and WebSocket/Telegram pause/resume state.
Reveal.initialize({
  hash: true,
  controls: true,
  progress: true,
  center: true,
  transition: "slide",
  backgroundTransition: "fade",
});

const teleprompterText = document.getElementById("teleprompter-text");
const slideCounter = document.getElementById("slide-counter");
const previousButton = document.getElementById("previous-slide");
const nextButton = document.getElementById("next-slide");
const pauseResumeButton = document.getElementById("pause-resume-lecture");
const lectureStatus = document.getElementById("lecture-status");

let lecturePaused = false;
let lectureState = "ready";
let controlSocket = null;
let teleprompterScrollTimer = null;

function getSlides() {
  return Array.from(document.querySelectorAll(".reveal .slides > section"));
}

function updatePresenterPanel() {
  const slides = getSlides();
  const currentSlide = Reveal.getCurrentSlide();
  const currentIndex = slides.indexOf(currentSlide);
  const notes = currentSlide?.dataset?.notes || "No speaker notes are available for this slide.";

  teleprompterText.textContent = notes;
  teleprompterText.scrollTop = 0;
  slideCounter.textContent = `Slide ${currentIndex + 1} of ${slides.length}`;

  previousButton.disabled = currentIndex <= 0;
  nextButton.disabled = currentIndex >= slides.length - 1;
  syncTeleprompterScroll();
}

function syncTeleprompterScroll() {
  if (teleprompterScrollTimer) {
    window.clearInterval(teleprompterScrollTimer);
    teleprompterScrollTimer = null;
  }

  if (lectureState !== "running" || lecturePaused) {
    return;
  }

  teleprompterScrollTimer = window.setInterval(() => {
    const maxScroll = teleprompterText.scrollHeight - teleprompterText.clientHeight;
    if (maxScroll <= 0 || teleprompterText.scrollTop >= maxScroll) {
      return;
    }
    teleprompterText.scrollTop += 1;
  }, 120);
}

function renderLectureState(paused, state = "ready") {
  lecturePaused = paused;
  lectureState = state;
  document.body.classList.toggle("lecture-paused", lecturePaused);
  pauseResumeButton.textContent = lecturePaused ? "Resume Lecture" : "Pause Lecture";
  pauseResumeButton.setAttribute("aria-pressed", lecturePaused ? "true" : "false");

  if (state === "ended") {
    lectureStatus.textContent = "Ended";
  } else if (lecturePaused) {
    lectureStatus.textContent = "Paused";
  } else if (state === "running") {
    lectureStatus.textContent = "Running";
  } else {
    lectureStatus.textContent = "Live";
  }
  syncTeleprompterScroll();
}

function applySlideAdvance(slideIndex) {
  const slides = getSlides();
  if (!Number.isInteger(slideIndex) || slideIndex < 0 || slideIndex >= slides.length) {
    return;
  }
  Reveal.slide(slideIndex);
  updatePresenterPanel();
}

function connectControlSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  controlSocket = new WebSocket(`${protocol}//${window.location.host}/ws/session`);

  controlSocket.addEventListener("open", () => {
    pauseResumeButton.disabled = false;
    lectureStatus.classList.remove("lecture-status--offline");
  });

  controlSocket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "control_state") {
      renderLectureState(Boolean(message.paused), message.state || "ready");
    } else if (message.type === "slide_advance") {
      renderLectureState(Boolean(message.paused), message.state || "running");
      applySlideAdvance(message.slide_index);
    }
  });

  controlSocket.addEventListener("close", () => {
    pauseResumeButton.disabled = true;
    lectureStatus.textContent = "Control disconnected";
    lectureStatus.classList.add("lecture-status--offline");
  });
}

previousButton.addEventListener("click", () => Reveal.prev());
nextButton.addEventListener("click", () => Reveal.next());
pauseResumeButton.addEventListener("click", () => {
  if (controlSocket?.readyState === WebSocket.OPEN) {
    controlSocket.send(JSON.stringify({ command: lecturePaused ? "resume" : "pause" }));
  }
});

Reveal.on("ready", updatePresenterPanel);
Reveal.on("slidechanged", updatePresenterPanel);

// Run once in case the ready event fires before this script finishes loading.
window.addEventListener("load", () => {
  updatePresenterPanel();
  renderLectureState(false);
  connectControlSocket();
});
