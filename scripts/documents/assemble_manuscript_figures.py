"""Replace manuscript figures from a generated assembly manifest, preserving fields/math.

Usage: python scripts/documents/assemble_manuscript_figures.py MANIFEST DOCX_DIR
Back up destination documents before use. Only image paragraphs and image bytes change.
"""
import argparse
import json
import posixpath
import zipfile
from pathlib import Path

from lxml import etree as ET
from PIL import Image

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}


def prop(parent, name, **attrs):
    node = parent.find("w:" + name, NS)
    if node is None:
        node = ET.SubElement(parent, "{" + NS["w"] + "}" + name)
    for key, value in attrs.items():
        node.set("{" + NS["w"] + "}" + key, str(value))
    return node


def content(root):
    return [root.xpath(path, namespaces=NS) for path in
            ("//w:t/text()", "//m:t/text()", "//w:instrText/text() | //w:fldSimple/@w:instr")]


def assemble(manifest, docx_dir):
    rows = json.loads(manifest.read_text(encoding="utf-8-sig"))["figures"]
    for name in sorted({r["source_identity"]["document"] for r in rows}):
        path = docx_dir / name
        with zipfile.ZipFile(path) as source:
            parts = {p: source.read(p) for p in source.namelist()}
        root = ET.fromstring(parts["word/document.xml"])
        before = content(root)
        rels = {r.get("Id"): posixpath.normpath("word/" + r.get("Target"))
                for r in ET.fromstring(parts["word/_rels/document.xml.rels"])}
        drawings = root.xpath("//wp:inline[a:graphic]", namespaces=NS)
        selected = [r for r in rows if r["source_identity"]["document"] == name]
        assert len(drawings) == len(selected), (name, len(drawings), len(selected))
        # A table caption must not be stranded on the preceding page.
        for paragraph in root.xpath('//w:body/w:p', namespaces=NS):
            following = paragraph.getnext()
            label = ''.join(paragraph.xpath('.//w:t/text()', namespaces=NS)).strip()
            if (following is not None and following.tag == '{' + NS['w'] + '}tbl'
                    and label.startswith('表')):
                pp = paragraph.find('w:pPr', NS)
                if pp is None:
                    pp = ET.Element('{' + NS['w'] + '}pPr'); paragraph.insert(0, pp)
                prop(pp, 'keepNext', val='1')
                prop(pp, 'keepLines', val='1')
            # Preserve heading spacing and alignment while preventing an orphan heading.
            if label.startswith(('2 问题定义与方法', '2.1 三参数 Weibull 分布与 MDM 偏移量', '3.2 参数条件与逐样本选择空间')):
                pp = paragraph.find('w:pPr', NS)
                prop(pp, 'keepNext', val='1')
                prop(pp, 'keepLines', val='1')
        for row in selected:
            drawing = drawings[row["source_identity"]["image_index"] - 1]
            png = Path(row["png"])
            if not png.is_absolute():
                png = manifest.parent / png
            target = rels[drawing.xpath(".//a:blip/@r:embed", namespaces=NS)[0]]
            assert target.endswith(".png"), target
            parts[target] = png.read_bytes()
            with Image.open(png) as im:
                cx = round(row["width_mm"] * 36000)
                cy = round(cx * im.height / im.width)
            for extent in drawing.xpath("./wp:extent | .//a:xfrm/a:ext", namespaces=NS):
                extent.set("cx", str(cx)); extent.set("cy", str(cy))
            paragraph = drawing.xpath("ancestor::w:p[1]", namespaces=NS)[0]
            pp = paragraph.find("w:pPr", NS)
            if pp is None:
                pp = ET.Element("{" + NS["w"] + "}pPr"); paragraph.insert(0, pp)
            prop(pp, "jc", val="center")
            prop(pp, "ind", firstLine="0", firstLineChars="0")
            prop(pp, "keepNext", val="1")
            # Caption stays with its own wrapped lines; it need not keep the next paragraph.
            caption = paragraph.getnext()
            if caption is not None and caption.tag == "{" + NS["w"] + "}p":
                cp = caption.find("w:pPr", NS)
                if cp is None:
                    cp = ET.Element("{" + NS["w"] + "}pPr"); caption.insert(0, cp)
                prop(cp, "keepLines", val="1")
        assert content(root) == before, "Text, equations or fields changed"
        parts["word/document.xml"] = ET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        temporary = path.with_suffix(".assembling.docx")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as out:
            for part, data in parts.items():
                out.writestr(part, data)
        temporary.replace(path)
        print(name, len(selected), "figures updated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("docx_dir", type=Path)
    args = parser.parse_args()
    assemble(args.manifest, args.docx_dir)
