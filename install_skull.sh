#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/IM-Lab-france/Skull-V2.git"
INSTALL_DIR="/opt/skull"
SERVICE_NAME="servo-sync.service"

# APT packages required because they cannot be installed via pip
APT_PACKAGES=(
  git
  build-essential
  python3
  python3-venv
  python3-pip
  ffmpeg
  libasound2
  libasound2-dev
  i2c-tools
  pulseaudio
  pulseaudio-utils
  pulseaudio-module-bluetooth
  bluez
)

TOTAL_STEPS=10
CURRENT_STEP=0

msg() {
  printf '[%s] %s\n' "$(date +'%H:%M:%S')" "$1"
}

announce_step() {
  CURRENT_STEP=$((CURRENT_STEP + 1))
  msg ""
  msg "==> (${CURRENT_STEP}/${TOTAL_STEPS}) $1"
}

run_quiet() {
  local description="$1"
  shift
  msg "   - $description"
  if "$@" >/dev/null; then
    msg "     -> OK"
  else
    msg "     -> ERREUR (voir sortie ci-dessus)"
    return 1
  fi
}

run_cmd() {
  local description="$1"
  shift
  msg "   - $description"
  if "$@"; then
    msg "     -> OK"
  else
    msg "     -> ERREUR (voir sortie ci-dessus)"
    return 1
  fi
}

READ_VALUE=""
SELECTED_BLUETOOTH_MAC=""
SELECTED_BLUETOOTH_NAME=""
PAIRED_BLUETOOTH_MAC=""
PAIRED_BLUETOOTH_NAME=""

is_interactive() {
  [[ -t 0 ]] || [[ -t 1 ]] || [[ -t 2 ]] || [[ -w /dev/tty ]]
}

read_input() {
  local prompt="$1"
  local default="${2:-}"
  local input=""

  if [[ -t 0 ]]; then
    read -r -p "$prompt" input
  elif [[ -w /dev/tty ]]; then
    printf '%s' "$prompt" > /dev/tty
    read -r input < /dev/tty
  else
    input="$default"
  fi

  if [[ -z "$input" && -n "$default" ]]; then
    input="$default"
  fi

  READ_VALUE="$input"
}

persist_bluetooth_device() {
  if [[ -z "$PAIRED_BLUETOOTH_MAC" ]]; then
    return
  fi

  mkdir -p "$INSTALL_DIR/config"
  local config_file="$INSTALL_DIR/config/bluetooth_device.env"

  local addr_escaped
  addr_escaped=$(printf '%q' "$PAIRED_BLUETOOTH_MAC")
  local name_escaped
  name_escaped=$(printf '%q' "$PAIRED_BLUETOOTH_NAME")

  cat >"$config_file" <<EOF
PLAYLIST_BT_DEVICE_ADDR=$addr_escaped
PLAYLIST_BT_DEVICE_NAME=$name_escaped
EOF

  chown "$SKULL_USER:$SKULL_GROUP" "$config_file"
  msg "   - Configuration bluetooth enregistree dans $config_file"
}

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Ce script doit etre execute en tant que root (utilisez sudo)." >&2
    exit 1
  fi
}

detect_user() {
  local detected="${SKULL_INSTALL_USER:-}"
  if [[ -z "$detected" && -n "${SUDO_USER:-}" ]]; then
    detected="$SUDO_USER"
  fi
  if [[ -z "$detected" ]]; then
    detected="$(logname 2>/dev/null || true)"
  fi
  if [[ -z "$detected" ]]; then
    echo "Impossible de determiner l'utilisateur cible. Definissez SKULL_INSTALL_USER." >&2
    exit 1
  fi
  if [[ "$detected" == "root" ]]; then
    echo "L'utilisateur cible ne peut pas etre root. Executez ce script avec sudo depuis votre compte utilisateur." >&2
    exit 1
  fi
  if ! id "$detected" >/dev/null 2>&1; then
    echo "Utilisateur '$detected' introuvable." >&2
    exit 1
  fi
  SKULL_USER="$detected"
  SKULL_GROUP="$(id -gn "$SKULL_USER")"
  SKULL_UID="$(id -u "$SKULL_USER")"
}

install_apt_packages() {
  msg "Installation des dependances systeme : ${APT_PACKAGES[*]}"
  run_quiet "Mise a jour du cache APT" apt-get update -qq
  run_cmd "Installation des paquets systeme (cela peut prendre quelques minutes)" \
    env DEBIAN_FRONTEND=noninteractive apt-get install -y \
      -o Dpkg::Progress-Fancy=1 \
      -o Dpkg::Use-Pty=0 \
      "${APT_PACKAGES[@]}"
}

prepare_source_tree() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    msg "Mise a jour du depot existant dans $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch origin
    git -C "$INSTALL_DIR" reset --hard origin/main
  else
    if [[ -d "$INSTALL_DIR" && -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
      echo "Le repertoire $INSTALL_DIR existe deja et n'est pas un depot git. Abandon pour eviter toute perte de donnees." >&2
      exit 1
    fi
    if [[ -d "$INSTALL_DIR" ]]; then
      rmdir "$INSTALL_DIR"
    fi
    msg "Clonage du depot dans $INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
}

write_requirements() {
  cat >"$INSTALL_DIR/requirements.txt" <<'EOF'
Flask>=3.0,<4.0
requests>=2.31,<3
pydub>=0.25.1,<0.26
simpleaudio>=1.0,<1.1
adafruit-circuitpython-pca9685>=3.4.0,<4.0
adafruit-blinka>=8.0.0,<9.0.0
EOF
  chown "$SKULL_USER:$SKULL_GROUP" "$INSTALL_DIR/requirements.txt"
}

setup_python_env() {
  msg "Preparation de l'environnement virtuel Python"
  if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    python3 -m venv "$INSTALL_DIR/.venv"
  fi
  "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip setuptools wheel
  msg "   - Installation des dependances Python (pip)"
  "$INSTALL_DIR/.venv/bin/pip" install --no-cache-dir --progress-bar off -r "$INSTALL_DIR/requirements.txt"
}

prepare_runtime_dirs() {
  mkdir -p "$INSTALL_DIR/config" "$INSTALL_DIR/data" "$INSTALL_DIR/logs"
  chown -R "$SKULL_USER:$SKULL_GROUP" "$INSTALL_DIR"
}

ensure_runtime_dir() {
  local runtime_dir="/run/user/$SKULL_UID"
  if [[ ! -d "$runtime_dir" ]]; then
    install -d -m 700 -o "$SKULL_USER" -g "$SKULL_GROUP" "$runtime_dir"
  fi
}

prompt_bluetooth_pairing() {
  msg "Placez l'enceinte bluetooth en mode appairage."
  if is_interactive; then
    read_input "Appuyez sur Entree lorsque l'enceinte clignote pret pour l'appairage..." ""
  else
    msg "Mode non interactif : attente 20s avant de poursuivre."
    sleep 20
  fi
}

manage_paired_devices() {
  mapfile -t paired < <(bluetoothctl paired-devices 2>/dev/null | sed -n 's/^Device \([0-9A-F:]\{17\}\) \(.*\)$/\1|\2/p' || true)
  if ((${#paired[@]} == 0)); then
    msg "Aucun peripherique bluetooth deja apparie."
    return
  fi

  msg "Peripheriques bluetooth actuellement apparies :"
  local idx=1
  for entry in "${paired[@]}"; do
    IFS='|' read -r mac name <<<"$entry"
    local display_name="$name"
    if [[ -z "$display_name" ]]; then
      display_name="(sans nom)"
    fi
    printf '  [%d] %s (%s)\n' "$idx" "$display_name" "$mac"
    idx=$((idx + 1))
  done

  if ! is_interactive; then
    msg "Mode non interactif : suppression des peripheriques ignores."
    return
  fi

  while true; do
    read_input "Entrez le numero d'un peripherique a supprimer (ou appuyez sur Entree pour continuer) : "
    local choice="${READ_VALUE//[[:space:]]/}"
    if [[ -z "$choice" ]]; then
      break
    fi
    if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
      msg "Choix invalide: $choice"
      continue
    fi
    local index=$((choice))
    if (( index < 1 || index > ${#paired[@]} )); then
      msg "Indice hors plage."
      continue
    fi
    local selected="${paired[index-1]}"
    IFS='|' read -r mac name <<<"$selected"
    local display_name="$name"
    if [[ -z "$display_name" ]]; then
      display_name="(sans nom)"
    fi
    msg "Suppression du peripherique $display_name ($mac)"
    if bluetoothctl remove "$mac"; then
      msg "Peripherique $display_name supprime."
    else
      msg "Impossible de supprimer $mac automatiquement."
    fi
    mapfile -t paired < <(bluetoothctl paired-devices 2>/dev/null | sed -n 's/^Device \([0-9A-F:]\{17\}\) \(.*\)$/\1|\2/p' || true)
    if ((${#paired[@]} == 0)); then
      msg "Plus aucun peripherique apparie."
      break
    fi
    idx=1
    msg "Peripheriques restants :"
    for entry in "${paired[@]}"; do
      IFS='|' read -r mac name <<<"$entry"
      local display_name="$name"
      if [[ -z "$display_name" ]]; then
        display_name="(sans nom)"
      fi
      printf '  [%d] %s (%s)\n' "$idx" "$display_name" "$mac"
      idx=$((idx + 1))
    done
  done
}

scan_and_select_device() {
  local scan_seconds="${SKULL_BT_SCAN_SECONDS:-30}"
  local attempt=1
  SELECTED_BLUETOOTH_MAC=""
  SELECTED_BLUETOOTH_NAME=""

  while true; do
    msg "Passage en mode recherche bluetooth pendant ${scan_seconds}s (tentative ${attempt})..."
    bluetoothctl --timeout "$scan_seconds" scan on >/dev/null 2>&1 || true
    bluetoothctl scan off >/dev/null 2>&1 || true

    mapfile -t discovered < <(bluetoothctl devices 2>/dev/null | sed -n 's/^Device \([0-9A-F:]\{17\}\) \(.*\)$/\1|\2/p' || true)
    declare -A paired_lookup=()
    while read -r line; do
      if [[ $line =~ ^Device[[:space:]]+([0-9A-F:]{17}) ]]; then
        paired_lookup["${BASH_REMATCH[1]}"]=1
      fi
    done < <(bluetoothctl paired-devices 2>/dev/null || true)

    if ((${#discovered[@]} == 0)); then
      msg "Aucun peripherique detecte."
      if is_interactive; then
        read_input "Reessayer un scan ? (o/N) : " "N"
        local retry="${READ_VALUE//[[:space:]]/}"
        if [[ "$retry" =~ ^([oOyY])$ ]]; then
          ((attempt++))
          continue
        fi
      fi
      return 1
    fi

    msg "Peripheriques bluetooth disponibles :"
    local idx=1
    for entry in "${discovered[@]}"; do
      IFS='|' read -r mac name <<<"$entry"
      local display_name="$name"
      if [[ -z "$display_name" ]]; then
        display_name="(sans nom)"
      fi
      local tag=""
      if [[ -n ${paired_lookup[$mac]+x} ]]; then
        tag=" [apparie]"
      fi
      printf '  [%d] %s (%s)%s\n' "$idx" "$display_name" "$mac" "$tag"
      idx=$((idx + 1))
    done

    if ! is_interactive; then
      local first="${discovered[0]}"
      IFS='|' read -r mac name <<<"$first"
      SELECTED_BLUETOOTH_MAC="$mac"
      SELECTED_BLUETOOTH_NAME="$name"
      local display_name="$name"
      if [[ -z "$display_name" ]]; then
        display_name="(sans nom)"
      fi
      msg "Mode non interactif : selection automatique de $display_name ($mac)."
      return 0
    fi

    read_input "Selectionnez un numero (R pour rescanner, S pour ignorer) : "
    local choice="${READ_VALUE//[[:space:]]/}"
    if [[ -z "$choice" ]]; then
      return 1
    fi
    if [[ "$choice" =~ ^[Rr]$ ]]; then
      ((attempt++))
      continue
    fi
    if [[ "$choice" =~ ^[Ss]$ ]]; then
      return 1
    fi
    if [[ "$choice" =~ ^[0-9]+$ ]]; then
      local index=$((choice))
      if (( index < 1 || index > ${#discovered[@]} )); then
        msg "Indice hors plage."
        continue
      fi
      local selected="${discovered[index-1]}"
      IFS='|' read -r mac name <<<"$selected"
      SELECTED_BLUETOOTH_MAC="$mac"
      SELECTED_BLUETOOTH_NAME="$name"
      local display_name="$name"
      if [[ -z "$display_name" ]]; then
        display_name="$mac"
      fi
      msg "Peripherique selectionne : $display_name ($mac)"
      return 0
    fi

    msg "Choix invalide: $choice"
  done
}

configure_bluetooth() {
  if ! command -v bluetoothctl >/dev/null 2>&1; then
    msg "bluetoothctl introuvable, configuration bluetooth ignoree."
    return
  fi

  msg "Configuration bluetoothctl (activation service et mode recherche)."
  if command -v systemctl >/dev/null 2>&1; then
    if systemctl list-unit-files bluetooth.service >/dev/null 2>&1; then
      systemctl enable --now bluetooth.service || msg "Impossible d'activer bluetooth.service (verifier manuellement)."
    else
      msg "bluetooth.service introuvable via systemctl, verifier l'installation BlueZ."
    fi
  fi

  if ! bluetoothctl <<'EOF'; then
power on
agent on
default-agent
discoverable on
pairable on
EOF
    msg "Impossible de parametrer bluetoothctl automatiquement."
  fi

  manage_paired_devices
  prompt_bluetooth_pairing

  local target_mac=""
  local target_name=""

  if [[ -n "${SKULL_BT_MAC:-}" ]]; then
    local candidate
    candidate=$(echo "$SKULL_BT_MAC" | tr '[:lower:]' '[:upper:]')
    if [[ "$candidate" =~ ^([0-9A-F]{2}:){5}[0-9A-F]{2}$ ]]; then
      target_mac="$candidate"
      target_name="${SKULL_BT_NAME:-}"
      msg "Appairage automatique demande via SKULL_BT_MAC=$target_mac"
    else
      msg "Valeur SKULL_BT_MAC invalide ($SKULL_BT_MAC). Passage en selection manuelle."
    fi
  fi

  if [[ -z "$target_mac" ]]; then
    if ! scan_and_select_device; then
      msg "Aucun peripherique bluetooth selectionne. Appairage ignore."
      return
    fi
    target_mac="$SELECTED_BLUETOOTH_MAC"
    target_name="$SELECTED_BLUETOOTH_NAME"
  fi

  local label="$target_mac"
  if [[ -n "$target_name" ]]; then
    label="$target_name ($target_mac)"
  fi

  if bluetoothctl <<EOF; then
scan on
pair $target_mac
trust $target_mac
connect $target_mac
scan off
EOF
    msg "Appairage bluetooth reussi pour $label."
  else
    msg "Echec de l'appairage bluetooth pour $label. Reessayez manuellement avec bluetoothctl."
    return
  fi

  if ! bluetoothctl autoconnect "$target_mac" >/dev/null 2>&1; then
    bluetoothctl connect "$target_mac" >/dev/null 2>&1 || true
  fi

  if [[ -z "$target_name" ]]; then
    target_name=$(bluetoothctl info "$target_mac" 2>/dev/null | sed -n 's/^[[:space:]]*Name:[[:space:]]*//p' | head -n1)
  fi

  PAIRED_BLUETOOTH_MAC="$target_mac"
  PAIRED_BLUETOOTH_NAME="${target_name:-}"
}

enable_i2c() {
  if [[ ! -e /boot/config.txt ]]; then
    msg "Fichier /boot/config.txt introuvable, activation I2C impossible automatiquement."
    return
  fi

  if command -v raspi-config >/dev/null 2>&1; then
    local current
    current=$(raspi-config nonint get_i2c 2>/dev/null || echo "1")
    if [[ "$current" != "0" ]]; then
      msg "Activation I2C via raspi-config"
      if ! raspi-config nonint do_i2c 0; then
        msg "Echec raspi-config pour I2C, verifier manuellement."
      fi
    else
      msg "I2C deja active (raspi-config)."
    fi
  else
    if grep -Eq '^[[:space:]]*dtparam=i2c_arm=on' /boot/config.txt; then
      msg "I2C deja active dans /boot/config.txt."
    else
      msg "Activation I2C en ajoutant dtparam=i2c_arm=on dans /boot/config.txt"
      printf '\ndtparam=i2c_arm=on\n' >> /boot/config.txt
    fi
  fi

  if [[ -f /etc/modules ]] && ! grep -Eq '^[[:space:]]*i2c-dev' /etc/modules; then
    msg "Ajout du module i2c-dev dans /etc/modules"
    printf 'i2c-dev\n' >> /etc/modules
  fi

  if ! lsmod | grep -q '^i2c_dev'; then
    modprobe i2c-dev || true
  fi
}

write_systemd_service() {
  msg "Creation du service systemd $SERVICE_NAME"

  cat >"/etc/systemd/system/$SERVICE_NAME" <<EOF
[Unit]
Description=Servo Sync Player (Skull-V2)
After=network-online.target bluetooth.service
Wants=network-online.target bluetooth.service

[Service]
Type=simple
User=$SKULL_USER
Group=$SKULL_GROUP
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
Environment=VIRTUAL_ENV=$INSTALL_DIR/.venv
Environment=PATH=$INSTALL_DIR/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=XDG_RUNTIME_DIR=/run/user/$SKULL_UID
Environment=PULSE_SERVER=unix:/run/user/$SKULL_UID/pulse/native
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$SKULL_UID/bus
EnvironmentFile=-$INSTALL_DIR/config/bluetooth_device.env
ExecStartPre=/bin/sh -c "if [ -n \"\${PLAYLIST_BT_DEVICE_ADDR:-}\" ]; then /usr/bin/bluetoothctl connect \"\${PLAYLIST_BT_DEVICE_ADDR}\" >/dev/null 2>&1 || true; fi"
ExecStart=$INSTALL_DIR/.venv/bin/python $INSTALL_DIR/web_app.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
  chmod 644 "/etc/systemd/system/$SERVICE_NAME"
}

enable_service() {
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "$SKULL_USER" || true
  fi
  systemctl daemon-reload
  systemctl enable --now "$SERVICE_NAME"
}

main() {
  require_root
  detect_user
  msg "Installation pour l'utilisateur $SKULL_USER (UID=$SKULL_UID)"
  announce_step "Installation des dependances systeme (APT)"
  install_apt_packages
  announce_step "Activation du support I2C"
  enable_i2c
  announce_step "Configuration Bluetooth"
  configure_bluetooth
  announce_step "Deploiement du code Skull-V2"
  prepare_source_tree
  announce_step "Generation du fichier requirements.txt"
  write_requirements
  announce_step "Installation des dependances Python"
  setup_python_env
  announce_step "Preparation des repertoires applicatifs"
  prepare_runtime_dirs
  persist_bluetooth_device
  announce_step "Verification / creation du runtime utilisateur"
  ensure_runtime_dir
  announce_step "Creation du service systemd"
  write_systemd_service
  announce_step "Activation du service"
  enable_service
  msg "Installation terminee."
  msg "Le service peut etre controle avec : systemctl status $SERVICE_NAME"
  msg "Si c'est la premiere activation I2C, redemarrez l'appareil."
}

main "$@"
