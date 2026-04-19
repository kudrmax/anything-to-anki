from __future__ import annotations

import re


def strip_markdown(text: str) -> str:
    """Remove markdown bold/italic markers, leaving plain text."""
    text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'_{2}(.+?)_{2}', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'\*(.+?)\*', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'_(.+?)_', r'\1', text, flags=re.DOTALL)
    return text




def highlight_all_forms(text: str, lemma: str, surface_form: str | None) -> str:
    """Convert markdown to HTML, then wrap ALL occurrences of target word forms with <b> tags.

    Matches:
    - surface_form exactly (e.g. "gave up") when provided
    - lemma + any trailing word characters (e.g. "run" matches "running", "runs")
    - for multi-word lemmas: first word inflected + rest exact (e.g. "gives up", "giving up")

    Note: irregular forms without surface_form (ran←run, went←go) are not matched.
    """
    text = strip_markdown(text)

    patterns: list[str] = []

    if surface_form:
        patterns.append(re.escape(surface_form))

    words = lemma.split()
    if len(words) == 1:
        patterns.append(r'\b' + re.escape(lemma) + r'\w*')
    else:
        rest = r'\s+' + r'\s+'.join(re.escape(w) for w in words[1:])
        patterns.append(r'\b' + re.escape(words[0]) + r'\w*' + rest + r'\b')

    combined = re.compile('(' + '|'.join(patterns) + ')', re.IGNORECASE)
    result = combined.sub(r'<b>\1</b>', text)
    return result.replace('\r\n', '<br>').replace('\n', '<br>')


def format_examples_as_list(html: str) -> str:
    """Convert <br>-separated examples into an HTML <ul> bullet list."""
    lines = [line.strip() for line in html.split('<br>') if line.strip()]
    if not lines:
        return html
    items = ''.join(f'<li>{line}</li>' for line in lines)
    return f'<ul>{items}</ul>'
