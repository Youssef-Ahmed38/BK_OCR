import os
import json
import shutil
import time
import logging
import re  # Added missing import for 're'
from datetime import datetime
import cv2
import numpy as np
import pandas as pd
from .config import (
    CROP_PAD, OCR_MAX_RETRIES, OCR_PSMS_DATE, OCR_PSMS_AMOUNT,
    OCR_PSMS_GENERAL, AMOUNT_WHITELIST, EXCLUDED_CLASSES,
    SAME_LABEL_MERGE_IOU, CONTAIN_PAD, CONTAIN_MIN_IOU,
    CONTAIN_MIN_OVERLAP, MIN_OVERLAP_FRAC_ROW, MIN_OVERLAP_FRAC_BOX,
    FALLBACK_MIN_CONF, HORIZ_FALLBACK_TOL, DATE_ASSIGN_TOLERANCE
)
from .ocr.ocr_core import ocr_try_variants, sanitize_amount_text, parse_amount
from .ocr.geometry import iou, rect_intersection, union_box, is_box_contained_or_overlaps

logger = logging.getLogger(__name__)


def process_image_file(image_path, working_dir, model, d_model, basename, ts):
    logger.info("Processing image: %s basename=%s ts=%s", image_path, basename, ts)

    CROP_OUTPUT_DIR = os.path.join(working_dir, f"cropped_texts_{basename}_{ts}")
    os.makedirs(CROP_OUTPUT_DIR, exist_ok=True)
    JSON_OUTPUT = os.path.join(working_dir, f"{basename}_{ts}.json")
    EXCEL_OUTPUT = os.path.join(working_dir, f"{basename}_{ts}.xlsx")

    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {image_path}")

    results = model(image)[0]
    global_text_boxes = []

    for b in results.boxes:
        cls_id = int(b.cls)
        name = model.names.get(cls_id, str(cls_id)).lower()

        if name == "text":
            xy = b.xyxy[0]
            try:
                xy = xy.cpu().numpy()
            except Exception:
                xy = np.array(xy)
            gx1, gy1, gx2, gy2 = map(int, xy[:4])
            conf = float(getattr(b, 'conf', 1.0))
            global_text_boxes.append({"x1": gx1, "y1": gy1, "x2": gx2, "y2": gy2, "conf": conf})

    logger.debug("Global text boxes detected: %d", len(global_text_boxes))

    vis_image = image.copy()
    raw_data = []
    contained_set = set()

    for idx_box, box in enumerate(results.boxes):
        cls_id = int(box.cls)
        class_name = model.names.get(cls_id, str(cls_id))
        class_name_lc = class_name.lower()

        if class_name in EXCLUDED_CLASSES or class_name_lc == "text":
            continue

        txy = box.xyxy[0]
        try:
            txy = txy.cpu().numpy()
        except Exception:
            txy = np.array(txy)

        x1, y1, x2, y2 = map(int, txy[:4])
        container = {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        contained = []

        for tb in global_text_boxes:
            if is_box_contained_or_overlaps(container, tb):
                contained.append(tb.copy())

        # [logic preserved] - match nearby text boxes for date items
        if class_name_lc == "date" and not contained:
            best_tb = None
            best_score = None
            cy_container = (container["y1"] + container["y2"]) // 2

            for tb in global_text_boxes:
                tb_h = max(1, tb["y2"] - tb["y1"])
                inter = rect_intersection(
                    (container["x1"], container["y1"], container["x2"], container["y2"]),
                    (tb["x1"], tb["y1"], tb["x2"], tb["y2"])
                )
                overlap_frac = inter / float(max(1, tb_h * max(1, tb["x2"] - tb["x1"])))
                center_dist = abs(((tb["y1"] + tb["y2"]) // 2) - cy_container)

                score = (1.0 - overlap_frac) * 2.0 + center_dist / 1000.0
                if best_tb is None or score < best_score:
                    best_tb = tb
                    best_score = score

            if best_tb is not None:
                tb_h_best = max(1, best_tb["y2"] - best_tb["y1"])
                inter = rect_intersection(
                    (container["x1"], container["y1"], container["x2"], container["y2"]),
                    (best_tb["x1"], best_tb["y1"], best_tb["x2"], best_tb["y2"])
                )
                overlap_frac = inter / float(max(1, (best_tb["x2"] - best_tb["x1"]) * (best_tb["y2"] - best_tb["y1"])))
                center_dist = abs(((best_tb["y1"] + best_tb["y2"]) // 2) - cy_container)

                if overlap_frac >= 0.08 or center_dist <= max(20, tb_h_best // 2):
                    contained.append(best_tb.copy())

        if not contained:
            continue

        for tb in contained:
            key = (tb["x1"], tb["y1"], tb["x2"], tb["y2"])
            contained_set.add(key)

        class_dir = os.path.join(CROP_OUTPUT_DIR, class_name)
        os.makedirs(class_dir, exist_ok=True)

        for idx_tb, tb in enumerate(sorted(contained, key=lambda b: (b["y1"], b["x1"]))):
            tx1 = max(0, int(tb["x1"]) - CROP_PAD)
            ty1 = max(0, int(tb["y1"]) - CROP_PAD)
            tx2 = min(image.shape[1], int(tb["x2"]) + CROP_PAD)
            ty2 = min(image.shape[0], int(tb["y2"]) + CROP_PAD)

            if tx2 <= tx1 or ty2 <= ty1:
                continue

            text_crop = image[ty1:ty2, tx1:tx2]
            crop_fn = os.path.join(class_dir, f"text_{idx_tb + 1:02d}_y{ty1}_y{ty2}.jpg")
            cv2.imwrite(crop_fn, text_crop)

            raw_entry = {
                "class": class_name_lc,
                "value": "",
                "arabic_description": "",
                "ymin": ty1,
                "ymax": ty2,
                "xcenter": (tx1 + tx2) // 2,
                "crop_fn": crop_fn,
                "ocr_conf": -999.0,
                "value_num": None,
                "d_model_detections": []
            }

            if class_name_lc == "date":
                whitelist = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-/"
                best_text, best_conf, best_meta = ocr_try_variants(
                    text_crop,
                    max_retries=OCR_MAX_RETRIES,
                    psms=OCR_PSMS_DATE,
                    whitelist_chars=whitelist
                )
                final_text = best_text.strip()
                if not any(c.isdigit() for c in final_text):
                    final_text = ""
                raw_entry["value"] = final_text
                # parse later in post-processing
                raw_entry["value_parsed"] = final_text
                raw_entry["ocr_conf"] = float(best_conf) if best_conf is not None else -999.0

            elif class_name_lc in ("debit", "credit", "balance"):
                best_text, best_conf, best_meta = ocr_try_variants(
                    text_crop,
                    max_retries=max(OCR_MAX_RETRIES, 8),
                    psms=OCR_PSMS_AMOUNT,
                    whitelist_chars=AMOUNT_WHITELIST
                )
                raw_entry["value"] = best_text.strip()
                raw_entry["ocr_conf"] = float(best_conf) if best_conf is not None else -999.0
                try:
                    cleaned = re.sub(r'[^\d\.-]', '', raw_entry["value"])
                    raw_entry["value_num"] = float(cleaned) if cleaned not in ("", ".", "-") else None
                except Exception:
                    raw_entry["value_num"] = None

            elif class_name_lc == "description":
                d_dets = []
                try:
                    d_results = d_model(text_crop)[0]
                    for db in d_results.boxes:
                        d_cls = int(db.cls)
                        d_name = str(d_model.names.get(d_cls, str(d_cls))).lower()
                        d_xy = db.xyxy[0]

                        try:
                            d_xy = d_xy.cpu().numpy()
                        except Exception:
                            d_xy = np.array(d_xy)

                        dx1, dy1, dx2, dy2 = map(int, d_xy[:4])
                        conf = float(getattr(db, 'conf', 1.0))
                        gx1, gy1, gx2, gy2 = tx1 + dx1, ty1 + dy1, tx1 + dx2, ty1 + dy2

                        d_dets.append({
                            "label": d_name,
                            "conf": conf,
                            "box_crop": (dx1, dy1, dx2, dy2),
                            "box_global": (gx1, gy1, gx2, gy2)
                        })
                except Exception:
                    d_dets = []

                # merge same label detections
                merged = []
                used_idx = [False] * len(d_dets)

                for i, a in enumerate(d_dets):
                    if used_idx[i]:
                        continue
                    boxA = a["box_global"]
                    lab = a["label"]
                    confA = a["conf"]
                    mb = boxA
                    mc = confA
                    used_idx[i] = True

                    for j in range(i + 1, len(d_dets)):
                        if used_idx[j]:
                            continue
                        b = d_dets[j]
                        if b["label"] != lab:
                            continue
                        if iou(mb, b["box_global"]) >= SAME_LABEL_MERGE_IOU:
                            mb = union_box(mb, b["box_global"])
                            mc = max(mc, b["conf"])
                            used_idx[j] = True

                    merged.append({"label": lab, "conf": mc, "box_global": mb})

                ocr_results_per_det = []

                for det in merged:
                    lab = det["label"]
                    bx1, by1, bx2, by2 = map(int, det["box_global"])
                    bx1e, by1e, bx2e, by2e = max(0, bx1 - 2), max(0, by1 - 2), min(image.shape[1], bx2 + 2), min(
                        image.shape[0], by2 + 2)
                    subcrop = image[by1e:by2e, bx1e:bx2e]

                    if subcrop.size == 0:
                        subcrop = text_crop

                    try:
                        if lab.startswith("ar") or "arab" in lab:
                            a_text, a_conf, _ = ocr_try_variants(subcrop, lang='ara')
                            ocr_text, ocr_conf = a_text, a_conf
                        else:
                            e_text, e_conf, _ = ocr_try_variants(subcrop, psms=OCR_PSMS_GENERAL)
                            ocr_text, ocr_conf = e_text, e_conf

                    except Exception:
                        ocr_text, ocr_conf = "", -999.0

                    ocr_results_per_det.append({
                        "label": lab,
                        "conf": det["conf"],
                        "box": (bx1e, by1e, bx2e, by2e),
                        "ocr_text": ocr_text,
                        "ocr_conf": ocr_conf
                    })
                    raw_entry["d_model_detections"].append(ocr_results_per_det[-1])

                if ocr_results_per_det:
                    logger.info("OCR DESC | crop=%s | merged_dets=%s", crop_fn,
                                [(d["label"], d["box"], d["ocr_text"], d["ocr_conf"])
                                 for d in ocr_results_per_det])
                else:
                    eng_text, eng_conf, _ = ocr_try_variants(text_crop)
                    raw_entry["value"] = eng_text.strip()
                    raw_entry["ocr_conf"] = float(eng_conf) if eng_conf is not None else -999.0

                if merged:
                    eng_parts = [
                        d["ocr_text"].strip() for d in ocr_results_per_det
                        if not (d["label"].startswith("ar") or "arab" in d["label"])
                    ]
                    ar_parts = [
                        d["ocr_text"].strip() for d in ocr_results_per_det
                        if (d["label"].startswith("ar") or "arab" in d["label"])
                    ]

                    combined_eng = " ".join([p for p in eng_parts if p]).strip()
                    combined_ar = " ".join([p for p in ar_parts if p]).strip()

                    if combined_ar and combined_eng:
                        raw_entry["value"] = combined_ar + " | " + combined_eng
                        raw_entry["arabic_description"] = combined_ar
                    elif combined_ar:
                        raw_entry["value"] = combined_ar
                        raw_entry["arabic_description"] = combined_ar
                    else:
                        raw_entry["value"] = combined_eng

                    try:
                        confs = [
                            float(d.get("ocr_conf", -999.0)) for d in ocr_results_per_det
                            if d.get("ocr_conf", None) is not None
                        ]
                        raw_entry["ocr_conf"] = max(confs) if confs else -999.0
                    except Exception:
                        raw_entry["ocr_conf"] = -999.0

            else:
                best_text, best_conf, best_meta = ocr_try_variants(text_crop, psms=OCR_PSMS_GENERAL)
                raw_entry["value"] = best_text.strip()
                raw_entry["ocr_conf"] = float(best_conf) if best_conf is not None else -999.0

            raw_data.append(raw_entry)

    # post-process (mirrors original script's logic)
    raw_data_sorted = sorted(raw_data, key=lambda r: (r["ymin"], r.get("xcenter", 0)))

    # disambiguation is intentionally left to caller or separate function; keep original behavior

    # compute median xcenters per class
    def median_or_none(xs):
        return int(np.median(xs)) if xs else None

    class_xs = {}
    for cls in ("date", "description", "debit", "credit", "balance"):
        xs = [r["xcenter"] for r in raw_data_sorted if r["class"] == cls and r.get("xcenter") is not None]
        class_xs[cls] = median_or_none(xs)

    if class_xs["description"] is None:
        all_xs = [r["xcenter"] for r in raw_data_sorted if r.get("xcenter") is not None]
        class_xs["description"] = median_or_none(all_xs)

    if class_xs["debit"] is None and class_xs["description"] is not None:
        class_xs["debit"] = class_xs["description"] + 450

    if class_xs["credit"] is None and class_xs["debit"] is not None:
        class_xs["credit"] = class_xs["debit"] + 160

    if class_xs["balance"] is None and class_xs["credit"] is not None:
        class_xs["balance"] = class_xs["credit"] + 160

    if class_xs["date"] is None and class_xs["description"] is not None:
        class_xs["date"] = class_xs["description"] - 650

    # build rows
    date_items = sorted([r for r in raw_data_sorted if r["class"] == "date" and str(r.get("value", "")).strip()],
                        key=lambda r: r["ymin"])
    desc_items_all = sorted([r for r in raw_data_sorted if r["class"] == "description"],
                            key=lambda r: r["ymin"])
    description_rows = []

    if date_items:
        for i, d in enumerate(date_items):
            start = d["ymin"]
            end = date_items[i + 1]["ymin"] if i + 1 < len(date_items) else float("inf")

            descs = [x for x in desc_items_all if x["ymin"] >= start and x["ymin"] < end]

            if i == 0:
                extra_above = [x for x in desc_items_all if
                               x["ymin"] < start and (start - x["ymin"]) <= DATE_ASSIGN_TOLERANCE]
                for e in extra_above:
                    if e not in descs:
                        descs.insert(0, e)

            for dsc in descs:
                date_val = d.get("value_parsed", d.get("value", "")).strip()
                description_rows.append({
                    "date": date_val,
                    "description": dsc["value"].strip(),
                    "ymin": dsc["ymin"],
                    "ymax": dsc["ymax"],
                    "xcenter": dsc.get("xcenter", None)
                })
    else:
        for dsc in desc_items_all:
            description_rows.append({
                "date": "",
                "description": dsc["value"].strip(),
                "ymin": dsc["ymin"],
                "ymax": dsc["ymax"],
                "xcenter": dsc.get("xcenter", None)
            })

    amount_boxes = []
    for r in raw_data_sorted:
        if r["class"] in ("debit", "credit", "balance"):
            amount_boxes.append({
                "class": r["class"],
                "value": r.get("value", ""),
                "value_num": r.get("value_num", None),
                "ocr_conf": float(r.get("ocr_conf", -999.0)),
                "ymin": r["ymin"],
                "ymax": r["ymax"],
                "xcenter": r.get("xcenter", None),
                "key": (r["class"], r["ymin"], r["ymax"], int(r.get("xcenter", 0)))
            })

    used_keys = set()

    def assign_amount_box_to_rows(box, rows):
        bh = max(1, box["ymax"] - box["ymin"])
        best_idx = None
        best_frac = 0.0
        for i, row in enumerate(rows):
            rymin, rymax = row["ymin"], row["ymax"]
            overlap = max(0, min(rymax, box["ymax"]) - max(rymin, box["ymin"]))
            row_h = max(1, rymax - rymin)
            frac_row = overlap / float(row_h)
            if frac_row > best_frac:
                best_frac = frac_row
                best_idx = i
        return best_idx, best_frac

    assignments = {i: {"debit": None, "credit": None, "balance": None} for i in range(len(description_rows))}

    for bi, box in enumerate(amount_boxes):
        if box["key"] in used_keys:
            continue

        best_idx, best_frac = assign_amount_box_to_rows(box, description_rows)
        bh = max(1, box["ymax"] - box["ymin"])

        if best_idx is not None:
            rymin, rymax = description_rows[best_idx]["ymin"], description_rows[best_idx]["ymax"]
            overlap = max(0, min(rymax, box["ymax"]) - max(rymin, box["ymin"]))
            frac_box = overlap / float(bh)
        else:
            frac_box = 0.0

        if best_frac >= MIN_OVERLAP_FRAC_ROW or frac_box >= MIN_OVERLAP_FRAC_BOX:
            cls = box["class"]
            if assignments[best_idx].get(cls) is None:
                assignments[best_idx][cls] = box
                used_keys.add(box["key"])
            else:
                existing = assignments[best_idx][cls]
                bh_exist = max(1, existing["ymax"] - existing["ymin"])
                overlap_exist = max(0, min(existing["ymax"], description_rows[best_idx]["ymax"]) -
                                    max(existing["ymin"], description_rows[best_idx]["ymin"]))
                frac_exist = overlap_exist / float(
                    max(1, description_rows[best_idx]["ymax"] - description_rows[best_idx]["ymin"]))

                if (box["ocr_conf"] > existing["ocr_conf"] + 5) or (best_frac > frac_exist + 0.15):
                    used_keys.discard(existing["key"])
                    assignments[best_idx][cls] = box
                    used_keys.add(box["key"])
                    continue

    for bi, box in enumerate(amount_boxes):
        if box["key"] in used_keys:
            continue

        row_centers = [(i, (r["ymin"] + r["ymax"]) // 2) for i, r in enumerate(description_rows)]
        if not row_centers:
            continue

        best_row_idx = min(row_centers, key=lambda t: abs(t[1] - ((box["ymin"] + box["ymax"]) // 2)))[0]
        vertical_dist = abs(((box["ymin"] + box["ymax"]) // 2) - (
                    (description_rows[best_row_idx]["ymin"] + description_rows[best_row_idx]["ymax"]) // 2))

        if vertical_dist > DATE_ASSIGN_TOLERANCE:
            continue

        if not any(c.isdigit() for c in str(box.get("value", ""))):
            continue

        if box.get("ocr_conf", -999.0) < FALLBACK_MIN_CONF:
            continue

        expected_x = class_xs.get(box["class"], None)
        if expected_x is not None and box.get("xcenter", None) is not None:
            if abs(box["xcenter"] - expected_x) > HORIZ_FALLBACK_TOL:
                continue

        cls = box["class"]
        if assignments[best_row_idx].get(cls) is None:
            assignments[best_row_idx][cls] = box
            used_keys.add(box["key"])

    final_rows = []

    def norm_amount_slot(slot):
        if not slot:
            return ""
        if slot.get("value_num") is not None:
            return float(slot["value_num"])
        txt = str(slot.get("value", "")).strip()
        if not txt:
            return ""
        parsed = parse_amount(sanitize_amount_text(txt))
        try:
            return float(parsed) if parsed != "" else ""
        except Exception:
            return txt

    for i, row in enumerate(description_rows):
        a = assignments.get(i, {})
        debit_val = norm_amount_slot(a.get("debit", None))
        credit_val = norm_amount_slot(a.get("credit", None))
        balance_val = norm_amount_slot(a.get("balance", None))

        final_rows.append({
            "date": row.get("date", "").strip(),
            "description": row.get("description", "").strip(),
            "debit": debit_val,
            "credit": credit_val,
            "balance": balance_val
        })

    def row_keep(r):
        if str(r.get("date", "")).strip():
            return True
        for k in ("debit", "credit", "balance"):
            v = r.get(k, "")
            if v is None:
                continue
            if isinstance(v, (int, float)):
                return True
            if str(v).strip() != "":
                return True
        return False

    filtered_rows = [r for r in final_rows if row_keep(r)]

    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(filtered_rows, f, indent=4, ensure_ascii=False)

    df = pd.DataFrame(filtered_rows, columns=["date", "description", "debit", "credit", "balance"])

    for col in ("debit", "credit", "balance"):
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df.to_excel(EXCEL_OUTPUT, index=False)

    logger.info("Finished processing: %s -> rows_kept=%d, json=%s, excel=%s",
                image_path, len(filtered_rows), JSON_OUTPUT, EXCEL_OUTPUT)

    for tb in global_text_boxes:
        col = (180, 180, 180)
        cv2.rectangle(vis_image, (tb["x1"], tb["y1"]), (tb["x2"], tb["y2"]), col, 1)

    for r in description_rows:
        cv2.rectangle(vis_image, (0, r["ymin"]), (vis_image.shape[1] - 1, r["ymax"]), (0, 255, 255), 1)

    out_img = os.path.join(working_dir, f"output_with_description_bands_{basename}_{ts}.jpg")
    cv2.imwrite(out_img, vis_image)

    zip_base = os.path.join(working_dir, f"cropped_texts_{basename}_{ts}")
    zip_path = shutil.make_archive(zip_base, 'zip', CROP_OUTPUT_DIR)

    return {
        "json_path": JSON_OUTPUT,
        "excel_path": EXCEL_OUTPUT,
        "vis_image": out_img,
        "cropped_zip": zip_path,
        "rows_kept": len(filtered_rows)
    }


def process_multi_page_pdf(image_paths, working_dir, model, d_model, basename, ts):
    """
    Process multiple PDF pages and aggregate results into single XLSX and JSON files.
    
    Args:
        image_paths: List of image file paths (one per PDF page)
        working_dir: Working directory for temporary files
        model: YOLO model for detection
        d_model: YOLO model for description detection
        basename: Base name for output files
        ts: Timestamp string for file naming
    
    Returns:
        Dictionary with paths to output files and processing statistics
    """
    logger.info("Processing multi-page PDF: %d pages, basename=%s ts=%s", 
                len(image_paths), basename, ts)
    
    if not image_paths:
        raise ValueError("No image paths provided for processing")
    
    # Create output directory for all crops
    CROP_OUTPUT_DIR = os.path.join(working_dir, f"cropped_texts_{basename}_{ts}")
    os.makedirs(CROP_OUTPUT_DIR, exist_ok=True)
    
    # Output file paths
    JSON_OUTPUT = os.path.join(working_dir, f"{basename}_{ts}.json")
    EXCEL_OUTPUT = os.path.join(working_dir, f"{basename}_{ts}.xlsx")
    
    all_rows = []
    total_rows_kept = 0
    
    # Process each page
    for page_num, image_path in enumerate(image_paths, start=1):
        try:
            logger.info("Processing page %d/%d: %s", page_num, len(image_paths), image_path)
            
            # Create page-specific subdirectory for crops
            page_crop_dir = os.path.join(CROP_OUTPUT_DIR, f"page_{page_num:03d}")
            os.makedirs(page_crop_dir, exist_ok=True)
            
            # Process the page using existing logic
            page_basename = f"{basename}_page{page_num:03d}"
            page_result = process_image_file(
                image_path, 
                working_dir, 
                model, 
                d_model, 
                page_basename, 
                ts
            )
            
            # Load the JSON result from the page
            with open(page_result["json_path"], "r", encoding="utf-8") as f:
                page_rows = json.load(f)
            
            # Add page number to each row for tracking
            for row in page_rows:
                row["page"] = page_num
            
            all_rows.extend(page_rows)
            total_rows_kept += page_result["rows_kept"]
            
            # Move crops to page-specific directory
            page_crop_source = os.path.join(working_dir, f"cropped_texts_{page_basename}_{ts}")
            if os.path.exists(page_crop_source):
                # Copy contents to page subdirectory
                for item in os.listdir(page_crop_source):
                    src = os.path.join(page_crop_source, item)
                    dst = os.path.join(page_crop_dir, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
                # Clean up page-specific directory
                shutil.rmtree(page_crop_source, ignore_errors=True)
            
            # Clean up page-specific files
            for temp_file in [page_result["json_path"], page_result["excel_path"]]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.exception("Failed to process page %d: %s", page_num, e)
            # Continue processing remaining pages
            continue
    
    # Save aggregated results
    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, indent=4, ensure_ascii=False)
    
    # Create DataFrame with page column
    df = pd.DataFrame(all_rows, columns=["page", "date", "description", "debit", "credit", "balance"])
    
    # Convert numeric columns
    for col in ("debit", "credit", "balance"):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Save to Excel
    df.to_excel(EXCEL_OUTPUT, index=False)
    
    # Create zip of all crops
    zip_base = os.path.join(working_dir, f"cropped_texts_{basename}_{ts}")
    zip_path = shutil.make_archive(zip_base, 'zip', CROP_OUTPUT_DIR)
    
    logger.info("Finished multi-page processing: %d pages -> %d rows, json=%s, excel=%s",
                len(image_paths), total_rows_kept, JSON_OUTPUT, EXCEL_OUTPUT)
    
    return {
        "json_path": JSON_OUTPUT,
        "excel_path": EXCEL_OUTPUT,
        "cropped_zip": zip_path,
        "rows_kept": total_rows_kept,
        "pages_processed": len(image_paths)
    }