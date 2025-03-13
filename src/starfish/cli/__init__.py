import re
import csv
import sys
import json
import logging
import pandas as pd
from pathlib import Path
from starfish import Starfish
from argparse import ArgumentParser
from starfish.common import unix2date, confirm, convert_to_units, parse_storage_string

logger = logging.getLogger()

def starfish():
    parser = ArgumentParser()
    parser.add_argument('-u', '--username', default='tokeefe')
    parser.add_argument('--url', 
        default='https://starfish01.rc.fas.harvard.edu')
    parser.add_argument('--zone', default='cnl')
    parser.add_argument('--exclude-paths', nargs='+', default=[])
    parser.add_argument('--paths', nargs='+') 
    parser.add_argument('--limit', type=int, default=100000000)
    parser.add_argument('--force-units', type=str)
    parser.add_argument('--depth-range', nargs=2, type=int, default=[0, 2])
    parser.add_argument('--size-range', nargs=2, type=str, default=['0B', 'max'])
    parser.add_argument('--confirm', action='store_true')
    parser.add_argument('--output-file', type=Path)
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    logging.basicConfig(level=level)

    sf = Starfish(args.url)
    sf.auth(args.username)

    size_min,size_max = args.size_range
    min_bytes = convert_to_units(size_min, 'B')
    usemax = size_max.strip().upper() == 'MAX'
    zone = sf.find_zone(args.zone)

    paths = args.paths if args.paths else zone['paths']
    for path in paths:
        if path in args.exclude_paths:
            logger.info(f'skipping excluded path {path}')
            continue
        if args.confirm:
            ans = confirm(f'do you want to query {path} [y or n]: ')
            if ans is False:
                continue
        share_size, share_units, fs_type = sf.total_share_size(
            path,
            units=args.force_units
        )
        if usemax:
            size_max = f'{share_size:.2f}TiB'
        max_bytes = convert_to_units(size_max, 'B')
        data = sf.volumes_and_paths(
            path,
            depth=args.depth_range,
            limit=args.limit,
            size=None # (size_min, size_max)
        )
        rows = list()
        for row in data:
            volume = row['volume']
            full_path = row['full_path']
            _full_path = re.sub(r'^F\/LABS\/', '', full_path)
            size,units,nbytes = get_size(row, force_units=args.force_units)
            if nbytes < min_bytes or nbytes > max_bytes:
                logger.debug(f'rejected: size of {full_path} is {size}{units} ' \
                    f'which is outside of the accepted range of {size_min}-{size_max}')
                continue
            logger.info(f'accepted: size of {full_path} is {size}{units} which is ' \
                f'within the accepted range of {size_min}-{size_max}')
            owner = row['username']
            if not owner:
                owner = str(row['uid'])
            rows.append({
                'Path': f'{volume}:{full_path}',
                'Used': round(size, 2),
                'Used Units': units,
                'Total': round(share_size, 2),
                'Total Units': share_units,
                'Type': fs_type,
                'Owner': owner,
                'Last Changed': unix2date(row['ct']),
                'Last Modified': unix2date(row['mt']),
                'Last Accessed': unix2date(row['at']),
                'Newest Changed (Tree)': newest_ctime(row),
                'Newest Modified (Tree)': newest_mtime(row),
                'Newest Accessed (Tree)': newest_atime(row),
            })

        if not args.output_file:
            logger.info('pass --output-file to save output file')
            sys.exit()

        df = pd.DataFrame(rows)        
        if 'Path' in df:
            df = df.sort_values(by='Path')

        file_mode = 'w'
        sheet_mode = None
        if args.output_file.exists():
            file_mode = 'a'
            sheet_mode = 'overlay'

        with pd.ExcelWriter(
                args.output_file,
                engine='openpyxl',
                if_sheet_exists=sheet_mode,
                mode=file_mode) as writer:
            sheet_name = Path(_full_path).parts[0]
            startrow = 0
            if sheet_name in writer.sheets:
                startrow = writer.sheets[sheet_name].max_row 
            logger.info(f'saving data to sheet {sheet_name} within {args.output_file}')
            df.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
                header=not bool(startrow),
                startrow=startrow
            )

def newest_ctime(row):
    if 'rec_aggrs' in row and 'max' in row['rec_aggrs']:
        return unix2date(row['rec_aggrs']['max']['ctime'])
    return None

def newest_mtime(row):
    if 'rec_aggrs' in row and 'max' in row['rec_aggrs']:
        return unix2date(row['rec_aggrs']['max']['mtime'])
    return None

def newest_atime(row):
    if 'rec_aggrs' in row and 'max' in row['rec_aggrs']:
        return unix2date(row['rec_aggrs']['max']['atime'])
    return None

def get_size(row, force_units=None):
    if 'rec_aggrs' in row:
        size_bytes = row['rec_aggrs']['size']
        size_human = row['rec_aggrs']['size_hum']
    else:
        size_bytes = row['size']
        size_human = f'{size_bytes}B'

    if force_units:
        size_human = convert_to_units(size_human, force_units)
        size_human = f'{size_human:.2f}{force_units}'

    size_human,units = parse_storage_string(size_human)
    return  size_human, units, float(size_bytes)
