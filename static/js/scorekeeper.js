(function () {
  "use strict";

  var root = document.getElementById("scorekeeperConsole");
  if (!root) return;

  var saveState = document.getElementById("scorekeeperSaveState");
  var errorBox = document.getElementById("scorekeeperError");
  var reasonInput = document.getElementById("scorekeeperCorrectionReason");
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var busy = false;

  function field(name) {
    return root.querySelector('[data-field="' + name + '"]');
  }

  function actionButtons(action) {
    return root.querySelectorAll('[data-score-action="' + action + '"]');
  }

  function setHidden(elements, hidden) {
    elements.forEach(function (element) { element.hidden = hidden; });
  }

  function setBusy(value) {
    busy = value;
    root.classList.toggle("is-saving", value);
    root.querySelectorAll("[data-score-action]").forEach(function (button) {
      if (value) {
        button.dataset.disabledBeforeSave = button.disabled ? "1" : "0";
        button.disabled = true;
      } else if (button.dataset.disabledBeforeSave) {
        button.disabled = button.dataset.disabledBeforeSave === "1";
        delete button.dataset.disabledBeforeSave;
      }
    });
  }

  function renderSegments(state) {
    var list = document.getElementById("scorekeeperSegmentList");
    if (!list) return;
    list.replaceChildren();
    if (!state.completed_segments.length) {
      var empty = document.createElement("span");
      empty.className = "muted";
      empty.textContent = "Belum ada " + state.terms.segment_label_lower + " selesai.";
      list.appendChild(empty);
      return;
    }
    state.completed_segments.forEach(function (scores, index) {
      var item = document.createElement("span");
      item.appendChild(document.createTextNode(
        state.terms.segment_label + " " + (index + 1) + " "
      ));
      var strong = document.createElement("strong");
      strong.textContent = scores[0] + "–" + scores[1];
      item.appendChild(strong);
      list.appendChild(item);
    });
  }

  function renderHistory(documentState) {
    var list = document.getElementById("scorekeeperHistory");
    if (!list) return;
    list.replaceChildren();
    if (!documentState.history.length) {
      var empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Belum ada aktivitas scorekeeper.";
      list.appendChild(empty);
      return;
    }
    documentState.history.forEach(function (event) {
      var item = document.createElement("li");
      var strong = document.createElement("strong");
      strong.textContent = event.label;
      item.appendChild(strong);
      if (event.side_code) item.appendChild(document.createTextNode(" · " + event.side_code));
      if (event.reason) {
        var small = document.createElement("small");
        small.textContent = event.reason;
        item.appendChild(small);
      }
      list.appendChild(item);
    });
    var summary = root.querySelector(".scorekeeper-history summary");
    if (summary) summary.textContent = "Riwayat scorekeeper (" + documentState.state.event_count + ")";
  }

  function applyDocument(documentState) {
    if (!documentState) return;
    var state = documentState.state;
    var match = documentState.match;
    root.dataset.version = String(documentState.version);
    root.dataset.status = match.status;
    field("current-a").textContent = state.current[0];
    field("current-b").textContent = state.current[1];
    field("segments-a").textContent = state.segments_won.a;
    field("segments-b").textContent = state.segments_won.b;
    field("segment-number").textContent = state.terms.segment_label + " " + state.next_segment;
    field("completed-heading").textContent = state.terms.segment_label + " selesai";
    field("score-hint").textContent = "Target " + state.terms.target +
      ", selisih " + state.terms.win_by + (state.terms.cap ? ", batas " + state.terms.cap : "");

    var statusLabel = field("status-label");
    statusLabel.textContent = match.status_label;
    statusLabel.className = "badge badge-status badge-" + match.status;

    actionButtons("point").forEach(function (button) {
      button.disabled = busy || !state.can_score;
      var unit = state.terms.unit_label_lower;
      var code = button.dataset.side === "a" ? match.team_a_code : match.team_b_code;
      button.setAttribute("aria-label", "Tambah satu " + unit + " untuk " + code);
      var small = button.querySelector("small");
      if (small) small.textContent = state.terms.unit_label;
    });
    actionButtons("start").forEach(function (button) {
      button.hidden = !documentState.can_start;
      button.disabled = busy;
    });
    actionButtons("finish").forEach(function (button) { button.disabled = busy; });
    actionButtons("undo").forEach(function (button) {
      button.hidden = !state.can_undo;
      button.disabled = busy;
    });
    actionButtons("open_correction").forEach(function (button) {
      button.hidden = !documentState.can_open_correction || state.can_undo;
      button.disabled = busy;
    });
    setHidden(root.querySelectorAll('[data-panel="ready"]'), !state.ready_to_finish);
    setHidden(root.querySelectorAll('[data-panel="correction-reason"]'), match.status !== "completed");
    renderSegments(state);
    renderHistory(documentState);
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
    saveState.textContent = "Perubahan belum tersimpan";
    saveState.classList.add("is-error");
  }

  function showSaved(message) {
    errorBox.hidden = true;
    errorBox.textContent = "";
    saveState.textContent = message || "Tersimpan";
    saveState.classList.remove("is-error");
    saveState.classList.add("is-saved");
    window.setTimeout(function () {
      saveState.classList.remove("is-saved");
      saveState.textContent = "Tersimpan · setiap aksi disimpan otomatis";
    }, 1800);
  }

  root.addEventListener("click", function (event) {
    var button = event.target.closest("[data-score-action]");
    if (!button || busy || button.disabled) return;
    var action = button.dataset.scoreAction;
    var needsReason = action === "open_correction" ||
      (action === "undo" && root.dataset.status === "completed");
    var reason = reasonInput ? reasonInput.value.trim() : "";
    if (needsReason && !reason) {
      showError("Isi alasan koreksi sebelum mengubah hasil pertandingan selesai.");
      if (reasonInput) reasonInput.focus();
      return;
    }

    var formData = new FormData();
    formData.append("action", action);
    formData.append("version", root.dataset.version);
    if (button.dataset.side) formData.append("side", button.dataset.side);
    if (reason) formData.append("reason", reason);

    setBusy(true);
    errorBox.hidden = true;
    saveState.textContent = "Menyimpan…";
    fetch(root.dataset.actionUrl, {
      method: "POST",
      body: formData,
      headers: {"X-CSRF-Token": csrfMeta ? csrfMeta.content : ""},
      credentials: "same-origin"
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          return {response: response, payload: payload};
        });
      })
      .then(function (result) {
        setBusy(false);
        if (result.payload.data) applyDocument(result.payload.data);
        if (!result.response.ok || !result.payload.ok) {
          showError(result.payload.error || "Skor tidak dapat disimpan.");
          return;
        }
        if (reasonInput) reasonInput.value = "";
        showSaved(result.payload.message);
      })
      .catch(function () {
        setBusy(false);
        showError("Koneksi terputus. Skor tidak ditambahkan; periksa jaringan lalu coba lagi.");
      });
  });
})();
