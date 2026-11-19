"""Cache the current institutional JCR table for metadata enrichment on registration."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request

import pymupdf


def main():
    website = Path(__file__).resolve().parents[1]
    registry = json.loads((website / 'src/data/library-journals.json').read_text(encoding='utf-8'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', help='Use an already downloaded copy of the source table')
    parser.add_argument('--output', default=str(Path(os.environ.get('WEIBULL_DATA_ROOT', website.parent / 'weibull-data')) /
                                              'literature-metadata' / f'jcr-{registry["year"]}.json'))
    args = parser.parse_args()
    source = registry['source']
    if args.pdf:
        data = Path(args.pdf).read_bytes()
    else:
        request = urllib.request.Request(source, headers={'User-Agent': 'WeibullLibrary/1.0 metadata maintenance'})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
    row = re.compile(r'^\s*(.*?)\s*(\d{4}-[\dX]{4}|N/A)\s+.+?\s+(?:[\d,]+|N/A)\s+'
                     r'(\d+(?:\.\d+)?|<0\.1|N/A)(?:\s+(?:\d+(?:\.\d+)?|<0\.1|N/A))?\s+(Q[1-4]|N/A)\s*$')
    journals = []
    with pymupdf.open(stream=data, filetype='pdf') as document:
        heading = document[0].get_text(sort=True)
        if f'JIF {registry["year"] + 1}' not in heading:
            raise ValueError('Table release year does not match the configured JCR data year')
        for page in document:
            for line in page.get_text(sort=True).splitlines():
                match = row.match(line)
                if not match:
                    continue
                name, issn, impact, quartile = match.groups()
                if not re.fullmatch(r'\d+(?:\.\d+)?', impact) or quartile == 'N/A':
                    continue
                journals.append({'name': name.strip(), 'issns': [issn] if issn != 'N/A' else [],
                                 'impactFactor': float(impact), 'quartile': quartile})
    if not journals:
        raise ValueError('No verified table rows were parsed')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.jcr-', dir=output.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'year': registry['year'], 'source': source, 'journals': journals}, stream, ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(json.dumps({'year': registry['year'], 'journals': len(journals), 'file': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
