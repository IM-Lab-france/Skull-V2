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

// Channel checkboxes
const elCbEyeLeft = $("#cbEyeLeft");
const elCbEyeRight = $("#cbEyeRight");
const elCbNeck = $("#cbNeck");
const elCbJaw = $("#cbJaw");

let fileJson = null;
let fileMp3 = null;
let serverReachable = true;
let nextStatusAttempt = 0;

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
  return name
    .trim()
    .replace(/\s+/g, "") // Supprimer tous les espaces
    .replace(/[^a-zA-Z0-9_-]/g, "") // Garder uniquement alphanumériques, _, -
    .substring(0, 50); // Limiter la longueur
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
async function fetchSessions() {
  try {
    const res = await fetch("/sessions");
    const data = await res.json();
    elSelect.innerHTML = "";

    data.sessions.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      elSelect.appendChild(opt);
    });
  } catch (e) {
    console.error("Erreur lors du chargement des sessions:", e);
  }
}
elRefresh?.addEventListener("click", fetchSessions);

// Controls
elPlay?.addEventListener("click", async () => {
  const sid = elSelect.value;
  if (!sid) {
    toast("Aucune session sélectionnée", true);
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
    } else {
      updateStatus();
    }
  } catch (e) {
    toast("Erreur réseau lors de la lecture", true);
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
  updateStatus();
  fetchChannels();
  fetchPitch(); // AJOUTER CETTE LIGNE
  setInterval(updateStatus, 1500);
  updatePitchDisplay(); // AJOUTER CETTE LIGNE
  updatePills();
});



