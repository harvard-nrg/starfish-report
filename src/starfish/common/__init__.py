import re
import datetime
from binary import BinaryUnits, DecimalUnits, convert_units

def convert_to_units(s, units):
    value, unit = parse_storage_string(s)
    new_units = parse_unit_string(units)
    result,_ = convert_units(value, unit, new_units)
    return result

def parse_storage_string(s):
    match = re.match(r'^(?P<num>\d+)(?P<unit>\w+)$', s.strip())
    num = float(match.group('num'))
    unit = match.group('unit')
    unit = parse_unit_string(unit)
    return num, unit

def parse_unit_string(unit):
    match unit:
        case 'B':
            return BinaryUnits.B
        case 'KiB':
            return BinaryUnits.KB
        case 'MiB':
            return BinaryUnits.MB
        case 'GiB':
            return BinaryUnits.GB
        case 'TiB':
            return BinaryUnits.TB
        case 'KB':
            return DecimalUnits.KB
        case 'MB':
            return DecimalUnits.MB
        case 'GB':
            return DecimalUnits.GB
        case 'TB':
            return DecimalUnits.TB
        case _:
            raise Exception(f'unknown storage unit {unit}')

def confirm(s):
    while True:
        ans = input(s).lower()
        match ans:
            case 'y':
                return True
            case 'n':
                return False

def unix2date(ts):
    s = datetime.datetime.fromtimestamp(ts, datetime.UTC)
    return s.strftime('%Y-%m-%d')
