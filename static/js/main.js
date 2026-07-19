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

  // ---------- share button (progressive enhancement, works for content
  // injected later too since it's a class on <html>, not a one-time toggle) ----------
  if (navigator.share) {
    document.documentElement.classList.add("share-supported");
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("#shareBtn");
    if (!btn || !navigator.share) return;
    navigator.share({
      title: btn.getAttribute("data-share-title") || document.title,
      text: btn.getAttribute("data-share-text") || "",
      url: btn.getAttribute("data-share-url") || window.location.href,
    }).catch(function () {});
  });

  // ---------- copy link button ----------
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".copyBtn");
    if (!btn) return;
    var text = btn.getAttribute("data-copy-text");
    if (text) {
      navigator.clipboard.writeText(text).then(function() {
        var originalText = btn.innerHTML;
        var isIcon = btn.classList.contains("floating-btn");
        var checkSvg20 = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        var checkSvg16 = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        btn.innerHTML = isIcon ? checkSvg20 : (checkSvg16 + " Tersalin");
        setTimeout(function() {
          btn.innerHTML = originalText;
        }, 2000);
      }).catch(function() {
        alert("Gagal menyalin text");
      });
    }
  });

  // ---------- modal detail pertandingan (klik kartu jadwal/kalender -> popup,
  // termasuk form komentar & kelola admin di dalamnya lewat AJAX) ----------
  (function () {
    var modal = document.getElementById("matchModal");
    var modalBody = document.getElementById("matchModalBody");
    var modalClose = document.getElementById("matchModalClose");
    if (!modal || !modalBody || !modalClose) return;

    var modalDirty = false; // true kalau ada form yang berhasil disubmit di dalam modal

    function openModal() {
      modal.hidden = false;
      document.body.classList.add("modal-open");
    }

    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove("modal-open");
      if (modalDirty) {
        modalDirty = false;
        window.location.reload();
      }
    }

    function loadFragment(url) {
      modalBody.innerHTML = '<div class="modal-loading">Memuat…</div>';
      openModal();
      fetch(url, { cache: "no-store" })
        .then(function (r) { return r.text(); })
        .then(function (html) { modalBody.innerHTML = html; })
        .catch(function () {
          modalBody.innerHTML = '<div class="modal-loading">Gagal memuat detail pertandingan. Coba lagi.</div>';
        });
    }

    // buka modal saat kartu/laga dengan [data-modal-match] diklik
    document.addEventListener("click", function (e) {
      var trigger = e.target.closest("[data-modal-match]");
      if (!trigger) return;
      e.preventDefault();
      loadFragment(trigger.getAttribute("data-modal-match"));
    });

    modalClose.addEventListener("click", closeModal);
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !modal.hidden) closeModal();
    });

    // form komentar & kelola admin di dalam modal -> submit lewat AJAX,
    // lalu render ulang isi modal dengan hasil terbaru dari server
    document.addEventListener("submit", function (e) {
      var form = e.target.closest(".js-ajax-form");
      if (!form || !modalBody.contains(form)) return;
      e.preventDefault();
      var submitBtn = form.querySelector("button[type='submit']");
      if (submitBtn) submitBtn.disabled = true;
      // form.action bisa "ke-shadow" kalau form punya <input name="action">
      // (mis. form skor/WO/reschedule di sini) -- getAttribute tidak kena masalah itu.
      fetch(form.getAttribute("action"), { method: "POST", body: new FormData(form) })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          modalDirty = true;
          modalBody.innerHTML = html;
        })
        .catch(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });
  })();

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
