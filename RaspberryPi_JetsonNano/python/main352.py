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
FONT_SIZES = (24, 20, 18, 16, 14, 12)
LINE_SPACING = 4
PADDING = 10
DISPLAY_COMMAND = 0x50
DISPLAY_DATA = 0x17

if LIB_DIR.exists():
    sys.path.append(str(LIB_DIR))

from affirmations import affirm
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd3in52 as epd_driver


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, filename=str(LOG_FILE))
    logging.info(PIC_DIR)


def initialize_display():
    epd = epd_driver.EPD()
    epd.init()
    epd.display_NUM(epd.WHITE)
    epd.lut_GC()
    epd.refresh()
    epd.send_command(DISPLAY_COMMAND)
    epd.send_data(DISPLAY_DATA)
    return epd


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if line and font.getlength(candidate) > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
    return lines


def create_affirmation_image(text: str, width: int, height: int) -> Image.Image:
    image = Image.new("1", (width, height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    max_width = width - 2 * PADDING
    max_height = height - 2 * PADDING

    # Use the largest font size at which the wrapped text fits on screen.
    for size in FONT_SIZES:
        font = ImageFont.truetype(str(PIC_DIR / "Font.ttc"), size)
        wrapped = "\n".join(wrap_text(text, font, max_width))
        left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=LINE_SPACING)
        if right - left <= max_width and bottom - top <= max_height:
            break

    offset_y = (height - (bottom - top)) // 2 - top
    draw.multiline_text((PADDING, offset_y), wrapped, font=font, fill=TEXT_COLOR, spacing=LINE_SPACING)
    return image


def main() -> None:
    epd = None

    try:
        now = datetime.datetime.now()
        logging.info("\n%s", now.strftime("%Y-%m-%d %H:%M:%S"))
        logging.info("Waking up...")

        epd = initialize_display()

        text = random.choice(affirm.get_affirmations())
        logging.info("Selected affirmation: %s", text)

        # Landscape: the panel is 240x360, so draw on a 360x240 image.
        image = create_affirmation_image(text, epd.height, epd.width)

        logging.info("CLS")
        epd.display(epd.getbuffer(image))
        epd.lut_GC()
        epd.refresh()

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
