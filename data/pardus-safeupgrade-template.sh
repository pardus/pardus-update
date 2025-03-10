#!/bin/bash

set +e

rm -f /system-update

message="System is upgrading, please don't turn off machine ..."
upmessage="Upgrading"
if [[ $LANG == "tr_TR.UTF-8" ]]; then
    message="Sistem güncelleniyor, lütfen makineyi kapatmayın ..."
    upmessage="Güncelleniyor"
elif [[ $LANG == "pt_PT.UTF-8" ]]; then
    message="O sistema está a ser atualizado, não desligue a máquina ..."
    upmessage="A atualizar"
fi

echo "$(date) - Pardus safe upgrade is starting" >> /var/log/pardus-upgrade.log

plymouth display-message --text="$message"

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
source /etc/profile

# block upgrade b43 and mscorefonts
apt-mark hold firmware-b43-installer
apt-mark hold firmware-b43legacy-installer
apt-mark hold ttf-mscorefonts-installer
echo 'libc6 libraries/restart-without-asking boolean true' | debconf-set-selections
apt -fuyq  install ./var/cache/apt/archives/*.deb \
    --no-download \
    -o Dpkg::Options::="@@askconf@@" \
    --allow-downgrades \
    --allow-change-held-packages \
    -o APT::Status-Fd=1 | while read line; do
        echo $line >> /var/log/pardus-upgrade.log
        echo $line > /dev/console
        if echo $line | grep "pmstatus" > /dev/null
        then
            numberr=`echo $line | cut -d":" -f3`
            plymouth display-message --text="$upmessage: ${numberr%??}%"
        fi
    done
apt-mark unhold firmware-b43-installer
apt-mark unhold firmware-b43legacy-installer
apt-mark unhold ttf-mscorefonts-installer

reboot -f
