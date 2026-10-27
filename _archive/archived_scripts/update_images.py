import re

full_md_path = r'C:\Web\Weibull\public\421-001-图片\full.md'
translation_md_path = r'C:\Web\Weibull\src\content\421-001-pdf翻译.md'

with open(full_md_path, 'r', encoding='utf-8') as f:
    full_content = f.read()

# Pattern to match ![](filename.jpg)
pattern = r'!\[\]\(([a-f0-9]+\.(?:jpg|png))\)'
images_in_full = re.findall(pattern, full_content)

print(f'Found {len(images_in_full)} image references in full.md')

with open(translation_md_path, 'r', encoding='utf-8') as f:
    translation_content = f.read()

old_pattern = r'!\[\]\([a-f0-9_\-]+\.(?:jpg|png)\)'
old_matches = re.findall(old_pattern, translation_content)
print(f'Found {len(old_matches)} image references in translation markdown')

# Replace all image references with the correct path
# Pattern matches: ![](any_uuid.jpg) or ![](any_hash.png)
# Replaces with: ![](/421-001-图片/images/filename)
def replace_image_path(match):
    full_match = match.group(0)
    # Extract filename from the match
    filename_match = re.search(r'\(([^)]+\.(?:jpg|png))\)', full_match)
    if filename_match:
        filename = filename_match.group(1)
        return f'![](/421-001-图片/images/{filename})'
    return full_match

# First pattern for UUID-based names
pattern_uuid = r'!\[\]\([a-f0-9]+\.(?:jpg|png)\)'
# Second pattern for hash-based names (with underscores and hyphens)
pattern_hash = r'!\[\]\([a-f0-9_\-]+\.(?:jpg|png)\)'

updated_content = re.sub(pattern_uuid, replace_image_path, translation_content)
updated_content = re.sub(pattern_hash, replace_image_path, updated_content)

with open(translation_md_path, 'w', encoding='utf-8') as f:
    f.write(updated_content)

print('Image paths updated successfully in translation file')

original_md_path = r'C:\Web\Weibull\src\content\421-001-pdf原文.md'
with open(original_md_path, 'r', encoding='utf-8') as f:
    original_content = f.read()

updated_original = re.sub(pattern_uuid, replace_image_path, original_content)
updated_original = re.sub(pattern_hash, replace_image_path, updated_original)

with open(original_md_path, 'w', encoding='utf-8') as f:
    f.write(updated_original)

print('Image paths updated successfully in original file')
