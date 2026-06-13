from pathlib import Path
import re
import shutil
import sys
import zipfile


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/extract-docx-images.py <input.docx> <output.md>")
        return 2

    docx = Path(sys.argv[1])
    md_path = Path(sys.argv[2])
    assets = md_path.with_suffix(".assets")
    assets.mkdir(exist_ok=True)

    md_text = md_path.read_text(encoding="utf-8")
    image_alts = re.findall(r"!\[([^\]]+)\]\(data:image/png;base64\.\.\.\)", md_text)
    if not image_alts:
        print("No placeholder image links found.")
        return 1

    with zipfile.ZipFile(docx) as zf:
        media = [
            name
            for name in zf.namelist()
            if name.startswith("word/media/") and name.lower().endswith(".png")
        ]

        if len(media) != len(image_alts):
            print(f"Image count mismatch: docx has {len(media)}, markdown has {len(image_alts)}")
            return 1

        replacements = []
        for idx, (entry, alt) in enumerate(zip(media, image_alts), start=1):
            match = re.search(r"图\s*(\d+)", alt)
            figure_no = match.group(1) if match else str(idx)
            filename = f"fig{figure_no}.png"
            out_path = assets / filename

            with zf.open(entry) as src, out_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)

            replacements.append((alt, filename))

    new_text = md_text
    for alt, filename in replacements:
        old = f"![{alt}](data:image/png;base64...)"
        new = f"![{alt}]({assets.name}/{filename})"
        new_text = new_text.replace(old, new, 1)

    md_path.write_text(new_text, encoding="utf-8", newline="\r\n")

    print(f"Extracted {len(replacements)} images to {assets}")
    for alt, filename in replacements:
        print(f"{filename}: {alt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
