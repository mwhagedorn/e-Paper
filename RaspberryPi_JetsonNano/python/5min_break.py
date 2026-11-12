import datetime
import logging
import random
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PIC_DIR = BASE_DIR / "pic"
LIB_DIR = BASE_DIR / "lib"
LOG_FILE = BASE_DIR / "quotes.log"

BACKGROUND_COLOR = 255
TEXT_COLOR = 0
FONT_SIZE = 24
LINE_SPACING = 4
PADDING = 30
WIDTH = 400
HEIGHT = 300

if LIB_DIR.exists():
    sys.path.append(str(LIB_DIR))

from breaks.five_min_break import get_breaks
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd4in2 as epd_driver


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, filename=str(LOG_FILE))
    logging.info(PIC_DIR)


def initialize_display():
    epd = epd_driver.EPD()
    epd.init()
    return epd


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and font.getlength(candidate) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def create_break_image(text: str) -> Image.Image:
    font = ImageFont.truetype(str(PIC_DIR / "FontsFree-Net-Bookerly.ttf"), FONT_SIZE)

    image = Image.new(mode="1", size=(WIDTH, HEIGHT), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)

    wrapped = "\n".join(wrap_text(text, font, WIDTH - 2 * PADDING))
    _, top, _, bottom = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=LINE_SPACING)
    offset_y = (HEIGHT - (bottom - top)) // 2 - top
    draw.multiline_text((PADDING, offset_y), wrapped, font=font, fill=TEXT_COLOR, spacing=LINE_SPACING)

    return image


def main() -> None:
    epd = None

    try:
        now = datetime.datetime.now()
        logging.info("\n%s", now.strftime("%Y-%m-%d %H:%M:%S"))
        logging.info("Waking up...")

        epd = initialize_display()

        text = random.choice(get_breaks())
        logging.info("Selected break: %s", text)

        image = create_break_image(text)

        logging.info("CLS")
        epd.display(epd.getbuffer(image))

        logging.info("Standby...")
        epd.sleep()

    except IOError as error:
        logging.info(error)
        time.sleep(5)

    except KeyboardInterrupt:
        logging.info("ctrl + c:")
        if epd is not None:
            epd.epdconfig.module_exit()
        sys.exit()


if __name__ == "__main__":
    configure_logging()
    main()
