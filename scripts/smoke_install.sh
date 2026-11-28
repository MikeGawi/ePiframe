#!/bin/bash
# Smoke test of an installed ePiframe (install.sh or the DEB package), run as root:
#
#   sudo scripts/smoke_install.sh [--port PORT]
#
# It finds the installation through its service (user, folder, configuration) and
# checks the epiframe command (run as root, so through its switch of user), the
# unit (systemd-analyze verify), check-config, the photo chain (epiframe test) with
# a generated photo, a file argument relative to the caller's folder
# (test-convert) and the service: started with the WebUI on 127.0.0.1:PORT and no
# scheduled photo changes, the WebUI answers, the service stops cleanly.
# config.cfg and the state of the service are restored afterwards. The CI runs it
# on clean runners after install.sh and after installing the DEB package; it works
# on a frame too (the test photo is removed, epiframe test --no-skip keeps the
# current photo).
#
# The script can be sourced (tests call its functions); it only runs main when executed.

set -o nounset -o pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=install.sh
source "$ROOT/install.sh" || exit 1

PORT=8080
# seconds to wait for the WebUI
WAIT=90
# no working hours: the service changes the photo only on request
NEVER="-,-,-,-,-,-,-"
PHOTO="epiframe-smoke.png"
SERVICE_STARTED="ePiframe Service: STARTED"

DATA_DIR=""
CONFIG=""
PHOTO_FILE=""
WORK=""
WAS_ACTIVE=0

# --------------------------------------------------------------------- arguments

function show_smoke_help {
	cat << EOF
Smoke test of an installed ePiframe (install.sh or the DEB package)

Usage: sudo scripts/smoke_install.sh [--port PORT]

  --port PORT   WebUI port for the test (default: $PORT)
EOF
}

function parse_smoke_arguments {
	while (( $# )); do
		case $1 in
			--port)
				[[ ${2:-} =~ ^[0-9]+$ ]] || die "--port needs a number"
				PORT=$2
				shift
				;;
			--help | -h) show_smoke_help; exit 0 ;;
			*) die "Unknown option $1 (see --help)" ;;
		esac
		shift
	done
}

# ------------------------------------------------------------------ installation

function unit_property {
	systemctl show -P "$1" "$SERVICE"
}

# unit_environment NAME: the value of NAME in the unit's Environment=
function unit_environment {
	unit_property Environment | tr ' ' '\n' | sed -n "s/^$1=//p"
}

# the user, the data folder and config.cfg of the installed service
function find_installation {
	[[ $(unit_property LoadState) == loaded ]] || die "$SERVICE is not installed"
	EPI_USER=$(unit_property User)
	DATA_DIR=$(unit_property WorkingDirectory)
	[[ -n $EPI_USER && -d $DATA_DIR ]] || die "$SERVICE has no User or WorkingDirectory"
	local config_dir
	config_dir=$(unit_environment EPIFRAME_CONFIG_DIR)
	CONFIG="${config_dir:-$DATA_DIR}/config.cfg"
	[[ -f $CONFIG ]] || die "There is no $CONFIG"
}

# config_value NAME
function config_value {
	sed -n "s/^$1=//p" "$CONFIG" | head -n 1
}

# frame_path PATH: a path of config.cfg (relative ones are in the data folder)
function frame_path {
	if [[ $1 == /* ]]; then
		echo "$1"
	else
		echo "$DATA_DIR/$1"
	fi
}

# set_entries NAME=VALUE...: change config.cfg as its owner (owner and mode stay)
function set_entries {
	local entry expressions=()
	for entry in "$@"; do
		grep -q "^${entry%%=*}=" "$CONFIG" || return 1
		expressions+=(-e "s|^${entry%%=*}=.*|$entry|")
	done
	as_user sed -i "${expressions[@]}" "$CONFIG"
}

# ------------------------------------------------------------------------- state

# keep config.cfg (cp -p keeps its mode: the folder is readable for
# test-convert) and stop a running service (its photo changes would take the
# frame while the test runs)
function save_state {
	WORK=$(mktemp -d) && chmod 0755 "$WORK" && cp -p "$CONFIG" "$WORK/config.cfg" || return 1
	if systemctl is-active --quiet "$SERVICE"; then
		WAS_ACTIVE=1
		systemctl stop "$SERVICE" || return 1
	fi
	return 0
}

function restore_state {
	[[ -n $WORK ]] || return 0
	systemctl stop "$SERVICE" 2> /dev/null
	# written into the file: its owner and mode stay
	[[ -f $WORK/config.cfg ]] && cat "$WORK/config.cfg" > "$CONFIG"
	[[ -n $PHOTO_FILE ]] && rm -f "$PHOTO_FILE"
	(( WAS_ACTIVE )) && systemctl start "$SERVICE"
	rm -rf "$WORK"
	WORK=""
}

function show_journal {
	journalctl -u "$SERVICE" -n 40 --no-pager >&2
}

function finish {
	local result=$?
	(( result )) && show_journal
	restore_state
	return "$result"
}

# ------------------------------------------------------------------------ checks

function check_unit {
	systemd-analyze verify --man=no "$(unit_property FragmentPath)"
}

# a photo in the local source folder, made with the configured ImageMagick
function add_photo {
	local folder
	folder=$(frame_path "$(config_value local_path)")
	PHOTO_FILE="$folder/$PHOTO"
	as_user mkdir -p "$folder" \
		&& as_user "$(config_value convert_bin_path)" -size 320x240 xc:red "$PHOTO_FILE"
}

# test-convert of a file name relative to the folder the command runs in
function convert_caller_file {
	install -m 0644 "$PHOTO_FILE" "$WORK/$PHOTO" \
		&& (cd "$WORK" && epiframe test-convert "$PHOTO")
}

function configure_service {
	set_entries use_web=1 web_host=127.0.0.1 "web_port=$PORT" "start_times=$NEVER" \
		"stop_times=$NEVER" control_display_power=0
}

function wait_for_webui {
	local deadline=$(( SECONDS + WAIT ))
	until curl -fsS -o /dev/null "http://127.0.0.1:$PORT/"; do
		systemctl is-active --quiet "$SERVICE" || return 1
		(( SECONDS < deadline )) || return 1
		sleep 1
	done
}

function check_service_log {
	local log
	log=$(config_value log_files)
	[[ -z $log ]] || grep -qF "$SERVICE_STARTED" "$(frame_path "$log")"
}

function stop_cleanly {
	systemctl stop "$SERVICE" && [[ $(unit_property Result) == success ]]
}

# ------------------------------------------------------------------------- main

function is_root {
	(( EUID == 0 ))
}

function smoke_main {
	parse_smoke_arguments "$@"
	is_root || die "Run the smoke test as root (sudo)"
	prepare_log
	find_installation
	header "Smoke test of $(epiframe --version 2> /dev/null) in $DATA_DIR (user $EPI_USER, $CONFIG)"
	save_state || die "Can't save the state of ePiframe"
	trap finish EXIT
	step "The epiframe command" epiframe --version
	step "Checking $SERVICE" check_unit
	step "Checking the configuration" epiframe check-config
	step "Adding a test photo" add_photo
	step "Converting a photo (epiframe test)" epiframe test --no-skip
	step "Converting a file of this folder" convert_caller_file
	step "WebUI on port $PORT, no photo changes" configure_service
	step "Starting $SERVICE" systemctl start "$SERVICE"
	step "Waiting for the WebUI" wait_for_webui
	step "Checking the service log" check_service_log
	step "Stopping $SERVICE" stop_cleanly
	rm -f "$LOG"
	header "The smoke test passed"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
	smoke_main "$@"
fi
