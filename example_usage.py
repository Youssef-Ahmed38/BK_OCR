#!/usr/bin/env python3
"""
Example script demonstrating how to use the multi-page PDF processing API.

Prerequisites:
- Flask server running on http://localhost:8000
- A PDF file to process

Usage:
    python example_usage.py path/to/your/file.pdf
"""

import sys
import requests
import json
from pathlib import Path


def process_single_page(pdf_path, api_url="http://localhost:8000"):
    """
    Process only the first page of a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        api_url: Base URL of the API server
    
    Returns:
        API response as dictionary
    """
    print(f"Processing first page only: {pdf_path}")
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
        data = {'multi_page': 'false'}  # Process only first page
        
        response = requests.post(
            f"{api_url}/process",
            files=files,
            data=data
        )
    
    return response.json()


def process_multi_page(pdf_path, api_url="http://localhost:8000"):
    """
    Process all pages of a PDF using the /process endpoint.
    
    Args:
        pdf_path: Path to the PDF file
        api_url: Base URL of the API server
    
    Returns:
        API response as dictionary
    """
    print(f"Processing all pages via /process: {pdf_path}")
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
        data = {'multi_page': 'true'}  # Process all pages
        
        response = requests.post(
            f"{api_url}/process",
            files=files,
            data=data
        )
    
    return response.json()


def process_pdf_dedicated(pdf_path, api_url="http://localhost:8000"):
    """
    Process all pages of a PDF using the dedicated /process-pdf endpoint.
    
    Args:
        pdf_path: Path to the PDF file
        api_url: Base URL of the API server
    
    Returns:
        API response as dictionary
    """
    print(f"Processing all pages via /process-pdf: {pdf_path}")
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
        
        response = requests.post(
            f"{api_url}/process-pdf",
            files=files
        )
    
    return response.json()


def download_file(url, output_path):
    """Download a file from a URL."""
    print(f"Downloading to {output_path}...")
    response = requests.get(url)
    response.raise_for_status()
    
    with open(output_path, 'wb') as f:
        f.write(response.content)
    
    print(f"✓ Downloaded: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python example_usage.py <path_to_pdf>")
        print("\nExamples:")
        print("  python example_usage.py bank_statement.pdf")
        print("  python example_usage.py /path/to/multi_page.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    if not pdf_path.lower().endswith('.pdf'):
        print(f"Warning: File does not have .pdf extension: {pdf_path}")
    
    print("=" * 70)
    print("Multi-Page PDF Processing - Example Usage")
    print("=" * 70)
    
    # Example 1: Process only first page
    print("\n### Example 1: Process First Page Only ###")
    try:
        result = process_single_page(pdf_path)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Process all pages via /process endpoint
    print("\n### Example 2: Process All Pages (via /process) ###")
    try:
        result = process_multi_page(pdf_path)
        print(json.dumps(result, indent=2))
        
        # Download the results if available
        if result.get('status') == 'success':
            uploads = result.get('uploaded', {})
            for filename, info in uploads.items():
                if filename.endswith('.json'):
                    if info.get('presigned_url'):
                        download_file(info['presigned_url'], f"output_{filename}")
                if filename.endswith('.xlsx'):
                    if info.get('presigned_url'):
                        download_file(info['presigned_url'], f"output_{filename}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 3: Process all pages via dedicated endpoint
    print("\n### Example 3: Process All Pages (via /process-pdf) ###")
    try:
        result = process_pdf_dedicated(pdf_path)
        print(json.dumps(result, indent=2))
        
        print(f"\n✓ Successfully processed {result.get('pages_processed', 0)} pages")
        print(f"  Total rows extracted: {result.get('rows_kept', 0)}")
        if result.get('pages_failed', 0) > 0:
            print(f"  Warning: {result['pages_failed']} page(s) failed")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
