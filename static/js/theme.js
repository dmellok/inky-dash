(function () {
  const KEY = "inky-theme";
  const root = document.documentElement;

  const saved = localStorage.getItem(KEY);
  if (saved === "dark" || saved === "light") {
    root.dataset.theme = saved;
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    root.dataset.theme = "dark";
  }

  // Multiple theme toggle surfaces (header on wide, drawer on narrow). All
  // share the .theme-toggle class so they stay in sync.
  const buttons = document.querySelectorAll(".theme-toggle");
  function paintIcons() {
    const isDark = root.dataset.theme === "dark";
    for (const b of buttons) {
      const icon = b.querySelector("i.ph");
      if (!icon) continue;
      icon.classList.remove("ph-moon", "ph-sun");
      icon.classList.add(isDark ? "ph-sun" : "ph-moon");
    }
  }
  paintIcons();
  for (const b of buttons) {
    b.addEventListener("click", () => {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      localStorage.setItem(KEY, next);
      paintIcons();
    });
  }
})();
