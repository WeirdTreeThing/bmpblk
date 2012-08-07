# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This will regenerate the BIOS bitmap images for both x86 and arm. You
# shouldn't need to do this, though.

# These are all the known locales, sorted more-or-less geograpically
ALL_LOCALES=en es_419 pt_BR en_GB fr es pt_PT ca it de \
  el nl da no sv fi et lv lt ru pl cs sk hu sl sr hr bg ro \
  uk tr iw ar fa hi th vi id fil zh_CN zh_TW ko ja

# Here are the launch locales for Stumpy/Lumpy (issue 6595), same ordering.
DEFAULT_LOCALES=en es_419 pt_BR en_GB fr es it de nl da no sv ko ja

default: outside_chroot fonts strings x86 arm clean

outside_chroot:
	@if [ -e /etc/debian_chroot ]; then \
		echo "ImageMagick is too complex to build inside the chroot."; \
		echo "You must be outside the chroot to do this"; \
		echo "(and you probably shouldn't be doing it anyway)."; \
		exit 1; \
	fi


fonts:
	# TODO(hungte) Move fonts generation to its own Makefile.
	cd fonts && ./make_ascii_bmps.py
	bmpblk_font --outfile images/hwid_fonts.bin fonts/outdir/*

strings:
	$(MAKE) -C strings/localized_text

x86:
	$(MAKE) -C images $@ DEFAULT_LOCALES="$(DEFAULT_LOCALES)"
	cp -f images/out_$@/bmpblock.bin bmpblock_$@.bin

arm:
	$(MAKE) -C images $@ DEFAULT_LOCALES="$(DEFAULT_LOCALES)"
	cp -f images/out_$@/bmpblock.bin bmpblock_$@.bin

clean:
	rm -rf fonts/outdir
	$(MAKE) -C strings/localized_text clean
	$(MAKE) -C images clean

.PHONY: outside_chroot fonts strings x86 arm
