"""Apply parenthesized, centered panel headings to Matplotlib figures."""
import re


def normalize_panel_labels(fig):
    for ax in fig.axes:
        titles = [ax._left_title, ax.title, ax._right_title]
        matches = []
        for text in titles + list(ax.texts):
            s = text.get_text().strip()
            match = re.match(r'^\(?([a-fA-F])\)?(?:[.、:]?\s+|$)(.*)', s, re.S)
            if match:
                matches.append((text, match.group(1).lower(), match.group(2).strip()))
        for text, letter, rest in matches:
            if not rest and text not in titles:
                existing = next((t for t in titles if t.get_text().strip()), None)
                if existing is not None:
                    rest = existing.get_text().strip()
                    existing.set_text('')
            text.set_text(f'({letter})' + ('  ' + rest if rest else ''))
            text.set_ha('center')
            text.set_fontfamily(['SimSun', 'Times New Roman'] if re.search(r'[\u3400-\u9fff]', rest)
                                else ['Times New Roman', 'SimSun'])
            text.set_fontweight('normal'); text.set_fontstyle('normal')
            if text in titles:
                y = text.get_position()[1]
                text.set_position((.5, y))
            else:
                # Framework sections share a single axes; retain their row positions.
                x, y = text.get_position()
                if len(matches) > 1:
                    text.set_position(((ax.get_xlim()[0] + ax.get_xlim()[1]) / 2, y))
                else:
                    text.set_transform(ax.transAxes)
                    text.set_position((.5, 1.04))
                    text.set_va('bottom')
            text.set_clip_on(False)
