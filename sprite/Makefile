# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This makefile lets you MANUALLY generate the QR code images, and should NOT be
# run automatically.

all: qr_rec.svg

# Web UI: http://goqr.me/
API_URL = https://api.qrserver.com/v1/create-qr-code/

# qzone: Border width in terms of number of squares
PARAMS = color=202124&bgcolor=e8eaed&qzone=2&format=svg

qr_rec.svg:
	curl "$(API_URL)?$(PARAMS)&data=https://google.com/chromeos/recovery" -o $@
