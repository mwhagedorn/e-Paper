##!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os

picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
import time
from PIL import Image, ImageDraw, ImageFont
import traceback
import textwrap
import pdb
import random
from functools import reduce
import re
import datetime

WIDTH  = 400
HEIGHT = 300
USE_EINK_DISPLAY = True
if USE_EINK_DISPLAY:
    from waveshare_epd import epd4in2 as epd_driver

# Log to output file to see what's going on
logging.basicConfig(level=logging.INFO,
                    filename='/home/mhagedorn/e-Paper/RaspberryPi_JetsonNano/python/examples/quotes.log')


# Splits a long text to smaller lines which can fit in a line with max_width.
# Uses a Font object for more accurate calculations
def text_wrap(text, font=None, max_width=None):
    lines = []
    if font.getsize(text)[0] < max_width:
        lines.append(text)
    else:
        words = text.split(' ')
        i = 0
        while i < len(words):
            line = ''
            while i < len(words) and font.getsize(line + words[i])[0] <= max_width:
                line = line + words[i] + " "
                i += 1
            if not line:
                line = words[i]
                i += 1
            lines.append(line)
    return lines


def slice_index(x):
    i = 0
    for c in x:
        if c.isalpha():
            i = i + 1
            return i
        i = i + 1


def upperfirst(x):
    i = slice_index(x)
    return x[:i].upper() + x[i:]



# Calculates font-size, line-wrapping, vertical centering, # of lines, strips not-needed parts AND does your dishes
def make_it_pretty(quotes, spacing, screen_height, screen_width, padding):
    logging.info("Formatting...")
    font_sizes = [48, 35, 24, 18]
    attempt = 0
    while True:
        attempt += 1
        text = random.choice(quotes)
        logging.info(f"Quote try {attempt}")
        for size in font_sizes:
            font = ImageFont.truetype(os.path.join(picdir, 'FontsFree-Net-Bookerly.ttf'), size)
            line_height = font.getsize('hg')[1] + spacing
            max_lines = (screen_height // line_height)
            split_quote = text.split("\n")
            result = [text_wrap(part, font=font, max_width=screen_width - (padding * 2)) for part in split_quote]
            blocks = reduce(lambda x, y: x + y, result)
            trimmed_blocks = [x.strip() for x in blocks]
            r = re.compile("[\w\"]+")
            filtered_list = list(filter(r.match, trimmed_blocks))
            line_length = len(filtered_list)
            quote_height = line_height * line_length
            offset_y = (screen_height / 2) - (quote_height / 2)
            if (line_length <= max_lines) and (quote_height + offset_y < screen_height):
                quote = upperfirst("\n".join(filtered_list))
                logging.info(
                    f"{quote},\n Font size: {size}, Line count: {line_length}, Quote height: {quote_height}, Offset: {offset_y}, Screen height: {screen_height}")
                return {
                    "quote": quote,
                    "offset": offset_y,
                    "font": font
                }


# Resize PIL image keeping ratio and using white background.
def resize(image, width, height):
    ratio_w = width / image.width
    ratio_h = height / image.height
    if ratio_w < ratio_h:
        # It must be fixed by width
        resize_width = width
        resize_height = round(ratio_w * image.height)
    else:
        # Fixed by height
        resize_width = round(ratio_h * image.width)
        resize_height = height
    image_resize = image.resize((resize_width, resize_height), Image.ANTIALIAS)
    background = Image.new('RGBA', (width, height), (255, 255, 255, 255))
    offset = (round((width - resize_width) / 2), round((height - resize_height) / 2))
    background.paste(image_resize, offset)
    return background.convert('RGB')


def get_affirmations():
    logging.info("Fetching affirmations..")
    affirmations = [
        "I am committed to doing my affirmations every day so that I can become the person I need to be to create "
        "everything I want for my life.",
        "I don't judge or condemn others, because I simply have no way of knowing that if I had lived their life, "
        "I might be, say and do exactly the same",
        "I don't worry about trying to impress people.  Instead, I focus on how I can add value to their lives.",
        "There is no better day than today to do the things I've been putting off.",
        "To reach levels of success I've never reached before, I must be committed at a level I've never been "
        "committed at before.",
        "To avoid the activities I know I should be doing is to avoid the life I want to be living.  I will stop "
        "avoiding and start living.",
        "It's often said that everything happens for a reason, however it is my responsibility to choose the most "
        "empowering reasons for each of the experiences in my life.",
        "Happiness is a choice.  I choose to be happy.",
        "Today I am willing to give up who I've been for who I can become.",
        "I am committed to taking myself to the next level so that I can take my success to the next level, "
        "because it only happens in that order",
        "I was born with an innate inner freedom, which is my inherent ability to decide how I experience each moment "
        "in my life",
        "I am happy, I am grateful for my life. I am whatever I choose to be",
        "I am disciplined. I am consistent.  I am whatever I choose to be.",
        "Where I am in my life is a result of who I was in the past, but where I go depends entirely on who I choose "
        "to be, from this moment on.",
        "If I want to upgrade my circle of influence, it begins with upgrading myself.",
        "I am destined to be whatever I choose to be.",
        "I make bold moves toward my dreams each day, refuse to give up, and know that nothing can stop me."
        "What I am capable of is determined by my potential, not my past."
        "Say it over and over until I believe it.  Then I will become it",
        "Every day I can be stressed out or blissed out.  The choice is mine",
        "There is nothing to fear because I cannot fail.  I can only learn, grow and become better than I've ever "
        "been before",
        "Yes I can.  Yes I will.  Yes I am able.",
        "Today I choose faith over fear.",
        "The way  to become fearless is to consistently remind myself and affirm that I can handle absolutely "
        "anything that life throws my way.",
        "I choose to make each day the best day of my life, which is determined not by what happens to me, but by how "
        "I show up no matter what happens. ",
        "I refuse to let the pain of my past limit the potential of my future.",
        "I have faith in the miracles of life, because only those who do get to experience them.",
        "I can't change the past, but I can change the future by changing what I do in the present.",
        "When I focus on things that are out of my control, I feel out of control.\n So, I choose to focus only on "
        "the one thing I have control over: being the best version of myself. ",
        "Gratitude and complaining cannot coexist simultaneously, so I choose the one that best serves me.",
        "I have the ability to be at peace, even when life is difficult or painful.",
        "Anything another person has overcome or accomplished is evidence of what's possible for me.",
        "I am committed to maintaining unwavering faith that I will reach my goal and putting forth extraordinary"
        "effort until I do, no matter what.\nThere is no other option.",
        "I will accomplish everything that needs to get done.",
        "I am going to make you so proud.",
        "Every day I am better than before.",
        "No matter how I started I am going to finish the week strong.",
        "I embrace critical feedback as a learning opportunity.",
        "I embrace the learning opportunities in every challenge",
        "I am a confident champion, fully equipped to handle the challenges place before me.\nI will succeed.",
        "Win or learn.",
        "You are loved for who you are, just for existing",
        "You must do the things you think you cannot do",
        "You are confident in your ability",
        "You have the skills you need to win",
        "You are mentally strong",
        "I am prepared to win",
        "I am focused on success",
        "I am successful",
        "I am unstoppable",
        "There's always a way when I am committed",
    ]
    return affirmations


def main():
    try:
        now = datetime.datetime.now()
        logging.info(f"\n{now.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"Waking up...")

        # conditionalize this
        #4in2 is 400w x 300h


        logging.info(picdir)
        result = get_affirmations()

        line_spacing = 1
        padding = 30

        view = Image.new('1', (WIDTH, HEIGHT), 255)  # 255: clear the frame
        draw = ImageDraw.Draw(view)

        logging.info(f"CLS")
        formatted_result = make_it_pretty(result, line_spacing, HEIGHT, WIDTH, padding)

        quote = formatted_result["quote"]
        offset_y = formatted_result["offset"]
        font = formatted_result["font"]

        logging.info("Updating...")
        now = datetime.datetime.now()



        draw.text((padding, offset_y), quote, fill=0, align="left", spacing=line_spacing, font=font)
        if USE_EINK_DISPLAY:
            epd = epd_driver.EPD()
            epd.init()
            epd.display(epd.getbuffer(view))
            epd.sleep()
        else:
            view.save("INK_EXPORT.bmp")
            final_image = Image.open("INK_EXPORT.bmp")
            final_image = Image.open("INK_EXPORT.bmp")

        logging.info("Standby...")


    except IOError as e:
        logging.info(e)
        time.sleep(5)


    except KeyboardInterrupt:
        logging.info("ctrl + c:")
        if USE_EINK_DISPLAY:
            epd.epdconfig.module_exit()
        exit()


if __name__ == "__main__":
    main()
