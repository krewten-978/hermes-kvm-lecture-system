// Phase 1C: initialize Reveal.js and keep presenter controls in sync.
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
}

previousButton.addEventListener("click", () => Reveal.prev());
nextButton.addEventListener("click", () => Reveal.next());
Reveal.on("ready", updatePresenterPanel);
Reveal.on("slidechanged", updatePresenterPanel);

// Run once in case the ready event fires before this script finishes loading.
window.addEventListener("load", updatePresenterPanel);
