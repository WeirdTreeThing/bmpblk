# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This generates BIOS bitmap images for specified board.

OUTPUT ?= build
STAGE ?= $(OUTPUT)/.stage
FONT_SIZE = 14
PHYSICAL_PRESENCE ?= keyboard
ARCHIVER ?= /usr/bin/archive

build:
	@[ ! -z "$(BOARD)" ] || (echo "Usage: BOARD=\$$BOARD make"; exit 1)
	mkdir -p "$(STAGE)"
	LOCALES="$(LOCALES)" \
		OUTPUT="$(OUTPUT)" \
		FONT_SIZE="$(FONT_SIZE)" \
		PHYSICAL_PRESENCE="$(PHYSICAL_PRESENCE)" \
		./build.py "$(BOARD)"

archive:
	./archive_images.py -a "$(ARCHIVER)" -d "$(OUTPUT)"
	"$(ARCHIVER)" "$(OUTPUT)/font.bin" create "$(OUTPUT)"/font/*.bmp

clean:
	rm -rf $(OUTPUT)
	find . -type f -name '*.pyc' -delete

.PHONY: build help archive clean
