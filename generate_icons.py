"""Run this once to generate PWA icons for the dashboard."""
from PIL import Image, ImageDraw, ImageFont
import os

os.makedirs('static/icons', exist_ok=True)

def make_icon(size):
    img = Image.new('RGB', (size, size), color='#0f1117')
    draw = ImageDraw.Draw(img)
    # Gradient-like background circle
    margin = size // 8
    draw.ellipse([margin, margin, size-margin, size-margin], fill='#1a1d27', outline='#00e5ff', width=max(2, size//48))
    # Hand emoji text
    font_size = size // 2
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    text = '🖐'
    bbox = draw.textbbox((0,0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text(((size-tw)//2, (size-th)//2 - size//12), text, font=font, fill='white')
    img.save(f'static/icons/icon-{size}.png')
    print(f'Created icon-{size}.png')

make_icon(192)
make_icon(512)
print('Icons created successfully!')
