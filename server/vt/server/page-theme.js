// The server's own pages follow the app's light/dark choice: ?theme= when a page is shown inside the app, else what the Studio saved as
// "vt-theme" on this same address, else the computer's setting (CSS prefers-color-scheme). Loaded first in <head> so nothing flashes.
(function () {
  try {
    var asked = new URLSearchParams(location.search).get("theme") || localStorage.getItem("vt-theme");
    if (asked === "dark" || asked === "light") document.documentElement.setAttribute("data-theme", asked);
  } catch (e) { /* no storage: the computer's setting decides */ }
})();
