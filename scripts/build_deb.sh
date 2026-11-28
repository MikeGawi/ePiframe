#!/bin/bash
# Build the ePiframe DEB packages: one per architecture with the same files and
# different Depends (armhf = 32-bit Raspberry Pi OS, also the Pi Zero; arm64 =
# 64-bit Raspberry Pi OS; amd64 = PCs, for tests).
#
#   scripts/build_deb.sh [--arch ARCH]... [--out DIR] [--check-tag TAG]
#
# The package holds the files ePiframe needs at runtime (tracked files of this
# checkout, with their changes) in /opt/epiframe, the display libraries at the
# commits pinned in install.sh, the service, the epiframe command and the
# maintainer scripts of packaging/deb. postinst creates the Python environment
# on the device. Needs bash, git, dpkg-deb and python3 >= 3.11; no root.
#
# The script can be sourced (tests call its functions); it only runs main when executed.

set -o nounset -o pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=install.sh
source "$ROOT/install.sh" || exit 1

PACKAGE="epiframe"
MAINTAINER="MikeGawi <MikeGawi@users.noreply.github.com>"
HOMEPAGE="https://github.com/MikeGawi/ePiframe"
PACKAGING="packaging/deb"
CODE_DIR="opt/epiframe"
ARCHITECTURES=(armhf arm64 amd64)
# what uv needs to build the editable package (pyproject.toml, README.md, LICENSE)
# and what ePiframe and postinst use
CODE_FILES=(src templates static pyproject.toml uv.lock README.md LICENSE install.sh
	scripts/piwheels_apt.py)
DEPENDS=(adduser ca-certificates curl dcraw fbi imagemagick "libsqlite3-0 (>= 3.35)"
	"python3 (>= 3.11)" sudo systemd webp)
# the lgpio library, then what the piwheels wheels of uv.lock link to that a
# Raspberry Pi OS Lite may lack (Bookworm: Python 3.11 wheels, Trixie: 3.13; the
# libavif alternative brings the AV1 libraries of the Trixie Pillow wheel);
# postinst reports any other missing one
ARMHF_DEPENDS=(liblgpio1 libopenblas0-pthread libgfortran5 liblcms2-2 libopenjp2-7
	libwebpdemux2 libwebpmux3 "libavif16 | libavif15")
# no 64-bit ARM wheels of spidev, nor of lgpio for Python 3.13: uv builds them
ARM64_DEPENDS=(liblgpio1 gcc python3-dev swig liblgpio-dev)

OUT_DIR="$ROOT/dist"
SELECTED=()
# the release tag the packages are built for (must match the project version)
TAG=""

# the sudoers rule names the systemctl of the device, not of the build machine
function systemctl_path {
	echo /usr/bin/systemctl
}

# --------------------------------------------------------------------- arguments

function show_build_help {
	cat << EOF
Build the ePiframe DEB packages

Usage: scripts/build_deb.sh [--arch ARCH]... [--out DIR] [--check-tag TAG]

  --arch ARCH   build only for ARCH (${ARCHITECTURES[*]}), can be repeated
                (default: all)
  --out DIR     folder for the packages (default: dist)
  --check-tag TAG
                stop unless the release tag TAG (e.g. v2.0.0-alpha.4) is the
                version in pyproject.toml (e.g. 2.0.0a4)
EOF
}

function parse_build_arguments {
	while (( $# )); do
		case $1 in
			--arch | --out | --check-tag)
				(( $# > 1 )) || die "$1 needs a value"
				case $1 in
					--arch)
						[[ " ${ARCHITECTURES[*]} " == *" $2 "* ]] || die "Unknown architecture $2"
						SELECTED+=("$2")
						;;
					--out) OUT_DIR=$2 ;;
					--check-tag) TAG=$2 ;;
				esac
				shift
				;;
			--help | -h) show_build_help; exit 0 ;;
			*) die "Unknown option $1 (see --help)" ;;
		esac
		shift
	done
	(( ${#SELECTED[@]} )) || SELECTED=("${ARCHITECTURES[@]}")
}

# ----------------------------------------------------------------------- version

# deb_version PEP440_VERSION: pre-releases sort before the release (2.0.0a3 ->
# 2.0.0~a3 < 2.0.0)
function deb_version {
	sed -E 's/^([0-9.]*[0-9])\.?(a|b|rc|dev)\.?([0-9]+)$/\1~\2\3/' <<< "$1"
}

# tag_version TAG: the PEP 440 version of a release tag (v2.0.0-alpha.4 ->
# 2.0.0a4, -beta.N -> bN, -rc.N -> rcN)
function tag_version {
	sed -E 's/^v//; s/-alpha\.?/a/; s/-beta\.?/b/; s/-rc\.?/rc/' <<< "$1"
}

# check_tag TAG VERSION: the tag names the version of pyproject.toml
function check_tag {
	[[ -z $1 || $(tag_version "$1") == "$2" ]] \
		|| die "The tag $1 is not the version $2 of pyproject.toml (bump the version or fix the tag)"
}

function project_version {
	python3 -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["project"]["version"])' \
		"$ROOT/pyproject.toml"
}

# ------------------------------------------------------------------------- files

# copy_code DESTINATION: the tracked runtime files of the checkout
function copy_code {
	install -d "$1" \
		&& git -C "$ROOT" ls-files -z -- "${CODE_FILES[@]}" \
		| tar -C "$ROOT" --null --files-from - -cf - \
		| tar -C "$1" -xf -
}

function fetch_libraries {
	INSTALL_DIR="$1/$CODE_DIR"
	EPI_USER=$(id -un)
	step "Waveshare (${WAVESHARE_COMMIT:0:7})" fetch_library "$WAVESHARE_REPO" "$WAVESHARE_COMMIT" "$WAVESHARE_PATH" waveshare_epd
	step "Pimoroni Inky (${INKY_COMMIT:0:7})" fetch_library "$INKY_REPO" "$INKY_COMMIT" "$INKY_PATH" inky
}

# add_system_files STAGE: the files outside /opt/epiframe and the maintainer scripts
function add_system_files {
	local stage=$1 packaging="$ROOT/$PACKAGING" doc="$1/usr/share/doc/$PACKAGE"
	install -d "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/lib/systemd/system" \
		"$stage/etc/sudoers.d" "$doc" \
		&& install -m 0755 "$packaging/postinst" "$packaging/prerm" "$packaging/postrm" "$stage/DEBIAN/" \
		&& echo "$SUDOERS_FILE" > "$stage/DEBIAN/conffiles" \
		&& install -m 0755 "$packaging/epiframe" "$stage/usr/bin/epiframe" \
		&& install -m 0644 "$packaging/$SERVICE" "$stage/usr/lib/systemd/system/$SERVICE" \
		&& sudoers_rules "$PACKAGE" | sed 's/(install.sh)/(DEB package)/' > "$stage$SUDOERS_FILE" \
		&& install -m 0644 "$packaging/copyright" "$doc/copyright" \
		&& install -m 0644 "$ROOT/plugins/README.md" "$doc/README.plugins.md"
}

# normalize_modes STAGE: what the build machine's umask and git left, as dpkg wants
function normalize_modes {
	chmod -R u=rwX,go=rX "$1" \
		&& chmod 0755 "$1/DEBIAN/postinst" "$1/DEBIAN/prerm" "$1/DEBIAN/postrm" \
			"$1/usr/bin/epiframe" "$1/$CODE_DIR/install.sh" \
		&& chmod 0440 "$1$SUDOERS_FILE"
}

# stage_tree STAGE: everything but DEBIAN/control
function stage_tree {
	step "Copying the code" copy_code "$1/$CODE_DIR"
	fetch_libraries "$1"
	step "Adding the system files" add_system_files "$1"
	step "Setting the file modes" normalize_modes "$1"
}

# --------------------------------------------------------------------- packages

# depends ARCH: the Depends field
function depends {
	local packages=("${DEPENDS[@]}")
	case $1 in
		armhf) packages+=("${ARMHF_DEPENDS[@]}") ;;
		arm64) packages+=("${ARM64_DEPENDS[@]}") ;;
	esac
	local IFS=, joined
	joined="${packages[*]}"
	echo "${joined//,/, }"
}

# control STAGE ARCH VERSION: the DEBIAN/control file
function control {
	local size
	size=$(du -sk --exclude=DEBIAN "$1" | cut -f1)
	cat << EOF
Package: $PACKAGE
Version: $3
Architecture: $2
Maintainer: $MAINTAINER
Installed-Size: $size
Depends: $(depends "$2")
Section: misc
Priority: optional
Homepage: $HOMEPAGE
Description: e-Paper and HDMI photo frame for Raspberry Pi
 ePiframe shows photos from a local folder, a shared Google Drive folder or
 plugins on Waveshare and Pimoroni Inky e-Paper displays or on an HDMI screen,
 with a web interface, a Telegram bot and a REST API.
 .
 The package creates the Python environment while it is configured, so the
 installation needs the internet. The service runs as the epiframe user, with
 the configuration in /etc/epiframe and the data in /var/lib/epiframe.
EOF
}

# build_package STAGE ARCH VERSION: the .deb in OUT_DIR, its path printed
function build_package {
	local file="$OUT_DIR/${PACKAGE}_${3}_${2}.deb"
	control "$1" "$2" "$3" > "$1/DEBIAN/control" \
		&& install -d "$OUT_DIR" \
		&& dpkg-deb --root-owner-group -Zxz --build "$1" "$file" > /dev/null \
		&& echo "$file"
}

function build_main {
	parse_build_arguments "$@"
	local version stage architecture
	version=$(project_version) || die "Can't read the version from pyproject.toml"
	check_tag "$TAG" "$version"
	version=$(deb_version "$version")
	stage=$(mktemp -d)
	# shellcheck disable=SC2064 # the folder is known now
	trap "rm -rf '$stage'" EXIT
	LOG="$stage.log"
	header "Building $PACKAGE $version"
	stage_tree "$stage/root"
	for architecture in "${SELECTED[@]}"; do
		step "Package for $architecture" build_package "$stage/root" "$architecture" "$version"
	done
	rm -f "$LOG"
	header "Packages"
	ls -1 "$OUT_DIR/${PACKAGE}_${version}_"*.deb
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
	build_main "$@"
fi
