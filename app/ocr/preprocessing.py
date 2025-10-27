import cv2
import numpy as np

def prep_identity(img):
    return img

def prep_resize(img, scale=2):
    h, w = img.shape[:2]
    s = scale
    if max(h, w) < 40:
        s = 3
    return cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)

def prep_clahe(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)

def prep_sharpen(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    return cv2.filter2D(gray, -1, kernel)

def prep_otsu(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th

def prep_adaptive(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21, 10
    )

def prep_blur_thresh(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th

def prep_invert(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return 255 - gray

PREPROCESS_FUNS = [
    prep_resize,
    prep_identity,
    prep_clahe,
    prep_sharpen,
    prep_otsu,
    prep_adaptive,
    prep_blur_thresh,
    prep_invert,
]