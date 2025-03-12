import os
import re
import pwd
import sys
import json
import shutil
import logging
import datetime
import requests
import subprocess
import urllib.parse
from pathlib import Path
from getpass import getpass
from functools import lru_cache
from binary import BinaryUnits, convert_units
from starfish.common import convert_to_units

logger = logging.getLogger(__name__)

class Starfish:
    def __init__(self, uri, token_file='~/.config/starfish/token'):
        self._uri = uri.rstrip('/')
        self._headers = dict()
        self._token_file = Path(token_file).expanduser()
        self._init_token_file()

    def zones(self):
        url = f'{self._uri}/api/zone'
        logger.debug(f'GET {url}')
        r = requests.get(
            url,
            headers=self._headers
        )
        return r.json()

    def zone(self, zoneid):
        url = f'{self._uri}/api/zone/{zoneid}'
        logger.debug(f'POST {url}')
        r = requests.get(
            url,
            headers=self._headers
        )
        return r.json()

    def find_zone(self, name):
        for zone in self.zones():
            if zone['name'] == name:
                return zone
        return None

    def volumes_and_paths(self, s, depth='0-1'):
        s = urllib.parse.quote(s, safe='')
        url = f'{self._uri}/api/query/{s}'
        logger.debug(f'GET {url}')
        format = [
            'volume',
            'full_path',
            'parent_path',
            'fn',
            'type',
            'size',
            'ct',
            'mt',
            'at',
            'uid',
            'username',
            'gid',
            'mode',
            'aggrs',
            'rec_aggrs'
        ]
        r = requests.get(
            url,
            params={
                'query': f'depth={depth}',
                'format': ' '.join(format),
                'humanize_nested': True
            },
            headers=self._headers,
        )
        return r.json()

    @lru_cache(maxsize=None)
    def get_fs_type(self, path):
        cmd = [
            'df',
            '--output=fstype',
            str(path)
        ]
        try:
            output = subprocess.check_output(
                cmd,
                stderr=subprocess.DEVNULL
            ).decode()
            fstype = output.split(os.linesep)[1].strip()
        except subprocess.CalledProcessError as e:
            raise FileNotFoundError(path)
        return fstype.upper()

    def disk_usage(self, path, group='cnl', fstype=None):
        if fstype == 'LUSTRE':
            cmd = [
                'lfs',
                'quota',
                '-g',
                group,
                path
            ]
            output = subprocess.check_output(cmd).decode()
            output = output.split('\n')
            data = output[3].strip()
            data = re.split(r'\s+', data)
            kbytes = int(data[1])
            nbytes = convert_to_units(f'{kbytes}KB', 'B')
        else:
            nbytes, _, _ = shutil.disk_usage(path)
        return int(nbytes)

    @lru_cache(maxsize=None)
    def total_share_size(self, path, units='TiB'):
        volume, share = path.split(':')
        path_a = Path('/net', volume, 'data', share)
        path_b = Path('/net', volume, 'srv', 'export', share, 'share_root')
        path_c = Path('/n', volume, re.sub(r'^F\/', '', share))
        nbytes = 0
        for path in [path_a, path_b, path_c]:
            try:
                fstype = self.get_fs_type(path)
                logger.debug(f'{path} is a "{fstype}" file system')
                nbytes = self.disk_usage(path, fstype=fstype)
                logger.debug(f'found size of {path}, {nbytes}B')
            except FileNotFoundError:
                pass
        match units:
            case 'MiB':
                convert_to = BinaryUnits.MB
            case 'TiB':
                convert_to = BinaryUnits.TB
            case 'GiB':
                convert_to = BinaryUnits.GB
            case _:
                raise Exception(f'conversion to {units} not supported')
        total,_ = convert_units(nbytes, BinaryUnits.B, convert_to)
        return total,fstype

    @lru_cache(maxsize=None)
    def get_username(self, uid):
        return pwd.getpwuid(uid).pw_name

    def auth(self, username, timeout=3600):
        with open(self._token_file) as fo:
            token = json.load(fo)
        expiry = datetime.datetime.fromisoformat(
            token['expiry']
        )
        if expiry <= datetime.datetime.now():
            logging.info('generating new API token')
            password = getpass('enter your starfish password: ')
            token = self._get_token(username, password, timeout)
            logger.info(f'updating {self._token_file}')
            self._token_file.write_text(json.dumps(token, indent=2))
        self._headers['Authorization'] = f'Bearer {token["token"]}'

    def _init_token_file(self):
        if not self._token_file.exists():
            self._token_file.parent.mkdir(
                mode=0o700,
                exist_ok=True,
                parents=True
            )
            self._token_file.touch(mode=0o600)
            logger.info(f'initializing {self._token_file}')
            self._token_file.write_text(
                json.dumps({
                    'expiry': '1970-01-01T00:00:00.000000'
                }, indent=2)
            )

    def _get_token(self, username, password, timeout=3600):
        body = {
            'username': username,
            'password': password,
            'token_timeout_secs': timeout,
            'token_description': 'string'
        }
        r = requests.post(f'{self._uri}/api/auth/', json=body)
        js = r.json()
        expiry = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
        js['expiry'] = expiry.isoformat()
        return js
