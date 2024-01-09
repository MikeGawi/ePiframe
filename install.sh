#!/bin/bash

function show_logo {

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

\033[1;37mePiframe - e-Paper Raspberry Pi Photo Frame
            with Google Photos\033[0m\n'
}

function install_apts {
	echo -e '\n\033[0;30mInstalling system components\033[0m'
	declare -A apts=( ["ImageMagick"]="imagemagick" ["WebP Format"]="webp" ["RAW formats"]="dcraw" ["RPi.GPIO"]="RPi.GPIO" ["RRDTool"]="rrdtool"\
				  ["LibAtlas"]="libatlas-base-dev" ["Python 3"]="python3" ["Pip 3"]="python3-pip" ["FBImageviewer"]="fbi")
	for apt in "${!apts[@]}"; do
		printf '\e[1;37m%-30s\e[m' "Installing $apt:"
		out=$(sudo apt-get install -y -qq "${apts[$apt]}" 2>&1 > /dev/null)
		if [ -z "$out" ]; then
			echo -e '\033[1;32mcheck!\033[0m'
		else
			echo -e '\033[0;31merror!\033[0m'
			echo -e "\033[1;37mPlease try to install 'sudo apt-get install ${apts[$apt]}' manually and run the script again\033[0m"
			echo -e "\033[0;31m$out\033[0m"
			exit 1
		fi
	done
}

function install_pips {
        echo -e '\n\033[0;30mInstalling Python components\033[0m'
        declare -A pips=( ["Requests"]="requests>=2.26.0" ["Pillow"]="pillow==9.3.0" ["Telebot"]="pyTelegramBotAPI" ["Dateutil"]="python-dateutil" ["ConfigParser"]="configparser>=5.0.0"\
                                  ["Google components"]="google-api-python-client google-auth-httplib2 google-auth-oauthlib"\
                                  ["SPI Libs"]="spidev==3.5" ["Pandas"]="pandas==1.2.0 numpy==1.20" ["Flask"]="flask<2.2.0" ["Flask-WTF"]="flask-wtf==1.0.0" \
                                  ["Flask-Login"]="flask-login==0.5.0" ["WTForms"]="wtforms>=3.0.0" ["SMBus"]="smbus2")
        declare -a order;
        order+=( "Requests" )
        order+=( "Telebot" )
        order+=( "Dateutil" )
        order+=( "Pillow" )
        order+=( "ConfigParser" )
        order+=( "SMBus" )
        order+=( "SPI Libs" )
        order+=( "Pandas" )
        order+=( "Flask-WTF" )
        order+=( "WTForms" )
        order+=( "Flask-Login" )
        order+=( "Flask" )
        order+=( "Google components" )

        for i in "${order[@]}"; do
                pip=${pips[$i]}
                printf '\e[1;37m%-30s\e[m' "Installing $i:"
                if [ "$i" == "Google components" ] || [ "$i" == "Telebot" ] || [ "$i" == "Pandas" ] || [ "$i" == "Flask" ]; then
                        out=$(sudo -H pip3 -q install --upgrade $pip 2>&1 > /dev/null)
                else
                        out=$(sudo -H pip3 -q install "$pip" 2>&1 > /dev/null)
                fi

                if [ -z "$out" ]; then
                        echo -e '\033[1;32mcheck!\033[0m'
                        sleep 5
                else
                        echo -e '\033[0;31merror!\033[0m'
                        if [ "$i" == "Google components" ] || [ "$i" == "Telebot" ] || [ "$i" == "Pandas" ] || [ "$i" == "Flask" ]; then
                                echo -e "\033[1;37mPlease try to install sudo -H pip3 install --upgrade $pip manually and run the script again\033[0m"
                        else
                                echo -e "\033[1;37mPlease try to install sudo -H pip3 install '$pip' manually and run the script again\033[0m"

                        fi
                        echo -e "\033[0;31m$out\033[0m"
                        exit 1
                fi
        done

sudo -H pip3 -q uninstall --yes werkzeug > /dev/null 2>&1
sudo -H pip3 -q install --no-cache-dir 'werkzeug==2.0.3' > /dev/null 2>&1
}

function check_pi {
	if  [ ! -d "/sys/bus/platform/drivers/gpiomem-bcm2835" ]; then
		echo -e '\033[0;31mThis application is meant to run on Raspberry Pi!\033[0m'
		echo -e '\033[1;37mTo install it manually please refer to the documentation\033[0m'
		exit 1
	fi
}

function check_spi {
	echo -e '\n\033[0;30mChecking/enabling SPI support\033[0m'
	printf '\e[1;37m%-30s\e[m' "Enabling SPI:"
	
	spi1=$(lsmod | grep spi_)
	spi2=$(ls -l /dev/spidev* 2> /dev/null)
	spi3=$(raspi-config nonint get_spi)

	if [ -z "$spi1" ] && [ -z "$spi2" ] && [ "$spi3" -eq 1 ]; then
		sudo raspi-config nonint do_spi 0
		sudo sed -i "s/#dtparam=spi=/dtparam=spi=/g" /boot/config.txt
	fi
	
	if [ "$(raspi-config nonint get_spi)" -eq 0 ]; then
		echo -e '\033[1;32mcheck!\033[0m'
	else
		echo -e '\033[0;31merror!\033[0m'
		echo -e "\033[1;37mPlease try to enable SPI manually in raspi-config and run the script again\033[0m"
		exit 1
	fi
}

function display_libs_waveshare {
	declare -A cmds
	cmds["Preparing"]='sudo rm -rf e-Paper-master/ waveshare.zip'
	cmds["Downloading"]='sudo wget -q https://github.com/waveshare/e-Paper/archive/master.zip -O waveshare.zip 2>&1 | grep -i "failed\|error"'
	cmds["Unpacking"]='sudo unzip -q waveshare.zip'
	cmds["Copying"]='sudo cp -r e-Paper-master/RaspberryPi_JetsonNano/python/lib .'
	cmds["Cleanup"]='sudo rm -r e-Paper-master/ waveshare.zip'
	
	declare -a order;
	order+=( "Preparing" )	
	order+=( "Downloading" )
	order+=( "Unpacking" )
	order+=( "Copying" )
	order+=( "Cleanup" )

	echo -e '\n\033[0;30mInstalling Waveshare display libraries\033[0m'

	for i in "${order[@]}"
	do
		printf '\e[1;37m%-30s\e[m' "$i:"
		out=$(${cmds[$i]} 2>&1)
		if [ -z "$out" ]; then
			echo -e '\033[1;32mcheck!\033[0m'
		else
			echo -e '\033[0;31merror!\033[0m'
			echo -e "\033[0;31m$out\033[0m"
			echo -e "\033[1;37mPlease try to manually start command ${cmds[$i]}\033[0m"
			exit 1
		fi
	done
}


function display_libs_pimoroni {
	declare -A cmds
	cmds["Preparing"]='sudo rm -rf inky-main/ pimoroni.zip'
	cmds["Downloading"]='sudo wget -q https://codeload.github.com/pimoroni/inky/zip/refs/heads/main -O pimoroni.zip 2>&1 | grep -i "failed\|error"'
	cmds["Unpacking"]='sudo unzip -q pimoroni.zip'
	cmds["Copying"]='sudo cp -r inky-main/library/inky/ lib/'
	cmds["Cleanup"]='sudo rm -r inky-main/ pimoroni.zip'

	declare -a order;
	order+=( "Preparing" )
	order+=( "Downloading" )
	order+=( "Unpacking" )
	order+=( "Copying" )
	order+=( "Cleanup" )

	echo -e '\n\033[0;30mInstalling Pimoroni display libraries\033[0m'

	for i in "${order[@]}"
	do
		printf '\e[1;37m%-30s\e[m' "$i:"
		out=$(${cmds[$i]} 2>&1)
		if [ -z "$out" ]; then
			echo -e '\033[1;32mcheck!\033[0m'
		else
			echo -e '\033[0;31merror!\033[0m'
			echo -e "\033[0;31m$out\033[0m"
			echo -e "\033[1;37mPlease try to manually start command ${cmds[$i]}\033[0m"
			exit 1
		fi
	done
}

function epi_code {
	declare -A cmds
	cmds["Preparing"]='sudo rm -rf ePiframe-master/ ePiframe.zip'
	cmds["Downloading"]='sudo wget -q https://github.com/MikeGawi/ePiframe/archive/master.zip -O ePiframe.zip 2>&1 | grep -i "failed\|error"'
	cmds["Unpacking"]='sudo unzip -q ePiframe.zip'
	cmds["Copying"]='sudo cp -r ePiframe-master/* .'
	cmds["Cleanup"]='sudo rm -r ePiframe-master/ ePiframe.zip'
	
	declare -a order;
	order+=( "Preparing" )
	order+=( "Downloading" )
	order+=( "Unpacking" )
	order+=( "Copying" )
	order+=( "Cleanup" )

	echo -e '\n\033[0;30mInstalling ePiframe code\033[0m'

	for i in "${order[@]}"
	do
		printf '\e[1;37m%-30s\e[m' "$i:"
		out=$(${cmds[$i]} 2>&1 > /dev/null)
		if [ -z "$out" ]; then
			echo -e '\033[1;32mcheck!\033[0m'
		else
			echo -e '\033[0;31merror!\033[0m'
			echo -e "\033[0;31m$out\033[0m"
			echo -e "\033[1;37mPlease try to manually start command ${cmds[$i]}\033[0m"
			exit 1
		fi
	done
}

function install_service {
	declare -A cmds
	cmds["Copying"]='sudo cp misc/ePiframe.service.org ePiframe.service'
	pwdesc=$(echo "$1"'/' | sed 's_/_\\/_g')
	cmds["Configuring"]="sudo sed -i s/EPIEPIEPI/$pwdesc/g ePiframe.service"
	cmds["Installing"]="sudo systemctl --quiet enable $1/ePiframe.service"
	
	declare -a order;
	order+=( "Copying" )
	order+=( "Configuring" )
	order+=( "Installing" )

	for i in "${order[@]}"
	do
		printf '\e[1;37m%-30s\e[m' "$i:"
		out=$(${cmds[$i]} 2>&1 > /dev/null)
		
		if [ -z "$out" ]; then
			echo -e '\033[1;32mcheck!\033[0m'
		else
			echo -e '\033[0;31merror!\033[0m'
			echo -e "\033[0;31m$out\033[0m"
			echo -e "\033[1;37mPlease try to manually start command ${cmds[$i]}\033[0m"
			exit 1
		fi
	done
}

function show_next_steps {
	echo -e '\n\033[0;30mNext steps:\033[0m'
	printf '\e[1;37m5. Configure ePiframe with config.cfg file\e[m\n'
	printf '\e[1;37m6. Check configuration with ./ePiframe.py --check-config\e[m\n'
	printf '\e[1;37m7. Do a test with ./ePiframe.py --test without sending photo to display\e[m\n'
	printf '\e[1;37m8. Reboot ePiframe device to start enabled SPI support\e[m\n'
	printf '\e[1;37m9. Enjoy Your ePiframe!\e[m\n'
}

function start_activate {
	sudo python3 activate.py
}

function show_uninstall {
	echo -e '\033[0;30mNext steps:\033[0m'
	printf '\e[1;37m1. Service has been stopped and uninstalled\e[m\n'
	printf '\e[1;37m2. Whole ePiframe code is in the directory where it was installed\e[m\n'
	printf '\e[1;37m3. The list of the dependencies installed for ePiframe is in the documentation\e[m\n'
	printf '\e[1;37m4. ePiframe says "bye" :(\e[m\n'
}

function show_help {
	echo -e '\033[1;37mePiframe - e-Paper Raspberry Pi Photo Frame with Google Photos\033[0m'
	echo -e '\033[0;30mScript arguments:\033[0m'
	printf '\e[1;37m	none			- perform ePiframe installation\e[m\n'
	printf '\e[1;37m	--help			- this help\e[m\n'
	printf '\e[1;37m	--uninstall		- uninstalls ePiframe\e[m\n'
	printf '\e[1;37m	--update		- update ePiframe\e[m\n'
	printf '\e[1;37m	--next-steps 		- show next steps after installation\e[m\n'
	printf '\e[1;37m	--activate 		- token and creds activation of Google Photos\e[m\n'
}

###############################################MAIN###############################################

if [ "$1" = "--help" ]; then
	show_help
	exit 0
fi

if [ "$1" = "--next-steps" ]; then
	show_next_steps
	exit 0
fi

#elevate to root
if [[ $EUID -ne 0 ]];
then
	#re-run with sudo
    exec sudo /bin/bash "$0" "$@"
	exit
fi

clear
show_logo

if [ "$1" = "--activate" ]; then
	start_activate
	exit 0
fi

if [ "$1" = "--update" ]; then
	echo -e "\n\033[0;30mUpdating ePiframe!\033[0m"
	
	server_version=$(wget --connect-timeout=3 -q -O - https://raw.githubusercontent.com/MikeGawi/ePiframe/master/misc/constants.py 2>/dev/null | grep EPIFRAME_VERSION)
	local_version=$(grep EPIFRAME_VERSION misc/constants.py)
	
	if [ "$server_version" = "$local_version" ]; then
		echo -e '\n\033[0;31mYou already have the latest version of ePiframe.\033[0m'		
		while true; do
			read -p $'\n\e[1;37mContinue anyway to reinstall it? [y/N]\e[0m' -n 1 -r -e yn
			case "${yn:-N}" in
				[Yy]* ) echo -e '\n\033[0;31mThe update will continue'; break;;
				[Nn]* ) echo -e '\n\033[0;31mThe update will stop'; exit 1; break;;
				* ) echo "Please answer yes or no.";;
			esac
		done
	fi
fi

if [ "$1" = "--uninstall" ] || [ "$1" = "--update" ]; then
	out=$(sudo systemctl is-enabled ePiframe.service 2> /dev/null)

	if [ -n "$out" ]; then
			sudo systemctl stop ePiframe.service
			sudo systemctl disable ePiframe.service
	fi
	
	if [ "$1" = "--uninstall" ]; then
		show_uninstall	
		exit 0
	fi
fi

echo -e "\n\033[0;30mStarted $(date)\033[0m"
check_pi
printf '\e[1;37m%-30s\e[m' "Is root:"
if [[ $EUID -eq 0 ]];
	then echo -e '\033[1;32mcheck!\033[0m'
else
	echo -e '\033[0;31merror!\033[0m'
	echo -e 'Run the script again with sudo'
	exit 1
fi

install_apts
install_pips

check_spi

if [ "$1" = "--update" ]; then
	path=$(pwd)
	
	mkdir -p backup
	
	if [ -f "config.cfg" ]; then
		cp config.cfg backup/config.cfg.bak
		cp config.cfg backup/config-"$(date +"%Y%m%d-%H%M%S")".cfg.bak
		echo -e '\n\033[0;30mSaved a copy of configuration file (config.cfg and a copy with timestamp as well) in backup folder\033[0m'
	else	
		while true; do
			echo -e '\n\033[0;31mNo config.cfg file! Are You in the correct path? All settings will be set to default\033[0m'		
			read -p $'\n\e[1;37mDo You want to continue? [Y/n]\e[0m' -n 1 -r -e yn
			case "${yn:-Y}" in
				[Yy]* ) echo -e '\n\033[0;31mThe update will continue'; break;;
				[Nn]* ) echo -e '\n\033[0;31mThe update will stop'; exit 1; break;;
				* ) echo "Please answer yes or no.";;
			esac
		done
	fi
	if [ -f "credentials.json" ]; then
		cp credentials.json backup/credentials.json.bak
		echo -e '\n\033[0;30mSaved a copy of credentials file (credentials.json) in backup folder\033[0m'
	fi
	if [ -f "token.pickle" ]; then
		cp token.pickle backup/token.pickle.bak
		echo -e '\n\033[0;30mSaved a copy of token file (token.pickle) in backup folder\033[0m'
	fi
	if [ -f "misc/users.db" ]; then
		cp misc/users.db backup/users.db.bak
		echo -e '\n\033[0;30mSaved a copy of Users DB (misc/users.db) in backup folder\033[0m'
	fi
	if [ -f "static/data/load.rrd" ]; then
		cp static/data/*.rrd backup/
		echo -e '\n\033[0;30mSaved a copy of Statistics RRD files (static/data/*.rrd) in backup folder\033[0m'
	fi	
else
	read -p $'\n\e[1;37mPlease enter destination path for ePiframe installation\n[DEFAULT:/home/pi/ePiframe]: \e[0m' -r path
	if [ -z "$path" ]; then
		path="/home/pi/ePiframe"
	fi
	sudo mkdir -p "$path"
	cd $path || exit
fi

epi_code
display_libs_waveshare
display_libs_pimoroni

out=$(sudo systemctl is-enabled ePiframe.service 2> /dev/null)

echo -e '\n\033[0;30mInstalling ePiframe service\033[0m'
if [ -n "$out" ]; then
	while true; do
		read -p $'\n\e[1;37mThere is an ePiframe.service enabled already. Do You want to remove it? [Y/n]\e[0m' -n 1 -r -e yn
		case "${yn:-Y}" in
			[Yy]* ) sudo systemctl disable ePiframe.service; break;;
			[Nn]* ) echo -e '\033[0;31mThe installation will continue but service configuration may fail\033[0m'; break;;
			* ) echo "Please answer yes or no.";;
		esac
	done
fi

install_service $path

if [ "$1" = "--update" ]; then
	if [ -f "backup/config.cfg.bak" ]; then
		cp backup/config.cfg.bak config.cfg
	fi
	sudo systemctl start ePiframe.service
else
	while true; do
		echo -e '\n\e[1;37mePiframe can use configured local storage as the source for photos but can also pull them from Google Photos but that needs to be activated.`\033[0m'
		read -p $'\n\e[1;37mDo You want to activate (if not already done) Google Photos token and credentials for Your ePiframe now? You can always start it later by running ./install.sh --activate command in the main path. [Y/n]\e[0m' -n 1 -r -e yn
		case "${yn:-Y}" in
			[Yy]* ) start_activate; break;;
			[Nn]* ) echo -e '\033[0;31mRemember to activate it later to allow ePiframe use Google Photos\033[0m'; break;;
			* ) echo "Please answer yes or no.";;
		esac
	done

	show_next_steps
fi

sudo chown -R pi:pi $path
sudo chmod +x $path/*.py

echo -e "\n\033[0;30mEnded $(date)\033[0m"
