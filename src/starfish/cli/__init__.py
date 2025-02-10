import csv
import sys
import json
import logging
import pandas as pd
from pathlib import Path
from starfish import Starfish
from argparse import ArgumentParser
from starfish.common import unix2date, confirm, convert_to_units

logger = logging.getLogger()

def starfish():
    parser = ArgumentParser()
    parser.add_argument('-u', '--username', default='tokeefe')
    parser.add_argument('--url', 
        default='https://starfish01.rc.fas.harvard.edu')
    parser.add_argument('--zone', default='cnl')
    parser.add_argument('--exclude-paths', nargs='+', default=[])
    parser.add_argument('--paths', nargs='+') 
    parser.add_argument('--depth-range', type=str, default='1-2')
    parser.add_argument('--size-min', default='0B')
    parser.add_argument('--confirm', action='store_true')
    parser.add_argument('--output-file', type=Path, required=True)
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    logging.basicConfig(level=level)

    sf = Starfish(args.url)
    sf.auth(args.username)

    size_min = convert_to_units(args.size_min, 'B')
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
        share_size = sf.total_share_size(path, units='TiB')
        data = sf.volumes_and_paths(path, depth=args.depth_range)
        rows = list()
        for row in data:
            volume = row['volume']
            full_path = row['full_path']
            size, size_human = get_size(row)
            if size < size_min:
                logger.info(f'skipping {row["full_path"]} since {size_human} < {args.size_min}')
                continue
            rows.append({
                'Path': f'{volume}:{full_path}',
                'Used': size_human,
                'Total': f'{share_size:.1f}TiB',
                'Owner': row['username'],
                'Last Changed': unix2date(row['ct']),
                'Last Modified': unix2date(row['mt']),
                'Last Accessed': unix2date(row['at']),
                'Newest Changed (Tree)': newest_ctime(row),
                'Newest Modified (Tree)': newest_mtime(row),
                'Newest Accessed (Tree)': newest_atime(row),
            })

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
            sheet_name = Path(full_path).parts[0]
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
    if 'rec_aggrs' in row:
        return unix2date(row['rec_aggrs']['max']['ctime'])
    return None

def newest_mtime(row):
    if 'rec_aggrs' in row:
        return unix2date(row['rec_aggrs']['max']['mtime'])
    return None

def newest_atime(row):
    if 'rec_aggrs' in row:
        return unix2date(row['rec_aggrs']['max']['atime'])
    return None

def get_size(row):
    if 'rec_aggrs' in row:
        size = row['rec_aggrs']['size']
        size_human = row['rec_aggrs']['size_hum']
    else:
        size = row['size']
        size_human = convert_to_units(f'{size}B', 'GiB')
        size_human = f'{size_human:.1f}GiB'
    return float(size), size_human
