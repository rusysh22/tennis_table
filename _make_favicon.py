from PIL import Image

src = Image.open(r"c:\Users\MShubkhi\Downloads\dani_coding\tennis_table\static\img\logo-interport.png").convert("RGBA")
w, h = src.size
print("source size:", w, h)

# The wave/ribbon icon sits in the upper-right area of the wordmark logo.
# Crop a square-ish region around it (with a little padding), then pad to a
# perfect square canvas so it reads cleanly as a favicon at small sizes.
left = int(w * 0.42)
right = w
top = 0
bottom = int(h * 0.52)
icon = src.crop((left, top, right, bottom))
print("icon crop size:", icon.size)

iw, ih = icon.size
side = max(iw, ih)
pad = int(side * 0.10)
canvas_size = side + pad * 2
canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
canvas.paste(icon, ((canvas_size - iw) // 2, (canvas_size - ih) // 2), icon)

out_dir = r"c:\Users\MShubkhi\Downloads\dani_coding\tennis_table\static\img"
canvas.save(f"{out_dir}\\favicon-source.png")

for size in (16, 32, 48, 180):
    resized = canvas.resize((size, size), Image.LANCZOS)
    resized.save(f"{out_dir}\\favicon-{size}.png")

print("done")
