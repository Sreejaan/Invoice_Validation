import torch
import json
import os
import re
import glob
from PIL import Image
from transformers import AutoProcessor, VisionEncoderDecoderModel
from peft import PeftModel
from pdf2image import convert_from_path
from typing import List, Dict, Optional
from tqdm.auto import tqdm # Import tqdm for the progress bar

# -----------------
# CONFIGURATION
# -----------------
BASE_MODEL_NAME = "naver-clova-ix/donut-base-finetuned-cord-v2"
# --- ⚠️ UPDATE THIS PATH ---
# This must be the path to your checkpoint folder
# (e.g., /content/drive/MyDrive/donut_peft_lora_output/checkpoint-100)
ADAPTER_PATH = "/content/drive/MyDrive/donut_peft_lora_output/checkpoint-100" 

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_model(base_model_path: str, adapter_path: str, device: str) -> (PeftModel, AutoProcessor):
    """
    Loads the base Donut model and applies the PEFT adapter.
    This function should only be called ONCE.
    """
    print(f"Loading base processor from {base_model_path}...")
    processor = AutoProcessor.from_pretrained(base_model_path)
    
    print(f"Loading base model from {base_model_path}...")
    base_model = VisionEncoderDecoderModel.from_pretrained(base_model_path)
    
    print(f"Loading PEFT adapter from {adapter_path}...")
    model = PeftModel.from_pretrained(base_model, adapter_path)
    
    print(f"Moving model to {device}...")
    model.to(device)
    model.eval()
    print("Model loaded successfully.")
    return model, processor


def parse_donut_output(output_string: str) -> Dict:
    """
    Cleans the raw output string from the Donut model and parses it as JSON.
    """
    match = re.search(r"<parse>(.*?)</parse>", output_string, re.DOTALL)
    
    if not match:
        json_match = re.search(r"\{.*\}", output_string, re.DOTALL)
        if not json_match:
            return {"error": "Failed to find JSON", "raw_output": output_string}
        json_str = json_match.group(0)
    else:
        json_str = match.group(1).strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": "JSONDecodeError", "raw_output": json_str}


def extract_invoice_data(input_path: str, model: PeftModel, processor: AutoProcessor, 
                         output_dir: str = ".", max_target_len: int = 512) -> Optional[str]:
    """
    Extracts data from a SINGLE PDF or image file and saves its JSON output.
    Returns the output file path on success, None on failure.
    """
    images = []
    base_name = os.path.basename(input_path).split('.')[0]
    
    try:
        if input_path.lower().endswith(".pdf"):
            images = convert_from_path(input_path, dpi=200)
        elif input_path.lower().endswith((".png", ".jpg", ".jpeg", ".tiff")):
            images = [Image.open(input_path).convert("RGB")]
        else:
            print(f"Skipping unsupported file type: {input_path}")
            return None
    except Exception as e:
        print(f"Error processing file {input_path}: {e}")
        return None

    tokenizer = processor.tokenizer
    all_page_data = []

    for i, img in enumerate(images):
        pixel_values = processor(images=img, return_tensors="pt").pixel_values.to(DEVICE)
        
        generated_ids = model.generate(
            pixel_values,
            max_length=max_target_len,
        )
        
        output_str = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        parsed_json = parse_donut_output(output_str)
        
        if len(images) > 1:
            parsed_json["page_number"] = i + 1
        
        all_page_data.append(parsed_json)

    if len(all_page_data) == 1:
        final_data = all_page_data[0]
    else:
        final_data = {"document_pages": all_page_data}

    output_filename = os.path.join(output_dir, f"{base_name}_extracted.json")
    os.makedirs(output_dir, exist_ok=True)
    
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=4)
        
    return output_filename


def process_invoice_batch(file_paths: List[str], model: PeftModel, processor: AutoProcessor, 
                          output_dir: str, max_target_len: int = 512):
    """
    Processes a batch of invoice files (PDF, PNG, JPG, TIFF)
    and shows a progress bar.
    """
    print(f"Starting batch processing for {len(file_paths)} files...")
    success_files = []
    failed_files = []

    # This is where the progress bar is created
    for file_path in tqdm(file_paths, desc="Processing Invoices"):
        output_path = extract_invoice_data(
            input_path=file_path,
            model=model,
            processor=processor,
            output_dir=output_dir,
            max_target_len=max_target_len
        )
        if output_path:
            success_files.append(output_path)
        else:
            failed_files.append(file_path)

    print("\n--- Batch Processing Complete ---")
    print(f"✅ Successful extractions: {len(success_files)}")
    print(f"❌ Failed files: {len(failed_files)}")
    if failed_files:
        print("\nFailed file list:")
        for f in failed_files:
            print(f"  - {f}")


def run_ocr(path:str):
    try:
        MAX_TARGET_LENGTH = MAX_TARGET_LENGTH
    except NameError:
        MAX_TARGET_LENGTH = 512 

    # --- ⚠️ UPDATE THIS PATH ---
    # Put the path to your FOLDER containing invoices
    INPUT_FOLDER_PATH = path
    
    # --- ⚠️ UPDATE THIS PATH ---
    # Where to save all the final JSON files
    OUTPUT_JSON_DIR = "./invoice_outputs" 

    # 1. Create the list of files to process
    # This example finds all pdf, png, jpg, and tiff files in the input folder
    file_types = ["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.tiff"]
    all_files = []
    for file_type in file_types:
        all_files.extend(glob.glob(os.path.join(INPUT_FOLDER_PATH, file_type)))

    if not all_files:
        print(f"Error: No valid files found in {INPUT_FOLDER_PATH}")
    else:
        # 2. Load the model and processor (only ONCE)
        model, processor = load_model(BASE_MODEL_NAME, ADAPTER_PATH, DEVICE)
    
        # 3. Run batch extraction
        process_invoice_batch(
            file_paths=all_files,
            model=model,
            processor=processor,
            output_dir=OUTPUT_JSON_DIR,
            max_target_len=MAX_TARGET_LENGTH
        )

# -----------------
# MAIN EXECUTION
# -----------------
if __name__ == "__main__":
    try:
        MAX_TARGET_LENGTH = MAX_TARGET_LENGTH
    except NameError:
        MAX_TARGET_LENGTH = 512 

    # --- ⚠️ UPDATE THIS PATH ---
    # Put the path to your FOLDER containing invoices
    INPUT_FOLDER_PATH = "/content/my_invoices_to_process/"
    
    # --- ⚠️ UPDATE THIS PATH ---
    # Where to save all the final JSON files
    OUTPUT_JSON_DIR = "./invoice_outputs" 

    # 1. Create the list of files to process
    # This example finds all pdf, png, jpg, and tiff files in the input folder
    file_types = ["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.tiff"]
    all_files = []
    for file_type in file_types:
        all_files.extend(glob.glob(os.path.join(INPUT_FOLDER_PATH, file_type)))

    if not all_files:
        print(f"Error: No valid files found in {INPUT_FOLDER_PATH}")
    else:
        # 2. Load the model and processor (only ONCE)
        model, processor = load_model(BASE_MODEL_NAME, ADAPTER_PATH, DEVICE)
    
        # 3. Run batch extraction
        process_invoice_batch(
            file_paths=all_files,
            model=model,
            processor=processor,
            output_dir=OUTPUT_JSON_DIR,
            max_target_len=MAX_TARGET_LENGTH
        )