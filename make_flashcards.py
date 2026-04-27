"""Parse chapters/*.md vocab markdown → produce ~/french-flashcards/cards.js.

Reads texts.json (a list of {id, name, author, shortName, files}) and parses
each referenced markdown file into a flat list of cards.

Output schema:
  const DATA = {
    texts:    [{id, name, author, shortName}],
    chapters: [{id, textId, number, title, levelCounts}],
    cards:    [{id, textId, chapterId, lemma, pos, posFull, cefr,
                pages, fr_defs, en_defs, conjugationHTML}],
  };
"""
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / 'cards.js'

# regex parsers
RE_CHAPTER = re.compile(r'^##\s+Chapter\s+(\d+):\s*(.+?)\s*$', re.M)
RE_LEVEL = re.compile(r'^###\s+(B1|B2|C1|C2|Unranked.*)$')
RE_CONJ_HEAD = re.compile(r'^###\s+Conjugations\b', re.I)
RE_ENTRY = re.compile(r'^- \*\*(?P<lemma>[^*]+)\*\* \((?P<pos>[^)]+)\)(?: \[→ conjugation below\])? — pp\. (?P<pages>.+)$')
RE_DEF_HEADER = re.compile(r'^  - \*\*(FR|EN):\*\*$')
RE_DEF_BULLET = re.compile(r'^    - (.+)$')
RE_CONJ_VERB = re.compile(r'^####\s+(\S+)\s*$')

# only emit conjugation for these infinitive endings (filters out spaCy mis-lemmas)
VERB_ENDING_RE = re.compile(r'(er|ir|re|oir)$')

POS_FULL = {'n.': 'NOUN', 'v.': 'VERB', 'adj.': 'ADJ', 'adv.': 'ADV'}


def looks_like_verb_lemma(lemma: str) -> bool:
    return bool(VERB_ENDING_RE.search(lemma))


def parse_chapter(md_text: str) -> dict:
    """Returns {chapter_number, chapter_title, entries: [card], conjugations: {lemma: html}}."""
    # Chapter header
    m = RE_CHAPTER.search(md_text)
    if not m:
        raise ValueError('no chapter header (## Chapter N: ...) found')
    ch_num = int(m.group(1))
    ch_title = m.group(2).strip()

    # Split into pre-conjugations and conjugations sections by "### Conjugations"
    parts = re.split(r'(?m)^###\s+Conjugations.*$', md_text, maxsplit=1)
    body = parts[0]
    conj_section = parts[1] if len(parts) > 1 else ''

    # Walk body line-by-line to collect entries grouped by level
    entries = []
    cur_level = None
    cur_entry = None
    cur_def_lang = None  # 'fr' or 'en'
    for line in body.split('\n'):
        # Level header
        m = RE_LEVEL.match(line)
        if m:
            cur_level = m.group(1)
            if cur_level.startswith('Unranked'):
                cur_level = 'Unranked'
            cur_entry = None
            cur_def_lang = None
            continue
        if cur_level is None:
            continue
        # Entry header
        m = RE_ENTRY.match(line)
        if m:
            if cur_entry:
                entries.append(cur_entry)
            pos = m.group('pos')
            pages = [int(p.strip()) for p in m.group('pages').split(',') if p.strip().isdigit()]
            cur_entry = {
                'lemma': m.group('lemma').strip(),
                'pos': pos,
                'posFull': POS_FULL.get(pos, pos.upper()),
                'cefr': cur_level,
                'pages': pages,
                'fr_defs': [],
                'en_defs': [],
            }
            cur_def_lang = None
            continue
        # Definition header
        m = RE_DEF_HEADER.match(line)
        if m and cur_entry:
            cur_def_lang = 'fr' if m.group(1) == 'FR' else 'en'
            continue
        # Definition bullet
        m = RE_DEF_BULLET.match(line)
        if m and cur_entry and cur_def_lang:
            text = m.group(1).strip()
            cur_entry[f'{cur_def_lang}_defs'].append(text)
            continue
    if cur_entry:
        entries.append(cur_entry)

    # Parse conjugations section: collect markdown blocks per verb
    conjugations = {}
    cur_verb = None
    cur_buf = []
    for line in conj_section.split('\n'):
        m = RE_CONJ_VERB.match(line)
        if m:
            if cur_verb and cur_buf:
                conjugations[cur_verb] = '\n'.join(cur_buf).strip()
            cur_verb = m.group(1)
            cur_buf = []
            continue
        if cur_verb is not None:
            cur_buf.append(line)
    if cur_verb and cur_buf:
        conjugations[cur_verb] = '\n'.join(cur_buf).strip()

    return {
        'number': ch_num,
        'title': ch_title,
        'entries': entries,
        'conjugations': conjugations,
    }


def md_table_to_html(md: str) -> str:
    """Convert the conjugation block (table + extra line) to HTML."""
    lines = [ln for ln in md.split('\n') if ln.strip()]
    table_lines = [ln for ln in lines if ln.startswith('|')]
    extra = [ln for ln in lines if not ln.startswith('|')]
    if len(table_lines) < 2:
        return ''
    # First row = headers, second = separator, rest = body
    def cells(row):
        # Strip leading/trailing | and split
        return [c.strip() for c in row.strip().strip('|').split('|')]

    def md_inline(s):
        # Handle bold first, then italic, otherwise *je* in ** ** gets matched first
        s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', s)
        return s

    headers = [md_inline(h) for h in cells(table_lines[0])]
    rows = [[md_inline(c) for c in cells(r)] for r in table_lines[2:]]
    html = ['<table class="conj">']
    html.append('<thead><tr>' + ''.join(f'<th>{h}</th>' for h in headers) + '</tr></thead>')
    html.append('<tbody>')
    for r in rows:
        html.append('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>')
    html.append('</tbody></table>')
    if extra:
        # extra line(s) like "participe présent: *parlant* · participe passé: *parlé*"
        text = ' '.join(extra).strip()
        # render *italic* spans
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
        html.append(f'<div class="conj-extra">{text}</div>')
    return '\n'.join(html)


def build_data(texts_cfg: list[dict]) -> dict:
    texts = []
    chapters = []
    cards = []

    for tx in texts_cfg:
        text_id = tx['id']
        texts.append({
            'id': text_id,
            'name': tx['name'],
            'author': tx['author'],
            'shortName': tx['shortName'],
        })
        for rel_path in tx['files']:
            md = (ROOT / rel_path).read_text(encoding='utf-8')
            parsed = parse_chapter(md)
            ch_id = f'{text_id}-ch{parsed["number"]}'
            level_counts = defaultdict(int)
            for e in parsed['entries']:
                level_counts[e['cefr']] += 1
            chapters.append({
                'id': ch_id,
                'textId': text_id,
                'number': parsed['number'],
                'title': parsed['title'],
                'levelCounts': dict(level_counts),
            })
            for e in parsed['entries']:
                # Filter bogus verb lemmas
                conj_html = ''
                if e['posFull'] == 'VERB':
                    if not looks_like_verb_lemma(e['lemma']):
                        # Reclassify as noun (it's a misanalysis)
                        e['pos'] = 'n.'
                        e['posFull'] = 'NOUN'
                    else:
                        md_block = parsed['conjugations'].get(e['lemma'])
                        if md_block:
                            conj_html = md_table_to_html(md_block)

                # Skip cards with no defs at all (shouldn't happen but be safe)
                if not e['fr_defs'] and not e['en_defs']:
                    continue

                card_id = f'{ch_id}-{e["lemma"]}-{e["posFull"]}'
                cards.append({
                    'id': card_id,
                    'textId': text_id,
                    'chapterId': ch_id,
                    'lemma': e['lemma'],
                    'pos': e['pos'],
                    'posFull': e['posFull'],
                    'cefr': e['cefr'],
                    'pages': e['pages'],
                    'fr_defs': e['fr_defs'],
                    'en_defs': e['en_defs'],
                    'conjugationHTML': conj_html,
                })

    return {'texts': texts, 'chapters': chapters, 'cards': cards}


def main():
    cfg = json.loads((ROOT / 'texts.json').read_text())
    data = build_data(cfg)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = 'const DATA = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';\n'
    OUT.write_text(js, encoding='utf-8')
    print(f'wrote {OUT}: {len(data["texts"])} texts, {len(data["chapters"])} chapters, {len(data["cards"])} cards')
    # per-chapter breakdown
    for ch in data['chapters']:
        print(f'  {ch["id"]} ({ch["title"]}): {ch["levelCounts"]}')


if __name__ == '__main__':
    main()
