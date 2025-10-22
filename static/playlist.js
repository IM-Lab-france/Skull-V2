const sessionList = document.getElementById("sessionList");
const playlistCurrent = document.getElementById("playlistCurrent");
const playlistQueue = document.getElementById("playlistQueue");
const toastBox = document.getElementById("toast");
const cooldownSpan = document.getElementById("cooldownRemaining");
const cooldownHint = document.getElementById("cooldownHint");
const scaryOverlay = document.getElementById("scaryOverlay");
const mainContainer = document.getElementById("mainContainer");
const catalogCard = document.getElementById("catalogCard");
const toggleCatalogBtn = document.getElementById("toggleCatalogBtn");

let sessions = Array.isArray(window.PLAYLIST_SESSIONS)
  ? window.PLAYLIST_SESSIONS
  : [];
let playlistState =
  typeof window.PLAYLIST_STATE === "object" && window.PLAYLIST_STATE
    ? window.PLAYLIST_STATE
    : {};
let cooldownSeconds = window.PLAYLIST_COOLDOWN || 180;
let cooldownRemaining = window.PLAYLIST_COOLDOWN_REMAINING || 0;
let countdownTimer = null;
let clientId = null;
let catalogVisible = false;

function showScaryOverlay() {
  if (scaryOverlay) scaryOverlay.classList.remove("hidden");
}
function hideScaryOverlay() {
  if (scaryOverlay) scaryOverlay.classList.add("hidden");
}

function openCatalog() {
  if (!catalogCard) return;
  catalogCard.classList.remove("hidden");
  if (mainContainer) {
    mainContainer.classList.add("catalog-open");
  }
  if (toggleCatalogBtn) {
    toggleCatalogBtn.textContent = "Fermer la sélection";
    toggleCatalogBtn.setAttribute("aria-expanded", "true");
  }
  catalogVisible = true;
  try {
    catalogCard.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (_) {
    /* ignore */
  }
}

function closeCatalog() {
  if (!catalogCard) return;
  catalogCard.classList.add("hidden");
  if (mainContainer) {
    mainContainer.classList.remove("catalog-open");
  }
  if (toggleCatalogBtn) {
    toggleCatalogBtn.textContent = "+ Ajouter un morceau";
    toggleCatalogBtn.setAttribute("aria-expanded", "false");
  }
  catalogVisible = false;
}

function toggleCatalog() {
  if (catalogVisible) {
    closeCatalog();
  } else {
    openCatalog();
  }
}

function showToast(message, type = "info") {
  if (!toastBox) return;
  toastBox.textContent = "👻 " + message;
  toastBox.classList.remove("error", "success");
  if (type === "error") {
    toastBox.classList.add("error");
  } else if (type === "success") {
    toastBox.classList.add("success");
  }
  toastBox.classList.add("show");
  setTimeout(() => toastBox.classList.remove("show"), 2600);
}

function updateCooldownUI() {
  const remaining = Math.max(0, Math.round(cooldownRemaining));
  if (cooldownSpan) {
    cooldownSpan.textContent = remaining;
  }
  const disable = remaining > 0;
  if (sessionList) {
    sessionList.querySelectorAll("button[data-session]").forEach((btn) => {
      btn.disabled = disable;
    });
  }
  if (disable && cooldownHint) {
    cooldownHint.classList.add("cooldown-active");
  } else if (cooldownHint) {
    cooldownHint.classList.remove("cooldown-active");
  }
}

function startCountdown(fromSeconds) {
  cooldownRemaining = fromSeconds || 0;
  updateCooldownUI();
  if (countdownTimer) {
    clearInterval(countdownTimer);
  }
  if (cooldownRemaining <= 0) {
    countdownTimer = null;
    return;
  }
  countdownTimer = setInterval(() => {
    cooldownRemaining -= 1;
    if (cooldownRemaining <= 0) {
      clearInterval(countdownTimer);
      countdownTimer = null;
      cooldownRemaining = 0;
    }
    updateCooldownUI();
  }, 1000);
}

function renderSessions(items) {
  sessions = Array.isArray(items) ? items : [];
  if (!sessionList) return;
  sessionList.innerHTML = "";
  if (!sessions.length) {
    const empty = document.createElement("li");
    empty.textContent = "🎃 Aucun sortilège musical disponible...";
    empty.className = "available-item";
    sessionList.appendChild(empty);
    return;
  }
  sessions.forEach((session) => {
    const li = document.createElement("li");
    li.className = "available-item";

    const info = document.createElement("div");
    info.className = "available-info";
    const title = document.createElement("strong");
    title.textContent = "🎶 " + (session.display || session.name);
    info.appendChild(title);

    const actions = document.createElement("div");
    actions.className = "available-actions";
    const submitBtn = document.createElement("button");
    submitBtn.textContent = "🔮 Lancer";
    submitBtn.dataset.session = session.name;
    submitBtn.addEventListener("click", () => {
      closeCatalog();
      enqueueSession(session.name);
    });
    actions.appendChild(submitBtn);

    li.appendChild(info);
    li.appendChild(actions);
    sessionList.appendChild(li);
  });
  updateCooldownUI();
}

function renderPlaylist(state) {
  playlistState = state && typeof state === "object" ? state : {};
  if (playlistCurrent) {
    const current = playlistState.current;
    if (current && current.session) {
      playlistCurrent.textContent = `▶️ Envoûtement: ${current.session}`;
    } else if (current && current.item) {
      playlistCurrent.textContent = `▶️ Envoûtement: ${current.item}`;
    } else {
      playlistCurrent.textContent = "😱 Silence terrifiant…";
    }
  }

  if (!playlistQueue) {
    return;
  }
  playlistQueue.innerHTML = "";
  const queue = Array.isArray(playlistState.queue) ? playlistState.queue : [];
  if (!queue.length) {
    const empty = document.createElement("li");
    empty.textContent = "🕸️ File d’attente hantée (vide)";
    empty.className = "playlist-item";
    playlistQueue.appendChild(empty);
    return;
  }
  queue.forEach((entry, index) => {
    const li = document.createElement("li");
    li.className = "playlist-item";
    const label =
      entry.session || entry.title || entry.display || `Sortilège ${index + 1}`;
    li.innerHTML = `<strong>👻 ${index + 1}. ${label}</strong>`;
    playlistQueue.appendChild(li);
  });
}

async function refreshSessions() {
  try {
    const res = await fetch("/api/sessions");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    clientId = data.client_id;
    renderSessions(data.sessions || []);
    renderPlaylist(data.playlist || playlistState);
    startCountdown(data.cooldown_remaining || 0);
  } catch (error) {
    showToast("Impossible de récupérer les sortilèges musicaux", "error");
  }
}

async function enqueueSession(session) {
  if (!session) return;
  showScaryOverlay(); // 👉 affiche la popin immédiatement
  try {
    const res = await fetch("/api/enqueue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session }),
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = payload.error || `Erreur ${res.status}`;
      if (payload.cooldown_remaining != null) {
        startCountdown(payload.cooldown_remaining);
      }
      throw new Error(msg);
    }
    renderPlaylist(payload.playlist || playlistState);
    showToast("Sortilège musical envoyé !", "success");
    startCountdown(payload.cooldown_remaining || cooldownSeconds);
  } catch (error) {
    showToast(
      error.message || "Envoi impossible… les esprits ne répondent pas !",
      "error"
    );
  } finally {
    hideScaryOverlay(); // 👉 la popin se ferme quoi qu’il arrive
  }
}

window.addEventListener("load", () => {
  renderSessions(sessions);
  renderPlaylist(playlistState);
  startCountdown(cooldownRemaining);
  updateCooldownUI();
  closeCatalog();
  if (toggleCatalogBtn) {
    toggleCatalogBtn.addEventListener("click", toggleCatalog);
  }
  refreshSessions();
  setInterval(refreshSessions, 10000);
});
