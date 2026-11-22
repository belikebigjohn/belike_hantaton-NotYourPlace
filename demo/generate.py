"""Generate clearly synthetic image fixtures for the manual app walkthrough."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
OUT.mkdir(exist_ok=True)

def font(size):
    for path in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/seguisb.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def base():
    image = Image.new("RGB", (1280, 720), "#d7e2ed")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1280, 150), fill="#c4d7eb")
    draw.rectangle((0, 510, 1280, 720), fill="#667688")
    draw.rectangle((24, 22, 618, 96), fill="#152b4a")
    draw.text((42, 36), "ДЕМО / СИНТЕТИКА", fill="white", font=font(42))
    return image, draw

image, d = base()
d.rectangle((1060, 155, 1082, 535), fill="#5a6c80")
d.rectangle((945, 150, 1195, 385), fill="#174995", outline="white", width=10)
d.text((1003, 170), "P", fill="white", font=font(150))
d.ellipse((1000, 315, 1042, 357), outline="white", width=8)
d.line((1020, 335, 1065, 352, 1090, 321), fill="white", width=9)
d.line((1065, 352, 1090, 370), fill="white", width=9)
d.polygon([(230, 450), (308, 355), (710, 355), (840, 450)], fill="#294a6c")
d.rounded_rectangle((160, 420, 880, 560), radius=42, fill="#245280")
d.rectangle((315, 380, 680, 435), fill="#91b6cf")
for x in (300, 745):
    d.ellipse((x-55, 510, x+55, 620), fill="#182b3d")
    d.ellipse((x-25, 540, x+25, 590), fill="#aebac7")
d.rectangle((450, 478, 690, 535), fill="white")
d.text((465, 480), "А001АА 86", fill="#142335", font=font(37))
image.save(OUT / "overview-demo.png")

image, d = base()
d.rounded_rectangle((130, 270, 1150, 600), radius=35, fill="#245280")
d.rounded_rectangle((290, 340, 990, 535), radius=12, fill="white", outline="#122338", width=8)
d.text((352, 380), "А001АА 86", fill="#122338", font=font(96))
image.save(OUT / "plate-demo.png")
