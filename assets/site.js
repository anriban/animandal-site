// Theme toggle, mobile menu, and publication search/filter. No dependencies.
(function () {
  var root = document.documentElement;

  // ---- theme
  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var dark = root.dataset.theme
        ? root.dataset.theme === "dark"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.theme = dark ? "light" : "dark";
      try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
    });
  }

  // ---- mobile menu
  var menu = document.getElementById("menu-toggle");
  var nav = document.getElementById("nav");
  if (menu && nav) {
    menu.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      menu.setAttribute("aria-expanded", String(open));
    });
  }

  // ---- project summaries: CSS shows six lines; add More/Less when the text is longer
  Array.prototype.forEach.call(document.querySelectorAll(".clamp"), function (box) {
    var p = box.querySelector("p");
    if (!p || p.scrollHeight <= p.clientHeight + 2) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "more-toggle";
    btn.textContent = "More";
    btn.setAttribute("aria-expanded", "false");
    btn.addEventListener("click", function () {
      var open = box.classList.toggle("is-open");
      btn.textContent = open ? "Less" : "More";
      btn.setAttribute("aria-expanded", String(open));
    });
    box.appendChild(btn);
  });

  // ---- publications
  var search = document.getElementById("pub-search");
  if (!search) return;
  var pubs = Array.prototype.slice.call(document.querySelectorAll(".pub"));
  var groups = Array.prototype.slice.call(document.querySelectorAll("[data-year-group]"));
  var buttons = Array.prototype.slice.call(document.querySelectorAll(".filter"));
  var count = document.getElementById("pub-count");
  var empty = document.getElementById("pub-empty");
  var type = "all";

  function apply() {
    var terms = search.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    var shown = 0;
    pubs.forEach(function (el) {
      var text = el.dataset.search;
      var ok = (type === "all" || el.dataset.type === type) &&
        terms.every(function (t) { return text.indexOf(t) !== -1; });
      el.hidden = !ok;
      if (ok) shown++;
    });
    groups.forEach(function (g) {
      var visible = g.querySelector(".pub:not([hidden])") !== null;
      g.hidden = !visible;
      var jump = document.querySelector('.year-jump a[href="#' + g.id + '"]');
      if (jump) jump.hidden = !visible;
    });
    count.textContent = shown === pubs.length
      ? pubs.length + " publications"
      : shown + " of " + pubs.length + " publications";
    empty.hidden = shown !== 0;
  }

  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      type = b.dataset.filter;
      buttons.forEach(function (x) {
        x.classList.toggle("is-active", x === b);
        x.setAttribute("aria-pressed", String(x === b));
      });
      apply();
    });
  });
  search.addEventListener("input", apply);

  // allow linking to a search, e.g. publications.html?q=pegasus
  var q = new URLSearchParams(location.search).get("q");
  if (q) { search.value = q; apply(); }
})();
