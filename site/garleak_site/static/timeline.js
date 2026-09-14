// SPDX-License-Identifier: AGPL-3.0-or-later
// Pick two versions on the timeline to open their pre-rendered diff. Without this
// script the timeline marks are plain links and every diff is listed under them.
(function () {
  var tl = document.querySelector(".tl[data-diff]");
  if (!tl) return;
  var base = tl.getAttribute("data-diff"), order = [], picked = [];
  var hint = document.getElementById("pickhint");
  if (hint) hint.hidden = false;
  [].forEach.call(tl.querySelectorAll("li[data-v]"), function (li) {
    var v = li.getAttribute("data-v"), b = document.createElement("button");
    order.push(v);
    b.type = "button";
    b.className = "pick";
    b.textContent = "Compare v" + v;
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", function () {
      var i = picked.indexOf(v);
      if (i > -1) picked.splice(i, 1); else picked.push(v);
      b.setAttribute("aria-pressed", i > -1 ? "false" : "true");
      if (picked.length === 2) {
        picked.sort(function (x, y) { return order.indexOf(x) - order.indexOf(y); });
        location.href = base + picked[0] + ".." + picked[1] + "/";
      }
    });
    li.appendChild(b);
  });
})();
