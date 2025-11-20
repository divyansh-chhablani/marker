# Integration Guide: Quality-Based LLM OCR

This guide shows developers how to integrate the Quality-Based LLM OCR processor into their existing Marker setup.

## Table of Contents
1. [Quick Integration](#quick-integration)
2. [Configuration Options](#configuration-options)
3. [Adding to Default Processors](#adding-to-default-processors)
4. [Custom Implementation](#custom-implementation)
5. [Testing](#testing)

---

## Quick Integration

### Step 1: Import the Processor

```python
from marker.processors.llm.llm_quality_ocr import QualityBasedLLMOCRProcessor
```

### Step 2: Add to Your Converter

#### Option A: Using Processor List (Recommended)

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

models = create_model_dict()

converter = PdfConverter(
    artifact_dict=models,
    config={
        "use_llm": True,
        "QualityBasedLLMOCRProcessor": {
            "page_ocr_error_trigger": True,
            "check_garbled_text": True,
        }
    },
    processor_list=[
        # Your existing processors...
        "marker.processors.llm.llm_quality_ocr.QualityBasedLLMOCRProcessor",
    ],
    llm_service="marker.services.gemini.GoogleGeminiService"
)
```

#### Option B: Programmatic Instantiation

```python
from marker.processors.llm.llm_quality_ocr import QualityBasedLLMOCRProcessor
from marker.services.gemini import GoogleGeminiService

# Create LLM service
llm_service = GoogleGeminiService()

# Create processor
quality_processor = QualityBasedLLMOCRProcessor(
    llm_service=llm_service,
    config={
        "page_ocr_error_trigger": True,
        "check_garbled_text": True,
        "garbled_threshold": 0.3,
    }
)

# Add to your processing pipeline manually
# (in your document processing loop)
quality_processor(document)
```

---

## Configuration Options

### Basic Configuration

```python
config = {
    "QualityBasedLLMOCRProcessor": {
        # Core settings
        "use_llm": True,                      # Must be True (inherited)
        "page_ocr_error_trigger": True,       # Route bad pages to LLM
        "check_garbled_text": True,           # Detect garbled text

        # Thresholds
        "garbled_threshold": 0.3,             # 30% special chars = garbled
        "min_text_length": 10,                # Skip blocks < 10 chars
        "max_text_length": 1000,              # Skip blocks > 1000 chars

        # Performance
        "max_concurrency": 3,                 # Parallel LLM requests
        "disable_tqdm": False,                # Show progress bars

        # Advanced
        "include_original_as_hint": False,    # Send original OCR to LLM
    }
}
```

### Preset Configurations

#### Conservative (Low Cost)
```python
CONSERVATIVE_CONFIG = {
    "QualityBasedLLMOCRProcessor": {
        "page_ocr_error_trigger": True,
        "check_garbled_text": False,
        "min_text_length": 20,
        "max_text_length": 500,
    }
}
```

#### Balanced (Recommended)
```python
BALANCED_CONFIG = {
    "QualityBasedLLMOCRProcessor": {
        "page_ocr_error_trigger": True,
        "check_garbled_text": True,
        "garbled_threshold": 0.3,
        "min_text_length": 10,
        "max_text_length": 1000,
    }
}
```

#### Aggressive (High Quality)
```python
AGGRESSIVE_CONFIG = {
    "QualityBasedLLMOCRProcessor": {
        "page_ocr_error_trigger": True,
        "check_garbled_text": True,
        "garbled_threshold": 0.2,
        "min_text_length": 5,
        "max_text_length": 2000,
        "include_original_as_hint": True,
    }
}
```

---

## Adding to Default Processors

To make the processor run automatically for all conversions:

### Step 1: Edit `marker/converters/pdf.py`

```python
# Add import at the top
from marker.processors.llm.llm_quality_ocr import QualityBasedLLMOCRProcessor

class PdfConverter(BaseConverter):
    default_processors: Tuple[BaseProcessor, ...] = (
        OrderProcessor,
        BlockRelabelProcessor,
        LineMergeProcessor,
        BlockquoteProcessor,
        CodeProcessor,
        DocumentTOCProcessor,
        EquationProcessor,
        FootnoteProcessor,
        IgnoreTextProcessor,
        LineNumbersProcessor,
        ListProcessor,
        PageHeaderProcessor,
        SectionHeaderProcessor,
        TableProcessor,
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        TextProcessor,
        LLMComplexRegionProcessor,
        LLMImageDescriptionProcessor,
        LLMEquationProcessor,
        LLMHandwritingProcessor,
        LLMMathBlockProcessor,
        LLMSectionHeaderProcessor,
        QualityBasedLLMOCRProcessor,  # ← Add this line
        LLMPageCorrectionProcessor,
        ReferenceProcessor,
        BlankPageProcessor,
        DebugProcessor,
    )
```

### Step 2: Set Default Configuration (Optional)

Edit your config file or environment:

```python
# In your application config
DEFAULT_MARKER_CONFIG = {
    "use_llm": True,
    "QualityBasedLLMOCRProcessor": {
        "page_ocr_error_trigger": True,
        "check_garbled_text": True,
    }
}
```

---

## Custom Implementation

### Extending the Processor

You can extend the processor to add custom quality heuristics:

```python
from marker.processors.llm.llm_quality_ocr import QualityBasedLLMOCRProcessor

class CustomQualityProcessor(QualityBasedLLMOCRProcessor):
    """Custom processor with additional quality checks"""

    # Add custom configuration
    custom_check_enabled: bool = True
    custom_threshold: float = 0.5

    def should_reocr_with_llm(self, block, page, document):
        # Run parent logic first
        should_reocr, reason, metadata = super().should_reocr_with_llm(
            block, page, document
        )

        if should_reocr:
            return should_reocr, reason, metadata

        # Add your custom check
        if self.custom_check_enabled:
            # Example: Check block confidence
            if hasattr(block, 'confidence'):
                if block.confidence < self.custom_threshold:
                    metadata['confidence'] = block.confidence
                    return True, "low_confidence", metadata

            # Example: Check for specific patterns
            text = block.raw_text(document)
            if self.contains_suspicious_pattern(text):
                return True, "suspicious_pattern", metadata

        return False, reason, metadata

    def contains_suspicious_pattern(self, text: str) -> bool:
        """Your custom pattern detection logic"""
        # Example: Detect repeated characters
        import re
        pattern = r'(.)\1{5,}'  # 5+ repeated chars
        return bool(re.search(pattern, text))
```

Usage:
```python
converter = PdfConverter(
    artifact_dict=models,
    processor_list=[
        # ... other processors ...
        "your_module.CustomQualityProcessor",
    ],
    config={
        "CustomQualityProcessor": {
            "custom_check_enabled": True,
            "custom_threshold": 0.7,
        }
    }
)
```

### Batch Processing Example

```python
from pathlib import Path
import json

def batch_process_with_quality_routing(
    input_dir: Path,
    output_dir: Path,
    config: dict
):
    """
    Process multiple PDFs with quality-based routing and collect stats
    """
    models = create_model_dict()
    results = []

    for pdf_path in input_dir.glob("*.pdf"):
        print(f"Processing: {pdf_path.name}")

        converter = PdfConverter(
            artifact_dict=models,
            config=config,
            processor_list=[
                # ... your processors ...
                "marker.processors.llm.llm_quality_ocr.QualityBasedLLMOCRProcessor",
            ]
        )

        try:
            result = converter(str(pdf_path))

            # Save output
            output_file = output_dir / f"{pdf_path.stem}.md"
            output_file.write_text(result.markdown)

            results.append({
                "file": pdf_path.name,
                "status": "success",
                "pages": converter.page_count,
            })

        except Exception as e:
            results.append({
                "file": pdf_path.name,
                "status": "error",
                "error": str(e)
            })

    # Save summary
    summary_file = output_dir / "processing_summary.json"
    summary_file.write_text(json.dumps(results, indent=2))

    return results


# Usage
results = batch_process_with_quality_routing(
    input_dir=Path("./pdfs"),
    output_dir=Path("./output"),
    config={
        "use_llm": True,
        "QualityBasedLLMOCRProcessor": {
            "page_ocr_error_trigger": True,
            "check_garbled_text": True,
        }
    }
)
```

---

## Testing

### Unit Tests

```python
import pytest
from marker.processors.llm.llm_quality_ocr import QualityBasedLLMOCRProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.groups.page import PageGroup
from marker.schema.document import Document


def test_garbled_detection():
    """Test garbled text detection"""
    processor = QualityBasedLLMOCRProcessor(
        llm_service=None,
        config={"garbled_threshold": 0.3}
    )

    # Normal text
    is_garbled, ratio = processor.is_text_garbled("Hello world")
    assert not is_garbled
    assert ratio < 0.3

    # Garbled text
    is_garbled, ratio = processor.is_text_garbled("§¶∞£¢€ƒ∂∑")
    assert is_garbled
    assert ratio > 0.3


def test_text_length_filtering():
    """Test text length filtering"""
    processor = QualityBasedLLMOCRProcessor(
        llm_service=None,
        config={
            "min_text_length": 10,
            "max_text_length": 100,
        }
    )

    # Mock objects
    page = PageGroup(page_id=0)
    page.ocr_errors_detected = False

    # Too short
    block = Block(text_extraction_method="surya")
    block.raw_text = lambda doc: "short"
    should_reocr, reason, _ = processor.should_reocr_with_llm(block, page, None)
    assert not should_reocr
    assert reason == "text_too_short"

    # Too long
    block.raw_text = lambda doc: "x" * 1000
    should_reocr, reason, _ = processor.should_reocr_with_llm(block, page, None)
    assert not should_reocr
    assert reason == "text_too_long_cost_control"


def test_page_error_routing():
    """Test page-level error routing"""
    processor = QualityBasedLLMOCRProcessor(
        llm_service=None,
        config={"page_ocr_error_trigger": True}
    )

    page = PageGroup(page_id=0)
    block = Block(text_extraction_method="surya")
    block.raw_text = lambda doc: "Some reasonable text here"

    # Page with errors
    page.ocr_errors_detected = True
    should_reocr, reason, metadata = processor.should_reocr_with_llm(
        block, page, None
    )
    assert should_reocr
    assert reason == "page_ocr_errors_detected"
    assert metadata["page_errors"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### Integration Test

```python
def test_end_to_end_quality_routing(sample_pdf_path):
    """Test complete pipeline with quality routing"""
    from marker.models import create_model_dict

    models = create_model_dict()

    converter = PdfConverter(
        artifact_dict=models,
        config={
            "use_llm": True,
            "QualityBasedLLMOCRProcessor": {
                "page_ocr_error_trigger": True,
                "check_garbled_text": True,
            }
        },
        processor_list=[
            # ... include QualityBasedLLMOCRProcessor ...
        ]
    )

    result = converter(sample_pdf_path)

    # Verify output
    assert result.markdown
    assert len(result.markdown) > 0

    # Check that some blocks were processed
    # (In practice, you'd check document metadata)
    assert converter.page_count > 0
```

---

## Environment Variables

Set these for LLM services:

```bash
# Google Gemini
export GOOGLE_API_KEY="your-api-key-here"

# Or for other services
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-claude-key"
```

---

## Troubleshooting

### Common Issues

#### 1. Processor Not Running

**Problem**: No blocks being sent to LLM

**Check**:
```python
# Verify use_llm is True
config = {"use_llm": True}

# Check logs
import logging
logging.getLogger("marker.processors.llm.llm_quality_ocr").setLevel(logging.DEBUG)
```

#### 2. High LLM Costs

**Problem**: Too many blocks being processed

**Solution**: Adjust thresholds
```python
config = {
    "QualityBasedLLMOCRProcessor": {
        "page_ocr_error_trigger": False,  # Disable page-level routing
        "garbled_threshold": 0.5,         # Higher = fewer triggers
        "max_text_length": 500,           # Lower limit
    }
}
```

#### 3. Import Errors

**Problem**: `ModuleNotFoundError`

**Solution**: Ensure file is in correct location
```bash
ls marker/processors/llm/llm_quality_ocr.py
# Should exist
```

---

## Next Steps

1. **Start with Balanced Config**: Use the recommended balanced configuration
2. **Monitor Costs**: Track LLM API usage
3. **Adjust Thresholds**: Based on your document types
4. **Add Custom Checks**: Extend the processor for your use case

---

## Support

- Check logs with DEBUG level for detailed routing decisions
- Review the main documentation: `QUALITY_BASED_LLM_OCR.md`
- Test with small batches first
- Monitor LLM costs closely

---

**Version**: 1.0.0
**Last Updated**: 2024
