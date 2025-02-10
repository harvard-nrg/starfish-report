# Starfish Report

Starfish Report enables you to generate an `.xlsx` report of your 
storage usage.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

## Installation

```console
python3 -m venv starfish
source starfish/bin/activate
(starfish) pip install --upgrade pip
(starfish) pip install git+https://github.com/harvard-nrg/starfish-report
```

## Usage
The main CLI tool is named `starfish`. You can specify a zone, depth range, minimum size, and output file

```console
starfish --username jharvard --zone myzone --depth-range 0-3 --size-min 10GiB --output-file ~/Desktop/report.xlsx
```

This command will output an Excel formatted file `~/Desktop/report.xlsx` containing separate sheets for each path found under the `myzone` zone.

## scanning a specific path

To scan a specific path, you can use the `--paths` argument

```console
starfish --username jharvard --zone myzone --paths h-vol-a:example/a/b --depth-range 1 --size-min 10GiB --output-file ~/Desktop/report.xlsx
```

## appending output

When running multiple `starfish` commands, specify the same `--output-file` to append data to that file

```console
starfish --username jharvard --zone myzone --paths h-vol-a:example/a/b/c/d --depth-range 1 --size-min 10GiB --output-file ~/Desktop/report.xlsx
```

## License

`starfish` is distributed under the terms of the [BSD-3-Clause](https://spdx.org/licenses/BSD-3-Clause.html) license.
