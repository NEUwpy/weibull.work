"""Compose local QA previews from the exported images, without changing them."""
from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ModuleNotFoundError:
    sys.path.append(str(Path.home()/'AppData/Local/hermes/hermes-agent/venv/Lib/site-packages'))
    from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'程序/检查预览'
OUT.mkdir(exist_ok=True)
FONT=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',24)


def stack(items, destination, width=1920):
    blocks=[]
    for label,path in items:
        im=Image.open(path).convert('RGB')
        chunks=[im] if im.width<=width else [im.crop((x,0,min(x+width,im.width),im.height)) for x in range(0,im.width,width)]
        for i,chunk in enumerate(chunks):
            block=Image.new('RGB',(width,chunk.height+44),'white')
            ImageDraw.Draw(block).text((12,6),label+(f' [{i+1}]' if len(chunks)>1 else ''),fill='black',font=FONT)
            block.paste(chunk,(0,44)); blocks.append(block)
    canvas=Image.new('RGB',(width,sum(b.height for b in blocks)),'white')
    y=0
    for block in blocks:
        canvas.paste(block,(0,y)); y+=block.height
    canvas.save(destination)


def grid(items, destination, columns, tile_width):
    tiles=[]
    for label,path in items:
        im=Image.open(path).convert('RGB')
        im=im.resize((tile_width,round(im.height*tile_width/im.width)),Image.Resampling.LANCZOS)
        tile=Image.new('RGB',(tile_width,im.height+44),'white')
        ImageDraw.Draw(tile).text((8,6),label,fill='black',font=FONT)
        tile.paste(im,(0,44)); tiles.append(tile)
    height=max(t.height for t in tiles)
    canvas=Image.new('RGB',(columns*tile_width,((len(tiles)+columns-1)//columns)*height),'white')
    for i,tile in enumerate(tiles): canvas.paste(tile,((i%columns)*tile_width,(i//columns)*height))
    canvas.save(destination)


for case in sorted(ROOT.glob('W(*)')):
    previews=case/'结果/中间数据/表格预览'
    for prefix in ('估计结果','生成样本'):
        stack([(f'{case.name} {prefix} n={n}',previews/f'{prefix}_n{n}.png') for n in (7,15,30)],OUT/f'{case.name}_{prefix}.png')
for eta in (100,1000):
    items=[]
    for beta in ('1.5','2','3','5'):
        case=ROOT/f'W({beta},{eta},500)'
        items.extend([(f'{case.name} n={n}',case/f'结果/样本量{n}_偏移量0.20.png') for n in (7,15,30)])
    grid(items,OUT/f'MDM_{eta}.png',3,800)
for beta in ('1.5','2','3','5'):
    grid([(f'W({beta},{eta},500)',ROOT/f'W({beta},{eta},500)/结果/估计分布_小提琴图.png') for eta in (100,1000)],OUT/f'小提琴_{beta}.png',2,1300)
print('QA previews composed for all 48 sheets and 32 figures.')
