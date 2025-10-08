// Enhanced front-end for Servo Sync Player UI



// - Drag & drop + buttons for JSON/MP3 selection



// - Upload with progress bar (XHR)



// - Sessions listing + controls + status badge



// - Real-time channel toggles (eyes/neck/jaw) via /channels



// - NOUVEAU: Nom de scène personnalisé







const $ = (sel) => document.querySelector(sel);







// Elements



const elForm = $("#uploadForm");



const elDrop = $("#dropzone");



const elPickJson = $("#btnPickJson");



const elPickMp3 = $("#btnPickMp3");



const elFileJson = $("#fileJson");



const elFileMp3 = $("#fileMp3");



const elPillJson = $("#pillJson .file-name");



const elPillMp3 = $("#pillMp3 .file-name");



const elBtnUpload = $("#btnUpload");



const elProg = $("#uploadProgress");



const elBar = $("#uploadBar");



const elSceneName = $("#sceneName"); // NOUVEAU







const elSelect = $("#sessionSelect");



const elRefresh = $("#refreshBtn");



const elPlay = $("#playBtn");



const elPause = $("#pauseBtn");



const elResume = $("#resumeBtn");



const elStop = $("#stopBtn");



const elStatus = $("#statusBox");



const elBadge = $("#badgeState");



const elConnection = document.getElementById('connectionStatus');



const elConnectionDot = document.getElementById('connectionStatusDot');



const elConnectionText = document.getElementById('connectionStatusText');



const elPlaylistList = $("#playlistList");



const elPlaylistCurrent = $("#playlistCurrent");



const elPlaylistSkip = $("#playlistSkipBtn");



const elPlaylistRefresh = $("#playlistRefreshBtn");



const elDeleteSession = $("#deleteSessionBtn");



const elDeleteModal = $("#deleteSessionModal");



const elDeleteModalName = $("#deleteSessionName");



const elDeleteModalMessage = $("#deleteSessionMessage");



const elDeleteModalConfirm = $("#deleteSessionConfirm");



const elDeleteModalCancel = $("#deleteSessionCancel");



const elDeleteModalClose = $("#deleteSessionClose");



const elVolumeButtons = document.querySelectorAll("[data-volume-action]");



const elRandomToggle = $("#randomModeToggle");



const elRandomHint = $("#randomModeHint");







// Channel checkboxes



const elCbEyeLeft = $("#cbEyeLeft");



const elCbEyeRight = $("#cbEyeRight");



const elCbNeck = $("#cbNeck");



const elCbJaw = $("#cbJaw");







let fileJson = null;



let fileMp3 = null;



let serverReachable = true;



let nextStatusAttempt = 0;



let playlistCurrentData = null;



let playlistQueueData = [];



let playlistFetchInFlight = false;



let lastPlaylistFetch = 0;



let volumeBusy = false;



let randomModeState = {

  enabled: false,

  eligibleCount: null,

  available: true,

  busy: false,

};
function renderRandomModeState() {

  if (elRandomToggle) {

    elRandomToggle.classList.toggle("toggle-active", randomModeState.enabled);

    elRandomToggle.setAttribute(

      "aria-pressed",

      randomModeState.enabled ? "true" : "false"

    );

    const label = randomModeState.enabled

      ? "Mode aleatoire : ON"

      : "Mode aleatoire : OFF";

    elRandomToggle.textContent = label;

    elRandomToggle.disabled = randomModeState.busy;

  }



  if (elRandomHint) {

    if (!randomModeState.available) {

      elRandomHint.textContent =

        "Aucun morceau eligible pour l'aleatoire (hors Accueil).";

    } else {

      if (

        typeof randomModeState.eligibleCount === "number" &&

        randomModeState.eligibleCount >= 0

      ) {

        const count = randomModeState.eligibleCount;

        elRandomHint.textContent =

          count === 1

            ? "1 morceau eligible pour l'aleatoire (hors Accueil)."

            : `${count} morceaux eligibles pour l'aleatoire (hors Accueil).`;

      } else {

        elRandomHint.textContent =

          "Ignorer la selection et choisir un morceau aleatoire (hors Accueil).";

      }

    }

  }

}



function applyRandomModeSnapshot(snapshot) {

  if (snapshot && typeof snapshot.enabled === "boolean") {

    randomModeState.enabled = snapshot.enabled;

  }



  if (snapshot && typeof snapshot.eligible_count === "number") {

    randomModeState.eligibleCount = snapshot.eligible_count;

  } else if (snapshot && Array.isArray(snapshot.eligible)) {

    randomModeState.eligibleCount = snapshot.eligible.length;

  }



  if (snapshot && typeof snapshot.available === "boolean") {

    randomModeState.available = snapshot.available;

  } else if (randomModeState.eligibleCount !== null) {

    randomModeState.available = randomModeState.eligibleCount > 0;

  }



  renderRandomModeState();

}



async function fetchRandomModeState() {

  if (!elRandomToggle) return;



  try {

    const res = await fetch("/random_mode");

    if (!res.ok) {

      return;

    }

    const payload = await res.json().catch(() => ({}));

    applyRandomModeSnapshot(payload);

  } catch (e) {

    // ignore network errors for optional feature

  }

}

function isJson(f) {



  return f && f.name.toLowerCase().endsWith(".json");



}



function isMp3(f) {



  return (



    f && (f.type === "audio/mpeg" || f.name.toLowerCase().endsWith(".mp3"))



  );



}







// NOUVEAU: fonction pour nettoyer le nom de scène



function sanitizeSceneName(name) {
  if (!name || !name.trim()) return null;
  const cleaned = name
    .trim()
    .replace(/[^a-zA-Z0-9 _-]/g, "") // garder alphanumériques, espaces, _, -
    .trim();
  if (!cleaned) return null;
  return cleaned.substring(0, 50); // Limiter la longueur
}







// NOUVEAU: fonction pour extraire la fréquence du nom de fichier JSON



function extractFrequencyFromFilename(filename) {



  const match = filename.match(/(\d+)Hz/i);



  return match ? match[1] : "60"; // 60Hz par défaut



}







function updatePills() {



  elPillJson.textContent = fileJson ? fileJson.name : "aucun";



  elPillMp3.textContent = fileMp3 ? fileMp3.name : "aucun";







  // Validation : nom de scène + fichiers requis



  const sceneName = elSceneName?.value?.trim();



  const hasValidSceneName = sceneName && sanitizeSceneName(sceneName);



  elBtnUpload.disabled = !(fileJson && fileMp3 && hasValidSceneName);



}







function handleFiles(files) {



  for (const f of files) {



    if (isJson(f)) fileJson = f;



    else if (isMp3(f)) fileMp3 = f;



  }



  updatePills();



}







// Validation en temps réel du nom de scène



elSceneName?.addEventListener("input", updatePills);







// Pickers



elPickJson?.addEventListener("click", () => elFileJson.click());



elPickMp3?.addEventListener("click", () => elFileMp3.click());







elFileJson?.addEventListener("change", (e) => {



  fileJson = e.target.files[0] || null;



  updatePills();



});



elRandomToggle?.addEventListener("click", async () => {



  if (randomModeState.busy) {



    return;



  }



  const desired = !randomModeState.enabled;



  randomModeState.busy = true;



  renderRandomModeState();



  try {



    const res = await fetch("/random_mode", {



      method: "POST",



      headers: { "Content-Type": "application/json" },



      body: JSON.stringify({ enabled: desired }),



    });



    const payload = await res.json().catch(() => ({}));



    if (!res.ok) {



      const message =

        (payload && (payload.error || payload.message)) ||

        `Erreur ${res.status}`;



      toast("Erreur mode aleatoire: " + message, true);



      return;



    }



    applyRandomModeSnapshot(payload);



    toast(desired ? "Mode aleatoire active" : "Mode aleatoire desactive");



  } catch (e) {



    toast("Erreur reseau mode aleatoire", true);



  } finally {



    randomModeState.busy = false;



    renderRandomModeState();



  }



});



elFileMp3?.addEventListener("change", (e) => {



  fileMp3 = e.target.files[0] || null;



  updatePills();



});







// Dropzone



["dragenter", "dragover"].forEach((ev) =>



  elDrop?.addEventListener(ev, (e) => {



    e.preventDefault();



    e.stopPropagation();



    elDrop.classList.add("hover");



  })



);



["dragleave", "drop"].forEach((ev) =>



  elDrop?.addEventListener(ev, (e) => {



    e.preventDefault();



    e.stopPropagation();



    elDrop.classList.remove("hover");



  })



);



elDrop?.addEventListener("drop", (e) => {



  handleFiles(e.dataTransfer.files);



});



elDrop?.addEventListener("click", () => elFileJson.click());







// Upload avec nom de scène personnalisé



elForm?.addEventListener("submit", (e) => {



  e.preventDefault();







  // Validation côté client



  const sceneName = elSceneName?.value?.trim();



  const sanitizedName = sanitizeSceneName(sceneName);







  if (!sanitizedName) {



    toast("Veuillez saisir un nom de scène valide", true);



    return;



  }







  if (!(fileJson && fileMp3)) {



    toast("Fichiers JSON et MP3 requis", true);



    return;



  }







  // Extraire la fréquence du nom du fichier JSON



  const frequency = extractFrequencyFromFilename(fileJson.name);







  const fd = new FormData();







  // Renommer les fichiers selon le format demandé



  const mp3Name = `${sanitizedName}.mp3`;



  const jsonName = `${sanitizedName}_${frequency}Hz.json`;







  fd.append("json", fileJson, jsonName);



  fd.append("mp3", fileMp3, mp3Name);



  fd.append("scene_name", sanitizedName); // Nom du répertoire







  const xhr = new XMLHttpRequest();



  xhr.open("POST", "/upload");







  xhr.upload.onprogress = (e) => {



    if (e.lengthComputable) {



      const pct = Math.round((e.loaded / e.total) * 100);



      elProg.hidden = false;



      elBar.style.width = pct + "%";



    }



  };







  xhr.onload = async () => {



    elProg.hidden = true;



    elBar.style.width = "0%";







    if (xhr.status >= 200 && xhr.status < 300) {



      toast(`Session "${sceneName}" uploadée avec succès`);



      await fetchSessions();



      if (elSelect.options.length) {



        elSelect.selectedIndex = elSelect.options.length - 1;



      }







      // Reset du formulaire



      fileJson = null;



      fileMp3 = null;



      elSceneName.value = "";



      elFileJson.value = "";



      elFileMp3.value = "";



      updatePills();



    } else {



      toast("Échec upload: " + xhr.responseText, true);



    }



  };







  xhr.onerror = () => {



    elProg.hidden = true;



    elBar.style.width = "0%";



    toast("Erreur réseau upload", true);



  };







  xhr.send(fd);



});







// Sessions

const deleteButtonDefaultLabel = elDeleteSession?.textContent || "Supprimer la session";

const deleteModalConfirmDefaultLabel = elDeleteModalConfirm?.textContent || "Oui, supprimer";

const deleteModalCancelDefaultLabel = elDeleteModalCancel?.textContent || "Annuler";

let pendingDeleteSession = null;

let deleteModalBusy = false;



function syncDeleteSessionState() {

  if (!elDeleteSession) return;

  const hasSessions = !!(elSelect && elSelect.options && elSelect.options.length);

  elDeleteSession.disabled = !hasSessions;

}



function computeFallbackSession(session) {

  if (!elSelect || !elSelect.options || elSelect.options.length <= 1) {

    return null;

  }

  const options = Array.from(elSelect.options);

  const currentIndex = options.findIndex((opt) => opt.value === session);

  if (currentIndex === -1) {

    return options[0] ? options[0].value : null;

  }

  const nextOption = options[currentIndex + 1] || options[currentIndex - 1];

  return nextOption ? nextOption.value : null;

}



function setDeleteModalBusy(isBusy, message = "") {

  deleteModalBusy = isBusy;

  if (elDeleteModal) {

    elDeleteModal.setAttribute("aria-busy", isBusy ? "true" : "false");

  }

  if (elDeleteModalConfirm) {

    elDeleteModalConfirm.disabled = isBusy;

    elDeleteModalConfirm.textContent = isBusy ? "Suppression..." : deleteModalConfirmDefaultLabel;

  }

  if (elDeleteModalCancel) {

    elDeleteModalCancel.disabled = isBusy;

    elDeleteModalCancel.textContent = deleteModalCancelDefaultLabel;

  }

  if (elDeleteModalClose) {

    elDeleteModalClose.disabled = isBusy;

  }

  if (typeof message === "string" && elDeleteModalMessage) {

    elDeleteModalMessage.textContent = message;

  }

}



function openDeleteModal(session) {

  pendingDeleteSession = session;

  if (elDeleteModalName) {

    elDeleteModalName.textContent = prettifySessionName(session) || session;

  }

  setDeleteModalBusy(false, "");

  if (elDeleteModalMessage) {

    elDeleteModalMessage.textContent = "";

  }

  if (elDeleteModal) {

    elDeleteModal.classList.remove("hidden");

    elDeleteModal.setAttribute("aria-hidden", "false");

  }

  document.body?.classList.add("modal-open");

  window.setTimeout(() => {

    elDeleteModalConfirm?.focus();

  }, 0);

}



function closeDeleteModal() {

  pendingDeleteSession = null;

  if (elDeleteModal) {

    elDeleteModal.classList.add("hidden");

    elDeleteModal.setAttribute("aria-hidden", "true");

  }

  document.body?.classList.remove("modal-open");

  setDeleteModalBusy(false, "");

}



async function fetchSessions(options = {}) {

  if (!elSelect) {

    syncDeleteSessionState();

    return [];

  }



  const { preferred = null, keepCurrent = true } = options;

  const previousValue = keepCurrent ? elSelect.value : null;



  try {

    const res = await fetch("/sessions");

    const data = await res.json();

    const sessions = Array.isArray(data.sessions) ? data.sessions : [];

    elSelect.innerHTML = "";



    sessions.forEach((s) => {

      const opt = document.createElement("option");

      opt.value = s;

      opt.textContent = s;

      elSelect.appendChild(opt);

    });



    if (elSelect.options.length) {

      const target = preferred ?? previousValue;

      if (target) {

        const match = Array.from(elSelect.options).find((opt) => opt.value === target);

        if (match) {

          match.selected = true;

        } else {

          elSelect.selectedIndex = 0;

        }

      } else {

        elSelect.selectedIndex = 0;

      }

    }



    syncDeleteSessionState();

    return sessions;

  } catch (e) {

    console.error("Erreur lors du chargement des sessions:", e);

    elSelect.innerHTML = "";

    syncDeleteSessionState();

    return [];

  }

}



syncDeleteSessionState();

elRefresh?.addEventListener("click", () => fetchSessions({ keepCurrent: true }));



elDeleteSession?.addEventListener("click", () => {

  if (!elSelect) return;

  const session = elSelect.value;

  if (!session) {

    toast("Aucune session sélectionnée", true);

    return;

  }

  openDeleteModal(session);

});



elDeleteModalConfirm?.addEventListener("click", async () => {

  if (!pendingDeleteSession || deleteModalBusy) return;

  const session = pendingDeleteSession;

  const fallbackSession = computeFallbackSession(session);



  setDeleteModalBusy(true, "Suppression en cours...");

  if (elDeleteSession) {

    elDeleteSession.disabled = true;

    elDeleteSession.textContent = "Suppression...";

  }



  try {

    const res = await fetch(`/sessions/${encodeURIComponent(session)}`, {

      method: "DELETE",

    });

    const payload = await res.json().catch(() => ({}));

    if (!res.ok || (payload && payload.error)) {

      const errorMsg = payload?.error || `HTTP ${res.status}`;

      setDeleteModalBusy(false, `Suppression impossible: ${errorMsg}`);

      toast(`Suppression impossible: ${errorMsg}`, true);

      return;

    }



    const removedCount =

      typeof payload?.removed_from_queue === "number" ? payload.removed_from_queue : 0;

    let successMsg = `Session supprimée: ${prettifySessionName(session) || session}`;

    if (removedCount > 0) {

      successMsg += ` (playlist: -${removedCount})`;

    }

    toast(successMsg);



    await fetchSessions({ preferred: fallbackSession, keepCurrent: false });

    await refreshPlaylist(true);

    updateStatus();



    closeDeleteModal();

  } catch (e) {

    console.error("Erreur suppression session:", e);

    setDeleteModalBusy(false, "Erreur réseau lors de la suppression.");

    toast("Erreur réseau suppression session", true);

    return;

  } finally {

    if (elDeleteSession) {

      elDeleteSession.textContent = deleteButtonDefaultLabel;

      elDeleteSession.disabled = false;

    }

    syncDeleteSessionState();

  }

});



elDeleteModalCancel?.addEventListener("click", () => {

  if (!deleteModalBusy) {

    closeDeleteModal();

  }

});



elDeleteModalClose?.addEventListener("click", () => {

  if (!deleteModalBusy) {

    closeDeleteModal();

  }

});



elDeleteModal?.addEventListener("click", (event) => {

  if (!deleteModalBusy && event.target === elDeleteModal) {

    closeDeleteModal();

  }

});



document.addEventListener("keydown", (event) => {

  if (event.key === "Escape" && !deleteModalBusy && elDeleteModal && !elDeleteModal.classList.contains("hidden")) {

    event.preventDefault();

    closeDeleteModal();

  }

});

// ===================== Playlist =====================







function prettifySessionName(name) {



  if (!name) return "";



  return name.replace(/[_-]+/g, " ").trim();



}







function renderPlaylist(payload) {



  playlistCurrentData = payload && payload.current ? payload.current : null;



  playlistQueueData = Array.isArray(payload && payload.queue) ? payload.queue : [];







  if (elPlaylistCurrent) {



    elPlaylistCurrent.innerHTML = "";



    if (playlistCurrentData && playlistCurrentData.session) {



      const strong = document.createElement("strong");



      strong.textContent = "En cours :";



      const span = document.createElement("span");



      span.textContent = " " + prettifySessionName(playlistCurrentData.session);



      elPlaylistCurrent.appendChild(strong);



      elPlaylistCurrent.appendChild(span);



    } else if (playlistQueueData.length) {



      elPlaylistCurrent.textContent = "Lecture en attente...";



    } else {



      elPlaylistCurrent.textContent = "Playlist vide";



    }



  }







  if (elPlaylistList) {



    elPlaylistList.innerHTML = "";



    if (!playlistQueueData.length) {



      const empty = document.createElement("li");



      empty.className = "playlist-empty";



      empty.textContent = "Aucun morceau en attente";



      elPlaylistList.appendChild(empty);



    } else {



      playlistQueueData.forEach((item, index) => {



        const li = document.createElement("li");



        li.className = "playlist-item";



        if (index === 0) li.classList.add("is-next");



        li.dataset.id = String(item.id);







        const name = document.createElement("span");



        name.className = "playlist-name";



        name.textContent = `${index + 1}. ${prettifySessionName(item.session)}`;







        const controls = document.createElement("div");



        controls.className = "playlist-controls";







        const btnUp = document.createElement("button");



        btnUp.className = "playlist-btn";



        btnUp.dataset.action = "up";



        btnUp.textContent = "Monter";







        const btnDown = document.createElement("button");



        btnDown.className = "playlist-btn";



        btnDown.dataset.action = "down";



        btnDown.textContent = "Descendre";







        const btnDelete = document.createElement("button");



        btnDelete.className = "playlist-btn danger";



        btnDelete.dataset.action = "delete";



        btnDelete.textContent = "Supprimer";







        controls.appendChild(btnUp);



        controls.appendChild(btnDown);



        controls.appendChild(btnDelete);







        li.appendChild(name);



        li.appendChild(controls);



        elPlaylistList.appendChild(li);



      });



    }



  }







  if (elPlaylistSkip) {



    const hasSomething =



      !!(playlistCurrentData && playlistCurrentData.session) ||



      playlistQueueData.length > 0;



    elPlaylistSkip.disabled = !hasSomething;



  }



}







async function refreshPlaylist(force = false) {



  if (playlistFetchInFlight) {



    return;



  }



  if (!force && !serverReachable) {



    return;



  }



  const now = Date.now();



  if (!force && now - lastPlaylistFetch < 1200) {



    return;



  }







  playlistFetchInFlight = true;



  lastPlaylistFetch = now;



  try {



    const res = await fetch("/playlist");



    if (!res.ok) {



      throw new Error(`playlist_http_${res.status}`);



    }



    const payload = await res.json();



    lastPlaylistFetch = Date.now();



    renderPlaylist(payload);



  } catch (e) {



    if (force) {



      toast("Playlist indisponible", true);



    }



    playlistQueueData = [];



    playlistCurrentData = null;



    if (elPlaylistCurrent) {



      elPlaylistCurrent.textContent = "Playlist indisponible";



    }



    if (elPlaylistList) {



      elPlaylistList.innerHTML = "";



      const empty = document.createElement("li");



      empty.className = "playlist-empty";



      empty.textContent = "Playlist indisponible";



      elPlaylistList.appendChild(empty);



    }



    if (elPlaylistSkip) {



      elPlaylistSkip.disabled = true;



    }



  } finally {



    playlistFetchInFlight = false;



  }



}







elPlaylistList?.addEventListener("click", async (event) => {



  const btn = event.target.closest("button[data-action]");



  if (!btn) return;



  const itemEl = btn.closest("li[data-id]");



  if (!itemEl) return;



  const id = parseInt(itemEl.dataset.id, 10);



  if (Number.isNaN(id)) return;



  const action = btn.dataset.action;







  try {



    if (action === "delete") {



      const res = await fetch(`/playlist/${id}`, { method: "DELETE" });



      if (!res.ok) {



        const txt = await res.text();



        throw new Error(txt);



      }



    } else if (action === "up" || action === "down") {



      const res = await fetch(`/playlist/${id}/move`, {



        method: "POST",



        headers: { "Content-Type": "application/json" },



        body: JSON.stringify({ direction: action }),



      });



      if (!res.ok) {



        const txt = await res.text();



        throw new Error(txt);



      }



    }



    await refreshPlaylist(true);



  } catch (e) {



    toast("Erreur playlist: " + e, true);



  }



});







elPlaylistSkip?.addEventListener("click", async () => {



  elPlaylistSkip.disabled = true;



  try {



    const res = await fetch("/playlist/skip", { method: "POST" });



    if (!res.ok) {



      const txt = await res.text();



      throw new Error(txt);



    }



    const payload = await res.json().catch(() => ({}));



    if (payload && payload.status === "idle") {



      toast("Playlist vide", true);



    }



    await refreshPlaylist(true);



    updateStatus();



  } catch (e) {



    toast("Erreur skip playlist: " + e, true);



  } finally {



    elPlaylistSkip.disabled = false;



  }



});







elPlaylistRefresh?.addEventListener("click", () => {



  refreshPlaylist(true);



});







// Controls



elPlay?.addEventListener("click", async () => {



  const sid = elSelect.value;



  if (!sid) {



    toast("Aucune session selectionnee", true);



    return;



  }







  try {



    const res = await fetch("/play", {



      method: "POST",



      headers: { "Content-Type": "application/json" },



      body: JSON.stringify({ session: sid }),



    });







    if (!res.ok) {



      const errorText = await res.text();



      toast("Erreur lecture: " + errorText, true);



      return;



    }







    const payload = await res.json().catch(() => ({}));



    if (payload && typeof payload === "object" && payload.random_mode) {



      applyRandomModeSnapshot(payload.random_mode);



    }



    const randomInfo =

      payload && typeof payload === "object" && payload.random_mode

        ? payload.random_mode

        : {};



    const actualSession =

      (payload && typeof payload === "object" && payload.session) || sid;



    const randomEnabled = Boolean(randomInfo && randomInfo.enabled);



    const randomApplied = Boolean(randomEnabled && randomInfo.applied);



    const randomUnavailable =

      randomEnabled && randomInfo.available === false;



    let message = null;



    if (payload.status === "queued") {



      const pos = payload.position ? ` (position ${payload.position})` : "";



      if (randomApplied) {



        const label =

          (randomInfo && randomInfo.selected) || actualSession || "inconnu";



        message = `Ajoute en mode aleatoire${pos} : ${label}`;



      } else {



        message = "Session ajoutee a la playlist" + pos;



        if (randomUnavailable) {



          message += " (aleatoire indisponible)";



        }



      }



    } else if (payload.status === "playing") {



      if (randomApplied) {



        const label =

          (randomInfo && randomInfo.selected) || actualSession || "inconnu";



        message = "Lecture aleatoire lancee : " + label;



      } else {



        message = "Lecture demarree";



        if (randomUnavailable) {



          message += " (aleatoire indisponible)";



        }



      }



    } else if (randomUnavailable) {



      message =

        "Mode aleatoire actif mais aucun morceau eligible (hors Accueil).";



    }



    if (message) {



      toast(message);



    }







    await refreshPlaylist(true);



    updateStatus();



  } catch (e) {



    toast("Erreur reseau lors de la lecture", true);



  }



});











elPause?.addEventListener("click", async () => {



  try {



    await fetch("/pause", { method: "POST" });



    updateStatus();



  } catch (e) {



    toast("Erreur pause", true);



  }



});







elResume?.addEventListener("click", async () => {



  try {



    await fetch("/resume", { method: "POST" });



    updateStatus();



  } catch (e) {



    toast("Erreur resume", true);



  }



});







elStop?.addEventListener("click", async () => {



  try {



    await fetch("/stop", { method: "POST" });



    await refreshPlaylist(true);



    updateStatus();



  } catch (e) {



    toast("Erreur stop", true);



  }



});











// Status



async function updateStatus() {



  const now = Date.now();



  if (!serverReachable && now < nextStatusAttempt) {



    return;



  }







  try {



    const res = await fetch("/status");



    if (!res.ok) {



      throw new Error(`status_http_${res.status}`);



    }



    const st = await res.json();



    elStatus.textContent = JSON.stringify(st, null, 2);



    if (st && typeof st === "object" && st.random_mode) {

      applyRandomModeSnapshot(st.random_mode);

    }







    const txt = st.running ? (st.paused ? "PAUSED" : "PLAYING") : "IDLE";



    elBadge.textContent = txt;



    elBadge.className =



      "badge " +



      (txt === "PLAYING"



        ? "is-playing"



        : txt === "PAUSED"



        ? "is-paused"



        : "is-idle");







    if (elConnection) {



      elConnection.classList.remove("offline");



      elConnection.classList.add("online");



    }



    if (elConnectionText) {



      elConnectionText.textContent = "Statut : connecte";



    }



    if (elConnectionDot) {



      elConnectionDot.setAttribute("aria-label", "connecte");



    }







    if (!serverReachable) {



      toast("Skull en ligne");



    }



    serverReachable = true;



    nextStatusAttempt = Date.now() + 1500;



    refreshPlaylist();



  } catch (e) {



    if (serverReachable) {



      toast("Skull non disponible", true);



      console.warn("Skull unreachable:", e);



    }



    serverReachable = false;



    nextStatusAttempt = Date.now() + 5000;







    elStatus.textContent = "Skull non disponible (serveur injoignable)";



    elBadge.textContent = "OFFLINE";



    elBadge.className = "badge is-offline";



    if (elPlaylistCurrent) {



      elPlaylistCurrent.textContent = "Playlist indisponible";



    }



    if (elPlaylistList) {



      elPlaylistList.innerHTML = "";



      const empty = document.createElement("li");



      empty.className = "playlist-empty";



      empty.textContent = "Playlist indisponible";



      elPlaylistList.appendChild(empty);



    }



    if (elPlaylistSkip) {



      elPlaylistSkip.disabled = true;



    }







    if (elConnection) {



      elConnection.classList.remove("online");



      elConnection.classList.add("offline");



    }



    if (elConnectionText) {



      elConnectionText.textContent = "Statut : hors ligne";



    }



    if (elConnectionDot) {



      elConnectionDot.setAttribute("aria-label", "hors ligne");



    }



  }



}







function setVolumeButtonsDisabled(disabled) {



  if (!elVolumeButtons || !elVolumeButtons.length) return;



  elVolumeButtons.forEach((btn) => {



    if (btn) btn.disabled = disabled;



  });



}







async function sendVolumeAction(action) {



  if (!action || volumeBusy) return;



  volumeBusy = true;



  setVolumeButtonsDisabled(true);



  try {



    const response = await fetch("/volume", {



      method: "POST",



      headers: { "Content-Type": "application/json" },



      body: JSON.stringify({ action }),



    });



    const payload = await response.json().catch(() => ({}));



    const ok = response.ok && payload && payload.ok !== false;



    if (!ok) {



      const message =



        (payload && (payload.error || payload.message)) ||



        `Commande volume échouée (${response.status})`;



      toast(message, true);



    } else {



      const message =



        (payload && payload.message) ||



        (action === "mute" ? "Volume coupé" : "Volume ajusté");



      toast(message);



    }



  } catch (error) {



    toast("Erreur réseau /volume", true);



  } finally {



    setVolumeButtonsDisabled(false);



    volumeBusy = false;



  }



}







function toast(msg, isErr = false) {



  const t = document.createElement("div");



  t.className = "toast" + (isErr ? " err" : "");



  t.textContent = msg;



  document.body.appendChild(t);



  setTimeout(() => t.classList.add("show"), 10);



  setTimeout(() => {



    t.classList.remove("show");



    t.addEventListener("transitionend", () => t.remove(), { once: true });



  }, 2500);



}







// ===================== Channels API =====================



function readChannelsFromUI() {



  return {



    eye_left: !!elCbEyeLeft?.checked,



    eye_right: !!elCbEyeRight?.checked,



    neck: !!elCbNeck?.checked,



    jaw: !!elCbJaw?.checked,



  };



}







function setChannelsToUI(c) {



  if (elCbEyeLeft) elCbEyeLeft.checked = !!c.eye_left;



  if (elCbEyeRight) elCbEyeRight.checked = !!c.eye_right;



  if (elCbNeck) elCbNeck.checked = !!c.neck;



  if (elCbJaw) elCbJaw.checked = !!c.jaw;



}







async function fetchChannels() {



  try {



    const res = await fetch("/channels");



    if (!res.ok) return;



    const c = await res.json();



    setChannelsToUI(c);



  } catch (e) {



    // Ignorer si l'endpoint n'est pas disponible



  }



}







async function postChannels(c) {



  try {



    const res = await fetch("/channels", {



      method: "POST",



      headers: { "Content-Type": "application/json" },



      body: JSON.stringify(c),



    });



    if (!res.ok) {



      const txt = await res.text();



      toast("Erreur canaux: " + txt, true);



    }



  } catch (e) {



    toast("Erreur réseau /channels", true);



  }



}







// Attach change handlers



[elCbEyeLeft, elCbEyeRight, elCbNeck, elCbJaw].forEach((cb) => {



  cb?.addEventListener("change", () => postChannels(readChannelsFromUI()));



});







// ===================== Pitch API =====================



const pitchSliders = {



  jaw: $("#pitchJaw"),



  eye_left: $("#pitchEyeLeft"),



  eye_right: $("#pitchEyeRight"),



  neck_pan: $("#pitchNeck"),



};







function updatePitchDisplay() {



  Object.entries(pitchSliders).forEach(([servo, slider]) => {



    if (slider) {



      const valueSpan = slider.nextElementSibling;



      if (valueSpan) valueSpan.textContent = slider.value + "°";



    }



  });



}







async function fetchPitch() {



  try {



    const res = await fetch("/pitch");



    if (!res.ok) return;



    const offsets = await res.json();







    Object.entries(pitchSliders).forEach(([servo, slider]) => {



      if (slider && servo in offsets) {



        slider.value = offsets[servo];



      }



    });



    updatePitchDisplay();



  } catch (e) {



    // Ignorer si l'endpoint n'est pas disponible



  }



}







async function postPitch() {



  const offsets = {};



  Object.entries(pitchSliders).forEach(([servo, slider]) => {



    if (slider) offsets[servo] = parseFloat(slider.value);



  });







  try {



    const res = await fetch("/pitch", {



      method: "POST",



      headers: { "Content-Type": "application/json" },



      body: JSON.stringify(offsets),



    });



    if (!res.ok) {



      const txt = await res.text();



      toast("Erreur pitch: " + txt, true);



    }



  } catch (e) {



    toast("Erreur réseau /pitch", true);



  }



}







// Attach pitch change handlers



Object.values(pitchSliders).forEach((slider) => {



  if (slider) {



    slider.addEventListener("input", updatePitchDisplay);



    slider.addEventListener("change", postPitch);



  }



});







// Boot



window.addEventListener("load", () => {



  fetchSessions();



  fetchRandomModeState();



  updateStatus();



  fetchChannels();



  fetchPitch(); // AJOUTER CETTE LIGNE



  setInterval(updateStatus, 1500);



  updatePitchDisplay(); // AJOUTER CETTE LIGNE



  refreshPlaylist(true);







  if (elVolumeButtons && elVolumeButtons.length) {



    elVolumeButtons.forEach((btn) => {



      btn.addEventListener("click", () => {



        const action = btn.dataset.volumeAction;



        sendVolumeAction(action);



      });



    });



  }







  updatePills();



});















