# BK_OCR

Bank Statement OCR Processing Application

## Overview

This Flask-based application performs OCR (Optical Character Recognition) on bank statements, extracting structured data from images and PDF files. The system uses YOLO models for text detection and Tesseract for OCR.

## Features

- **Single Image Processing**: Process individual bank statement images
- **Multi-Page PDF Processing**: Process entire PDF documents with multiple pages
- **Data Extraction**: Extract dates, descriptions, debits, credits, and balances
- **Multiple Output Formats**: Generate both Excel (XLSX) and JSON outputs
- **MinIO Integration**: Upload processed results to MinIO object storage
- **Robust Error Handling**: Continue processing even if individual pages fail

## Installation

### Prerequisites

- Python 3.8+
- Tesseract OCR installed on the system
- YOLO model files (FSA.pt, d3.pt)

### Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables in `.env`:
```bash
# MinIO Configuration
MINIO_ENDPOINT=your-minio-endpoint
ACCESS_KEY=your-access-key
SECRET_KEY=your-secret-key
BUCKET_NAME=your-bucket-name

# Model Paths
MODEL_PATH=FSA.pt
D_MODEL_PATH=d3.pt
```

3. Run the application:
```bash
python run.py
```

## API Endpoints

### Health Check
```
GET /health
```
Returns service status.

### Process Single Image or PDF (First Page Only)
```
POST /process
Content-Type: multipart/form-data

Parameters:
- file: Image or PDF file (required)
- multi_page: "true" to process all pages (default: "false")
```

**Example Response:**
```json
{
  "status": "success",
  "uploaded": {
    "filename.json": {
      "object_name": "Data/filename.json",
      "presigned_url": "https://..."
    },
    "filename.xlsx": {
      "object_name": "Data/filename.xlsx", 
      "presigned_url": "https://..."
    }
  },
  "rows_kept": 45,
  "elapsed_seconds": 12.5
}
```

### Process Multi-Page PDF
```
POST /process-pdf
Content-Type: multipart/form-data

Parameters:
- file: PDF file (required)
```

**Example Response:**
```json
{
  "status": "success",
  "uploaded": {
    "filename.json": {...},
    "filename.xlsx": {...}
  },
  "rows_kept": 150,
  "pages_processed": 3,
  "pages_total": 3,
  "elapsed_seconds": 35.2
}
```

## Output Format

### JSON Output
```json
[
  {
    "page": 1,
    "date": "01/01/2024",
    "description": "Payment received",
    "debit": null,
    "credit": 1000.0,
    "balance": 5000.0
  }
]
```

### Excel Output
Excel file with columns: `page`, `date`, `description`, `debit`, `credit`, `balance`

## Error Handling

The application includes robust error handling for:
- Invalid PDF files
- Empty or corrupted pages
- Missing model files
- OCR failures
- Upload failures

Failed pages are logged but don't stop the processing of remaining pages.

## Development

### Project Structure
```
BK_OCR/
├── app/
│   ├── api.py              # Flask API routes
│   ├── processor.py        # Image/PDF processing logic
│   ├── pdf_utils.py        # PDF conversion utilities
│   ├── models.py           # YOLO model loading
│   ├── config.py           # Configuration management
│   └── ocr/                # OCR core functionality
├── run.py                  # Application entry point
├── requirements.txt        # Python dependencies
└── .env                    # Environment configuration
```

## License

[Add your license information here]