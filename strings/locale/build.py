#!/usr/bin/env python2
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Build localized text resources by extracting firmware localization strings
   and convert into TXT and PNG files into stage folder.

Usage:
   ./build.py <locale-list>
"""

# TODO(hungte) Read, write and handle UTF8 BOM.

import signal
import enum
import glob
import multiprocessing
import os
import re
import subprocess
import sys

from PIL import Image
import yaml

SCRIPT_BASE = os.path.dirname(os.path.abspath(__file__))
KEY_LOCALES = 'locales'
KEY_INPUTS = 'inputs'
KEY_FILES = 'files'
KEY_FONTS = 'fonts'
KEY_STYLES = 'styles'
LEGACY_MENU_INPUTS = 'legacy_menu_inputs'
LEGACY_MENU_FILES = 'legacy_menu_files'
LEGACY_CLAMSHELL_FILES = 'legacy_clamshell_files'
VENDOR_INPUTS = 'vendor_inputs'
VENDOR_FILES = 'vendor_files'
DIAGNOSTIC_FILES = 'diagnostic_files'

STRINGS_FILE = 'strings.txt'
LEGACY_STRINGS_FILE = 'legacy_strings.txt'
LEGACY_MENU_STRINGS_FILE = 'legacy_menu_strings.txt'
VENDOR_STRINGS_FILE = 'vendor_strings.txt'
FORMAT_FILE = 'format.yaml'
LEGACY_FORMAT_FILE = 'legacy_format.yaml'
VENDOR_FORMAT_FILE = 'vendor_format.yaml'
TXT_TO_PNG_SVG = os.path.join(SCRIPT_BASE, '..', 'text_to_png_svg')
OUTPUT_DIR = os.path.join(os.getenv('OUTPUT', os.path.join(SCRIPT_BASE, '..',
                                                           '..', 'build')),
                          '.stage', 'locale')

VENDOR_STRINGS_DIR = os.getenv("VENDOR_STRINGS_DIR")
VENDOR_STRINGS = VENDOR_STRINGS_DIR != None

class UIType(enum.Enum):
  MENU = 1
  LEGACY_MENU = 2
  LEGACY_CLAMSHELL = 3

UI = (UIType.MENU if os.getenv("MENU_UI") == "1" else
      UIType.LEGACY_MENU if os.getenv("LEGACY_MENU_UI") == "1" else
      UIType.LEGACY_CLAMSHELL)

class DataError(Exception):
  pass


def GetImageWidth(filename):
  """Returns the width of given image file."""
  return Image.open(filename).size[0]

def ParseLocaleInputFile(locale_dir, strings_file, input_format):
  """Parses firmware string file in given locale directory for BuildTextFiles

  Args:
    locale: The locale folder with firmware string files.
    strings_file: The name of the string txt file
    input_format: Format description for each line in strings_file.

  Returns:
    A dictionary for mapping of "name to content" for files to be generated.
  """
  input_file = os.path.join(locale_dir, strings_file)
  with open(input_file, 'r') as f:
    input_data = f.readlines()
  if len(input_data) != len(input_format):
    raise DataError('Input file <%s> for locale <%s> '
                    'does not match input format.' %
                    (strings_file, locale_dir))
  input_data = [s.strip() for s in input_data]
  return dict(zip(input_format, input_data))

def ParseLocaleInputFiles(locale_dir, input_format,
                          legacy_menu_format, vendor_format):
  """Parses all firmware string files in given locale directory for
  BuildTextFiles

  Args:
    locale: The locale folder with firmware string files.
    input_format: Format description for each line in LEGACY_STRINGS_FILE.
    legacy_menu_format: Format description for each line in
      LEGACY_MENU_STRINGS_FILE.
    vendor_format: Format description for each line in VENDOR_STRINGS_FILE.

  Returns:
    A dictionary for mapping of "name to content" for files to be generated.
  """
  result = dict()
  result.update(ParseLocaleInputFile(locale_dir,
                                     STRINGS_FILE if UI == UIType.MENU
                                     else LEGACY_STRINGS_FILE,
                                     input_format))
  # Now parse legacy menu strings
  if UI == UIType.LEGACY_MENU:
    print " (legacy_menu_ui enabled)"
    result.update(ParseLocaleInputFile(locale_dir,
                                       LEGACY_MENU_STRINGS_FILE,
                                       legacy_menu_format))

  # Parse vendor files if enabled
  if VENDOR_STRINGS:
    print " (vendor specific strings)"
    result.update(
      ParseLocaleInputFile(os.path.join(VENDOR_STRINGS_DIR, locale_dir),
                                        VENDOR_STRINGS_FILE,
                                        vendor_format))

  # Walk locale directory to add pre-generated items.
  for input_file in glob.glob(os.path.join(locale_dir, "*.txt")):
    if (os.path.basename(input_file) == LEGACY_STRINGS_FILE or
        os.path.basename(input_file) == LEGACY_MENU_STRINGS_FILE or
        os.path.basename(input_file) == VENDOR_STRINGS_FILE):
      continue
    name, _ = os.path.splitext(os.path.basename(input_file))
    with open(input_file, "r") as f:
      result[name] = f.read().strip()

  return result


def CreateFile(file_name, contents, output_dir):
  """Creates a text file in output directory by given contents.

  Args:
    file_name: Output file name without extension.
    contents: A list of strings for file content.
    output_dir: The directory to store output file.
  """
  output_name = os.path.join(output_dir, file_name + '.txt')
  with open(output_name, 'w') as f:
    f.write('\n'.join(contents) + '\n')


def ModifyContent(input_data, command):
  """Modifies some input content with given Regex commands.

  Args:
    input_data: Input string to be modified.
    command: Regex commands to execute.

  Returns:
    Processed output string.
  """
  if not command.startswith('s/'):
    raise DataError('Unknown command: %s' % command)
  _, pattern, repl, _ = command.split('/')
  return re.sub(pattern, repl, input_data)


def BuildTextFiles(inputs, files, output_dir):
  """Builds text files from given input data.

  Args:
    inputs: Dictionary of contents for given file name.
    files: List of file records: [name, content].
    output_dir: Directory to generate text files.
  """
  for file_name, file_content in files.iteritems():
    if file_content is None:
      CreateFile(file_name, [inputs[file_name]], output_dir)
    else:
      contents = []
      for data in file_content:
        if '@' in data:
          name, _, command = data.partition('@')
          contents.append(ModifyContent(inputs[name], command))
        else:
          contents.append('' if data == '' else inputs[data])
      CreateFile(file_name, contents, output_dir)


def ConvertPngFile(locale, file_name, styles, fonts, output_dir):
  """Converts text files into PNG image files.

  Args:
    locale: Locale (language) to select implicit rendering options.
    file_name: String of input file name to generate.
    styles: Dictionary to get associated per-file style options.
    fonts: Dictionary to get associated per-file font options.
    output_dir: Directory to generate image files.
  """
  input_file = os.path.join(output_dir, file_name + '.txt')
  command = [TXT_TO_PNG_SVG, "--lan=%s" % locale, "--outdir=%s" % output_dir]
  if file_name in styles:
    command.append(styles[file_name])
  if locale in fonts:
    command.append("--font='%s'" % fonts[locale])
  font_size = os.getenv("FONTSIZE")
  if font_size is not None:
    command.append('--point=%r' % font_size)
  if UI == UIType.MENU:
    command.append('--margin="0 0"')
  command.append(input_file)

  if subprocess.call(' '.join(command), shell=True,
                     stdout=subprocess.PIPE) != 0:
    return False

  # Check output file size
  output_file = os.path.join(output_dir, file_name + '.png')

  return True

def main(argv):
  with open(FORMAT_FILE if UI == UIType.MENU else LEGACY_FORMAT_FILE) as f:
    formats = yaml.load(f)

  if VENDOR_STRINGS:
    with open(os.path.join(VENDOR_STRINGS_DIR, VENDOR_FORMAT_FILE)) as f:
      formats.update(yaml.load(f))

  # Decide locales to build.
  if len(argv) > 0:
    locales = argv
  else:
    locales = os.getenv('LOCALES', '').split()
  if not locales:
    locales = formats[KEY_LOCALES]

  # Ignore SIGINT in child processes
  sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
  pool = multiprocessing.Pool(multiprocessing.cpu_count())
  signal.signal(signal.SIGINT, sigint_handler)

  results = []
  for locale in locales:
    print locale,
    inputs = ParseLocaleInputFiles(locale, formats[KEY_INPUTS],
                                   formats.get(LEGACY_MENU_INPUTS),
                                   formats[VENDOR_INPUTS] if VENDOR_STRINGS
                                                          else None)
    output_dir = os.path.normpath(os.path.join(OUTPUT_DIR, locale))
    if not os.path.exists(output_dir):
      os.makedirs(output_dir)
    files = formats[KEY_FILES]
    styles = formats[KEY_STYLES]
    if UI == UIType.LEGACY_MENU:
      files.update(formats[LEGACY_MENU_FILES])
    elif UI == UIType.LEGACY_CLAMSHELL:
      files.update(formats[LEGACY_CLAMSHELL_FILES])

    # Now parse strings for optional features
    if os.getenv("DIAGNOSTIC_UI") == "1":
      files.update(formats[DIAGNOSTIC_FILES])

    if VENDOR_STRINGS:
      files.update(formats[VENDOR_FILES])
    BuildTextFiles(inputs, files, output_dir)

    results += [pool.apply_async(ConvertPngFile,
                                 (locale, file_name,
                                  styles, formats[KEY_FONTS],
                                  output_dir))
                for file_name in formats[KEY_FILES]]
  pool.close()
  print ""

  try:
    success = [r.get() for r in results]
  except KeyboardInterrupt:
    pool.terminate()
    pool.join()
    exit('Aborted by user')
  else:
    pool.join()
    if not all(success):
      exit('Failed to render some locales')


if __name__ == '__main__':
  main(sys.argv[1:])
