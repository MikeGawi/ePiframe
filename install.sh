#!/bin/bash
# ePiframe installer for Raspberry Pi OS Bookworm / Trixie (and other Debian based
# systems with --no-hardware).
#
#   sudo ./install.sh [--path DIR] [--branch REF] ...   install
#   sudo ./install.sh --update [--path DIR]             update to the latest release
#   sudo ./install.sh --uninstall                       remove the service
#
# The code is a git checkout (latest v2 release tag, or --branch), the Python
# environment is a uv venv (.venv in the checkout, system Python, uv.lock) and the
# service runs as the user who installed ePiframe. See ./install.sh --help.
#
# The script can be sourced (tests call its functions); it only runs main when executed.

set -o nounset -o pipefail

REPO_URL="https://github.com/MikeGawi/ePiframe.git"
SERVICE="ePiframe.service"
UNIT_FILE="/etc/systemd/system/$SERVICE"
UNIT_TEMPLATE="misc/ePiframe.service.org"
SUDOERS_FILE="/etc/sudoers.d/epiframe"
COMMAND_FILE="/usr/local/bin/epiframe"
BIN_DIR="/usr/local/bin"
SYSTEM_PYTHON="/usr/bin/python3"
DEFAULT_CONFIG="src/epiframe/config/config.default"

# uv (Python package and project manager) release used when no recent uv is installed
UV_VERSION="0.11.19"
UV_RELEASES="https://github.com/astral-sh/uv/releases/download"
PIWHEELS_INDEX="https://www.piwheels.org/simple"

# vendor display libraries, pinned to the versions ePiframe was checked against
WAVESHARE_REPO="https://github.com/waveshareteam/e-Paper.git"
WAVESHARE_COMMIT="d28b3c4cfc78eef1c6cd6e6e3013654e449d2864"
WAVESHARE_PATH="RaspberryPi_JetsonNano/python/lib/waveshare_epd"
INKY_REPO="https://github.com/pimoroni/inky.git"
# v2.7.0
INKY_COMMIT="36de9bcdf39367cb94505d9637d837537f5f5429"
INKY_PATH="inky"

# system packages: tools used by ePiframe, then the Raspberry Pi only ones (lgpio
# library of the piwheels lgpio wheel) and the build tools for the packages without
# 64-bit ARM wheels (spidev, lgpio on Python 3.13)
APT_PACKAGES=(git ca-certificates curl imagemagick webp dcraw fbi python3)
APT_PI_PACKAGES=(liblgpio1)
APT_BUILD_PACKAGES=(gcc python3-dev swig liblgpio-dev)
# HDMI (fbi, vcgencmd) and the e-Paper interfaces (SPI, GPIO, I2C for the Inky EEPROM)
USER_GROUPS=(video tty)
USER_PI_GROUPS=(spi gpio i2c)
# Python modules checked after the installation
PYTHON_MODULES=(epiframe.cli numpy PIL.Image cryptography.hazmat.primitives.hashes)
PYTHON_PI_MODULES=(spidev gpiozero lgpio smbus2 gpiod)

ACTION="install"
INSTALL_DIR=""
EPI_USER=""
REF=""
ASSUME_YES=0
HARDWARE=1
REBOOT_NEEDED=0
LOG="/dev/null"
UV=""
# the plugins folder (default: plugins in the installation folder) and extra options
# of the plugin packages' uv pip install (the DEB package sets both)
PLUGINS_DIR=""
PLUGIN_UV_OPTIONS=()

if [[ -t 1 ]]; then
	BOLD=$'\033[1;37m'
	DIM=$'\033[0;37m'
	GREEN=$'\033[1;32m'
	RED=$'\033[0;31m'
	RESET=$'\033[0m'
else
	BOLD="" DIM="" GREEN="" RED="" RESET=""
fi

function show_logo {
	[[ -t 1 ]] || return 0
	# the backticks are part of the picture
	# shellcheck disable=SC2016
	echo -e '
\033[0;37m MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM
\033[0;37m M\033[1;30mMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN                                  \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN               \033[0;37m`MMMMMMMMMMMMMMm\033[1;30m   \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN     \033[0;37m.+yhhy+.   \033[0;37m.-M\033[1;30mM\033[0;30ms`````hMN..   \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN   \033[0;37m.h\033[1;30mMMmyshNM\033[0;30mh.  \033[0;37m`M\033[1;30mM\033[0;30mo     \033[0;37mh\033[1;30mM\033[0;30mN     \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN  \033[0;37m`m\033[1;30mMM\033[0;30my\033[0;30m````\033[1;30m.m\033[0;30mMm` \033[0;37m`M\033[1;30mM\033[0;30mo     \033[0;37mh\033[1;30mM\033[0;30mN     \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN  \033[0;37m:M\033[1;30mMMM\033[0;37mMMMM\033[1;30mMM\033[0;30mMM: \033[0;37m`M\033[1;30mM\033[0;30mo     \033[0;37mh\033[1;30mM\033[0;30mN     \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN  \033[0;37m`N\033[1;30mMM\033[0;30md:         \033[0;37m`M\033[1;30mM\033[0;30mo     \033[0;37mh\033[1;30mM\033[0;30mN     \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN   \033[0;37m-m\033[1;30mMMdsos\033[0;37mdMMo\033[1;30m  \033[0;37m`M\033[1;30mM\033[0;30mo     \033[0;37my\033[1;30mM\033[0;30mN`    \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN    \033[0;37m`m\033[1;30mymNN\033[0;30mNdy+`  \033[0;37m`N\033[0;30mNo     \033[0;37m`\033[0;30mNMMN:  \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN                                  \033[0;37mN\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mM\033[0;30mN\033[0;37m..................................N\033[1;30mM\033[0;30mM
\033[0;37m M\033[1;30mMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\033[0;30mM
\033[0;37m M\033[0;30mMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\033[0m

\033[1;37mePiframe - e-Paper Raspberry Pi Photo Frame\033[0m\n'
}

# ------------------------------------------------------------------------- output

function header {
	printf '\n%s%s%s\n' "$DIM" "$1" "$RESET"
}

function info {
	printf '%s%s%s\n' "$BOLD" "$1" "$RESET"
}

function warn {
	printf '%sWarning: %s%s\n' "$RED" "$1" "$RESET" >&2
}

function die {
	printf '%sError: %s%s\n' "$RED" "$1" "$RESET" >&2
	exit 1
}

# try_step LABEL COMMAND...: run COMMAND (in this shell) with its output in the log,
# return its result
function try_step {
	local label=$1
	shift
	printf '%s%-36s%s' "$BOLD" "$label:" "$RESET"
	if "$@" >> "$LOG" 2>&1; then
		printf '%scheck!%s\n' "$GREEN" "$RESET"
		return 0
	fi
	printf '%serror!%s\n' "$RED" "$RESET"
	return 1
}

# step LABEL COMMAND...: try_step, stop on failure
function step {
	local label=$1
	try_step "$@" && return 0
	if [[ -f $LOG ]]; then
		tail -n 20 "$LOG" >&2
		die "$label failed, the full output is in $LOG"
	fi
	die "$label failed"
}

# confirm QUESTION DEFAULT(Y|N): ask a yes/no question; --yes, an empty answer and
# the end of the input take the default
function confirm {
	local question=$1 default=$2 answer="" hint="[y/N]"
	[[ $default == Y ]] && hint="[Y/n]"
	if (( ASSUME_YES )); then
		answer=$default
	elif ! read -r -p "${BOLD}${question} ${hint} ${RESET}" answer; then
		echo
	fi
	answer=${answer:-$default}
	[[ $answer == [Yy]* ]]
}

# --------------------------------------------------------------------- arguments

function show_help {
	cat << EOF
ePiframe - e-Paper Raspberry Pi Photo Frame installer

Usage: sudo ./install.sh [option]...

  (no action)       install ePiframe
  --update          update an installation to the latest release (or its branch)
  --uninstall       remove the service (the ePiframe folder stays)
  --plugins         install the Python packages of the plugins (requirements.txt
                    in a plugin folder), e.g. after adding a plugin
  --next-steps      show the steps after the installation
  --help            this help

Options:
  --path DIR        installation folder (default: ~/ePiframe of the user;
                    --update: the folder of the installed service)
  --user NAME       user who owns the files and runs the service
                    (default: the user who ran sudo)
  --branch REF      release tag or branch to install (default: the latest release)
  --repo URL        git repository (default: $REPO_URL)
  --yes             don't ask, take the default answers
  --no-hardware     not a Raspberry Pi: skip the Raspberry Pi checks, SPI/I2C and
                    the GPIO packages (development machines, CI)
EOF
}

function parse_arguments {
	while (( $# )); do
		case $1 in
			--update) ACTION="update" ;;
			--uninstall) ACTION="uninstall" ;;
			--plugins) ACTION="plugins" ;;
			--next-steps) ACTION="next-steps" ;;
			--help | -h) ACTION="help" ;;
			# internal: the second half of --update, run by the updated script
			--resume-update) ACTION="resume-update" ;;
			--yes | -y) ASSUME_YES=1 ;;
			--no-hardware) HARDWARE=0 ;;
			--path | --user | --branch | --repo)
				(( $# > 1 )) || die "$1 needs a value"
				case $1 in
					--path) INSTALL_DIR=$2 ;;
					--user) EPI_USER=$2 ;;
					--branch) REF=$2 ;;
					--repo) REPO_URL=$2 ;;
				esac
				shift
				;;
			*) die "Unknown option $1 (see --help)" ;;
		esac
		shift
	done
}

# ------------------------------------------------------------------------ checks

function check_install_dir {
	[[ $1 =~ ^/[A-Za-z0-9._/-]+$ ]] \
		|| die "The installation folder must be an absolute path of letters, digits and ._-/ ($1)"
}

function user_home {
	getent passwd "$1" | cut -d: -f6
}

function check_user {
	[[ -n $EPI_USER ]] || die "Run the installer with sudo as the user who will own ePiframe, or pass --user NAME"
	id -u "$EPI_USER" > /dev/null 2>&1 || die "There is no user $EPI_USER"
	[[ $EPI_USER != root ]] || warn "ePiframe will run as root"
}

function check_os {
	command -v apt-get > /dev/null || die "ePiframe needs Raspberry Pi OS (or another Debian based system with apt)"
	local codename=""
	if [[ -f /etc/os-release ]]; then
		codename=$(sed -n 's/^VERSION_CODENAME=//p' /etc/os-release | tr -d '"')
	fi
	case $codename in
		stretch | buster | bullseye)
			die "Raspberry Pi OS $codename is too old: ePiframe needs Bookworm or newer (Python 3.11). Install a fresh OS (copy config.cfg and misc/users.db of ePiframe 1.x first)"
			;;
	esac
}

function machine {
	uname -m
}

function check_machine {
	local arch
	arch=$(machine)
	case $arch in
		armv6l | armv7l | aarch64) ;;
		x86_64) (( ! HARDWARE )) || die "This is not a Raspberry Pi ($arch), use --no-hardware to install anyway" ;;
		*) die "Unsupported architecture $arch" ;;
	esac
	if (( HARDWARE )); then
		local model=""
		[[ -r /proc/device-tree/model ]] && model=$(tr -d '\0' < /proc/device-tree/model)
		[[ $model == *"Raspberry Pi"* ]] \
			|| die "This is not a Raspberry Pi (${model:-unknown model}), use --no-hardware to install anyway"
	fi
}

function check_python {
	[[ -x $SYSTEM_PYTHON ]] || die "There is no $SYSTEM_PYTHON"
	"$SYSTEM_PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
		|| die "ePiframe needs Python 3.11 or newer ($("$SYSTEM_PYTHON" -V 2>&1)), install Raspberry Pi OS Bookworm or newer"
	"$SYSTEM_PYTHON" -c 'import sqlite3, sys; sys.exit(sqlite3.sqlite_version_info < (3, 35))' \
		|| die "ePiframe needs SQLite 3.35 or newer, install Raspberry Pi OS Bookworm or newer"
}

# ----------------------------------------------------------------- system packages

function apt_install {
	DEBIAN_FRONTEND=noninteractive apt-get install -y -q "$@"
}

function apt_packages {
	local packages=("${APT_PACKAGES[@]}")
	if (( HARDWARE )); then
		packages+=("${APT_PI_PACKAGES[@]}")
		[[ $(machine) == aarch64 ]] && packages+=("${APT_BUILD_PACKAGES[@]}")
	fi
	echo "${packages[@]}"
}

function install_system_packages {
	header "Installing system packages"
	local packages
	read -r -a packages <<< "$(apt_packages)"
	step "Updating the package lists" apt-get update -q
	step "Installing ${#packages[@]} packages" apt_install "${packages[@]}"
	step "Checking Python and SQLite" check_python
}

# ---------------------------------------------------------------------------- uv

function uv_target {
	case $1 in
		armv6l) echo "arm-unknown-linux-musleabihf" ;;
		armv7l) echo "armv7-unknown-linux-gnueabihf" ;;
		aarch64) echo "aarch64-unknown-linux-gnu" ;;
		x86_64) echo "x86_64-unknown-linux-gnu" ;;
		*) return 1 ;;
	esac
}

# version_at_least VERSION MINIMUM
function version_at_least {
	[[ $(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n 1) == "$2" ]]
}

# print the path of an installed uv that is recent enough
function find_uv {
	local uv version
	for uv in "$BIN_DIR/uv" "$(command -v uv 2> /dev/null)"; do
		[[ -n $uv && -x $uv ]] || continue
		version=$("$uv" --version 2> /dev/null | cut -d' ' -f2)
		if [[ -n $version ]] && version_at_least "$version" "$UV_VERSION"; then
			echo "$uv"
			return 0
		fi
	done
	return 1
}

function download_uv {
	local target archive folder
	target=$(uv_target "$(machine)") || return 1
	archive="uv-$target.tar.gz"
	folder=$(mktemp -d)
	curl -fsSL --retry 3 -o "$folder/$archive" "$UV_RELEASES/$UV_VERSION/$archive" \
		&& curl -fsSL --retry 3 -o "$folder/$archive.sha256" "$UV_RELEASES/$UV_VERSION/$archive.sha256" \
		&& (cd "$folder" && sha256sum -c "$archive.sha256") \
		&& tar -xzf "$folder/$archive" -C "$folder" \
		&& install -m 0755 "$folder/uv-$target/uv" "$folder/uv-$target/uvx" "$BIN_DIR/"
	local result=$?
	rm -rf "$folder"
	return $result
}

function install_uv {
	header "Installing uv (Python package manager)"
	if UV=$(find_uv); then
		info "Found $("$UV" --version)"
		return 0
	fi
	step "Downloading uv $UV_VERSION" download_uv
	UV="$BIN_DIR/uv"
}

# --------------------------------------------------------------------------- code

function as_user {
	sudo -u "$EPI_USER" -H -- "$@"
}

# latest_tag REPOSITORY: the newest v2+ release tag (no pre-releases)
function latest_tag {
	{ git -c versionsort.suffix=- ls-remote --tags --refs --sort=-version:refname "$1" 'v[2-9]*' || true; } \
		| sed 's|.*refs/tags/||' | { grep -v -- - || true; } | head -n 1
}

function check_new_install_dir {
	if [[ -d $INSTALL_DIR/.git && -d $INSTALL_DIR/src/epiframe ]]; then
		die "ePiframe is installed in $INSTALL_DIR already, use --update"
	fi
	if [[ -e $INSTALL_DIR ]] && [[ -n $(ls -A "$INSTALL_DIR" 2> /dev/null) ]]; then
		die "$INSTALL_DIR is not empty, choose another folder with --path"
	fi
	return 0
}

function clone_code {
	install -d -o "$EPI_USER" -g "$(id -gn "$EPI_USER")" "$INSTALL_DIR" \
		&& as_user git clone --quiet --branch "$REF" "$REPO_URL" "$INSTALL_DIR"
}

function install_code {
	header "Downloading ePiframe"
	if [[ -z $REF ]]; then
		REF=$(latest_tag "$REPO_URL")
		[[ -n $REF ]] || die "No ePiframe 2 release found in $REPO_URL, choose a branch or tag with --branch (e.g. --branch v2)"
	fi
	step "Cloning $REF" clone_code
}

# -------------------------------------------------------------------- Python venv

function sync_venv {
	as_user env UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 \
		"$UV" sync --directory "$INSTALL_DIR" --locked --no-dev --python "$SYSTEM_PYTHON"
}

# apt packages needed by the piwheels wheels (system libraries they link to)
function install_wheel_libraries {
	local packages
	if ! packages=$(as_user "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/scripts/piwheels_apt.py" 2>> "$LOG"); then
		warn "Can't read the system libraries the piwheels packages need, the check below will tell if one is missing"
		return 0
	fi
	local list
	read -r -d '' -a list <<< "$packages"
	(( ${#list[@]} )) || return 0
	step "Installing libraries for piwheels" apt_install "${list[@]}"
}

# the requirements.txt files of the installed plugins
function plugin_requirements {
	local file
	for file in "${PLUGINS_DIR:-$INSTALL_DIR/plugins}"/*/requirements.txt; do
		[[ -f $file ]] && echo "$file"
	done
	return 0
}

# piwheels next to PyPI on 32-bit ARM (the best wheel of both wins)
function plugin_index_options {
	case $(machine) in
		armv6l | armv7l) echo "--extra-index-url $PIWHEELS_INDEX --index-strategy unsafe-best-match" ;;
	esac
	return 0
}

# the plugins' Python packages, constrained to the versions of uv.lock so that a
# plugin can't change the packages ePiframe was tested with; uv sync removes them,
# so they are installed again after every sync
function install_plugin_packages {
	local requirements=() file options constraints
	while IFS= read -r file; do
		requirements+=(--requirement "$file")
	done < <(plugin_requirements)
	(( ${#requirements[@]} )) || return 0
	read -r -a options <<< "$(plugin_index_options)"
	constraints=$(as_user mktemp) || return 1
	as_user "$UV" export --directory "$INSTALL_DIR" --frozen --no-dev --no-hashes \
		--no-emit-project --quiet --output-file "$constraints" \
		&& as_user env UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 \
			"$UV" pip install --python "$INSTALL_DIR/.venv/bin/python" \
			--constraint "$constraints" "${options[@]}" "${PLUGIN_UV_OPTIONS[@]}" \
			"${requirements[@]}"
	local result=$?
	rm -f "$constraints"
	return $result
}

function install_wheel_libraries_on_arm32 {
	case $(machine) in
		armv6l | armv7l) install_wheel_libraries ;;
	esac
	return 0
}

function python_modules {
	local modules=("${PYTHON_MODULES[@]}")
	(( HARDWARE )) && modules+=("${PYTHON_PI_MODULES[@]}")
	echo "${modules[@]}"
}

# the import of lgpio creates its notification pipe (.lgd-nfy*) in the current
# folder, so the check runs in an empty folder of the user (the installer may be
# started anywhere, dpkg runs postinst in /)
function check_python_modules {
	local modules folder
	read -r -a modules <<< "$(python_modules)"
	folder=$(as_user mktemp -d) || return 1
	(cd "$folder" && as_user "$INSTALL_DIR/.venv/bin/python" -c \
		'import importlib, sys; [importlib.import_module(name) for name in sys.argv[1:]]' \
		"${modules[@]}")
	local result=$?
	rm -rf "$folder"
	return $result
}

function install_python_environment {
	header "Installing the Python environment (this takes a while on a Pi Zero)"
	step "Installing Python packages" sync_venv
	if [[ -n $(plugin_requirements) ]]; then
		try_step "Installing plugin packages" install_plugin_packages \
			|| warn "The Python packages of the plugins can't be installed (see $LOG), ePiframe will skip the plugins that need them"
	fi
	install_wheel_libraries_on_arm32
	step "Checking Python packages" check_python_modules
}

# ------------------------------------------------------------- display libraries

# fetch_library REPOSITORY COMMIT PATH NAME: copy PATH of COMMIT to lib/NAME
function fetch_library {
	local repository=$1 commit=$2 path=$3 name=$4
	local library="$INSTALL_DIR/lib" stamp="$INSTALL_DIR/lib/.$4.commit"
	if [[ -d $library/$name && -f $stamp && $(< "$stamp") == "$commit" ]]; then
		return 0
	fi
	local folder
	folder=$(mktemp -d)
	git -C "$folder" init -q \
		&& git -C "$folder" remote add origin "$repository" \
		&& git -C "$folder" sparse-checkout set --no-cone "/$path/" \
		&& git -C "$folder" fetch -q --depth 1 --filter=blob:none origin "$commit" \
		&& git -C "$folder" -c advice.detachedHead=false checkout -q FETCH_HEAD \
		&& rm -rf "${library:?}/$name" \
		&& install -d "$library" \
		&& cp -r "$folder/$path" "$library/$name" \
		&& echo "$commit" > "$stamp" \
		&& chown -R "$EPI_USER:$(id -gn "$EPI_USER")" "$library"
	local result=$?
	rm -rf "$folder"
	return $result
}

function install_display_libraries {
	header "Installing display libraries"
	step "Waveshare (${WAVESHARE_COMMIT:0:7})" fetch_library "$WAVESHARE_REPO" "$WAVESHARE_COMMIT" "$WAVESHARE_PATH" waveshare_epd
	step "Pimoroni Inky (${INKY_COMMIT:0:7})" fetch_library "$INKY_REPO" "$INKY_COMMIT" "$INKY_PATH" inky
}

# ---------------------------------------------------------------------- hardware

function enable_interface {
	local name=$1
	[[ $(raspi-config nonint "get_$name") == 0 ]] && return 0
	raspi-config nonint "do_$name" 0 || return 1
	REBOOT_NEEDED=1
}

function enable_interfaces {
	(( HARDWARE )) || return 0
	header "Enabling the display interfaces"
	if ! command -v raspi-config > /dev/null; then
		warn "There is no raspi-config, enable SPI (and I2C for Pimoroni Inky) by hand"
		return 0
	fi
	local name
	for name in spi i2c; do
		try_step "Enabling ${name^^}" enable_interface "$name" \
			|| warn "Can't enable ${name^^}, enable it in raspi-config by hand"
	done
}

function user_groups {
	local groups=("${USER_GROUPS[@]}") group existing=()
	(( HARDWARE )) && groups+=("${USER_PI_GROUPS[@]}")
	for group in "${groups[@]}"; do
		getent group "$group" > /dev/null && existing+=("$group")
	done
	local IFS=,
	echo "${existing[*]}"
}

function add_user_groups {
	local groups
	groups=$(user_groups)
	[[ -z $groups ]] || usermod -a -G "$groups" "$EPI_USER"
}

# ------------------------------------------------------------------------ service

function systemctl_path {
	command -v systemctl || echo /usr/bin/systemctl
}

function sudoers_rules {
	local systemctl
	systemctl=$(systemctl_path)
	cat << EOF
# ePiframe (install.sh): the service user may reboot, power off and restart ePiframe
$1 ALL=(root) NOPASSWD: $systemctl reboot, $systemctl poweroff, $systemctl --no-block restart $SERVICE
EOF
}

function install_sudoers {
	local file
	file=$(mktemp)
	sudoers_rules "$EPI_USER" > "$file" \
		&& visudo -c -q -f "$file" \
		&& install -m 0440 "$file" "$SUDOERS_FILE"
	local result=$?
	rm -f "$file"
	return $result
}

# render_unit TEMPLATE USER DIR
function render_unit {
	sed -e "s|@USER@|$2|g" -e "s|@DIR@|$3|g" "$1"
}

function install_unit {
	local file
	file=$(mktemp)
	render_unit "$INSTALL_DIR/$UNIT_TEMPLATE" "$EPI_USER" "$INSTALL_DIR" > "$file" \
		&& rm -f "$UNIT_FILE" \
		&& install -m 0644 "$file" "$UNIT_FILE" \
		&& systemctl daemon-reload \
		&& systemctl enable --quiet "$SERVICE"
	local result=$?
	rm -f "$file"
	return $result
}

# command_script USER DIR: the epiframe command on the PATH
function command_script {
	cat << EOF
#!/bin/sh
# ePiframe (install.sh): runs the frame's epiframe command in its folder (the paths
# in config.cfg are relative to it) and as its user (files created by root would
# lock the service out); file arguments stay relative to the current folder
if [ "\$(id -u)" -eq 0 ] && [ "$1" != root ]; then
	exec runuser -u '$1' -- "\$0" "\$@"
fi
export EPIFRAME_CALLER_DIR="\$PWD"
cd '$2' || exit 1
exec '$2/.venv/bin/epiframe' "\$@"
EOF
}

function install_command {
	command_script "$EPI_USER" "$INSTALL_DIR" > "$COMMAND_FILE" && chmod 0755 "$COMMAND_FILE"
}

function install_service {
	header "Installing the ePiframe service"
	step "Adding $EPI_USER to the device groups" add_user_groups
	step "Allowing reboot and restart" install_sudoers
	step "Installing $SERVICE" install_unit
	step "Installing the epiframe command" install_command
}

function installed_service_dir {
	systemctl show -P WorkingDirectory "$SERVICE" 2> /dev/null || true
}

function service_enabled {
	systemctl is-enabled --quiet "$SERVICE" 2> /dev/null
}

function stop_service {
	systemctl stop "$SERVICE" 2> /dev/null || true
}

function replace_existing_service {
	service_enabled || return 0
	local folder
	folder=$(installed_service_dir)
	confirm "An ePiframe service is installed already (${folder:-unknown folder}), replace it?" Y \
		|| die "The installation stopped"
	stop_service
	step "Disabling the old service" systemctl disable --quiet "$SERVICE"
}

# ------------------------------------------------------------------------- config

function create_config {
	[[ -f $INSTALL_DIR/config.cfg ]] && return 0
	install -o "$EPI_USER" -g "$(id -gn "$EPI_USER")" -m 0600 \
		"$INSTALL_DIR/$DEFAULT_CONFIG" "$INSTALL_DIR/config.cfg"
}

function offer_drive_setup {
	confirm "Set up the Google Drive photo source now?" N || return 0
	(cd "$INSTALL_DIR" && as_user "$INSTALL_DIR/.venv/bin/epiframe" setup-drive) \
		|| warn "The Google Drive setup didn't finish, run 'epiframe setup-drive' later"
}

# ------------------------------------------------------------------------ update

function is_checkout {
	[[ -d $1/.git && -d $1/src/epiframe ]]
}

function find_install_dir {
	if [[ -z $INSTALL_DIR ]]; then
		INSTALL_DIR=$(installed_service_dir)
	fi
	if [[ -z $INSTALL_DIR || $INSTALL_DIR == / ]]; then
		INSTALL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
	fi
	if [[ -f $INSTALL_DIR/misc/constants.py && ! -d $INSTALL_DIR/.git ]]; then
		die "$INSTALL_DIR is ePiframe 1.x: install ePiframe 2 into a new folder and copy config.cfg and misc/users.db into it"
	fi
	is_checkout "$INSTALL_DIR" || die "There is no ePiframe installation in $INSTALL_DIR, pass it with --path"
	[[ -n $EPI_USER ]] || EPI_USER=$(stat -c %U "$INSTALL_DIR")
}

function git_user {
	as_user git -C "$INSTALL_DIR" "$@"
}

# update_target: what --update checks out: --branch, the current branch or the
# latest release tag (needs fetched tags)
function update_target {
	if [[ -n $REF ]]; then
		echo "$REF"
	elif ! git_user symbolic-ref -q --short HEAD; then
		git_user -c versionsort.suffix=- tag --list 'v[2-9]*' --sort=-version:refname \
			| { grep -v -- - || true; } | head -n 1
	fi
}

# target_commit TARGET: a branch means its fetched origin branch
function target_commit {
	git_user rev-parse -q --verify "origin/$1^{commit}" 2> /dev/null \
		|| git_user rev-parse -q --verify "$1^{commit}"
}

function check_clean_checkout {
	local changed
	changed=$(git_user status --porcelain --untracked-files=no)
	[[ -z $changed ]] || die "Files of the ePiframe code were changed, the update would overwrite them:
$changed
Save them elsewhere and undo the changes (git -C $INSTALL_DIR checkout -- FILE)"
}

function backup_files {
	local folder file
	folder="$INSTALL_DIR/backup/$(date +%Y%m%d-%H%M%S)"
	as_user mkdir -p "$folder" || return 1
	for file in config.cfg misc/users.db misc/secret.key; do
		[[ -f $INSTALL_DIR/$file ]] && as_user cp -p "$INSTALL_DIR/$file" "$folder/"
	done
	echo "$folder"
}

function checkout_target {
	local target=$1
	if git_user show-ref -q --verify "refs/remotes/origin/$target"; then
		git_user checkout -q "$target" && git_user merge -q --ff-only "origin/$target"
	else
		git_user -c advice.detachedHead=false checkout -q "$target"
	fi
}

function restore_config {
	local backup=$1
	if [[ ! -f $INSTALL_DIR/config.cfg && -f $backup/config.cfg ]]; then
		as_user cp -p "$backup/config.cfg" "$INSTALL_DIR/config.cfg"
	fi
	return 0
}

function update_code {
	header "Updating ePiframe in $INSTALL_DIR"
	check_clean_checkout
	step "Fetching the latest code" git_user fetch -q --tags --force origin
	local target current wanted
	target=$(update_target)
	[[ -n $target ]] || die "No ePiframe 2 release found, choose a branch or tag with --branch"
	wanted=$(target_commit "$target") || die "There is no $target in the repository"
	current=$(git_user rev-parse HEAD)
	if [[ $wanted == "$current" ]]; then
		info "ePiframe is up to date ($target)"
		confirm "Reinstall it anyway?" N || exit 0
	fi
	stop_service
	local backup
	backup=$(backup_files) || die "Can't save the configuration"
	info "Saved the configuration in $backup"
	step "Switching to $target" checkout_target "$target"
	restore_config "$backup"
}

# --------------------------------------------------------------------- next steps

function show_next_steps {
	local folder=${INSTALL_DIR:-~/ePiframe}
	header "Next steps"
	if (( REBOOT_NEEDED )); then
		info "1. Connect the display and reboot (SPI/I2C were enabled)"
	else
		info "1. Connect the display"
	fi
	info "2. Coming from ePiframe 1.x? Copy its config.cfg and misc/users.db into $folder"
	info "3. Configure ePiframe in $folder/config.cfg (the photo source at least)"
	info "4. Check it with: epiframe check-config"
	info "   Google Drive: epiframe setup-drive, WebUI users: epiframe users"
	info "5. Test it without the display: epiframe test, with the display: epiframe test-display"
	info "6. Start it: sudo systemctl start ePiframe (it starts on boot too)"
	info "Files given to epiframe commands are relative to $folder"
}

function show_uninstalled {
	header "ePiframe was uninstalled"
	info "The service, the epiframe command and the sudoers rule were removed"
	info "The ePiframe folder (configuration, photos, Python environment) was kept: ${INSTALL_DIR:-unknown}"
	info "uv ($BIN_DIR/uv) and the system packages were kept"
}

# ------------------------------------------------------------------------ actions

function prepare_log {
	LOG=$(mktemp /tmp/epiframe-install.XXXXXX.log)
	chmod 0644 "$LOG"
}

# everything after the system packages and the code
function install_frame {
	install_uv
	install_python_environment
	install_display_libraries
	enable_interfaces
	install_service
}

function run_install {
	EPI_USER=${EPI_USER:-${SUDO_USER:-}}
	check_user
	INSTALL_DIR=${INSTALL_DIR:-$(user_home "$EPI_USER")/ePiframe}
	check_install_dir "$INSTALL_DIR"
	check_os
	check_machine
	check_new_install_dir
	replace_existing_service
	header "Installing ePiframe into $INSTALL_DIR for $EPI_USER"
	# git and the checks need the system packages before the code
	install_system_packages
	install_code
	install_frame
	step "Creating config.cfg" create_config
	offer_drive_setup
	show_next_steps
}

function run_update {
	find_install_dir
	check_install_dir "$INSTALL_DIR"
	check_os
	check_machine
	update_code
	# the rest runs with the updated installer
	local arguments=(--resume-update --path "$INSTALL_DIR" --user "$EPI_USER")
	(( ASSUME_YES )) && arguments+=(--yes)
	(( HARDWARE )) || arguments+=(--no-hardware)
	rm -f "$LOG"
	exec /bin/bash "$INSTALL_DIR/install.sh" "${arguments[@]}"
}

function run_resume_update {
	check_user
	check_install_dir "$INSTALL_DIR"
	install_system_packages
	install_frame
	header "Starting ePiframe"
	step "Starting $SERVICE" systemctl start "$SERVICE"
	(( REBOOT_NEEDED )) && info "Reboot to use the newly enabled SPI/I2C"
	info "ePiframe was updated to $(git_user describe --tags --always)"
}

function run_plugins {
	find_install_dir
	check_install_dir "$INSTALL_DIR"
	header "Installing the Python packages of the plugins in $INSTALL_DIR"
	if [[ -z $(plugin_requirements) ]]; then
		info "No plugin has a requirements.txt"
		return 0
	fi
	install_uv
	step "Installing plugin packages" install_plugin_packages
	install_wheel_libraries_on_arm32
	info "Restart ePiframe to use them: sudo systemctl restart ePiframe"
}

function run_uninstall {
	INSTALL_DIR=${INSTALL_DIR:-$(installed_service_dir)}
	if service_enabled || [[ -f $UNIT_FILE ]]; then
		stop_service
		step "Disabling $SERVICE" systemctl disable --quiet "$SERVICE"
	fi
	rm -f "$UNIT_FILE" "$SUDOERS_FILE" "$COMMAND_FILE"
	systemctl daemon-reload
	show_uninstalled
}

function elevate {
	(( EUID == 0 )) && return 0
	[[ -f $0 ]] || die "Run the installer with sudo"
	exec sudo /bin/bash "$0" "$@"
}

function main {
	parse_arguments "$@"
	case $ACTION in
		help) show_help; return 0 ;;
		next-steps) show_next_steps; return 0 ;;
	esac
	elevate "$@"
	show_logo
	prepare_log
	echo "${DIM}Started $(date), log: $LOG${RESET}"
	case $ACTION in
		install) run_install ;;
		update) run_update ;;
		resume-update) run_resume_update ;;
		uninstall) run_uninstall ;;
		plugins) run_plugins ;;
	esac
	echo "${DIM}Ended $(date)${RESET}"
	rm -f "$LOG"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
	main "$@"
fi
