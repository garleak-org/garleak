// SPDX-License-Identifier: AGPL-3.0-or-later
// Load the Pagefind search interface if the index was built (CI runs Pagefind after
// the build). The site works without it, and this page then says so.
(function () {
  var box = document.getElementById("search"), note = document.getElementById("search-note");
  if (!box) return;
  var s = document.createElement("script");
  s.src = "/pagefind/pagefind-ui.js";
  s.onload = function () {
    var css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = "/pagefind/pagefind-ui.css";
    document.head.appendChild(css);
    var ui = new PagefindUI({ element: "#search", showSubResults: true, showImages: false });
    var q = new URLSearchParams(location.search).get("q");
    if (q && ui.triggerSearch) ui.triggerSearch(q);
    if (note) note.hidden = true;
  };
  s.onerror = function () {
    if (note) note.textContent = "This copy of the site has no search index. The index is built when the site is deployed. Browse the listings meanwhile.";
  };
  document.head.appendChild(s);
})();
