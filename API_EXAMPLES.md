# Multi-Page PDF Processing API Examples

This file contains example API calls using curl to test the multi-page PDF processing functionality.

## Prerequisites

1. Start the Flask server:
```bash
python run.py
```

2. Ensure you have a PDF file to test with (e.g., `test.pdf`)

## Example API Calls

### 1. Health Check
```bash
curl -X GET http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok"
}
```

### 2. Process First Page Only (Default)
```bash
curl -X POST http://localhost:8000/process \
  -F "file=@test.pdf"
```

### 3. Process All Pages via /process Endpoint
```bash
curl -X POST http://localhost:8000/process \
  -F "file=@test.pdf" \
  -F "multi_page=true"
```

### 4. Process All Pages via /process-pdf Endpoint
```bash
curl -X POST http://localhost:8000/process-pdf \
  -F "file=@test.pdf"
```

## Expected Response Format

### Success Response
```json
{
  "status": "success",
  "uploaded": {
    "filename_20241027_120000.json": {
      "object_name": "Data/filename_20241027_120000.json",
      "presigned_url": "https://your-minio-url/..."
    },
    "filename_20241027_120000.xlsx": {
      "object_name": "Data/filename_20241027_120000.xlsx",
      "presigned_url": "https://your-minio-url/..."
    },
    "cropped_texts_filename_20241027_120000.zip": {
      "object_name": "BK_Crops/cropped_texts_filename_20241027_120000.zip",
      "presigned_url": "https://your-minio-url/..."
    }
  },
  "rows_kept": 45,
  "pages_processed": 3,
  "pages_total": 3,
  "elapsed_seconds": 25.5
}
```

### Response with Failed Pages
```json
{
  "status": "success",
  "uploaded": {...},
  "rows_kept": 30,
  "pages_processed": 2,
  "pages_total": 3,
  "pages_failed": 1,
  "warning": "1 page(s) failed to process",
  "elapsed_seconds": 20.3
}
```

### Error Response
```json
{
  "error": "PDF conversion failed",
  "detail": "PDF file has no pages: test.pdf"
}
```

## Downloading Results

Download the JSON output:
```bash
curl -o output.json "https://your-presigned-url"
```

Download the Excel output:
```bash
curl -o output.xlsx "https://your-presigned-url"
```

Download the cropped images:
```bash
curl -o crops.zip "https://your-presigned-url"
```

## Testing with Different Scenarios

### Valid Multi-Page PDF
```bash
curl -X POST http://localhost:8000/process-pdf \
  -F "file=@bank_statement_3pages.pdf" \
  -o response.json

# Check the response
cat response.json | python -m json.tool
```

### Single Image File
```bash
curl -X POST http://localhost:8000/process \
  -F "file=@statement_page1.jpg"
```

### Invalid File Type (Should Fail on /process-pdf)
```bash
curl -X POST http://localhost:8000/process-pdf \
  -F "file=@statement.jpg"
```

Expected error:
```json
{
  "error": "only PDF files are supported by this endpoint"
}
```

## Response Fields Explained

- **status**: "success" or "error"
- **uploaded**: Dictionary of uploaded files with their MinIO object names and presigned URLs
- **rows_kept**: Total number of data rows extracted from all pages
- **pages_processed**: Number of pages successfully processed
- **pages_total**: Total number of pages in the PDF
- **pages_failed**: Number of pages that failed to process (optional, only if > 0)
- **warning**: Warning message if some pages failed (optional)
- **elapsed_seconds**: Total processing time in seconds
- **error**: Error message (only if status is "error")
- **detail**: Detailed error information (only if status is "error")

## Output File Format

### JSON Output Structure
```json
[
  {
    "page": 1,
    "date": "01/01/2024",
    "description": "Opening Balance",
    "debit": null,
    "credit": null,
    "balance": 5000.0
  },
  {
    "page": 1,
    "date": "01/02/2024",
    "description": "Payment received",
    "debit": null,
    "credit": 1000.0,
    "balance": 6000.0
  },
  {
    "page": 2,
    "date": "01/03/2024",
    "description": "Withdrawal",
    "debit": 500.0,
    "credit": null,
    "balance": 5500.0
  }
]
```

### Excel Output
The Excel file contains the same data with columns:
- page (integer)
- date (string)
- description (string)
- debit (float or empty)
- credit (float or empty)
- balance (float or empty)

## Troubleshooting

### 1. "models not loaded on server"
Ensure the YOLO model files (FSA.pt, d3.pt) are in the correct location specified in .env

### 2. "PDF conversion failed"
- Check that PyMuPDF is installed: `pip install PyMuPDF`
- Verify the PDF file is not corrupted
- Check server logs for detailed error messages

### 3. "MinIO upload failed"
- Verify MinIO credentials in .env
- Check MinIO server is accessible
- Ensure the bucket exists

### 4. Processing takes too long
- Reduce DPI in config (default is 300)
- Process only necessary pages
- Check server resources (CPU, memory)
