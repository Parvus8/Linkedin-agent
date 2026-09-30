"""Renders post illustrations as 1200x1200 PNGs: code snippets and summary cards."""
from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.styles import get_style_by_name

SIZE = 1200
PAD = 80
BG = (22, 27, 34)
CODE_BG = (13, 17, 23)
FG = (230, 237, 243)
ACCENT = (88, 166, 255)

FONT_CANDIDATES = {
    "regular": ["C:/Windows/Fonts/segoeui.ttf", "DejaVuSans.ttf"],
    "bold": ["C:/Windows/Fonts/segoeuib.ttf", "DejaVuSans-Bold.ttf"],
    "mono": ["C:/Windows/Fonts/consola.ttf", "DejaVuSansMono.ttf"],
}


def font(kind, size):
    for path in FONT_CANDIDATES[kind]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def wrap(draw, text, fnt, width):
    lines = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split():
            test = f"{line} {word}".strip()
            if draw.textlength(test, font=fnt) <= width:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        lines.append(line)
    return lines


def new_canvas():
    img = Image.new("RGB", (SIZE, SIZE), BG)
    return img, ImageDraw.Draw(img)


def draw_title(draw, title, y):
    fnt = font("bold", 64)
    for line in wrap(draw, title, fnt, SIZE - 2 * PAD)[:3]:
        draw.text((PAD, y), line, font=fnt, fill=FG)
        y += 80
    draw.rectangle([PAD, y + 10, PAD + 120, y + 18], fill=ACCENT)
    return y + 60


def render_card(spec, out):
    img, draw = new_canvas()
    y = draw_title(draw, spec.get("title", ""), PAD + 40)
    fnt = font("regular", 42)
    for point in spec.get("points", [])[:5]:
        draw.ellipse([PAD, y + 20, PAD + 16, y + 36], fill=ACCENT)
        for line in wrap(draw, point, fnt, SIZE - 2 * PAD - 50):
            if y > SIZE - PAD - 56:
                break
            draw.text((PAD + 50, y), line, font=fnt, fill=FG)
            y += 56
        y += 30
    img.save(out)


def render_code(spec, out):
    img, draw = new_canvas()
    y = draw_title(draw, spec.get("title", ""), PAD + 40)
    lines = str(spec.get("code", "")).expandtabs(4).rstrip().split("\n")

    # Shrink the font until the longest line fits inside the code window.
    box_w = SIZE - 2 * PAD
    inner_w = box_w - 80
    longest = max((len(l) for l in lines), default=1)
    size = 34
    fnt = font("mono", size)
    while size > 16 and draw.textlength("M" * longest, font=fnt) > inner_w:
        size -= 2
        fnt = font("mono", size)
    line_h = int(size * 1.5)
    max_lines = max(1, (SIZE - y - PAD - 110) // line_h)
    lines = lines[:max_lines]

    box_h = 70 + line_h * len(lines) + 30
    draw.rounded_rectangle([PAD, y, PAD + box_w, y + box_h], radius=20, fill=CODE_BG)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        draw.ellipse([PAD + 30 + i * 34, y + 22, PAD + 50 + i * 34, y + 42], fill=color)

    try:
        lexer = get_lexer_by_name(spec.get("language", "text"))
    except Exception:
        lexer = TextLexer()
    style = get_style_by_name("monokai")

    x0 = PAD + 40
    x, cy = x0, y + 70
    for ttype, value in lex("\n".join(lines), lexer):
        color = style.style_for_token(ttype)["color"]
        fill = f"#{color}" if color else "#f8f8f2"
        for j, part in enumerate(value.split("\n")):
            if j > 0:
                x, cy = x0, cy + line_h
            if part:
                draw.text((x, cy), part, font=fnt, fill=fill)
                x += draw.textlength(part, font=fnt)
    img.save(out)


def render(spec, out):
    """Renders the image described by spec into out. Returns True if an image was written."""
    kind = (spec or {}).get("type")
    if kind == "code" and spec.get("code"):
        render_code(spec, out)
        return True
    if kind == "card" and spec.get("points"):
        render_card(spec, out)
        return True
    return False
