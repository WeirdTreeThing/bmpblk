# Firmware Localized Texts

This directory contains translations for the message strings shown in the
firmware UI.

## Steps to Modify/Add Messages
The message translation process works as follows:

1. If you make a code change that requires message changes, adjust the English
strings in the firmware_strings.grd file.

2. To trigger translation of updated messages, take the the current version of
firmware_strings.grd and update the [copy in Google's internal code repository
](https://cs.corp.google.com/piper///depot/google3/googleclient/chrome/transconsole_resources/strings/cros/firmware_strings.grd)

```shell
$ prodaccess
$ g4d -f localization   # Creates a g4 client, and cd's into it.
$ cp $CROS/src/platform/bmpblk/strings/locale/firmware_strings.grd googleclient/chrome/transconsole_resources/strings/cros/firmware_strings.grd
$ g4 change
```

3. Wait until the actual translation process finishes (may take a week).

4. Build all_xtbs target in the Google's internal code repository, and copy the
resulting `firmware_strings_LANG.xtb` files which contain the translated strings
into your Chromium OS local branch.

```shell
$ prodaccess
$ g4d localization   # cd's into the g4 client.
$ blaze build //googleclient/chrome/transconsole_resources:all_xtbs
$ cp blaze-genfiles/googleclient/chrome/transconsole_resources/strings/cros/firmware_strings_*.xtb $CROS/src/platform/bmpblk/strings/locale/
```

5. Create a code review that updates the corresponding files in this
directory. Do a sanity check to verify that your review only contains string
changes (i.e. no unexpected message ID changes).

6. Have your code change reviewed and submit it as usual.