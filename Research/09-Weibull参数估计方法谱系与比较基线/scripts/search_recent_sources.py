"""Bounded public-index discovery; returned hits are candidates, not included studies."""
import concurrent.futures
import datetime
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
QUERY = 'three parameter Weibull estimation small sample'
REQUESTS = {
    'crossref': 'https://api.crossref.org/works?' + urlencode({
        'query.title': QUERY, 'filter': 'from-pub-date:2006-01-01,until-pub-date:2026-09-28', 'rows': 35}),
    'openalex': 'https://api.openalex.org/works?' + urlencode({
        'search': QUERY, 'filter': 'from_publication_date:2006-01-01,to_publication_date:2026-09-28', 'per-page': 35}),
    'semantic_scholar': 'https://api.semanticscholar.org/graph/v1/paper/search?' + urlencode({
        'query': QUERY, 'year': '2006:2026', 'limit': 35, 'fields': 'title,year,externalIds,openAccessPdf,url'}),
}

def fetch(entry):
    name, url = entry
    result = {'index': name, 'url': url, 'query': QUERY,
              'requested_window': '2006-01-01/2026-09-28', 'limit': 35}
    try:
        request = Request(url, headers={'User-Agent': 'Research09 literature audit/1.0'})
        with urlopen(request, timeout=35) as response:
            result['status'] = response.status
            result['response'] = json.load(response)
    except Exception as error:
        result['error'] = str(error)
    return result

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch, REQUESTS.items()))
    target = ROOT / 'evidence/recent_index_search_20260928.json'
    target.write_text(json.dumps({'searched_at': datetime.datetime.now().astimezone().isoformat(),
        'purpose': 'bounded candidate discovery; no completeness or inclusion claim', 'requests': results},
        ensure_ascii=False, indent=2), encoding='utf-8')
    for result in results:
        data = result.get('response', {})
        items = data.get('message', {}).get('items', []) if result['index'] == 'crossref' else data.get('results', data.get('data', []))
        print(result['index'], result.get('status', result.get('error')), 'returned', len(items))
        for item in items:
            print(json.dumps({key: item.get(key) for key in ('title', 'year', 'publication_year', 'DOI', 'doi', 'openAccessPdf') if item.get(key)}, ensure_ascii=False))
