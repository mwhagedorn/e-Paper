# ... existing code ...

BACKGROUND_COLOR = "white"
TEXT_COLOR = 0
FONT_SIZE = 24
TEXT_POSITION = (30, 120)
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


def create_break_image(text: str) -> Image.Image:
    font = ImageFont.truetype(str(PIC_DIR / "FontsFree-Net-Bookerly.ttf"), FONT_SIZE)

    image = Image.new(mode="RGBA", size=(WIDTH, HEIGHT), color=BACKGROUND_COLOR)
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
