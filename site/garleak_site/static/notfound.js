// SPDX-License-Identifier: AGPL-3.0-or-later
// On the 404 page, say whether the address was a Garleak identifier, and if so whether
// it was ever issued (SPEC §2.3.7). The page says the same in general terms without it.
(function () {
  var data = document.getElementById("issued"), out = document.getElementById("idnote");
  if (!data || !out) return;
  data = JSON.parse(data.textContent);
  var m = location.pathname.match(/^(\/example)?\/(abs|scratch)\/(?:(paper|scratch):)?([^\/]+?)\/?$/);
  if (!m) return;
  var pre = m[1] || "", type = m[3] || (m[2] === "abs" ? "paper" : "scratch"), key = m[4];
  var arch = data[pre];
  if (!arch) return;
  var k = key.match(/^([1-9][0-9]*)(?:v([1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?)?$/);
  function say(text, href, label) {
    out.textContent = text + " ";
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      a.textContent = label;
      out.appendChild(a);
    }
    out.hidden = false;
  }
  var list = pre + (type === "paper" ? "/list/" : "/scratch/list/");
  if (!k) return say("“" + key + "” is not a Garleak identifier. Identifiers look like paper:4471, paper:4471v3 or paper:4471v3.2.", list, "Browse the listings");
  var issued = arch[type], n = k[1], versions = issued[n];
  var nums = Object.keys(issued).map(Number).sort(function (a, b) { return a - b; });
  if (!versions) {
    var span = nums.length ? " The " + type + " numbers issued so far run from " + nums[0] + " to " + nums[nums.length - 1] + "." : " No " + type + " numbers have been issued yet.";
    return say(type + ":" + key + " was never issued." + span, list, "See what exists");
  }
  var page = pre + (type === "paper" ? "/abs/" : "/scratch/") + n + "/";
  var want = k[2] ? k[2] + (k[3] !== undefined ? "." + k[3] : "") : "";
  say(type + ":" + n + " exists, but it has no version " + want + ". Its versions are " + versions.map(function (v) { return "v" + v; }).join(", ") + ".", page, "Open " + type + ":" + n);
})();
