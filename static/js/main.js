(function () {
  "use strict";

  // ---------- mobile nav ----------
  var toggle = document.getElementById("navToggle");
  var nav = document.getElementById("mainNav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.classList.toggle("open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    nav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        nav.classList.remove("open");
        toggle.classList.remove("open");
      });
    });
  }

  // ---------- countdown ----------
  var cd = document.getElementById("countdown");
  if (cd) {
    var target = new Date(cd.getAttribute("data-target"));
    var elD = document.getElementById("cd-days");
    var elH = document.getElementById("cd-hours");
    var elM = document.getElementById("cd-mins");
    var elS = document.getElementById("cd-secs");
    var elLabel = document.getElementById("cd-label");

    function tick() {
      var now = new Date();
      var diff = target - now;
      if (diff <= 0) {
        if (elLabel) elLabel.textContent = "Turnamen sedang berlangsung!";
        elD.textContent = elH.textContent = elM.textContent = elS.textContent = "00";
        return;
      }
      var s = Math.floor(diff / 1000);
      var d = Math.floor(s / 86400); s -= d * 86400;
      var h = Math.floor(s / 3600); s -= h * 3600;
      var m = Math.floor(s / 60); s -= m * 60;
      elD.textContent = String(d).padStart(2, "0");
      elH.textContent = String(h).padStart(2, "0");
      elM.textContent = String(m).padStart(2, "0");
      elS.textContent = String(s).padStart(2, "0");
    }
    tick();
    setInterval(tick, 1000);
  }

  // ---------- live score auto-refresh (poll JSON, patch DOM) ----------
  var liveRoot = document.querySelector("[data-live-poll]");
  if (liveRoot) {
    var indicator = document.getElementById("liveUpdated");

    function paintTime() {
      if (indicator) {
        var now = new Date();
        indicator.textContent = "Update terakhir: " + now.toLocaleTimeString("id-ID");
      }
    }

    function refresh() {
      fetch("/api/matches", { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var byId = {};
          data.forEach(function (m) { byId[m.id] = m; });
          document.querySelectorAll("[data-match-id]").forEach(function (card) {
            var m = byId[card.getAttribute("data-match-id")];
            if (!m) return;

            var badge = card.querySelector("[data-field='status']");
            if (badge && badge.textContent.trim() !== m.status_label) {
              badge.textContent = m.status_label;
              badge.className = "badge badge-status badge-" + m.status;
            }
            var sa = card.querySelector("[data-field='sets_a']");
            var sb = card.querySelector("[data-field='sets_b']");
            if (sa && sb) {
              if (sa.textContent != m.sets_a || sb.textContent != m.sets_b) {
                card.classList.add("score-flash");
                setTimeout(function () { card.classList.remove("score-flash"); }, 900);
              }
              sa.textContent = m.sets_a;
              sb.textContent = m.sets_b;
            }
          });
          paintTime();
        })
        .catch(function () {});
    }
    paintTime();
    setInterval(refresh, 15000);
  }

  // ---------- reveal-on-scroll ----------
  var revealTargets = document.querySelectorAll(".match-card, .cal-day, .bracket-node, .stat-card");
  if ("IntersectionObserver" in window && revealTargets.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.style.animationPlayState = "running";
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    revealTargets.forEach(function (el) { io.observe(el); });
  }
})();
