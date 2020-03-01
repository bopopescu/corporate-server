# Takes the IP or host name of the domaincontroller to check.
wait_for_domaincontroller_to_be_online () {
	for i in  $(seq 1 60); do
		echo "Waiting for domaincontroller $1 to be online."
		sleep 60;
		if curl "http://$1/univention/management/" &> /dev/null; then
			sleep 500
			echo "Domaincontroller $1 is now online."
			return 0
		fi
	done
	return 1
}

write_slave1_preseed () {
	cat > /var/lib/univention-client-boot/preseed/slave1_preseed <<- _EOF_
		# no live installer
		d-i live-installer/enable boolean false

		#
		# Select German as default locale and for keyboard layout
		#
		d-i debian-installer/locale string en_US.UTF-8
		d-i localechooser/supported-locales multiselect en_US.UTF-8, de_DE.UTF-8
		d-i keyboard-configuration/xkb-keymap select de(nodeadkeys)
		d-i ucr/xorg/keyboard/options/XkbModel string pc105
		d-i ucr/xorg/keyboard/options/XkbLayout string de
		d-i ucr/xorg/keyboard/options/XkbVariant string nodeadkeys
		d-i ucr/xorg/keyboard/options/XkbOptions string

		# configure second interface to ipv6
		d-i ucr/interfaces/ens6/type string manual
		d-i ucr/interfaces/ens6/start string true

		#
		# Configure local repository server
		#
		d-i debian-installer/allow_unauthenticated boolean true
		d-i mirror/country string manual
		d-i mirror/protocol select http
		d-i mirror/http/proxy string
		# The host name of the repository server is filled through the PXE configuration generated by UDM
		d-i mirror/http/hostname string `ucr get ldap/master`
		d-i mirror/http/directory string /univention-repository/`ucr get version/version`/maintained/`ucr get version/version`-`ucr get version/patchlevel`
		# Package archives
		d-i mirror/codename string `echo ucs$(ucr get version/version)$(ucr get version/patchlevel) | tr -d "."`
		d-i mirror/suite string `echo ucs$(ucr get version/version)$(ucr get version/patchlevel) | tr -d "."`
		d-i mirror/udeb/suite string `echo ucs$(ucr get version/version)$(ucr get version/patchlevel) | tr -d "."`

		#
		# Disable password for user 'root'
		#
		d-i passwd/root-login boolean true
		# Alternative: printf "univention" | mkpasswd -s -m sha-512
		d-i passwd/root-password-crypted string \$6\$WPDGnOwE.MVZ\$W4YsWl5FGIS.gVBORRNAhEx6shvKLh9Dy3Ov7.HbkEV0urswBN8Lp0GCDVtAkAXfFGJvoYPcWij5ZnMXh1UaX.

		# Don't create a first user
		d-i passwd/make-user boolean false

		#
		# Partition hard disk: Use "lvm" and one big "/" partition
		#
		# Choices: lvm crypto regular
		d-i partman-auto/method string regular
		# Choices: atomic home multi
		d-i partman-auto/choose_recipe string atomic
		d-i partman-lvm/device_remove_lvm boolean true
		d-i partman-md/device_remove_md boolean true
		d-i partman-lvm/confirm boolean true
		d-i partman-lvm/confirm_nooverwrite boolean true
		d-i partman-partitioning/confirm_write_new_label boolean true
		d-i partman/choose_partition select finish
		d-i partman/confirm boolean true
		d-i partman/confirm_nooverwrite boolean true

		# Pre-select the standard UCS kernel
		d-i base-installer/kernel/image string linux-image-`uname -r`
		d-i base-installer/includes string less
		d-i base-installer/debootstrap_script string /usr/share/debootstrap/scripts/sid

		# Only minimal install
		d-i apt-setup/use_mirror boolean false
		d-i apt-setup/no_mirror boolean true
		d-i apt-setup/services-select multiselect none
		d-i apt-setup/cdrom/set-first boolean false
		tasksel tasksel/first multiselect none
		d-i pkgsel/include string univention-system-setup-boot univention-management-console-web-server univention-management-console-module-setup univention-kernel-image openssh-server
		postfix postfix/main_mailer_type string No configuration
		openssh-server ssh/disable_cr_auth boolean false
		d-i ucf/changeprompt select keep_current
		d-i pkgsel/upgrade select none
		popularity-contest popularity-contest/participate boolean false

		# Install GRUB in MBR by default on new systems
		d-i grub-installer/only_debian boolean true
		d-i grub-installer/bootdev string default
		grub-pc grub-pc/install_devices multiselect
		grub-pc grub-pc/install_devices_empty boolean true

		#
		# Disable starting "Univention System Setup Boot"
		#
		d-i ucr/system/setup/boot/start string false

		#
		# Univention System Setup profile
		#
		univention-system-setup-boot uss/di-univention-system-setup/skip boolean true
		univention-system-setup-boot uss/components string
		univention-system-setup-boot uss/packages_install string
		univention-system-setup-boot uss/packages_remove string
		# Choices: domaincontroller_master domaincontroller_backup domaincontroller_slave memberserver base
		univention-system-setup-boot uss/server/role string domaincontroller_slave

		# After installation
		d-i finish-install/reboot_in_progress note
	_EOF_
}
