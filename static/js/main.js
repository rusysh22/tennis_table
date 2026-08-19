(function () {
  "use strict";

  // ---------- mobile nav ----------
  var toggle = document.getElementById("navToggle");
  var nav = document.getElementById("mainNav");
  if (toggle && nav) {
    var mobileNav = window.matchMedia("(max-width: 860px)");
    var navItems = nav.querySelectorAll("a, button");
    function setNavState(open) {
      open = Boolean(open && mobileNav.matches);
      nav.classList.toggle("open", open);
      toggle.classList.toggle("open", open);
      document.body.classList.toggle("nav-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Tutup menu" : "Buka menu");
      if (mobileNav.matches) {
        nav.setAttribute("aria-hidden", open ? "false" : "true");
        navItems.forEach(function (item) { item.tabIndex = open ? 0 : -1; });
      } else {
        nav.removeAttribute("aria-hidden");
        navItems.forEach(function (item) { item.removeAttribute("tabindex"); });
      }
    }
    toggle.addEventListener("click", function () {
      setNavState(!nav.classList.contains("open"));
    });
    nav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        setNavState(false);
      });
    });
    document.addEventListener("click", function (event) {
      if (
        mobileNav.matches &&
        nav.classList.contains("open") &&
        !nav.contains(event.target) &&
        !toggle.contains(event.target)
      ) {
        setNavState(false);
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && nav.classList.contains("open")) {
        setNavState(false);
        toggle.focus();
      }
    });
    if (mobileNav.addEventListener) mobileNav.addEventListener("change", function () { setNavState(false); });
    setNavState(false);
  }

  // ---------- password visibility ----------
  document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
    var inputId = button.getAttribute("aria-controls");
    var input = inputId ? document.getElementById(inputId) : null;
    if (!input) return;
    button.addEventListener("click", function () {
      var reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      button.textContent = reveal ? "Sembunyikan" : "Lihat";
      button.setAttribute("aria-label", reveal ? "Sembunyikan password" : "Tampilkan password");
      input.focus();
    });
  });

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
        if (elLabel) elLabel.textContent = "Waktu jadwal telah tiba! Silakan refresh halaman.";
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
    var liveApiUrl = liveRoot.getAttribute("data-live-api") || "/api/v1/matches?limit=100";

    function paintTime() {
      if (indicator) {
        var now = new Date();
        indicator.textContent = "Update terakhir: " + now.toLocaleTimeString("id-ID");
      }
    }

    function refresh() {
      fetch(liveApiUrl, { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (payload) {
          var data = payload.data || [];
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
              var setsA = m.score.segments_won.a;
              var setsB = m.score.segments_won.b;
              if (sa.textContent != setsA || sb.textContent != setsB) {
                card.classList.add("score-flash");
                setTimeout(function () { card.classList.remove("score-flash"); }, 900);
              }
              sa.textContent = setsA;
              sb.textContent = setsB;
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

  // ---------- announcement modal ----------
  (function() {
    var annModal = document.getElementById("announcementModal");
    var annClose = document.getElementById("announcementClose");
    var bellBtns = document.querySelectorAll(".bell-trigger");
    if (!annModal || !annClose) return;

    var annTextEl = document.getElementById("annText");
    var annText = annTextEl ? annTextEl.textContent.trim() : "";
    var timeout;
    var isUnread = annText && sessionStorage.getItem("announcementSeen") !== annText;

    function updateBellState() {
      bellBtns.forEach(function(btn) {
        if (isUnread) btn.classList.add("unread");
        else btn.classList.remove("unread");
      });
    }

    function openAnnouncement() {
      annModal.hidden = false;
      document.body.classList.add("modal-open");
      
      // Reset animation for progress bar
      var prog = annModal.querySelector(".announcement-progress");
      if (prog) {
        prog.style.animation = "none";
        prog.offsetHeight; // trigger reflow
        prog.style.animation = null;
      }

      clearTimeout(timeout);
      timeout = setTimeout(closeAnnouncement, 10000);
      
      if (isUnread) {
        isUnread = false;
        updateBellState();
        sessionStorage.setItem("announcementSeen", annText);
      }
    }

    function closeAnnouncement() {
      if (annModal.hidden) return;
      annModal.hidden = true;
      document.body.classList.remove("modal-open");
      clearTimeout(timeout);
    }

    updateBellState();

    bellBtns.forEach(function(btn) {
      btn.addEventListener("click", function() {
        openAnnouncement();
      });
    });

    annClose.addEventListener("click", closeAnnouncement);
    annModal.addEventListener("click", function(e) {
      if (e.target === annModal) closeAnnouncement();
    });
    document.addEventListener("keydown", function(e) {
      if (e.key === "Escape" && !annModal.hidden) closeAnnouncement();
    });
  })();

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
    var modalBox = modal ? modal.querySelector(".modal-box") : null;
    if (!modal || !modalBody || !modalClose) return;

    var modalDirty = false; // true kalau ada form yang berhasil disubmit di dalam modal
    var previousFocus = null;

    function loadingMarkup() {
      return '<div class="modal-loading"><i aria-hidden="true"></i><strong>Menyiapkan match center</strong><span>Memuat skor dan detail pertandingan…</span></div>';
    }

    function openModal(trigger) {
      previousFocus = trigger || document.activeElement;
      modal.hidden = false;
      document.body.classList.add("modal-open");
      modalBody.setAttribute("aria-busy", "true");
      window.requestAnimationFrame(function () { modalClose.focus(); });
    }

    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove("modal-open");
      modalBody.removeAttribute("aria-busy");
      if (previousFocus && typeof previousFocus.focus === "function") {
        previousFocus.focus();
      }
      if (modalDirty) {
        modalDirty = false;
        window.location.reload();
      }
    }

    function loadFragment(url, trigger) {
      modalBody.innerHTML = loadingMarkup();
      openModal(trigger);
      fetch(url, { cache: "no-store" })
        .then(function (r) {
          if (!r.ok) throw new Error("Gagal memuat detail pertandingan");
          return r.text();
        })
        .then(function (html) {
          modalBody.innerHTML = html;
          modalBody.removeAttribute("aria-busy");
        })
        .catch(function () {
          modalBody.removeAttribute("aria-busy");
          modalBody.innerHTML = '<div class="modal-loading is-error"><strong>Detail belum dapat dimuat</strong><span>Tutup panel ini, lalu coba buka kembali.</span></div>';
        });
    }

    // buka modal saat kartu/laga dengan [data-modal-match] diklik
    document.addEventListener("click", function (e) {
      var trigger = e.target.closest("[data-modal-match]");
      if (!trigger) return;
      e.preventDefault();
      loadFragment(trigger.getAttribute("data-modal-match"), trigger);
    });

    modalClose.addEventListener("click", closeModal);
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });
    document.addEventListener("keydown", function (e) {
      if (modal.hidden) return;
      if (e.key === "Escape") {
        closeModal();
        return;
      }
      if (e.key !== "Tab" || !modalBox) return;
      var focusable = Array.prototype.filter.call(
        modalBox.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'),
        function (el) { return el.offsetWidth || el.offsetHeight || el.getClientRects().length; }
      );
      if (!focusable.length) return;
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
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

  // ---------- klik analytics (GA4) ----------
  // Cuma kirim event kalau gtag ada (config.ga_measurement_id diisi di base.html);
  // di dev lokal/tanpa ID, ini jadi no-op tanpa perlu cek tambahan di tiap tempat.
  (function () {
    if (typeof gtag !== "function") return;

    function send(category, label) {
      gtag("event", "click", { event_category: category, event_label: label });
    }

    document.addEventListener("click", function (e) {
      var el;

      if ((el = e.target.closest(".main-nav a"))) {
        send("nav", el.textContent.trim());
      } else if ((el = e.target.closest(".hero-actions a, .hero-quicknav a"))) {
        send("hero_cta", el.textContent.trim());
      } else if ((el = e.target.closest(".sub-nav a"))) {
        send("sub_nav", el.textContent.trim());
      } else if ((el = e.target.closest("#shareBtn"))) {
        send("share", el.getAttribute("data-share-title") || "match");
      } else if ((el = e.target.closest("[data-modal-match]"))) {
        send("match_detail", el.getAttribute("data-modal-match"));
      } else if ((el = e.target.closest(".bell-trigger"))) {
        send("announcement", "bell");
      } else if ((el = e.target.closest(".admin-shell button[type='submit'], .admin-shell .btn"))) {
        send("admin_action", el.textContent.trim());
      }
    });
  })();

  // ---------- reveal-on-scroll ----------
  var revealTargets = document.querySelectorAll(".match-card, .cal-day, .bracket-node, .stat-card, .gallery-item");
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

  // ---------- lightbox modal ----------
  (function() {
    var lightbox = document.getElementById("lightboxModal");
    var lightboxImg = document.getElementById("lightboxImg");
    var lightboxClose = document.getElementById("lightboxClose");

    if (!lightbox || !lightboxImg) return;

    // Delegate click for dynamically loaded docs
    document.addEventListener("click", function(e) {
      if (e.target.classList.contains("public-doc-img")) {
        e.preventDefault();
        var src = e.target.getAttribute("data-full-src");
        if (src) {
          lightboxImg.src = src;
          lightbox.classList.add("active");
          document.body.style.overflow = "hidden"; // Prevent background scroll
        }
      }
    });

    function closeLightbox() {
      lightbox.classList.remove("active");
      document.body.style.overflow = "";
      setTimeout(function() { lightboxImg.src = ""; }, 300); // clear after transition
    }

    if (lightboxClose) {
      lightboxClose.addEventListener("click", closeLightbox);
    }
    lightbox.addEventListener("click", function(e) {
      if (e.target === lightbox) {
        closeLightbox();
      }
    });
    document.addEventListener("keydown", function(e) {
      if (e.key === "Escape" && lightbox.classList.contains("active")) {
        closeLightbox();
      }
    });
  })();

  // ---------- youtube live embed fallback (jaringan diblokir) ----------
  // Iframe cross-origin tidak selalu bisa dideteksi gagal-muat via onerror
  // (kadang browser tetap fire "load" walau isinya halaman error dari
  // jaringan yang memblokir youtube.com), jadi dipakai timeout: kalau
  // "load" belum juga terjadi dalam beberapa detik, tampilkan pesan.
  (function () {
    var frame = document.getElementById("ytLiveEmbed");
    var fallback = document.getElementById("ytLiveFallback");
    if (!frame || !fallback) return;

    var timer = setTimeout(function () {
      fallback.classList.add("show");
    }, 7000);

    frame.addEventListener("load", function () {
      clearTimeout(timer);
    });
  })();

  // ---------- live chat (first-party, polling-based) ----------
  (function () {
    var box = document.getElementById("liveChatBox");
    var list = document.getElementById("liveChatMessages");
    var form = document.getElementById("liveChatForm");
    var newBadge = document.getElementById("liveChatNewBadge");
    var jumpNew = document.getElementById("liveChatJumpNew");
    if (!box || !list || !form) return;

    var apiUrl = box.getAttribute("data-chat-api");
    var sendUrl = box.getAttribute("data-send-url");
    var deleteUrl = box.getAttribute("data-delete-url");
    var isAdmin = box.getAttribute("data-is-admin") === "1";
    var isSending = false;
    var lastId = null;
    var existing = list.querySelectorAll("[data-msg-id]");
    if (existing.length) lastId = existing[existing.length - 1].getAttribute("data-msg-id");
    list.scrollTop = list.scrollHeight;

    function clearNewBadge() {
      if (newBadge) newBadge.hidden = true;
    }
    if (newBadge) {
      document.addEventListener("visibilitychange", function () {
        if (!document.hidden) clearNewBadge();
      });
      box.addEventListener("click", clearNewBadge);
    }

    function isNearBottom() {
      return list.scrollHeight - list.scrollTop - list.clientHeight < 48;
    }
    function scrollToBottom() {
      list.scrollTop = list.scrollHeight;
      if (jumpNew) jumpNew.hidden = true;
    }
    if (jumpNew) {
      jumpNew.addEventListener("click", scrollToBottom);
      list.addEventListener("scroll", function () {
        if (isNearBottom()) jumpNew.hidden = true;
      });
    }

    var latestNewBadge = null;

    function escapeAndAppend(msg, forceScroll) {
      var wasNearBottom = isNearBottom();
      var empty = list.querySelector(".live-chat-empty");
      if (empty) empty.remove();

      var row = document.createElement("div");
      row.className = "live-chat-msg";
      row.setAttribute("data-msg-id", msg.id);

      var nameEl = document.createElement("strong");
      nameEl.textContent = msg.name;
      row.appendChild(nameEl);

      if (latestNewBadge) latestNewBadge.remove();
      var badge = document.createElement("span");
      badge.className = "live-chat-msg-badge";
      badge.textContent = "baru";
      row.appendChild(badge);
      latestNewBadge = badge;

      var textEl = document.createElement("span");
      textEl.textContent = msg.message;
      row.appendChild(textEl);

      if (isAdmin) {
        var del = document.createElement("button");
        del.type = "button";
        del.className = "live-chat-delete";
        del.title = "Hapus pesan";
        del.setAttribute("data-msg-id", msg.id);
        del.textContent = "✕";
        row.appendChild(del);
      }

      list.appendChild(row);
      lastId = msg.id;
      if (forceScroll || wasNearBottom) {
        scrollToBottom();
      } else if (jumpNew) {
        jumpNew.hidden = false;
      }
    }

    function poll() {
      var url = apiUrl + (lastId ? "?after=" + encodeURIComponent(lastId) : "");
      fetch(url, { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (payload) {
          var incoming = payload.data || [];
          incoming.forEach(function (m) { escapeAndAppend(m); });
          if (incoming.length && newBadge && document.hidden) newBadge.hidden = false;
        })
        .catch(function () {});
    }
    setInterval(poll, 4000);

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (isSending) return; // hard guard against double-submit races
      isSending = true;

      var submitBtn = form.querySelector('button[type="submit"]');
      var originalLabel = submitBtn ? submitBtn.textContent : "";
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Mengirim...";
      }

      var formData = new FormData(form);
      fetch(sendUrl, { method: "POST", body: formData })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            escapeAndAppend(data.message, true);
            form.querySelector('[name="message"]').value = "";
            form.querySelector('[name="message"]').focus();
          } else {
            alert(data.error || "Gagal mengirim pesan.");
          }
        })
        .catch(function () {
          alert("Gagal mengirim pesan. Periksa koneksi Anda.");
        })
        .finally(function () {
          isSending = false;
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = originalLabel;
          }
        });
    });

    var emojiToggle = document.getElementById("liveChatEmojiToggle");
    var emojiPopup = document.getElementById("liveChatEmojiPopup");
    if (emojiToggle && emojiPopup) {
      function closeEmojiPopup() {
        emojiPopup.hidden = true;
        emojiToggle.setAttribute("aria-expanded", "false");
      }
      function openEmojiPopup() {
        emojiPopup.hidden = false;
        emojiToggle.setAttribute("aria-expanded", "true");
      }
      emojiToggle.addEventListener("click", function (e) {
        e.stopPropagation();
        if (emojiPopup.hidden) openEmojiPopup(); else closeEmojiPopup();
      });
      emojiPopup.addEventListener("click", function (e) {
        var btn = e.target.closest(".live-chat-emoji");
        if (!btn) return;
        var input = form.querySelector('[name="message"]');
        if (!input) return;
        var emoji = btn.getAttribute("data-emoji") || "";
        var next = (input.value ? input.value + " " : "") + emoji;
        input.value = next.slice(0, input.maxLength > 0 ? input.maxLength : next.length);
        closeEmojiPopup();
        input.focus();
      });
      document.addEventListener("click", function (e) {
        if (!emojiPopup.hidden && !emojiPopup.contains(e.target) && e.target !== emojiToggle) {
          closeEmojiPopup();
        }
      });
      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && !emojiPopup.hidden) closeEmojiPopup();
      });
    }

    document.addEventListener("click", function (e) {
      var btn = e.target.closest(".live-chat-delete");
      if (!btn || !deleteUrl) return;
      if (!confirm("Hapus pesan ini?")) return;
      var formData = new FormData();
      formData.append("message_id", btn.getAttribute("data-msg-id"));
      var csrfInput = form.querySelector('[name="csrf_token"]');
      if (csrfInput) formData.append("csrf_token", csrfInput.value);
      fetch(deleteUrl, { method: "POST", body: formData })
        .then(function () {
          var row = btn.closest(".live-chat-msg");
          if (row) row.remove();
        })
        .catch(function () {});
    });
  })();

})();

// Global function for voting
window.toggleVotePopup = function(team, matchId) {
  var popupId = 'vote-popup-' + team + '-' + matchId;
  var popup = document.getElementById(popupId);
  if (!popup) return;
  var isVisible = popup.style.display === 'flex';
  
  // hide all others first
  document.querySelectorAll('.vote-popup').forEach(function(p) { p.style.display = 'none'; });
  
  if (!isVisible) {
    popup.style.display = 'flex';
  }
};

document.addEventListener('click', function(e) {
  if (!e.target.closest('.team-chip-wrapper') && !e.target.closest('.vote-popup')) {
    document.querySelectorAll('.vote-popup').forEach(function(p) { p.style.display = 'none'; });
  }
});

window.submitVote = function(matchId, team, emoji) {
  // close popup
  var popup = document.getElementById('vote-popup-' + team + '-' + matchId);
  if (popup) popup.style.display = 'none';

  var formData = new FormData();
  formData.append('team', team);
  formData.append('emoji', emoji);
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  if (csrfMeta) formData.append('csrf_token', csrfMeta.content);

  fetch(`/pertandingan/${matchId}/vote`, {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    var toast = document.getElementById('vote-toast');
    if (toast) {
      toast.style.display = 'block';
      toast.className = 'vote-toast ' + (data.success ? 'success' : 'error');
      toast.textContent = data.message || (data.success ? `Berhasil! Sisa kesempatan: ${data.votes_left}` : '');
      setTimeout(() => { toast.style.display = 'none'; }, 3000);
    } else if (!data.success && data.message) {
      alert(data.message);
    }
    
    if (data.success) {
      // Update count
      var summaryDiv = document.getElementById('vote-summary-' + team + '-' + matchId);
      if (summaryDiv) {
        var items = summaryDiv.querySelectorAll('.vs-item');
        var found = false;
        items.forEach(function(item) {
          if (item.querySelector('.vs-emoji').textContent === emoji) {
            item.querySelector('.vs-count').textContent = data.new_count;
            found = true;
          }
        });
        if (!found) {
          var newItem = document.createElement('span');
          newItem.className = 'vs-item';
          newItem.innerHTML = '<span class="vs-emoji">' + emoji + '</span><span class="vs-count">' + data.new_count + '</span>';
          summaryDiv.appendChild(newItem);
        }
      }
      
      // Update bars
      var barA = document.getElementById('vote-bar-a-' + matchId);
      var barB = document.getElementById('vote-bar-b-' + matchId);
      if (barA && data.pct_a !== undefined) {
        barA.style.width = data.pct_a + '%';
        barA.parentElement.title = 'Persentase: ' + data.pct_a + '%';
      }
      if (barB && data.pct_b !== undefined) {
        barB.style.width = data.pct_b + '%';
        barB.parentElement.title = 'Persentase: ' + data.pct_b + '%';
      }
    }
  })
  .catch(err => {
    console.error('Vote error:', err);
  });
};
