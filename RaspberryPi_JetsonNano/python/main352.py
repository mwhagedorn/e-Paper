import sys
import os


picdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'pic')
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
from waveshare_epd import epd3in52 as epd_driver
import time
from PIL import Image, ImageDraw, ImageFont
import random
import datetime
from affirmations import affirm

# Log to output file to see what's going on
logging.basicConfig(level=logging.INFO,
                    filename='/home/mwhagedorn/e-Paper/RaspberryPi_JetsonNano/python/quotes.log')
logging.info(picdir)


def main():
    try:
        now = datetime.datetime.now()
        logging.info(f"\n{now.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"Waking up...")
        epd = epd_driver.EPD()
        epd.init()
        epd.display_NUM(epd.WHITE)
        epd.lut_GC()
        epd.refresh()

        epd.send_command(0x50)
        epd.send_data(0x17)

        logging.info(picdir)

        text = random.choice(affirm.get_affirmations())

        font18 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 18)


        view = Image.new('1', (epd.width, epd.height), 255)  # 255: clear the frame
        draw = ImageDraw.Draw(view)
        logging.info(f"CLS")
        Himage = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame
        draw = ImageDraw.Draw(Himage)
        draw.text((10, 0),text, font=font18, fill=0)
        epd.display(epd.getbuffer(view))

        logging.info("Standby...")
        epd.sleep()

    except IOError as e:
        logging.info(e)
        time.sleep(5)


    except KeyboardInterrupt:
        logging.info("ctrl + c:")
        epd.epdconfig.module_exit()
        exit()


if __name__ == "__main__":
    main()