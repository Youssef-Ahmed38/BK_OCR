import re
import numpy as np
from PIL import Image
from pytesseract import Output
import pytesseract
from .preprocessing import PREPROCESS_FUNS
import cv2  # Needed for to_pil conversion

def to_pil(cv_img):
    if len(cv_img.shape) == 2:
        return Image.fromarray(cv_img)
    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

def ocr_try_variants(img, max_retries=6, psms=("7", "6", "11"), whitelist_chars=None, lang=None):
    best_conf = -999.0
    best_text = ""
    best_meta = {}
    candidates = []

    for prep in PREPROCESS_FUNS:
        for psm in psms:
            candidates.append((prep, psm))
            if len(candidates) >= max_retries:
                break
        if len(candidates) >= max_retries:
            break

    for prep, psm in candidates:
        try:
            proc = prep(img)
            cfg = f"--oem 1 --psm {psm}"
            if whitelist_chars:
                cfg += f" -c tessedit_char_whitelist={whitelist_chars}"

            data = pytesseract.image_to_data(proc, lang=lang, output_type=Output.DICT, config=cfg) if lang \
                else pytesseract.image_to_data(proc, output_type=Output.DICT, config=cfg)

            texts = data.get("text", [])
            confs = data.get("conf", [])
            words = []
            word_confs = []

            for t, c in zip(texts, confs):
                if t and str(t).strip():
                    words.append(str(t).strip())
                    try:
                        cval = float(c)
                    except Exception:
                        cval = -1.0
                    word_confs.append(cval)

            valid = [c for c in word_confs if c >= 0]
            mean_conf = float(np.mean(valid)) if valid else -1.0
            joined = " ".join(words).strip()

            if mean_conf > best_conf or (abs(mean_conf - best_conf) < 1e-6 and len(joined) > len(best_text)):
                best_conf = mean_conf
                best_text = joined
                best_meta = {
                    "prep": prep.__name__,
                    "psm": psm,
                    "words": words,
                    "confs": word_confs
                }

        except Exception:
            continue

    return best_text, best_conf, best_meta

def sanitize_amount_text(s):
    if not s:
        return s
    t = s.strip()
    t = t.replace('S', '5').replace('s', '5').replace('O', '0').replace('o', '0').replace('B', '8')
    t = re.sub(r'[^0-9\.,\-\$\£\€\(\)]', '', t)
    return t

def parse_amount(txt):
    if txt is None:
        return ""
    s = str(txt).strip()
    s = s.replace('|', '').replace('$', '').replace('£', '').replace('€', '').replace(' ', '')
    s = re.sub(r'[^0-9\.,\-]', '', s)

    if s == "":
        return ""

    try:
        if '.' in s and ',' in s:
            last_dot = s.rfind('.')
            last_comma = s.rfind(',')
            tmp = s.replace('.', '').replace(',', '.') if last_comma > last_dot else s.replace(',', '')
            return "{:.2f}".format(float(tmp))

        if ',' in s and '.' not in s:
            parts = s.split(',')
            tmp = s.replace('.', '').replace(',', '.') if len(parts[-1]) in (1, 2) else s.replace(',', '')
            return "{:.2f}".format(float(tmp))

        if '.' in s and ',' not in s:
            if s.count('.') == 1 and len(s.split('.')[-1]) <= 2:
                return "{:.2f}".format(float(s))
            else:
                tmp = s.replace('.', '')
                return "{:.2f}".format(float(tmp))

        if s.replace('-', '').isdigit():
            return "{:.2f}".format(float(s))

    except Exception:
        return s

    return s