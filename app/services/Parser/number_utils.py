import re

def clean_number(val):

    val = val.replace("O","0").replace("l","1")

    if "," in val and "." in val:
        val = val.replace(".","").replace(",",".")
    else:
        val = val.replace(",",".")
    
    try:
        return float(val)
    except:
        return None


def extract_numbers(text):

    return re.findall(r"\d+[.,]\d{2}", text)