import re
from parser.number_utils import clean_number, extract_numbers
from parser.keywords import TOTAL_WORDS


def parse_total(text):

    lines = text.split("\n")

    # keyword search
    for i,line in enumerate(lines):

        low = line.lower()

        if any(w in low for w in TOTAL_WORDS):

            nums = extract_numbers(line)

            if nums:
                return clean_number(nums[-1])

            if i+1 < len(lines):

                nums = extract_numbers(lines[i+1])

                if nums:
                    return clean_number(nums[-1])

    # fallback biggest number
    nums = extract_numbers(text)

    if nums:

        vals = [clean_number(n) for n in nums if clean_number(n)]

        if vals:
            return max(vals)

    return None