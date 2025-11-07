import os
import json
import random
import shutil

# --------------------------
# CONFIGURATION
# --------------------------
INPUT_JSON = "extracted_invoices_f.json"     # Input JSON containing sub-JSONs
IMAGE_FOLDER = r"C:\Users\shanb\Downloads\Hackathon\data4hack"               # Folder containing all PDFs/Images
OUTPUT_DIR = r"C:\Users\shanb\Downloads\Hackathon\dataset"
TRAIN_RATIO = 0.9                         # 90% train, 10% val
TASK_TAG = "parse"                        # For Donut: <parse> ... </parse>
# --------------------------

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def main():
    # Load your combined JSON
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    file_keys = list(data.keys())
    random.shuffle(file_keys)

    split_idx = int(len(file_keys) * TRAIN_RATIO)
    train_files = file_keys[:split_idx]
    val_files = file_keys[split_idx:]

    # Prepare output structure
    train_img_dir = os.path.join(OUTPUT_DIR, "train", "images")
    val_img_dir = os.path.join(OUTPUT_DIR, "val", "images")
    ensure_dir(train_img_dir)
    ensure_dir(val_img_dir)

    train_meta = []
    val_meta = []

    for idx, fname in enumerate(file_keys):
        # each file corresponds to one invoice
        gt_json = data[fname]
        # convert dict → compact JSON string
        gt_text = json.dumps(gt_json, ensure_ascii=False)
        # add Donut task tags
        wrapped_gt = f"<{TASK_TAG}>{gt_text}</{TASK_TAG}>"

        record = {
            "image": fname,
            "ground_truth": wrapped_gt
        }

        # Copy the file
        src_path = os.path.join(IMAGE_FOLDER, fname)
        if not os.path.exists(src_path):
            print(f"⚠️ Warning: file not found: {src_path}")
            continue

        if fname in train_files:
            shutil.copy(src_path, train_img_dir)
            train_meta.append(record)
        else:
            shutil.copy(src_path, val_img_dir)
            val_meta.append(record)

    # Write metadata.jsonl
    with open(os.path.join(OUTPUT_DIR, "train", "metadata.jsonl"), "w", encoding="utf-8") as f:
        for rec in train_meta:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with open(os.path.join(OUTPUT_DIR, "val", "metadata.jsonl"), "w", encoding="utf-8") as f:
        for rec in val_meta:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"✅ Created {len(train_meta)} training samples and {len(val_meta)} validation samples.")
    print(f"✅ Output directory: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    main()
