"""Place two existing scientific plots side by side, preserving every source pixel."""
from pathlib import Path
from PIL import Image, ImageChops

base=Path('D:/weibull/docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825')
paths=[base/'260826-W2,1000,500/样本量7_偏移量0.10.png',
       base/'260906-W5参数估计案例/W(5,1000,500)/样本量7_偏移量0.10.png']
images=[Image.open(p).convert('RGB') for p in paths]
assert images[0].size==images[1].size, [im.size for im in images]
w,h=images[0].size
gap=80
joined=Image.new('RGB',(2*w+gap,h),'white')
joined.paste(images[0],(0,0))
joined.paste(images[1],(w+gap,0))
out=base/'260929-MDM形状2与5梯度对比/样本量7_偏移量0.10_左形状2_右形状5_原图并列.png'
joined.save(out,dpi=(600,600))
saved=Image.open(out).convert('RGB')
assert ImageChops.difference(saved.crop((0,0,w,h)),images[0]).getbbox() is None
assert ImageChops.difference(saved.crop((w+gap,0,2*w+gap,h)),images[1]).getbbox() is None
print('Source dimensions:',w,h)
print('Both source plots preserved pixel-for-pixel.')
print(str(out))
