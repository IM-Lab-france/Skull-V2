// Enhanced front-end for Servo Sync Player UI

// - Drag & drop + buttons for JSON/MP3 selection

// - Upload with progress bar (XHR)

// - Sessions listing + controls + status badge

// - Real-time channel toggles (eyes/neck/jaw) via /channels

// - NOUVEAU: Nom de scÃ¨ne personnalisÃ©

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

const elConnection = document.getElementById("connectionStatus");

const elConnectionDot = document.getElementById("connectionStatusDot");

const elConnectionText = document.getElementById("connectionStatusText");

const elPlaylistList = $("#playlistList");

const elPlaylistCurrent = $("#playlistCurrent");

const elPlaylistSkip = $("#playlistSkipBtn");

const elPlaylistRefresh = $("#playlistRefreshBtn");

const elCategoryManager = document.getElementById("categoryManager");

const elCategoryList = document.getElementById("categoryManagerList");

const elCategoryAddInput = document.getElementById("categoryAddInput");

const elCategoryAddBtn = document.getElementById("categoryAddBtn");

const elCategoryStatus = document.getElementById("categoryManagerStatus");

const elDeleteSession = $("#deleteSessionBtn");

const elDeleteModal = $("#deleteSessionModal");

const elDeleteModalName = $("#deleteSessionName");

const elDeleteModalMessage = $("#deleteSessionMessage");

const elDeleteModalConfirm = $("#deleteSessionConfirm");

const elDeleteModalCancel = $("#deleteSessionCancel");

const elDeleteModalClose = $("#deleteSessionClose");

const elVolumeButtons = document.querySelectorAll("[data-volume-action]");
const elVolumeSlider = document.getElementById("volumeSlider");
const elVolumeSliderValue = document.getElementById("volumeSliderValue");

const elBtStatus = document.getElementById("bluetoothStatus");

const elBtStatusDot = document.getElementById("bluetoothStatusDot");

const elBtStatusText = document.getElementById("bluetoothStatusText");

const elBtTopStatus = document.getElementById("bluetoothTopStatus");

const elBtTopStatusDot = document.getElementById("bluetoothTopStatusDot");

const elBtTopStatusText = document.getElementById("bluetoothTopStatusText");

const elShuffleAllBtn = document.getElementById("shuffleAllBtn");

const elRestartServiceBtn = document.getElementById("restartServiceBtn");

const elRestartBluetoothBtn = document.getElementById("restartBluetoothBtn");

const elEsp32Card = document.getElementById("esp32Card");

const elEsp32StatusDot = document.getElementById("esp32StatusDot");

const elEsp32StatusText = document.getElementById("esp32StatusText");

const elEsp32TopStatus = document.getElementById("esp32TopStatus");

const elEsp32TopStatusDot = document.getElementById("esp32TopStatusDot");

const elEsp32TopStatusText = document.getElementById("esp32TopStatusText");

const elEsp32StatusRefresh = document.getElementById("esp32StatusRefreshBtn");

const elEsp32ConfigForm = document.getElementById("esp32ConfigForm");

const elEsp32Host = document.getElementById("esp32Host");

const elEsp32Port = document.getElementById("esp32Port");

const elEsp32Enabled = document.getElementById("esp32Enabled");

const elEsp32RelayOn = document.getElementById("esp32RelayOnBtn");

const elEsp32RelayOff = document.getElementById("esp32RelayOffBtn");

const elEsp32AutoRelayToggle = document.getElementById("esp32AutoRelayToggle");

const elEsp32Restart = document.getElementById("esp32RestartBtn");

const elEsp32RelayState = document.getElementById("esp32RelayState");

const elEsp32AutoRelayState = document.getElementById("esp32AutoRelayState");

const elEsp32CurrentSession = document.getElementById("esp32CurrentSession");

const elEsp32WifiInfo = document.getElementById("esp32WifiInfo");

const elEsp32StatusRaw = document.getElementById("esp32StatusRaw");

const elEsp32ButtonsRefresh = document.getElementById("esp32ButtonsRefreshBtn");

const elEsp32ButtonsContainer = document.getElementById(
  "esp32ButtonsContainer"
);

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

let sessionCategories = new Map();

let availableCategories = [];

let categoryAddBusy = false;

let cachedSessionNames = [];

let playlistFetchInFlight = false;

let lastPlaylistFetch = 0;

let volumeBusy = false;
let volumePendingValue = null;
let volumeSliderActive = false;
let volumeSliderDebounce = null;

let shuffleBusy = false;

let restartServiceBusy = false;

let restartBluetoothBusy = false;

let randomModeState = {
  enabled: false,

  eligibleCount: null,

  available: true,

  busy: false,
};

const ESP32_STATUS_INTERVAL = 5000;

const ESP32_DEFAULT_BUTTON_COUNT = 3;
const ESP32_ALL_CATEGORY = "Tous";

function normalizeEsp32ButtonCount(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) {
    return ESP32_DEFAULT_BUTTON_COUNT;
  }
  return Math.min(
    ESP32_DEFAULT_BUTTON_COUNT,
    Math.max(1, Math.floor(num))
  );
}

let esp32Config = {
  host: "",

  port: 80,

  enabled: false,

  buttonCount: ESP32_DEFAULT_BUTTON_COUNT,
};

let esp32StatusTimerId = null;

let esp32StatusSnapshot = null;

let esp32ButtonAssignments = [];

const esp32ButtonComponents = new Map();

let esp32Busy = {
  status: false,

  relay: false,

  auto: false,

  restart: false,

  config: false,

  buttons: false,
};

let statusFetchInFlight = false;
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

// NOUVEAU: fonction pour nettoyer le nom de scÃ¨ne

function sanitizeSceneName(name) {
  if (!name || !name.trim()) return null;
  const cleaned = name
    .trim()
    .replace(/[^a-zA-Z0-9 _-]/g, "") // garder alphanumÃ©riques, espaces, _, -
    .trim();
  if (!cleaned) return null;
  return cleaned.substring(0, 50); // Limiter la longueur
}

// NOUVEAU: fonction pour extraire la frÃ©quence du nom de fichier JSON

function extractFrequencyFromFilename(filename) {
  const match = filename.match(/(\d+)Hz/i);

  return match ? match[1] : "60"; // 60Hz par dÃ©faut
}

function updatePills() {
  elPillJson.textContent = fileJson ? fileJson.name : "aucun";

  elPillMp3.textContent = fileMp3 ? fileMp3.name : "aucun";

  // Validation : nom de scÃ¨ne + fichiers requis

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

// Validation en temps rÃ©el du nom de scÃ¨ne

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

// Upload avec nom de scÃ¨ne personnalisÃ©

elForm?.addEventListener("submit", (e) => {
  e.preventDefault();

  // Validation cÃ´tÃ© client

  const sceneName = elSceneName?.value?.trim();

  const sanitizedName = sanitizeSceneName(sceneName);

  if (!sanitizedName) {
    toast("Veuillez saisir un nom de scÃ¨ne valide", true);

    return;
  }

  if (!(fileJson && fileMp3)) {
    toast("Fichiers JSON et MP3 requis", true);

    return;
  }

  // Extraire la frÃ©quence du nom du fichier JSON

  const frequency = extractFrequencyFromFilename(fileJson.name);

  const fd = new FormData();

  // Renommer les fichiers selon le format demandÃ©

  const mp3Name = `${sanitizedName}.mp3`;

  const jsonName = `${sanitizedName}_${frequency}Hz.json`;

  fd.append("json", fileJson, jsonName);

  fd.append("mp3", fileMp3, mp3Name);

  fd.append("scene_name", sanitizedName); // Nom du rÃ©pertoire

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
      toast(`Session "${sceneName}" uploadÃ©e avec succÃ¨s`);

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
      toast("Ã‰chec upload: " + xhr.responseText, true);
    }
  };

  xhr.onerror = () => {
    elProg.hidden = true;

    elBar.style.width = "0%";

    toast("Erreur rÃ©seau upload", true);
  };

  xhr.send(fd);
});

// Sessions

const deleteButtonDefaultLabel =
  elDeleteSession?.textContent || "Supprimer la session";

const deleteModalConfirmDefaultLabel =
  elDeleteModalConfirm?.textContent || "Oui, supprimer";

const deleteModalCancelDefaultLabel =
  elDeleteModalCancel?.textContent || "Annuler";

let pendingDeleteSession = null;

let deleteModalBusy = false;

function syncDeleteSessionState() {
  if (!elDeleteSession) return;

  const hasSessions = !!(
    elSelect &&
    elSelect.options &&
    elSelect.options.length
  );

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

    elDeleteModalConfirm.textContent = isBusy
      ? "Suppression..."
      : deleteModalConfirmDefaultLabel;
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

function sanitizeCategoryList(rawCategories) {
  if (!Array.isArray(rawCategories)) {
    return [];
  }

  const seen = new Set();
  const result = [];

  rawCategories.forEach((item) => {
    if (typeof item !== "string") {
      return;
    }

    const value = item.trim();
    if (!value) {
      return;
    }

    const key = value.toLowerCase();
    if (seen.has(key)) {
      return;
    }

    seen.add(key);
    result.push(value);
  });

  return result;
}

function setCategoryStatus(message = "", isError = false) {
  if (!elCategoryStatus) {
    return;
  }

  elCategoryStatus.textContent = message || "";
  elCategoryStatus.classList.remove("is-error", "is-success");

  if (!message) {
    return;
  }

  elCategoryStatus.classList.add(isError ? "is-error" : "is-success");
}

function getCategoryForSession(sessionName, fallbackCategory = null) {
  if (!sessionName) {
    return fallbackCategory || null;
  }

  if (sessionCategories && sessionCategories.has(sessionName)) {
    const stored = sessionCategories.get(sessionName);
    if (typeof stored === "string" && stored.trim()) {
      return stored;
    }
    return null;
  }

  if (typeof fallbackCategory === "string" && fallbackCategory.trim()) {
    return fallbackCategory;
  }

  return null;
}

function formatSessionLabel(sessionName, fallbackCategory = null) {
  const displayName = prettifySessionName(sessionName) || sessionName || "";
  const category = getCategoryForSession(sessionName, fallbackCategory);
  if (category) {
    return `[${category}] ${displayName}`;
  }
  return displayName;
}

function rebuildSessionSelect(sessionNames, preferredValue, previousValue) {
  if (!elSelect) {
    return;
  }

  elSelect.innerHTML = "";

  if (!Array.isArray(sessionNames) || !sessionNames.length) {
    return;
  }

  const grouped = new Map();

  sessionNames.forEach((name) => {
    const key = getCategoryForSession(name) || "";
    if (!grouped.has(key)) {
      grouped.set(key, []);
    }
    grouped.get(key).push(name);
  });

  const categoryOrder = [];

  availableCategories.forEach((category) => {
    if (grouped.has(category)) {
      categoryOrder.push(category);
    }
  });

  if (grouped.has("")) {
    categoryOrder.push("");
  }

  grouped.forEach((_, key) => {
    if (!categoryOrder.includes(key)) {
      categoryOrder.push(key);
    }
  });

  const useGrouping = categoryOrder.length > 1;
  const targetValue = preferredValue ?? previousValue ?? null;

  const sortSessions = (items) =>
    items.slice().sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));

  categoryOrder.forEach((categoryKey) => {
    const names = sortSessions(grouped.get(categoryKey) || []);

    if (useGrouping) {
      const optgroup = document.createElement("optgroup");
      optgroup.label = categoryKey || "Sans cat\u00E9gorie";

      names.forEach((name) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = formatSessionLabel(name);
        optgroup.appendChild(option);
      });

      elSelect.appendChild(optgroup);
    } else {
      names.forEach((name) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = formatSessionLabel(name);
        elSelect.appendChild(option);
      });
    }
  });

  if (!elSelect.options.length) {
    return;
  }

  if (targetValue) {
    const match = Array.from(elSelect.options).find(
      (opt) => opt.value === targetValue
    );
    if (match) {
      match.selected = true;
      return;
    }
  }

  elSelect.selectedIndex = 0;
}

function populateCategorySelect(select, selectedValue) {
  if (!select) {
    return;
  }

  const normalized = typeof selectedValue === "string" ? selectedValue : "";

  select.innerHTML = "";

  const optionNone = document.createElement("option");
  optionNone.value = "";
  optionNone.textContent = "-- Aucun --";
  select.appendChild(optionNone);

  const values = [...availableCategories];
  if (normalized && !values.some((item) => item === normalized)) {
    values.push(normalized);
  }

  values.forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    select.appendChild(option);
  });

  select.value = normalized;
  select.dataset.currentCategory = normalized;
}

function renderCategoryManager(sessionNames) {
  if (!elCategoryList) {
    return;
  }

  elCategoryList.innerHTML = "";

  if (!Array.isArray(sessionNames) || !sessionNames.length) {
    const empty = document.createElement("p");
    empty.className = "category-empty";
    empty.textContent = "Aucune session disponible pour le moment.";
    elCategoryList.appendChild(empty);
    return;
  }

  const sorted = sessionNames
    .slice()
    .sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));

  sorted.forEach((session) => {
    const row = document.createElement("div");
    row.className = "category-row";
    row.dataset.session = session;

    const label = document.createElement("span");
    label.className = "category-row-name";
    label.textContent = prettifySessionName(session) || session;
    row.appendChild(label);

    const select = document.createElement("select");
    select.className = "select category-row-select";
    select.dataset.session = session;
    populateCategorySelect(select, getCategoryForSession(session));
    row.appendChild(select);

    elCategoryList.appendChild(row);
  });
}

function setCategoryRowBusy(row, busy) {
  if (!row) {
    return;
  }

  row.classList.toggle("category-row--busy", Boolean(busy));
}

function refreshAllCategorySelectOptions() {
  if (!elCategoryList) {
    return;
  }

  Array.from(elCategoryList.querySelectorAll(".category-row-select")).forEach(
    (select) => {
      const session = select.dataset.session;
      populateCategorySelect(select, getCategoryForSession(session));
    }
  );
  populateEsp32ButtonOptions();
}

function updateEntryCategory(entry, session, category) {
  if (!entry || entry.session !== session) {
    return entry;
  }

  return {
    ...entry,
    category: category || null,
  };
}

function updateCachedPlaylistCategories(session, category) {
  if (playlistCurrentData) {
    playlistCurrentData = updateEntryCategory(playlistCurrentData, session, category);
  }

  if (Array.isArray(playlistQueueData) && playlistQueueData.length) {
    playlistQueueData = playlistQueueData.map((item) =>
      updateEntryCategory(item, session, category)
    );
  }

  if (elPlaylistCurrent || elPlaylistList) {
    renderPlaylist({
      current: playlistCurrentData,
      queue: playlistQueueData,
    });
  }
}

async function handleCategoryAdd() {
  if (!elCategoryAddInput) {
    return;
  }

  const rawName = elCategoryAddInput.value.trim();
  if (!rawName) {
    toast("Nom de cat\u00E9gorie vide", true);
    setCategoryStatus("Nom de cat\u00E9gorie vide", true);
    elCategoryAddInput.focus();
    return;
  }

  if (categoryAddBusy) {
    return;
  }

  categoryAddBusy = true;
  setCategoryStatus(`Ajout de "${rawName}"...`);

  if (elCategoryAddBtn) {
    elCategoryAddBtn.disabled = true;
  }

  try {
    const res = await fetch("/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: rawName }),
    });

    const payload = await res.json().catch(() => ({}));

    if (!res.ok) {
      const message =
        (payload && (payload.error || payload.message)) ||
        `Erreur ${res.status}`;
      throw new Error(message);
    }

    const created = res.status === 201;

    availableCategories = sanitizeCategoryList(payload.categories);
    const storedName =
      typeof payload.category === "string" && payload.category.trim()
        ? payload.category.trim()
        : rawName;

    refreshAllCategorySelectOptions();

    if (created) {
      setCategoryStatus(`Cat\u00E9gorie "${storedName}" ajout\u00E9e`);
    } else {
      setCategoryStatus(`Cat\u00E9gorie "${storedName}" d\u00E9j\u00E0 disponible`);
    }

    elCategoryAddInput.value = "";
    elCategoryAddInput.focus();
  } catch (error) {
    const message =
      error && error.message
        ? error.message
        : "Erreur lors de l'ajout de la cat\u00E9gorie";
    toast(message, true);
    setCategoryStatus(message, true);
  } finally {
    categoryAddBusy = false;
    if (elCategoryAddBtn) {
      elCategoryAddBtn.disabled = false;
    }
  }
}

async function persistSessionCategory(select, session, nextValue, previousValue) {
  if (!select || !session) {
    return;
  }

  const normalized =
    typeof nextValue === "string" && nextValue.trim() ? nextValue.trim() : "";

  const row = select.closest(".category-row");

  setCategoryRowBusy(row, true);
  select.disabled = true;
  setCategoryStatus(
    `Mise \u00E0 jour de "${prettifySessionName(session) || session}"...`
  );

  try {
    const res = await fetch(
      `/sessions/${encodeURIComponent(session)}/category`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: normalized || null }),
      }
    );

    const payload = await res.json().catch(() => ({}));

    if (!res.ok) {
      const message =
        (payload && (payload.error || payload.message)) ||
        `Erreur ${res.status}`;
      throw new Error(message);
    }

    const storedCategory =
      typeof payload.category === "string" && payload.category.trim()
        ? payload.category.trim()
        : null;

    availableCategories = sanitizeCategoryList(payload.categories);
    sessionCategories.set(session, storedCategory);

    populateCategorySelect(select, storedCategory);
    refreshAllCategorySelectOptions();

    const currentValue = elSelect ? elSelect.value : null;
    rebuildSessionSelect(cachedSessionNames, currentValue, currentValue);

    updateCachedPlaylistCategories(session, storedCategory);

    const prettyName = prettifySessionName(session) || session;
    if (storedCategory) {
      setCategoryStatus(
        `Cat\u00E9gorie "${storedCategory}" appliqu\u00E9e \u00E0 ${prettyName}`
      );
    } else {
      setCategoryStatus(`Cat\u00E9gorie supprim\u00E9e pour ${prettyName}`);
    }

    select.focus();
  } catch (error) {
    const message =
      error && error.message
        ? error.message
        : "Erreur lors de la mise \u00E0 jour de la cat\u00E9gorie";
    toast(message, true);
    setCategoryStatus(message, true);
    populateCategorySelect(select, previousValue || "");
  } finally {
    select.disabled = false;
    setCategoryRowBusy(row, false);
  }
}

function handleCategorySelectChange(event) {
  const target = event.target;

  if (!target || !(target instanceof HTMLSelectElement)) {
    return;
  }

  if (!target.classList.contains("category-row-select")) {
    return;
  }

  const session = target.dataset.session;
  if (!session) {
    return;
  }

  const previousValue = target.dataset.currentCategory || "";
  const nextValue = target.value || "";

  if (previousValue === nextValue) {
    return;
  }

  persistSessionCategory(target, session, nextValue, previousValue);
}

async function fetchSessions(options = {}) {
  if (!elSelect) {
    syncDeleteSessionState();

    return [];
  }

  const { preferred = null, keepCurrent = true } = options;

  const previousValue = keepCurrent ? elSelect.value : null;

  setCategoryStatus("");

  try {
    const res = await fetch("/sessions");

    const data = await res.json();

    const rawSessions = Array.isArray(data.sessions) ? data.sessions : [];
    const sessionNames = [];
    const categoriesMap = new Map();
    const seen = new Set();

    rawSessions.forEach((entry) => {
      if (entry && typeof entry === "object") {
        const name =
          typeof entry.name === "string"
            ? entry.name
            : typeof entry.session === "string"
            ? entry.session
            : null;
        if (!name || seen.has(name)) {
          return;
        }
        seen.add(name);
        sessionNames.push(name);
        const category =
          typeof entry.category === "string" && entry.category.trim()
            ? entry.category.trim()
            : null;
        categoriesMap.set(name, category);
        return;
      }

      if (typeof entry === "string" && !seen.has(entry)) {
        seen.add(entry);
        sessionNames.push(entry);
        categoriesMap.set(entry, null);
      }
    });

    cachedSessionNames = sessionNames.slice();
    sessionCategories = categoriesMap;
    availableCategories = sanitizeCategoryList(data.categories);

    rebuildSessionSelect(sessionNames, preferred ?? previousValue, previousValue);

    populateEsp32ButtonOptions();

    renderCategoryManager(sessionNames);

    syncDeleteSessionState();

    return sessionNames;
  } catch (e) {
    console.error("Erreur lors du chargement des sessions:", e);

    if (elSelect) {
      elSelect.innerHTML = "";
    }

    sessionCategories = new Map();
    availableCategories = [];
    cachedSessionNames = [];

    populateEsp32ButtonOptions();

    renderCategoryManager([]);

    syncDeleteSessionState();

    setCategoryStatus("Impossible de charger les sessions", true);

    return [];
  }
}

elCategoryAddBtn?.addEventListener("click", () => {
  handleCategoryAdd();
});

elCategoryAddInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    handleCategoryAdd();
  }
});

elCategoryList?.addEventListener("change", handleCategorySelectChange);

syncDeleteSessionState();

elRefresh?.addEventListener("click", () =>
  fetchSessions({ keepCurrent: true })
);

elDeleteSession?.addEventListener("click", () => {
  if (!elSelect) return;

  const session = elSelect.value;

  if (!session) {
    toast("Aucune session sÃ©lectionnÃ©e", true);

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
      typeof payload?.removed_from_queue === "number"
        ? payload.removed_from_queue
        : 0;

    let successMsg = `Session supprimÃ©e: ${
      prettifySessionName(session) || session
    }`;

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

    setDeleteModalBusy(false, "Erreur rÃ©seau lors de la suppression.");

    toast("Erreur rÃ©seau suppression session", true);

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
  if (
    event.key === "Escape" &&
    !deleteModalBusy &&
    elDeleteModal &&
    !elDeleteModal.classList.contains("hidden")
  ) {
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

  playlistQueueData = Array.isArray(payload && payload.queue)
    ? payload.queue
    : [];

  if (
    playlistCurrentData &&
    playlistCurrentData.session &&
    typeof playlistCurrentData.category === "string"
  ) {
    sessionCategories.set(
      playlistCurrentData.session,
      playlistCurrentData.category
    );
  }

  if (Array.isArray(playlistQueueData) && playlistQueueData.length) {
    playlistQueueData.forEach((item) => {
      if (item && item.session && typeof item.category === "string") {
        sessionCategories.set(item.session, item.category);
      }
    });
  }

  if (elPlaylistCurrent) {
    elPlaylistCurrent.innerHTML = "";

    if (playlistCurrentData && playlistCurrentData.session) {
      const strong = document.createElement("strong");

      strong.textContent = "En cours :";

      const span = document.createElement("span");

      span.textContent =
        " " +
        formatSessionLabel(
          playlistCurrentData.session,
          playlistCurrentData.category
        );

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

        name.textContent = `${index + 1}. ${formatSessionLabel(
          item.session,
          item.category
        )}`;

        const controls = document.createElement("div");

        controls.className = "playlist-controls";

        const btnUp = document.createElement("button");

        btnUp.className = "playlist-btn icon-only";

        btnUp.dataset.action = "up";

        btnUp.setAttribute("aria-label", "Monter");

        btnUp.innerHTML =
          '<span aria-hidden="true" class="playlist-icon playlist-icon--up">&#9650;</span>';

        const btnDown = document.createElement("button");

        btnDown.className = "playlist-btn icon-only";

        btnDown.dataset.action = "down";

        btnDown.setAttribute("aria-label", "Descendre");

        btnDown.innerHTML =
          '<span aria-hidden="true" class="playlist-icon playlist-icon--down">&#9660;</span>';

        const btnDelete = document.createElement("button");

        btnDelete.className = "playlist-btn danger icon-only";

        btnDelete.dataset.action = "delete";

        btnDelete.setAttribute("aria-label", "Supprimer");

        btnDelete.innerHTML =
          '<span aria-hidden="true" class="playlist-icon playlist-icon--delete">&#128465;</span>';

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

    fetchRandomModeState();

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

    const randomUnavailable = randomEnabled && randomInfo.available === false;

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

    fetchRandomModeState();

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

    fetchRandomModeState();

    updateStatus();
  } catch (e) {
    toast("Erreur stop", true);
  }
});

// Status

async function updateStatus() {
  const now = Date.now();

  if (statusFetchInFlight) {
    return;
  }

  if (!serverReachable && now < nextStatusAttempt) {
    return;
  }

  statusFetchInFlight = true;

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

    applyBluetoothStatus(st && st.bluetooth ? st.bluetooth : null);

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
      elConnectionText.textContent = "Skull : connecte";
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

    applyBluetoothStatus(null);

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
      elConnectionText.textContent = "Skull : hors ligne";
    }

    if (elConnectionDot) {
      elConnectionDot.setAttribute("aria-label", "hors ligne");
    }
  } finally {
    statusFetchInFlight = false;
  }
}

function setVolumeButtonsDisabled(disabled) {
  if (elVolumeButtons && elVolumeButtons.length) {
    elVolumeButtons.forEach((btn) => {
      if (btn) btn.disabled = disabled;
    });
  }

  if (elVolumeSlider) {
    if (disabled) {
      elVolumeSlider.setAttribute("disabled", "disabled");
    } else {
      elVolumeSlider.removeAttribute("disabled");
    }
  }
}

function clampVolumeSliderValue(value) {
  if (!elVolumeSlider) return 0;
  const minRaw = Number(elVolumeSlider.min);
  const maxRaw = Number(elVolumeSlider.max);
  const min = Number.isFinite(minRaw) ? minRaw : 0;
  const max = Number.isFinite(maxRaw) ? maxRaw : 127;
  const raw = Number(value);
  if (!Number.isFinite(raw)) return min;
  return Math.min(max, Math.max(min, Math.round(raw)));
}

function setVolumeSliderValue(value, force = false) {
  if (!elVolumeSlider) return;
  if (!force && volumeSliderActive) return;
  const clamped = clampVolumeSliderValue(value);
  elVolumeSlider.value = String(clamped);
  if (elVolumeSliderValue) {
    elVolumeSliderValue.textContent = String(clamped);
  }
}

function scheduleVolumeSet(value) {
  if (!elVolumeSlider) return;
  const clamped = clampVolumeSliderValue(value);
  volumePendingValue = clamped;
  if (volumeSliderDebounce) {
    clearTimeout(volumeSliderDebounce);
  }
  volumeSliderDebounce = setTimeout(() => {
    volumeSliderDebounce = null;
    triggerPendingVolumeSet();
  }, 150);
}

function triggerPendingVolumeSet() {
  if (volumeBusy || volumePendingValue === null) return;
  const value = volumePendingValue;
  volumePendingValue = null;
  sendVolumeAction("set", value);
}

function setRestartServiceDisabled(disabled) {
  if (!elRestartServiceBtn) return;

  if (disabled) {
    elRestartServiceBtn.setAttribute("disabled", "disabled");
  } else {
    elRestartServiceBtn.removeAttribute("disabled");
  }
}

function applyBluetoothStatus(info) {
  let statusClass = "bt-status";

  let text = "Bluetooth : inconnu";

  let topState = "unknown";

  let sliderTarget = null;

  if (info && typeof info === "object") {
    if (info.connected === true) {
      statusClass += " is-connected";

      let volumeSuffix = "";
      if (
        info &&
        Object.prototype.hasOwnProperty.call(info, "volume_percent") &&
        typeof info.volume_percent === "number" &&
        Number.isFinite(info.volume_percent)
      ) {
        const pct = Math.max(0, Math.min(100, Math.round(info.volume_percent)));
        volumeSuffix = ` (${pct}%)`;
        sliderTarget = info.volume_percent;
      }

      text = "Bluetooth : connecte" + volumeSuffix;

      topState = "online";
    } else if (info.connected === false) {
      statusClass += " is-disconnected";

      text = "Bluetooth : deconnecte";

      topState = "offline";
      sliderTarget = 0;
    } else {
      statusClass += " is-unknown";

      topState = "unknown";
    }
  } else {
    statusClass += " is-unknown";

    topState = "unknown";
  }

  if (elBtStatus) {
    elBtStatus.className = statusClass;
  }

  if (elBtStatusDot) {
    elBtStatusDot.className = "bt-dot";
  }

  if (elBtStatusText) {
    elBtStatusText.textContent = text;
  }

  if (elBtTopStatus) {
    const base = "connection-chip connection-chip--secondary";

    const stateClass =
      topState === "online"
        ? "online"
        : topState === "offline"
        ? "offline"
        : "unknown";

    elBtTopStatus.className = `${base} ${stateClass}`;
  }

  if (elBtTopStatusDot) {
    elBtTopStatusDot.className = "connection-dot";

    elBtTopStatusDot.setAttribute("aria-label", text);
  }

  if (elBtTopStatusText) {
    elBtTopStatusText.textContent = text;
  }

  if (sliderTarget !== null) {
    setVolumeSliderValue(sliderTarget);
  }
}

async function triggerServiceRestart() {
  if (restartServiceBusy) return;

  restartServiceBusy = true;
  setRestartServiceDisabled(true);

  try {
    const res = await fetch("/service/restart", { method: "POST" });
    const payload = await res.json().catch(() => ({}));

    if (!res.ok) {
      const message =
        payload && typeof payload.error === "string"
          ? payload.error
          : `service_restart_http_${res.status}`;
      throw new Error(message);
    }

    toast("Service en redÃ©marrage");
  } catch (error) {
    const message =
      error && error.message ? error.message : "RedÃ©marrage Ã©chouÃ©";
    toast(`Erreur redÃ©marrage: ${message}`, true);
  } finally {
    restartServiceBusy = false;
    setRestartServiceDisabled(false);
  }
}

async function triggerBluetoothRestart() {
  if (restartBluetoothBusy) return;
  restartBluetoothBusy = true;
  setRestartBluetoothDisabled(true);

  try {
    const res = await fetch("/bluetooth/restart", { method: "POST" });
    const payload = await res.json().catch(() => ({}));

    if (!res.ok) {
      const message =
        payload && typeof payload.error === "string"
          ? payload.error
          : `bluetooth_restart_http_${res.status}`;
      throw new Error(message);
    }

    toast("Bluetooth en redémarrage");
  } catch (error) {
    const message =
      error && error.message ? error.message : "Redémarrage échoué";
    toast(`Erreur redémarrage Bluetooth: ${message}`, true);
  } finally {
    restartBluetoothBusy = false;
    setRestartBluetoothDisabled(false);
  }
}

function setRestartBluetoothDisabled(disabled) {
  if (!elRestartBluetoothBtn) return;
  if (disabled) {
    elRestartBluetoothBtn.setAttribute("disabled", "disabled");
  } else {
    elRestartBluetoothBtn.removeAttribute("disabled");
  }
}

async function triggerShuffleAll() {
  if (shuffleBusy) return;

  shuffleBusy = true;

  if (elShuffleAllBtn) {
    elShuffleAllBtn.setAttribute("disabled", "disabled");
  }

  try {
    const res = await fetch("/playlist/shuffle", {
      method: "POST",
    });

    const payload = await res.json().catch(() => ({}));

    if (!res.ok) {
      const message =
        payload && typeof payload.error === "string"
          ? payload.error
          : `shuffle_http_${res.status}`;

      throw new Error(message);
    }

    const count =
      payload && typeof payload.count === "number" ? payload.count : null;

    toast(
      count
        ? `Lecture aleatoire continue prete (${count} sessions)`
        : "Lecture aleatoire continue prete"
    );

    await refreshPlaylist(true);

    fetchRandomModeState();

    updateStatus();
  } catch (error) {
    const message = error && error.message ? error.message : "Erreur shuffle";

    toast(`Erreur mode aleatoire: ${message}`, true);
  } finally {
    shuffleBusy = false;

    if (elShuffleAllBtn) {
      elShuffleAllBtn.removeAttribute("disabled");
    }
  }
}

async function sendVolumeAction(action, value) {
  if (!action) return;

  let targetValue = null;
  if (action === "set") {
    targetValue = clampVolumeSliderValue(value);
    if (volumeBusy) {
      volumePendingValue = targetValue;
      return;
    }
  } else if (volumeBusy) {
    return;
  }

  volumeBusy = true;

  setVolumeButtonsDisabled(true);

  try {
    const body = { action };
    if (action === "set") {
      body.value = targetValue;
    }

    const response = await fetch("/volume", {
      method: "POST",

      headers: { "Content-Type": "application/json" },

      body: JSON.stringify(body),
    });

    const payload = await response.json().catch(() => ({}));

    const ok = response.ok && payload && payload.ok !== false;

    if (!ok) {
      const message =
        (payload && (payload.error || payload.message)) ||
        `Commande volume echouee (${response.status})`;

      toast(message, true);
    } else {
      const reportedVolume =
        payload && typeof payload.volume === "number"
          ? payload.volume
          : null;

      if (action === "mute") {
        setVolumeSliderValue(0, true);
      } else if (action === "set") {
        const applied = reportedVolume !== null ? reportedVolume : targetValue;
        setVolumeSliderValue(applied, true);
      } else if (reportedVolume !== null) {
        setVolumeSliderValue(reportedVolume, true);
      }

      if (action !== "set") {
        const message =
          (payload && payload.message) ||
          (action === "mute" ? "Volume coupe" : "Volume ajuste");

        toast(message);
      }
    }
  } catch (error) {
    toast("Erreur reseau /volume", true);
  } finally {
    setVolumeButtonsDisabled(false);

    volumeBusy = false;

    triggerPendingVolumeSet();
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
    toast("Erreur rÃ©seau /channels", true);
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

      if (valueSpan) valueSpan.textContent = slider.value + "Â°";
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
    toast("Erreur rÃ©seau /pitch", true);
  }
}

// Attach pitch change handlers

Object.values(pitchSliders).forEach((slider) => {
  if (slider) {
    slider.addEventListener("input", updatePitchDisplay);

    slider.addEventListener("change", postPitch);
  }
});

// -------------------- ESP32 Gateway --------------------

function esp32ValueIsOn(value) {
  if (value === true) {
    return true;
  }

  if (value === false) {
    return false;
  }

  if (typeof value === "number") {
    if (value === 0) {
      return false;
    }
    if (value === 1) {
      return true;
    }
  }

  if (typeof value === "string") {
    const norm = value.trim().toLowerCase();
    if (norm === "1" || norm === "true" || norm === "on") {
      return true;
    }
    if (norm === "0" || norm === "false" || norm === "off") {
      return false;
    }
  }

  return Boolean(value);
}

function setEsp32Badge(element, value, labels = { on: "ON", off: "OFF" }) {
  if (!element) {
    return;
  }

  element.classList.remove(
    "esp32-badge-on",
    "esp32-badge-off",
    "esp32-badge-idle"
  );

  if (value === null || value === undefined || Number.isNaN(value)) {
    element.textContent = "-";
    element.classList.add("esp32-badge-idle");
    return;
  }

  const isOn = esp32ValueIsOn(value);
  if (isOn) {
    element.textContent = labels?.on ?? "ON";
    element.classList.add("esp32-badge-on");
  } else {
    element.textContent = labels?.off ?? "OFF";
    element.classList.add("esp32-badge-off");
  }
}

function setEsp32Reachability(state, message = "") {
  const resolvedDefault =
    state === true
      ? "En ligne"
      : state === false
      ? "Hors ligne"
      : "Inactif (desactive)";

  const resolvedMessage = message || resolvedDefault;
  const topLabel = `ESP32 : ${resolvedMessage}`;
  const stateClass =
    state === true ? "online" : state === false ? "offline" : "disabled";

  if (elEsp32StatusDot) {
    elEsp32StatusDot.classList.remove("online", "offline", "disabled");
    elEsp32StatusDot.classList.add(stateClass);
    elEsp32StatusDot.setAttribute("aria-label", resolvedMessage.toLowerCase());
  }

  if (elEsp32StatusText) {
    elEsp32StatusText.textContent = resolvedMessage;
  }

  if (elEsp32TopStatus) {
    const base = "connection-chip connection-chip--secondary";
    elEsp32TopStatus.className = `${base} ${stateClass}`;
  }

  if (elEsp32TopStatusDot) {
    elEsp32TopStatusDot.className = "connection-dot";
    elEsp32TopStatusDot.setAttribute("aria-label", topLabel);
  }

  if (elEsp32TopStatusText) {
    elEsp32TopStatusText.textContent = topLabel;
  }
}

function setEsp32ControlAvailability(enabled) {
  const disabled = !enabled;
  const controls = [
    elEsp32RelayOn,
    elEsp32RelayOff,
    elEsp32AutoRelayToggle,
    elEsp32Restart,
    elEsp32StatusRefresh,
    elEsp32ButtonsRefresh,
  ];
  controls.forEach((el) => {
    if (el) {
      el.disabled = disabled;
    }
  });

  esp32ButtonComponents.forEach(({ select, saveBtn }) => {
    if (select) {
      select.disabled = disabled;
    }
    if (saveBtn) {
      saveBtn.disabled = disabled;
    }
  });
}

function updateEsp32AutoRelayButton(state) {
  if (!elEsp32AutoRelayToggle) {
    return;
  }

  const isActive = esp32ValueIsOn(state);
  elEsp32AutoRelayToggle.setAttribute(
    "aria-pressed",
    isActive ? "true" : "false"
  );
  elEsp32AutoRelayToggle.textContent = isActive
    ? "Auto-relay ON"
    : "Auto-relay OFF";
}

function resetEsp32StatusView() {
  setEsp32Badge(elEsp32RelayState, null);
  setEsp32Badge(elEsp32AutoRelayState, null);
  if (elEsp32CurrentSession) {
    elEsp32CurrentSession.textContent = "-";
  }
  if (elEsp32WifiInfo) {
    elEsp32WifiInfo.textContent = "-";
  }
  if (elEsp32StatusRaw) {
    elEsp32StatusRaw.textContent = "";
  }
  updateEsp32ButtonStates(null);
  updateEsp32AutoRelayButton(false);
}

function formatEsp32WifiInfo(wifi) {
  if (!wifi || typeof wifi !== "object") {
    return "-";
  }

  const ip =
    typeof wifi.ip === "string" && wifi.ip.trim() ? wifi.ip.trim() : "";
  const rssiValue = wifi.rssi;
  const hasRssi = typeof rssiValue === "number" && Number.isFinite(rssiValue);

  if (ip && hasRssi) {
    return `${ip} (RSSI ${rssiValue})`;
  }
  if (ip) {
    return ip;
  }
  if (hasRssi) {
    return `RSSI ${rssiValue}`;
  }
  return "-";
}

function rebuildEsp32Buttons(count) {
  if (!elEsp32ButtonsContainer) {
    return;
  }

  const total = normalizeEsp32ButtonCount(count);

  esp32ButtonComponents.clear();
  elEsp32ButtonsContainer.innerHTML = "";

  for (let idx = 0; idx < total; idx += 1) {
    const item = document.createElement("div");
    item.className = "esp32-button-item";

    const header = document.createElement("div");
    header.className = "esp32-button-header";

    const label = document.createElement("span");
    label.textContent = `Bouton ${idx + 1}`;

    const badge = document.createElement("span");
    badge.className = "badge esp32-badge-idle";
    badge.id = `esp32ButtonState${idx}`;
    badge.textContent = "-";

    header.append(label, badge);

    const select = document.createElement("select");
    select.className = "select esp32-button-select";
    select.dataset.esp32Button = String(idx);

    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "-- Aucun --";
    select.append(emptyOption);

    const actions = document.createElement("div");
    actions.className = "esp32-button-actions";

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn secondary esp32-button-save";
    saveBtn.dataset.esp32Button = String(idx);
    saveBtn.textContent = "Associer";

    actions.append(saveBtn);
    item.append(header, select, actions);
    elEsp32ButtonsContainer.append(item);

    esp32ButtonComponents.set(idx, {
      select,
      badge,
      saveBtn,
      container: item,
    });
  }

  populateEsp32ButtonOptions();
  applyEsp32ButtonAssignments(esp32ButtonAssignments);
  setEsp32ControlAvailability(esp32Config.enabled);
}

function populateEsp32ButtonOptions() {
  const seen = new Set();
  const categoriesList = [];

  const pushCategory = (category) => {
    if (typeof category !== "string") {
      return;
    }
    const value = category.trim();
    if (!value) {
      return;
    }
    const key = value.toLowerCase();
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    categoriesList.push(value);
  };

  pushCategory(ESP32_ALL_CATEGORY);

  const baseCategories = Array.isArray(availableCategories)
    ? availableCategories
    : [];

  baseCategories.forEach(pushCategory);

  (Array.isArray(esp32ButtonAssignments) ? esp32ButtonAssignments : []).forEach(
    pushCategory
  );

  esp32ButtonComponents.forEach(({ select }, index) => {
    if (!select) {
      return;
    }

    const assigned = esp32ButtonAssignments[index] || "";
    const previousValue = select.value;

    select.innerHTML = "";

    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "-- Aucun --";
    select.append(emptyOption);

    categoriesList.forEach((category) => {
      const opt = document.createElement("option");
      opt.value = category;
      opt.textContent = category;
      select.append(opt);
    });

    const target = (assigned || previousValue || "").trim();
    if (target) {
      if (!seen.has(target)) {
        const opt = document.createElement("option");
        opt.value = target;
        opt.textContent = target;
        opt.dataset.missing = "true";
        select.append(opt);
      }
      select.value = target;
    } else {
      select.value = "";
    }

    select.dataset.currentCategory = select.value || "";
  });
}

function applyEsp32ButtonAssignments(assignments) {
  const total =
    (esp32Config && Number.isFinite(esp32Config.buttonCount)
      ? esp32Config.buttonCount
      : ESP32_DEFAULT_BUTTON_COUNT) || ESP32_DEFAULT_BUTTON_COUNT;

  const sanitized = [];
  if (Array.isArray(assignments)) {
    for (let idx = 0; idx < total; idx += 1) {
      const value = assignments[idx];
      sanitized.push(typeof value === "string" ? value.trim() : "");
    }
  } else {
    for (let idx = 0; idx < total; idx += 1) {
      sanitized.push("");
    }
  }

  esp32ButtonAssignments = sanitized;
  populateEsp32ButtonOptions();
}

function updateEsp32ButtonStates(states) {
  const list = Array.isArray(states) ? states : null;

  esp32ButtonComponents.forEach(({ badge }, index) => {
    if (!badge) {
      return;
    }

    if (!list) {
      setEsp32Badge(badge, null, { on: "Relache", off: "Appuye" });
      return;
    }

    const raw = list[index];
    if (raw === 0) {
      setEsp32Badge(badge, false, { on: "Relache", off: "Appuye" });
    } else if (raw === 1) {
      setEsp32Badge(badge, true, { on: "Relache", off: "Appuye" });
    } else {
      setEsp32Badge(badge, null, { on: "Relache", off: "Appuye" });
    }
  });
}

function scheduleEsp32StatusPolling() {
  if (esp32StatusTimerId) {
    clearInterval(esp32StatusTimerId);
    esp32StatusTimerId = null;
  }

  if (!esp32Config.enabled) {
    return;
  }

  esp32StatusTimerId = window.setInterval(() => {
    refreshEsp32Status({ silent: true });
  }, ESP32_STATUS_INTERVAL);
}

async function refreshEsp32Status(options = {}) {
  if (!elEsp32Card) {
    return;
  }

  if (!esp32Config.enabled) {
    setEsp32Reachability(null, "Inactif (desactive)");
    resetEsp32StatusView();
    return;
  }

  if (esp32Busy.status) {
    return;
  }

  const { silent = false } = options;
  esp32Busy.status = true;

  try {
    const res = await fetch("/esp32/status");
    const data = await res.json();

    if (res.ok && data && data.reachable) {
      esp32StatusSnapshot = data.status || {};
      setEsp32Reachability(true, "En ligne");

      setEsp32Badge(elEsp32RelayState, esp32StatusSnapshot.relay);
      setEsp32Badge(elEsp32AutoRelayState, esp32StatusSnapshot.autoRelay);
      updateEsp32AutoRelayButton(esp32StatusSnapshot.autoRelay);

      if (elEsp32CurrentSession) {
        elEsp32CurrentSession.textContent =
          esp32StatusSnapshot.currentSession || "-";
      }

      if (elEsp32WifiInfo) {
        elEsp32WifiInfo.textContent = formatEsp32WifiInfo(
          esp32StatusSnapshot.wifi
        );
      }

      if (elEsp32StatusRaw) {
        elEsp32StatusRaw.textContent = JSON.stringify(
          esp32StatusSnapshot,
          null,
          2
        );
      }

      updateEsp32ButtonStates(esp32StatusSnapshot.buttons);
      return;
    }

    const errorText =
      data?.error || (res.ok ? "Injoignable" : `HTTP ${res.status}`);
    setEsp32Reachability(false, `Hors ligne (${errorText})`);
    resetEsp32StatusView();
    esp32StatusSnapshot = null;

    if (!silent) {
      toast(`ESP32 statut: ${errorText}`, true);
    }
  } catch (err) {
    console.error("ESP32 status error:", err);
    setEsp32Reachability(false, "Hors ligne (erreur)");
    resetEsp32StatusView();
    esp32StatusSnapshot = null;
    if (!silent) {
      toast("Erreur reseau ESP32 (status)", true);
    }
  } finally {
    esp32Busy.status = false;
  }
}

async function fetchEsp32Buttons(options = {}) {
  if (!elEsp32ButtonsContainer || !esp32Config.enabled) {
    return;
  }

  if (esp32Busy.buttons) {
    return;
  }

  const { silent = false } = options;
  esp32Busy.buttons = true;

  if (elEsp32ButtonsRefresh) {
    elEsp32ButtonsRefresh.disabled = true;
  }

  try {
    const res = await fetch("/esp32/button-config");
    const data = await res.json();

    if (Array.isArray(data?.categories)) {
      availableCategories = sanitizeCategoryList(data.categories);
    }

    const assignments = Array.isArray(data?.assignments)
      ? data.assignments
      : Array.isArray(data?.sessions)
      ? data.sessions
      : [];
    applyEsp32ButtonAssignments(assignments);

    const states = Array.isArray(data?.states)
      ? data.states
      : Array.isArray(data?.buttons)
      ? data.buttons
      : null;
    if (states) {
      updateEsp32ButtonStates(states);
    }

    if (!res.ok) {
      const errorText =
        data?.error || `HTTP ${res.status}`;
      if (!silent) {
        toast(`ESP32 boutons: ${errorText}`, true);
      }
      return;
    }

    if (data && data.reachable === false) {
      const errorText = data.error || "Injoignable";
      if (!silent) {
        toast(`ESP32 boutons: ${errorText}`, true);
      }
    }
  } catch (err) {
    console.error("ESP32 button config error:", err);
    if (!silent) {
      toast("Erreur reseau ESP32 (boutons)", true);
    }
  } finally {
    esp32Busy.buttons = false;
    if (elEsp32ButtonsRefresh) {
      elEsp32ButtonsRefresh.disabled = !esp32Config.enabled;
    }
  }
}

async function setEsp32Relay(on) {
  if (!esp32Config.enabled) {
    toast("Activer l'ESP32 avant de piloter le relais", true);
    return;
  }

  if (esp32Busy.relay) {
    return;
  }

  esp32Busy.relay = true;

  if (elEsp32RelayOn) {
    elEsp32RelayOn.disabled = true;
  }

  if (elEsp32RelayOff) {
    elEsp32RelayOff.disabled = true;
  }

  try {
    const res = await fetch("/esp32/relay", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ on: Boolean(on) }),
    });
    const data = await res.json();

    if (res.ok && data && data.success !== false) {
      toast(on ? "Relais ESP32 active" : "Relais ESP32 desactive");
      await refreshEsp32Status({ silent: true });
    } else {
      const errorText =
        data?.error || (res.ok ? "Injoignable" : `HTTP ${res.status}`);
      toast(`ESP32 relais: ${errorText}`, true);
    }
  } catch (err) {
    console.error("ESP32 relay error:", err);
    toast("Erreur reseau ESP32 (relais)", true);
  } finally {
    esp32Busy.relay = false;
    setEsp32ControlAvailability(esp32Config.enabled);
  }
}

async function setEsp32AutoRelay(nextState) {
  if (!esp32Config.enabled) {
    toast("Activer l'ESP32 avant de modifier l'auto-relay", true);
    return;
  }

  if (esp32Busy.auto) {
    return;
  }

  esp32Busy.auto = true;

  if (elEsp32AutoRelayToggle) {
    elEsp32AutoRelayToggle.disabled = true;
  }

  try {
    const res = await fetch("/esp32/auto-relay", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ enabled: Boolean(nextState) }),
    });
    const data = await res.json();

    if (res.ok && data && data.success !== false) {
      toast(nextState ? "Mode auto-relay active" : "Mode auto-relay desactive");
      await refreshEsp32Status({ silent: true });
    } else {
      const errorText =
        data?.error || (res.ok ? "Injoignable" : `HTTP ${res.status}`);
      toast(`ESP32 auto-relay: ${errorText}`, true);
    }
  } catch (err) {
    console.error("ESP32 auto-relay error:", err);
    toast("Erreur reseau ESP32 (auto-relay)", true);
  } finally {
    esp32Busy.auto = false;
    if (elEsp32AutoRelayToggle) {
      elEsp32AutoRelayToggle.disabled = !esp32Config.enabled;
    }
  }
}

function toggleEsp32AutoRelay() {
  const current = esp32ValueIsOn(esp32StatusSnapshot?.autoRelay);
  setEsp32AutoRelay(!current);
}

async function requestEsp32Restart() {
  if (!esp32Config.enabled) {
    toast("Activer l'ESP32 avant de redemarrer", true);
    return;
  }

  if (esp32Busy.restart) {
    return;
  }

  if (!window.confirm("Redemarrer l'ESP32 maintenant ?")) {
    return;
  }

  esp32Busy.restart = true;

  if (elEsp32Restart) {
    elEsp32Restart.disabled = true;
  }

  try {
    const res = await fetch("/esp32/restart", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });
    const data = await res.json();

    if (res.ok && data && data.success !== false) {
      toast("Commande de redemarrage envoyee");
      setEsp32Reachability(false, "Hors ligne (redemarrage)");
    } else {
      const errorText =
        data?.error || (res.ok ? "Injoignable" : `HTTP ${res.status}`);
      toast(`ESP32 restart: ${errorText}`, true);
    }
  } catch (err) {
    console.error("ESP32 restart error:", err);
    toast("Erreur reseau ESP32 (restart)", true);
  } finally {
    esp32Busy.restart = false;
    if (elEsp32Restart) {
      elEsp32Restart.disabled = !esp32Config.enabled;
    }
  }
}

async function handleEsp32ButtonSave(buttonIndex) {
  if (!Number.isInteger(buttonIndex) || buttonIndex < 0) {
    return;
  }

  if (!esp32Config.enabled) {
    toast("Activer l'ESP32 avant de modifier les boutons", true);
    return;
  }

  const entry = esp32ButtonComponents.get(buttonIndex);
  if (!entry || esp32Busy.buttons) {
    return;
  }

  const { select, saveBtn } = entry;
  const categoryValue = select && typeof select.value === "string"
    ? select.value.trim()
    : "";

  esp32Busy.buttons = true;

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.textContent = "Envoi...";
  }

  try {
    const res = await fetch("/esp32/button-config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        button: buttonIndex,
        category: categoryValue,
      }),
    });
    const data = await res.json();

    if (res.ok && data && data.success !== false) {
      if (Array.isArray(data.categories)) {
        availableCategories = sanitizeCategoryList(data.categories);
      }
      if (Array.isArray(data.assignments)) {
        applyEsp32ButtonAssignments(data.assignments);
      } else if (Array.isArray(data.sessions)) {
        applyEsp32ButtonAssignments(data.sessions);
      } else {
        esp32ButtonAssignments[buttonIndex] = categoryValue;
        populateEsp32ButtonOptions();
      }
      if (select) {
        select.dataset.currentCategory = categoryValue;
      }
      const label = categoryValue ? ` -> ${categoryValue}` : "";
      toast(`Bouton ${buttonIndex + 1} mis a jour${label}`);

      if (data && data.reachable === false && data.error) {
        toast(
          `ESP32 bouton ${buttonIndex + 1}: ${data.error} (non applique sur l'ESP32)`,
          true
        );
      } else {
        await refreshEsp32Status({ silent: true });
      }
    } else {
      const errorText =
        data?.error || (res.ok ? "Injoignable" : `HTTP ${res.status}`);
      toast(`ESP32 bouton ${buttonIndex + 1}: ${errorText}`, true);
    }
  } catch (err) {
    console.error("ESP32 button update error:", err);
    toast("Erreur reseau ESP32 (boutons)", true);
  } finally {
    esp32Busy.buttons = false;
    if (saveBtn) {
      saveBtn.disabled = !esp32Config.enabled;
      saveBtn.textContent = "Associer";
    }
    if (elEsp32ButtonsRefresh) {
      elEsp32ButtonsRefresh.disabled = !esp32Config.enabled;
    }
  }
}

async function fetchEsp32Config() {
  if (!elEsp32Card) {
    return;
  }

  try {
    const res = await fetch("/esp32/config");
    const data = await res.json();

    if (!res.ok) {
      const errorText = data?.error || `HTTP ${res.status}`;
      setEsp32Reachability(null, "Inactif (desactive)");
      setEsp32ControlAvailability(false);
      resetEsp32StatusView();
      toast(`ESP32 config: ${errorText}`, true);
      return;
    }

    esp32Config = {
      host: typeof data.host === "string" ? data.host.trim() : "",
      port:
        typeof data.port === "number" && Number.isFinite(data.port)
          ? data.port
          : parseInt(data.port, 10) || 80,
      enabled: Boolean(data.enabled),
      buttonCount: normalizeEsp32ButtonCount(data.buttonCount),
    };

    if (elEsp32Host) {
      elEsp32Host.value = esp32Config.host || "";
    }
    if (elEsp32Port) {
      elEsp32Port.value = String(esp32Config.port || 80);
    }
    if (elEsp32Enabled) {
      elEsp32Enabled.checked = esp32Config.enabled;
    }

    rebuildEsp32Buttons(esp32Config.buttonCount);

    if (esp32Config.enabled) {
      setEsp32ControlAvailability(true);
      await refreshEsp32Status({ silent: true });
      await fetchEsp32Buttons({ silent: true });
    } else {
      setEsp32ControlAvailability(false);
      setEsp32Reachability(null, "Inactif (desactive)");
      resetEsp32StatusView();
    }

    scheduleEsp32StatusPolling();
  } catch (err) {
    console.error("ESP32 config load error:", err);
    setEsp32Reachability(null, "Inactif (desactive)");
    setEsp32ControlAvailability(false);
    resetEsp32StatusView();
    toast("Impossible de charger la configuration ESP32", true);
  }
}

async function handleEsp32ConfigSubmit(event) {
  event.preventDefault();

  if (esp32Busy.config) {
    return;
  }

  esp32Busy.config = true;

  const submitBtn = document.getElementById("esp32ConfigSaveBtn");
  if (submitBtn) {
    submitBtn.disabled = true;
  }

  const host = elEsp32Host ? elEsp32Host.value.trim() : "";
  const rawPort = elEsp32Port ? elEsp32Port.value.trim() : "";
  let port = parseInt(rawPort, 10);
  if (!Number.isFinite(port) || port <= 0) {
    port = 80;
  }
  const enabled = elEsp32Enabled ? elEsp32Enabled.checked : false;

  const payload = {
    host,
    port,
    enabled,
  };

  try {
    const res = await fetch("/esp32/config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok || data?.error) {
      const errorText = data?.error || `HTTP ${res.status}`;
      toast(`Configuration ESP32: ${errorText}`, true);
      return;
    }

    toast("Configuration ESP32 mise a jour");

    esp32Config = {
      host: typeof data.host === "string" ? data.host.trim() : "",
      port:
        typeof data.port === "number" && Number.isFinite(data.port)
          ? data.port
          : parseInt(data.port, 10) || 80,
      enabled: Boolean(data.enabled),
      buttonCount: normalizeEsp32ButtonCount(data.buttonCount),
    };

    if (elEsp32Host) {
      elEsp32Host.value = esp32Config.host || "";
    }
    if (elEsp32Port) {
      elEsp32Port.value = String(esp32Config.port || 80);
    }
    if (elEsp32Enabled) {
      elEsp32Enabled.checked = esp32Config.enabled;
    }

    rebuildEsp32Buttons(esp32Config.buttonCount);

    if (esp32Config.enabled) {
      setEsp32ControlAvailability(true);
      await refreshEsp32Status({ silent: true });
      await fetchEsp32Buttons({ silent: true });
    } else {
      setEsp32ControlAvailability(false);
      setEsp32Reachability(null, "Inactif (desactive)");
      resetEsp32StatusView();
    }

    scheduleEsp32StatusPolling();
  } catch (err) {
    console.error("ESP32 config update error:", err);
    toast("Erreur lors de la sauvegarde ESP32", true);
  } finally {
    esp32Busy.config = false;
    if (submitBtn) {
      submitBtn.disabled = false;
    }
  }
}

function initEsp32Section() {
  if (!elEsp32Card) {
    return;
  }

  if (elEsp32ConfigForm) {
    elEsp32ConfigForm.addEventListener("submit", handleEsp32ConfigSubmit);
  }

  if (elEsp32StatusRefresh) {
    elEsp32StatusRefresh.addEventListener("click", () => {
      if (!esp32Config.enabled) {
        toast("Activer l'ESP32 avant de tester la connexion", true);
        return;
      }
      refreshEsp32Status();
    });
  }

  if (elEsp32RelayOn) {
    elEsp32RelayOn.addEventListener("click", () => setEsp32Relay(true));
  }

  if (elEsp32RelayOff) {
    elEsp32RelayOff.addEventListener("click", () => setEsp32Relay(false));
  }

  if (elEsp32AutoRelayToggle) {
    elEsp32AutoRelayToggle.addEventListener("click", toggleEsp32AutoRelay);
  }

  if (elEsp32Restart) {
    elEsp32Restart.addEventListener("click", requestEsp32Restart);
  }

  if (elEsp32ButtonsRefresh) {
    elEsp32ButtonsRefresh.addEventListener("click", () => {
      fetchEsp32Buttons();
    });
  }

  if (elEsp32ButtonsContainer) {
    elEsp32ButtonsContainer.addEventListener("click", (event) => {
      const target = event.target;
      if (
        target &&
        target.classList &&
        target.classList.contains("esp32-button-save")
      ) {
        const idx = parseInt(target.dataset.esp32Button, 10);
        if (Number.isInteger(idx)) {
          handleEsp32ButtonSave(idx);
        }
      }
    });

    elEsp32ButtonsContainer.addEventListener("change", (event) => {
      const target = event.target;
      if (
        target &&
        target.classList &&
        target.classList.contains("esp32-button-select")
      ) {
        const idx = parseInt(target.dataset.esp32Button, 10);
        if (Number.isInteger(idx)) {
          const value =
            target && typeof target.value === "string"
              ? target.value.trim()
              : "";
          esp32ButtonAssignments[idx] = value;
          target.dataset.currentCategory = value;
        }
      }
    });
  }

  setEsp32Reachability(null, "Inactif (desactive)");
  setEsp32ControlAvailability(false);
  resetEsp32StatusView();
  rebuildEsp32Buttons(ESP32_DEFAULT_BUTTON_COUNT);
  fetchEsp32Config();
}

// Boot

window.addEventListener("load", () => {
  initEsp32Section();

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
        if (!action) return;

        if (action === "mute") {
          if (volumeSliderDebounce) {
            clearTimeout(volumeSliderDebounce);
            volumeSliderDebounce = null;
          }
          volumePendingValue = null;
          setVolumeSliderValue(0, true);
        }

        sendVolumeAction(action);
      });
    });
  }

  if (elVolumeSlider) {
    const initialValue =
      typeof elVolumeSlider.value === "string" && elVolumeSlider.value !== ""
        ? Number(elVolumeSlider.value)
        : clampVolumeSliderValue(elVolumeSlider.min || 0);
    setVolumeSliderValue(initialValue, true);

    const endSliderInteraction = () => {
      volumeSliderActive = false;
    };

    elVolumeSlider.addEventListener("input", (event) => {
      volumeSliderActive = true;
      const value = clampVolumeSliderValue(event.target.value);
      setVolumeSliderValue(value, true);
      scheduleVolumeSet(value);
    });

    elVolumeSlider.addEventListener("change", (event) => {
      const value = clampVolumeSliderValue(event.target.value);
      setVolumeSliderValue(value, true);
      if (volumeSliderDebounce) {
        clearTimeout(volumeSliderDebounce);
        volumeSliderDebounce = null;
      }
      volumePendingValue = value;
      triggerPendingVolumeSet();
      endSliderInteraction();
    });

    ["pointerup", "pointercancel", "mouseup", "touchend", "blur"].forEach(
      (evt) => {
        elVolumeSlider.addEventListener(evt, endSliderInteraction);
      }
    );
  }

  if (elShuffleAllBtn) {
    elShuffleAllBtn.addEventListener("click", () => {
      triggerShuffleAll();
    });
  }

  if (elRestartServiceBtn) {
    elRestartServiceBtn.addEventListener("click", () => {
      if (restartServiceBusy) return;
      const confirmMessage = "RedÃ©marrer le service servo-sync ?";
      if (window.confirm(confirmMessage)) {
        triggerServiceRestart();
      }
    });
  }

  if (elRestartBluetoothBtn) {
    elRestartBluetoothBtn.addEventListener("click", () => {
      if (restartBluetoothBusy) return;
      const confirmMessage = "Redémarrer le service Bluetooth ?";
      if (window.confirm(confirmMessage)) {
        triggerBluetoothRestart();
      }
    });
  }

  updatePills();
});
