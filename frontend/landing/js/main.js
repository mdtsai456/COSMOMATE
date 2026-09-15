(function () {
  function random(seed) {
    return function () {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function placeStars(layer, count, minSize, maxSize, className, next) {
    if (!layer) {
      return;
    }

    for (let i = 0; i < count; i += 1) {
      const size = minSize + next() * (maxSize - minSize);
      const star = document.createElement("span");
      star.className = "star " + className;
      star.style.width = size + "px";
      star.style.height = size + "px";
      star.style.left = next() * 100 + "%";
      star.style.top = next() * 100 + "%";
      layer.appendChild(star);
    }
  }

  /** Place star layers only. Zoom / veil is handled by app.js. */
  window.initLandingIntro = function initLandingIntro() {
    const farLayer = document.querySelector(".stars-far");
    const nearLayer = document.querySelector(".stars-near");
    if (!document.querySelector(".stage")) {
      return;
    }

    if (farLayer) {
      farLayer.innerHTML = "";
    }
    if (nearLayer) {
      nearLayer.innerHTML = "";
    }

    const next = random(20260813);
    placeStars(farLayer, 160, 1, 2.2, "star-far", next);
    placeStars(nearLayer, 70, 2, 3.6, "star-near", next);
  };
})();
