KNOWN_VENDORS = [
"rewe","lidl","aldi","edeka","kaufland",
"carrefour","auchan","intermarche",
"mercadona","eroski",
"migros","bim","a101","şok",
"starbucks","mcdonald","burger king",
"shell","esso","bp","aral"
]

def detect_vendor(text):

    t = text.lower()

    for v in KNOWN_VENDORS:
        if v in t:
            return v.title()

    # fallback: first uppercase line
    for line in text.split("\n"):

        if line.isupper() and 3 < len(line) < 50:
            return line.strip()

    return None