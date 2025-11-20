#!/usr/bin/env python3
"""
Quality-Based LLM OCR Example

This example demonstrates how to use the QualityBasedLLMOCRProcessor
to intelligently route low-quality OCR blocks to LLM for re-extraction.

Usage:
    python examples/quality_based_llm_ocr_example.py <pdf_path>

Requirements:
    - Set GOOGLE_API_KEY environment variable for Gemini API
    - Install marker with: pip install marker-pdf
"""

import os
import sys
import logging
from pathlib import Path

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.renderers.markdown import MarkdownRenderer


def setup_logging(debug: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def example_1_basic_usage(pdf_path: str):
    """
    Example 1: Basic usage with default settings

    This uses page-level OCR error detection to route problematic
    pages to LLM for re-extraction.
    """
    print("\n" + "="*60)
    print("Example 1: Basic Quality-Based LLM OCR")
    print("="*60 + "\n")

    # Load models
    print("Loading models...")
    models = create_model_dict()

    # Create converter with quality-based routing
    converter = PdfConverter(
        artifact_dict=models,
        config={
            "use_llm": True,

            # Enable quality-based routing
            "QualityBasedLLMOCRProcessor": {
                "page_ocr_error_trigger": True,   # Route bad pages to LLM
                "check_garbled_text": False,      # Disable for basic usage
            }
        },
        processor_list=[
            # Use default processors plus our custom one
            "marker.processors.order.OrderProcessor",
            "marker.processors.block_relabel.BlockRelabelProcessor",
            "marker.processors.line_merge.LineMergeProcessor",
            "marker.processors.blockquote.BlockquoteProcessor",
            "marker.processors.code.CodeProcessor",
            "marker.processors.document_toc.DocumentTOCProcessor",
            "marker.processors.equation.EquationProcessor",
            "marker.processors.footnote.FootnoteProcessor",
            "marker.processors.ignoretext.IgnoreTextProcessor",
            "marker.processors.line_numbers.LineNumbersProcessor",
            "marker.processors.list.ListProcessor",
            "marker.processors.page_header.PageHeaderProcessor",
            "marker.processors.sectionheader.SectionHeaderProcessor",
            "marker.processors.table.TableProcessor",
            "marker.processors.llm.llm_quality_ocr.QualityBasedLLMOCRProcessor",  # Add here!
            "marker.processors.text.TextProcessor",
            "marker.processors.reference.ReferenceProcessor",
            "marker.processors.blank_page.BlankPageProcessor",
        ],
        llm_service="marker.services.gemini.GoogleGeminiService"
    )

    # Process document
    print(f"Processing: {pdf_path}")
    result = converter(pdf_path)

    # Display results
    print("\n" + "-"*60)
    print("RESULTS")
    print("-"*60)
    print(f"Pages processed: {converter.page_count}")
    print(f"\nFirst 500 characters of output:\n")
    print(result.markdown[:500])
    print("...\n")

    return result


def example_2_aggressive_quality_check(pdf_path: str):
    """
    Example 2: Aggressive quality checking

    This enables all quality checks including garbled text detection
    for maximum quality at higher cost.
    """
    print("\n" + "="*60)
    print("Example 2: Aggressive Quality Checking")
    print("="*60 + "\n")

    models = create_model_dict()

    converter = PdfConverter(
        artifact_dict=models,
        config={
            "use_llm": True,

            "QualityBasedLLMOCRProcessor": {
                "page_ocr_error_trigger": True,   # Route bad pages
                "check_garbled_text": True,       # Enable garbled detection
                "garbled_threshold": 0.25,        # Lower threshold = more sensitive
                "min_text_length": 5,             # Process shorter blocks
                "max_text_length": 2000,          # Process longer blocks
                "include_original_as_hint": True, # Send original to LLM as hint
            }
        },
        llm_service="marker.services.gemini.GoogleGeminiService"
    )

    result = converter(pdf_path)
    print(f"Processed with aggressive quality checks")
    return result


def example_3_cost_optimized(pdf_path: str):
    """
    Example 3: Cost-optimized configuration

    This minimizes LLM usage by only routing the worst quality blocks.
    """
    print("\n" + "="*60)
    print("Example 3: Cost-Optimized Configuration")
    print("="*60 + "\n")

    models = create_model_dict()

    converter = PdfConverter(
        artifact_dict=models,
        config={
            "use_llm": True,

            "QualityBasedLLMOCRProcessor": {
                "page_ocr_error_trigger": True,   # Only page-level errors
                "check_garbled_text": False,      # Disable garbled check
                "min_text_length": 20,            # Skip short blocks
                "max_text_length": 500,           # Skip long blocks (expensive)
            }
        },
        llm_service="marker.services.gemini.GoogleGeminiService"
    )

    result = converter(pdf_path)
    print(f"Processed with cost-optimized settings")
    return result


def example_4_with_statistics(pdf_path: str):
    """
    Example 4: Process with detailed statistics

    This example shows how to track which blocks were sent to LLM.
    """
    print("\n" + "="*60)
    print("Example 4: Processing with Statistics")
    print("="*60 + "\n")

    # Enable debug logging to see routing decisions
    logging.getLogger("marker.processors.llm.llm_quality_ocr").setLevel(logging.DEBUG)

    models = create_model_dict()

    converter = PdfConverter(
        artifact_dict=models,
        config={
            "use_llm": True,
            "QualityBasedLLMOCRProcessor": {
                "page_ocr_error_trigger": True,
                "check_garbled_text": True,
                "garbled_threshold": 0.3,
            }
        },
        llm_service="marker.services.gemini.GoogleGeminiService"
    )

    result = converter(pdf_path)

    # In practice, you'd extract stats from document metadata
    print("\nStatistics:")
    print(f"- Total pages: {converter.page_count}")
    print(f"- Check debug logs above for routing decisions")

    return result


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python quality_based_llm_ocr_example.py <pdf_path> [example_number]")
        print("\nExamples:")
        print("  1 - Basic usage (default)")
        print("  2 - Aggressive quality checking")
        print("  3 - Cost-optimized")
        print("  4 - With statistics")
        sys.exit(1)

    pdf_path = sys.argv[1]
    example_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    # Check file exists
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    # Check API key
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY not set. LLM processing will fail.")
        print("Set it with: export GOOGLE_API_KEY='your-key-here'")

    # Setup logging
    setup_logging(debug=(example_num == 4))

    # Run selected example
    examples = {
        1: example_1_basic_usage,
        2: example_2_aggressive_quality_check,
        3: example_3_cost_optimized,
        4: example_4_with_statistics,
    }

    example_func = examples.get(example_num, example_1_basic_usage)
    result = example_func(pdf_path)

    print("\n" + "="*60)
    print("Processing Complete!")
    print("="*60)


if __name__ == "__main__":
    main()
