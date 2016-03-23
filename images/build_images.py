#!/usr/bin/env python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''
Prepares image resources into output folder, and generates final bitmap block
output file.

Usage:
  ./build_images.py <board-names>

  Use 'ALL' in <board-names> if you want to build every boards defined in
  configuration file.
'''

import glob
import os
import shutil
import subprocess
import sys
import yaml

import convert_to_bmp3

# Composition settings
CHARGE_BACKGROUND_COLOR = (0, 0, 0)

# The files that use different scaling parameter.
BACKGROUND_IMAGE = 'Background'
CHARGE_BACKGROUND_IMAGE = 'reserve_charging_background'
BACKGROUND_LIST = (BACKGROUND_IMAGE, CHARGE_BACKGROUND_IMAGE)
DUMMY_IMAGE = 'dummy'

# Files with different background
CHARGE_ASSETS_PREFIX = "reserve_charging"

# Path, directory names and output file name.
BMPBLK_OUTPUT = "bmpblk.bin"
SCRIPT_BASE = os.path.dirname(os.path.abspath(__file__))
LOCALE_DIR = 'locale'
FONT_DIR = 'font'
PNG_FILES = '*.png'
SVG_FILES = '*.svg'
TEXT_COLORS_AUTODETECT = 0

# Base processing utilities, built by vboot_reference
BMPLKU = "bmpblk_utility"
BMPLKFONT = "bmpblk_font"

DEFAULT_RESOLUTION = (1366.0, 768.0)
DEFAULT_PANEL_SIZE = DEFAULT_RESOLUTION
DEFAULT_ASSETS_DIR = 'assets'
DEFAULT_LOCALES = ['en', 'es-419', 'pt-BR', 'fr', 'es', 'pt-PT', 'ca', 'it',
                   'de', 'el', 'nl', 'da', 'nb', 'sv', 'fi', 'et', 'lv', 'lt',
                   'ru', 'pl', 'cs', 'sk', 'hu', 'sl', 'sr', 'hr', 'bg', 'ro',
                   'uk', 'tr', 'he', 'ar', 'fa', 'hi', 'th', 'ms', 'vi', 'id',
                   'fil', 'zh-CN', 'zh-TW', 'ko', 'ja',
                   'bn', 'gu', 'kn', 'ml', 'mr', 'ta', 'te']

DEFAULT_OPTIONAL_SCREENS = []
DEFAULT_TEXT_COLORS = TEXT_COLORS_AUTODETECT
DEFAULT_SIZE_LIMIT = 970112  # Based by recent ARM firmware.

# YAML key names.
PANEL_SIZE_KEY = 'panel'
RESOLUTION_KEY = 'res'
ASSETS_DIR_KEY = 'assets_dir'
ASSETS_RESOLUTION_KEY = 'assets_res'
SDCARD_KEY = 'sdcard'
BAD_USB3_KEY = 'bad_usb3'
PHY_REC_KEY = 'phy_rec'
LOCALES_KEY = 'locales'
OPTIONAL_SCREENS_KEY = 'optional_screens'
TEXT_COLORS_KEY = 'text_colors'
SIZE_LIMIT_KEY = 'size_limit'

KNOWN_KEYS = set((PANEL_SIZE_KEY, RESOLUTION_KEY, SDCARD_KEY, BAD_USB3_KEY,
                  PHY_REC_KEY, ASSETS_DIR_KEY, ASSETS_RESOLUTION_KEY,
                  LOCALES_KEY, OPTIONAL_SCREENS_KEY, TEXT_COLORS_KEY,
                  SIZE_LIMIT_KEY))


class BuildImageError(Exception):
  """The exception class for all errors generated during build image process."""
  pass


def shell(command, capture_stdout=False):
  """Executes command by shell interpreter.

  Args:
    command: a string, the shell script command to invoke.
    capture_stdout: True to capture an return data sent to stdout, otherwise
                    leave it untouched.
  Returns:
    Output on stdout if capture_stdout is True, otherwise None.
  """
  if capture_stdout:
    return subprocess.check_output(command, shell=True)
  else:
    subprocess.check_call(command, shell=True)


def find_utility(name):
  """Finds a utility program and setup PATH for it.

  Args:
      name: a string, name of the utility program to find.
  """
  if os.system("type %s >/dev/null 2>&1" % name) == 0:
    return

  vbutil_dir = os.path.join(SCRIPT_BASE, '..', '..', 'vboot_reference',
                            'build', 'utility')
  if os.path.exists(os.path.join(vbutil_dir, name)):
    os.putenv('PATH', os.getenv('PATH') + (':%s' % vbutil_dir))
  else:
    raise BuildImageError('%s is not found in PATH.' % name)


def load_boards_config(filename):
  """Loads the configuration of all boards from a YAML file.

  Args:
    filename: a string, file name of a YAML config file.

  Returns:
    A dictionary, where keys are board names, and values are corresponding board
    configuration.
  """
  with open(filename, 'r') as conf_file:
    raw_config = yaml.load(conf_file)
  config = {}

  # Normalize configurations.
  for boards, data in raw_config.iteritems():
    for board in boards.replace(',', ' ').split():
      if data is None:
        data = {}
      if PANEL_SIZE_KEY not in data:
        data[PANEL_SIZE_KEY] = DEFAULT_PANEL_SIZE
      if RESOLUTION_KEY not in data:
        data[RESOLUTION_KEY] = DEFAULT_RESOLUTION
      if ASSETS_DIR_KEY not in data:
        data[ASSETS_DIR_KEY] = DEFAULT_ASSETS_DIR
      if ASSETS_RESOLUTION_KEY not in data:
        data[ASSETS_RESOLUTION_KEY] = DEFAULT_RESOLUTION
      if OPTIONAL_SCREENS_KEY not in data:
        data[OPTIONAL_SCREENS_KEY] = DEFAULT_OPTIONAL_SCREENS
      if TEXT_COLORS_KEY not in data:
        data[TEXT_COLORS_KEY] = DEFAULT_TEXT_COLORS
      if SIZE_LIMIT_KEY not in data:
        data[SIZE_LIMIT_KEY] = DEFAULT_SIZE_LIMIT
      if set(data) - KNOWN_KEYS:
        raise BuildImageError('Unknown entries in config %s: %r' %
                              (board, list(set(data) - KNOWN_KEYS)))
      config[board] = data
  return config


def build_replace_map(config):
  """Builds a map for replacing entries in given board configuration.

  Args:
    config: a dictionary, board configuration.

  Returns:
    A dictionary, each key represents the name of entry to be replaced by value.
  """
  sdcard = config.get(SDCARD_KEY, True)
  bad_usb3 = config.get(BAD_USB3_KEY, False)
  physical_recovery = config.get(PHY_REC_KEY, False)
  replace_map = {}

  if not sdcard:
    replace_map['BadDevices'] = 'BadUSB'
    replace_map['InsertDevices'] = 'InsertUSB'
    replace_map['insert'] = ('insert_usb2' if bad_usb3 else 'insert_usb')
  elif bad_usb3:
    replace_map['insert'] = 'insert_sd_usb2'

  if physical_recovery:
    replace_map['todev'] = 'todev_phyrec'

  return replace_map


def get_locales(config):
  """Gets the locales to include when building for one board.

  The locales are decided by following order:
    1. The LOCALES environment variable.
    2. The 'locales' entry, if defined in config.
    3. DEFAULT_LOCALES.

  Args:
    config: a dictionary, board configuration to specify default locales.

  Returns:
    A list, locales to use.
  """
  locales = os.getenv('LOCALES')
  if locales:
    return locales.split()

  # Otherwise, follow the recommendation from config
  if LOCALES_KEY in config:
    return config[LOCALES_KEY]

  return DEFAULT_LOCALES


def convert_to_bmp(source, output_folder, scale_params, background_colors,
                   replace_map, max_colors=128):
  """Utility function to convert images into BMP format. Creates requested
  files in output directory.

  Args:
    source: a string, source file(s). May contain glob-style wildcards.
    output: a string, output folder.
    scale_params: A list, scale parameters in (normal, background) format.
                  'normal' is the scaling factor when the image is a normal
                  image, and 'background' is the parameter for background image.
    background_colors: A list, background color to fill if the input image has
                  transparency, in (normal, charge) format.
                  'normal' is the background color for images, and 'charge' is
                  for images in charing mode (usually black).
    replace_map: A dictionary, keys are file names to change and values are
                 new output names.
    max_colors: Maximum of colors can be used in output image.
  """
  files = glob.glob(source)
  if not files:
    raise BuildImageError('Unable to find file(s): %s' % source)

  for image in files:
    image_base, image_ext = os.path.splitext(os.path.basename(image))
    output_file = os.path.join(
        output_folder, image_base + convert_to_bmp3.DEFAULT_OUTPUT_EXT)
    background_color = background_colors[0]
    scale_param = scale_params[0]

    if image_base in BACKGROUND_LIST:
      scale_param = scale_params[1]
    elif image_base.startswith(CHARGE_ASSETS_PREFIX):
      background_color = background_colors[1]

    if image_base in replace_map:
      print 'Replace: %s <= %s' % (image, replace_map[image_base])
      if replace_map[image_base] == DUMMY_IMAGE:
        # Dummy is always in top folder, without scale.
        scale_param = ''
        image = DUMMY_IMAGE + '.png'
      else:
        image = os.path.join(os.path.dirname(image),
                             replace_map[image_base] + image_ext)

    # TODO(hungte) Cache results to speed up YAML generation.
    convert_to_bmp3.convert_to_bmp(
        image, scale_param, background=background_color,
        output_file=output_file, max_colors=max_colors)


def build_image(board, config):
  """Builds all images required by a board.

  Args:
    board: a string, name of the board to use.
    config: a dictionary of board configuration.

  Returns:
    A string for the output folder containing all resources.
  """

  output_base = os.getenv('OUTPUT', os.path.join('..', 'build'))
  output_dir = os.path.join(output_base, board)
  stage_dir = os.path.join(output_base, '.stage')
  assets_dir = config[ASSETS_DIR_KEY]

  resolution = config[RESOLUTION_KEY]
  panel_size = config[PANEL_SIZE_KEY]
  assets_resolution = config[ASSETS_RESOLUTION_KEY]
  replace_map = build_replace_map(config)
  optional_screens = config[OPTIONAL_SCREENS_KEY]
  background_colors = (convert_to_bmp3.BACKGROUND_COLOR,
                       CHARGE_BACKGROUND_COLOR)

  # TODO(hungte) Allow overriding stage directory for 2x resolution files.
  if not os.path.exists(stage_dir):
    raise BuildImageError('Missing stage folder: %s, run make in strings' %
                          stage_dir)

  # Calculate the new aspect ratio (always shrink,never expand).
  aspect_ratio = ((resolution[0] / float(resolution[1])) /
                  (panel_size[0] / float(panel_size[1])))
  if aspect_ratio < 1:
    scale = (aspect_ratio, 1)
  else:
    scale = (1 / aspect_ratio, 1)

  # Resizing text to smaller size makes it really hard to read, and most smaller
  # resolutions, for example 800x600, can still use 100% text, so we only want
  # to resize for larger resolutions.
  if (resolution[1] > assets_resolution[1]):
    # TODO(hungte) Regenerate text files in different sizes instead of rescale.
    rescale_factor = resolution[1] / float(assets_resolution[1])
    scale = (scale[0] * rescale_factor, scale[1] * rescale_factor)

  scale_params = ('%d%%x%d%%' % (round(scale[0] * 100), round(scale[1] * 100)),
                  '%dx%d!' % (resolution[0], resolution[1]))
  print "%s: %s scaling: %s" % (board, assets_dir, ','.join(scale_params))

  # Prepare output folder
  if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
  os.makedirs(output_dir)

  # Prepare images in current and assets folder
  convert_to_bmp(PNG_FILES, output_dir, scale_params, background_colors,
                 replace_map)
  convert_to_bmp(os.path.join(assets_dir, PNG_FILES), output_dir, scale_params,
                 background_colors, replace_map)

  # If we need to scale, use vector text images for better quality (which still
  # looks good with less colors).
  if scale == (1, 1):
    text_files = PNG_FILES
    text_max_colors = 7
  else:
    text_files = SVG_FILES
    text_max_colors = 5
  if config[TEXT_COLORS_KEY] != TEXT_COLORS_AUTODETECT:
    text_max_colors = config[TEXT_COLORS_KEY]

  # Prepares strings and localized images.
  convert_to_bmp(os.path.join(stage_dir, text_files),
                 output_dir, scale_params, background_colors,
                 replace_map, text_max_colors)
  locale_dir = os.path.join(stage_dir, LOCALE_DIR)
  locales = get_locales(config)

  # Show progress because processing SVG files may take a long time.
  sys.stderr.write(" > processing: ")
  for locale in locales:
    sys.stderr.write(locale + " ")
    locale_output_dir = os.path.join(output_dir, LOCALE_DIR, locale)
    os.makedirs(locale_output_dir)
    convert_to_bmp(os.path.join(locale_dir, locale, text_files),
                   locale_output_dir, scale_params, background_colors,
                   replace_map, text_max_colors)
  sys.stderr.write("\n")

  sys.stderr.write("creating locale list file\n")
  with open(os.path.join(output_dir, 'locales'), 'w') as locale_list:
    locale_list.write('\n'.join(locales))

  font_dir = os.path.join(stage_dir, FONT_DIR)
  font_output_dir = os.path.join(output_dir, FONT_DIR)
  os.makedirs(font_output_dir)
  convert_to_bmp(os.path.join(font_dir, text_files), font_output_dir,
                 scale_params, background_colors, replace_map, text_max_colors)

  # Build font file.
  shell("bmpblk_font --outfile %s/hwid_fonts.font %s/font/*.bmp" %
        (output_dir, output_dir), capture_stdout=True)

  # Create YAML file.
  shell("cd %s && OPTIONAL_SCREENS='%s' %s/make_default_yaml.py %s" %
        (output_dir, ' '.join(optional_screens), SCRIPT_BASE,
         ' '.join(locales)))
  return output_dir


def build_bitmap_block(board, config, output_dir):
  """Builds the bitmap block output file (and archive files) in output_dir.

  Args:
    board: a string, the name of board to use.
    config: a dictionary of board configuration.
    output_dir: a string of folder to contain resources and to output files.
  """
  panel_size = config[PANEL_SIZE_KEY]
  size_limit = config[SIZE_LIMIT_KEY]

  # Get version information.
  vcsid = os.getenv('VCSID')
  # VCSID comes in REV-GITHASH (0.0.1-r1-abcdef....).
  if vcsid:
    rev, unused_token, git_version = vcsid.rpartition('-')
    if rev == '9999':
      git_version = git_version[:6]
      git_dirty = '_mod'
    else:
      git_version = rev
      git_dirty = ''
  else:
    git_version = shell('git show -s --format="%h"', capture_stdout=True)
    git_dirty = shell("git diff --shortstat", capture_stdout=True) and "_mod"

  archive_name = ("chromeos-bmpblk-%s-%s%s.tbz2" %
                  (board, git_version.strip(), git_dirty.strip()))

  # Compile bitmap block file.
  shell("cd %s && %s -c DEFAULT.yaml %s && tar -acf %s %s" %
        (output_dir, BMPLKU, BMPBLK_OUTPUT, archive_name, BMPBLK_OUTPUT))
  print ("\nBitmap block file generated in: %s/%s\n"
         "Archive file to upload: %s/%s\n"
         "To preview, run following command OUTSIDE chroot:\n"
         "   ../bitmap_viewer %s/DEFAULT.yaml %sx%s\n" %
         (output_dir, BMPBLK_OUTPUT, output_dir, archive_name, output_dir,
          panel_size[0], panel_size[1]))
  shell("ls -l %s/%s" % (output_dir, BMPBLK_OUTPUT))

  # Check size limitation.
  output_file = os.path.join(output_dir, BMPBLK_OUTPUT)
  output_size = os.path.getsize(output_file)
  if output_size > size_limit:
    raise BuildImageError('Exceed output size limitation (%d > %d): %s' %
                          (output_size, size_limit, board))


def main(args):
  """Entry point when executed from command line.

  Args:
    args: a list, boards to build.
  """
  config_database = load_boards_config('boards.yaml')
  find_utility(BMPLKU)
  find_utility(BMPLKFONT)
  if args == ['ALL']:
    args = config_database.keys()
    print 'Building all boards: ', args
  for board in args:
    config = config_database.get(board, None)
    if config is None:
      raise BuildImageError('Unknown board: %s' % board)
    build_bitmap_block(board, config, build_image(board, config))


if __name__ == '__main__':
  try:
    main(sys.argv[1:])
  except BuildImageError, err:
    sys.stderr.write("ERROR: %s\n" % err)

