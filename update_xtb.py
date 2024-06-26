#!/usr/bin/env python
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script for strings updating."""

import argparse
import glob
import logging
import os
import re
from xml.etree import ElementTree


DEFAULT_SRC_STRING_PATH = (
    'blaze-genfiles/googleclient/chrome/' 'transconsole_resources/strings/cros'
)
DEFAULT_DEST_STRINGS_PATH = os.path.join(
    os.path.dirname(__file__), 'strings', 'locale'
)


def get_locales_from_dir(src_dir):
    """Gets a set of locales of xtb files in src_dir."""
    locales = set()
    for file in glob.glob(os.path.join(src_dir, 'firmware_strings_*.xtb')):
        basename = os.path.basename(file)
        m = re.match(r'^firmware_strings_([A-Za-z0-9-]+).xtb$', basename)
        locales.add(m.group(1))
    return locales


def load_xtb_to_dict(xtb_dir, locale):
    """Loads xtb file to dict.

    Args:
        xtb_dir: The directory of xtb files.
        locale: The locale of the xtb file to be loaded.

    Returns:
        A dict of message_id => message.
    """
    xtb_file = os.path.join(xtb_dir, f'firmware_strings_{locale}.xtb')
    xtb_root = ElementTree.parse(xtb_file).getroot()
    res = {}
    for item in xtb_root:
        res[item.attrib['id']] = item.text
    return res


def save_dict_to_xtb(data, out_dir, locale):
    """Saves the dict to xtb file.

    Args:
        data: The dict of message_id => message.
        out_dir: The directory of xtb files.
        locale: The locale of the xtb file to be saved.
    """
    out_xtb = ElementTree.Element('translationbundle', {'lang': locale})
    out_xtb.text = '\n'
    for message_id, text in sorted(data.items()):
        e = ElementTree.SubElement(out_xtb, 'translation', {'id': message_id})
        e.text = text
        e.tail = '\n'
    out_file = os.path.join(out_dir, f'firmware_strings_{locale}.xtb')
    logging.info('Saving %r', out_file)
    with open(out_file, 'rb+') as f:
        # From chromium/src/tools/grit/grit/xtb_reader.py.
        # Skip the header and write the data of the <translationbundle> tag.
        front_of_file = f.read(1024)
        f.seek(front_of_file.find(b'<translationbundle'))
        out = ElementTree.tostring(out_xtb, encoding='utf-8')
        f.write(out)
        f.truncate()


def merge_xtb_data(locale, in_dir, out_dir, message_ids):
    """Merges the xtb data.

    Args:
        locale: The locale of the xtb file to be merged.
        in_dir: The source.
        out_dir: The destination.
        message_ids: List of the message ids. Only these ids will be modified.

    Returns:
        (new_ids, update_ids, del_ids): The set of the new/updated/removed
        message ids.
    """
    logging.info('Merging %r', locale)

    new_ids = set()
    update_ids = set()
    del_ids = set()

    in_data = load_xtb_to_dict(in_dir, locale)
    out_data = load_xtb_to_dict(out_dir, locale)
    for message_id in message_ids:
        if message_id in in_data and message_id not in out_data:
            new_ids.add(message_id)
            out_data[message_id] = in_data[message_id]
        elif message_id in in_data and message_id in out_data:
            if in_data[message_id] != out_data[message_id]:
                update_ids.add(message_id)
                out_data[message_id] = in_data[message_id]
            else:
                logging.warning(
                    "Locale %r: Id %r didn't change.", locale, message_id
                )
        elif message_id not in in_data and message_id in out_data:
            del_ids.add(message_id)
            out_data.pop(message_id)
        else:
            logging.warning(
                'Locale %r: Id %r not in input/output file.', locale, message_id
            )
    logging.info('New: %s', new_ids)
    logging.info('Updated: %s', update_ids)
    logging.info('Removed: %s', del_ids)
    save_dict_to_xtb(out_data, out_dir, locale)
    return new_ids, update_ids, del_ids


def get_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbosity', '-v', action='count', default=0)
    parser.add_argument(
        '--from',
        dest='in_dir',
        default=DEFAULT_SRC_STRING_PATH,
        help='The source directory of the generated xtb files.',
    )
    parser.add_argument(
        '--to',
        dest='out_dir',
        default=DEFAULT_DEST_STRINGS_PATH,
        help='The destination directory of the xtb files.',
    )
    subparser = parser.add_subparsers(dest='cmd')

    merge_parser = subparser.add_parser(
        'merge', help='Merge the xtb files with specific message ids.'
    )
    merge_parser.add_argument(
        'message_ids',
        metavar='ID',
        nargs='+',
        help='The ids of the strings which should be updated.',
    )

    diff_parser = subparser.add_parser(
        'diff', help='Show the different of message ids of a xtb file.'
    )
    diff_parser.add_argument(
        '--id-only', action='store_true', help="Don't show the message content."
    )
    diff_parser.add_argument('locale', help='The locale file to diff.')

    return parser.parse_args(), parser


def print_diff_item(key, data, id_only):
    if id_only:
        print(key)
    else:
        print(f'{key!r}: {data}')


def diff(args):
    in_data = load_xtb_to_dict(args.in_dir, args.locale)
    out_data = load_xtb_to_dict(args.out_dir, args.locale)
    print(
        '---------------------------------------------------------------------'
    )
    print('New:')
    for key, value in in_data.items():
        if key not in out_data:
            print_diff_item(key, value, args.id_only)
    print(
        '---------------------------------------------------------------------'
    )
    print('Updated:')
    for key, value in in_data.items():
        if key in out_data and value != out_data[key]:
            print_diff_item(
                key,
                f'\n{out_data[key]!r}\n=>\n{value!r}\n',
                args.id_only,
            )
    print(
        '---------------------------------------------------------------------'
    )
    print('Deleted:')
    for key, value in out_data.items():
        if key not in in_data:
            print_diff_item(key, value, args.id_only)
    print(
        '---------------------------------------------------------------------'
    )


def merge(args):
    in_locales = get_locales_from_dir(args.in_dir)
    out_locales = get_locales_from_dir(args.out_dir)
    if not out_locales.issubset(in_locales):
        raise RuntimeError(
            f'Missing locales in input xtb files: {out_locales - in_locales}'
        )
    if not in_locales.issubset(out_locales):
        logging.warning(
            'Ignoring extra locales in input xtb files: %s',
            in_locales - out_locales,
        )

    prev_id_sets = None
    for locale in sorted(out_locales):
        id_sets = merge_xtb_data(
            locale, args.in_dir, args.out_dir, args.message_ids
        )
        if prev_id_sets and id_sets != prev_id_sets:
            logging.warning(
                'Locale %r: Updated ids are different with the previous '
                'locale:\n%r\n=>\n%r',
                locale,
                prev_id_sets,
                id_sets,
            )
        prev_id_sets = id_sets


def main():
    args, parser = get_arguments()
    logging.basicConfig(level=logging.WARNING - 10 * args.verbosity)
    if args.cmd == 'diff':
        diff(args)
    elif args.cmd == 'merge':
        merge(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
