def iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH

    if interArea == 0:
        return 0.0

    boxAArea = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    boxBArea = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])
    union = boxAArea + boxBArea - interArea

    if union <= 0:
        return 0.0

    return interArea / union

def rect_intersection(a, b):
    xA = max(a[0], b[0])
    yA = max(a[1], b[1])
    xB = min(a[2], b[2])
    yB = min(a[3], b[3])

    iw = max(0, xB - xA)
    ih = max(0, yB - yA)
    return iw * ih

def union_box(boxA, boxB):
    def to_tuple(b):
        if isinstance(b, dict):
            return int(b["x1"]), int(b["y1"]), int(b["x2"]), int(b["y2"])
        else:
            return tuple(map(int, b))

    a = to_tuple(boxA)
    b = to_tuple(boxB)

    x1 = min(a[0], b[0])
    y1 = min(a[1], b[1])
    x2 = max(a[2], b[2])
    y2 = max(a[3], b[3])

    return x1, y1, x2, y2

def is_box_contained_or_overlaps(container, box, pad=4, min_iou=0.18, min_overlap_frac=0.55):
    c = (
        container["x1"] - pad,
        container["y1"] - pad,
        container["x2"] + pad,
        container["y2"] + pad
    )
    b = (box["x1"], box["y1"], box["x2"], box["y2"])

    # Full containment
    if b[0] >= c[0] and b[1] >= c[1] and b[2] <= c[2] and b[3] <= c[3]:
        return True

    # Center point containment
    cx = (b[0] + b[2]) // 2
    cy = (b[1] + b[3]) // 2
    if c[0] <= cx <= c[2] and c[1] <= cy <= c[3]:
        return True

    # Overlap fraction
    inter = rect_intersection(c, b)
    box_area_val = max(1, (b[2] - b[0]) * (b[3] - b[1]))
    overlap_frac = float(inter) / float(box_area_val)
    if overlap_frac >= min_overlap_frac:
        return True

    # IOU threshold
    if iou(c, b) >= min_iou:
        return True

    return False

def center_of(item):
    return (item["ymin"] + item["ymax"]) // 2