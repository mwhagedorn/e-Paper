import datetime
import logging
import os
import random
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PIC_DIR = BASE_DIR / "pic"
LIB_DIR = BASE_DIR / "lib"
LOG_FILE = Path("/home/mhagedorn/e-Paper/RaspberryPi_JetsonNano/python/quotes.log")

BACKGROUND_COLOR = 255
TEXT_COLOR = 0
FONT_SIZE = 18
TEXT_POSITION = (10, 0)
DISPLAY_COMMAND = 0x50
DISPLAY_DATA = 0x17

if LIB_DIR.exists():
    sys.path.append(str(LIB_DIR))

from breaks.five_min_break import get_breaks
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


def create_break_image(epd, text: str) -> Image.Image:
    font = ImageFont.truetype(str(PIC_DIR / "Font.ttc"), FONT_SIZE)

    image = Image.new("1", (epd.height, epd.width), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    draw.text(TEXT_POSITION, text, font=font, fill=TEXT_COLOR)

    return image


def main() -> None:
    epd = None

    try:
        now = datetime.datetime.now()
        logging.info("\n%s", now.strftime("%Y-%m-%d %H:%M:%S"))
        logging.info("Waking up...")

        epd = initialize_display()

        text = random.choice(get_breaks())
        image = create_break_image(epd, text)

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