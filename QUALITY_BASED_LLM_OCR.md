# Quality-Based LLM OCR for Marker

## Overview

This enhancement adds intelligent, quality-based routing to LLM for OCR re-extraction. Instead of using expensive LLM processing for all blocks, it analyzes OCR quality and only routes problematic blocks to the LLM, optimizing the cost/quality trade-off.

## 🎯 Problem Statement

The default Marker flow is:
```
PDF → Surya OCR → LLM Post-Processing (if use_llm=True)
```

**Issues:**
1. **LLM runs on ALL blocks** when `use_llm=True`, regardless of OCR quality
2. **High cost** for documents where most OCR is already good
3. **No selective routing** based on actual quality metrics

## ✨ Solution

The `QualityBasedLLMOCRProcessor` intelligently routes blocks to LLM based on quality indicators:

```
PDF → Surya OCR → Quality Analysis → {
    Good quality: Use Surya OCR ✅
    Poor quality: Re-OCR with LLM 🔄
}
```

## 📊 Quality Indicators

The processor uses multiple quality checks:

| Indicator | Source | Threshold | Description |
|-----------|--------|-----------|-------------|
| **Page OCR Errors** | `page.ocr_errors_detected` | Boolean | Set by Surya's OCRErrorPredictor model |
| **Garbled Text** | Character analysis | 30% special chars | Detects high ratio of non-alphanumeric characters |
| **Text Length** | Character count | 10-1000 chars | Cost control: skip too short/long blocks |
| **Extraction Method** | `text_extraction_method` | `"surya"` | Only re-OCR Surya extractions (not pdftext) |

## 🚀 Quick Start

### 1. Installation

The processor is already included in the Marker codebase at:
```
marker/processors/llm/llm_quality_ocr.py
```

### 2. Basic Usage

```python
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

# Load models
models = create_model_dict()

# Create converter with quality-based LLM routing
converter = PdfConverter(
    artifact_dict=models,
    config={
        "use_llm": True,  # Enable LLM processing

        # Quality-based routing configuration
        "QualityBasedLLMOCRProcessor": {
            "page_ocr_error_trigger": True,   # Route bad pages to LLM
            "check_garbled_text": True,       # Detect garbled text
            "garbled_threshold": 0.3,         # 30% special chars = garbled
            "min_text_length": 10,            # Skip very short blocks
            "max_text_length": 1000,          # Skip very long blocks
        }
    },
    processor_list=[
        # ... default processors ...
        "marker.processors.llm.llm_quality_ocr.QualityBasedLLMOCRProcessor",
    ],
    llm_service="marker.services.gemini.GoogleGeminiService"
)

# Process document
result = converter("document.pdf")
print(result)
```

### 3. Add to Default Processor List

To make it run automatically, edit `marker/converters/pdf.py`:

```python
from marker.processors.llm.llm_quality_ocr import QualityBasedLLMOCRProcessor

class PdfConverter(BaseConverter):
    default_processors: Tuple[BaseProcessor, ...] = (
        # ... existing processors ...
        LLMPageCorrectionProcessor,
        QualityBasedLLMOCRProcessor,  # Add this line
        ReferenceProcessor,
        # ... rest of processors ...
    )
```

## ⚙️ Configuration Options

### All Configuration Parameters

```python
config = {
    "QualityBasedLLMOCRProcessor": {
        # Page-level routing
        "page_ocr_error_trigger": True,  # Route entire pages with OCR errors

        # Garbled text detection
        "check_garbled_text": True,      # Enable garbling detection
        "garbled_threshold": 0.3,        # 30% special chars = garbled (0.0-1.0)

        # Cost control
        "min_text_length": 10,           # Skip blocks < 10 chars (not worth it)
        "max_text_length": 1000,         # Skip blocks > 1000 chars (too expensive)

        # LLM hints
        "include_original_as_hint": False,  # Send original OCR text to LLM as hint

        # Processor settings (inherited from BaseLLMProcessor)
        "max_concurrency": 3,            # Max parallel LLM requests
        "disable_tqdm": False,           # Show progress bars
        "use_llm": True,                 # Enable LLM (required)
    }
}
```

### Quality Tiers

Choose your tier based on cost/quality needs:

#### **Tier 1: Surya Only (Free)**
```python
config = {"use_llm": False}  # Don't use QualityBasedLLMOCRProcessor
```
- Cost: $0
- Quality: Good
- Speed: Fast

#### **Tier 2: LLM for Bad Pages (Recommended)**
```python
config = {
    "QualityBasedLLMOCRProcessor": {
        "page_ocr_error_trigger": True,
        "check_garbled_text": False,
    }
}
```
- Cost: $0.01 - $0.10 per document
- Quality: Very Good
- Speed: Fast

#### **Tier 3: LLM for Bad Pages + Garbled Text**
```python
config = {
    "QualityBasedLLMOCRProcessor": {
        "page_ocr_error_trigger": True,
        "check_garbled_text": True,
        "garbled_threshold": 0.3,
    }
}
```
- Cost: $0.10 - $0.50 per document
- Quality: Excellent
- Speed: Medium

#### **Tier 4: LLM for Everything**
Set `min_text_length: 0` and `max_text_length: 999999` to route all blocks:
```python
config = {
    "QualityBasedLLMOCRProcessor": {
        "page_ocr_error_trigger": True,
        "check_garbled_text": True,
        "min_text_length": 0,
        "max_text_length": 999999,
    }
}
```
- Cost: $1.00 - $10.00 per document
- Quality: Maximum
- Speed: Slow

## 🔍 How It Works

### Processing Flow

```
1. Surya OCR Builder runs (extracts text from all pages)
   ↓
2. QualityBasedLLMOCRProcessor evaluates each block:
   ↓
   ├─ Is text_extraction_method == "surya"?
   │   ├─ No → Skip (pdftext already good)
   │   └─ Yes → Continue
   ↓
   ├─ Is page.ocr_errors_detected == True?
   │   ├─ Yes → Route to LLM ✅
   │   └─ No → Continue
   ↓
   ├─ Is text length < min_text_length?
   │   ├─ Yes → Skip (not worth cost)
   │   └─ No → Continue
   ↓
   ├─ Is text length > max_text_length?
   │   ├─ Yes → Skip (cost control)
   │   └─ No → Continue
   ↓
   ├─ Is text garbled (>30% special chars)?
   │   ├─ Yes → Route to LLM ✅
   │   └─ No → Skip (quality OK)
   ↓
3. LLM re-extracts text for selected blocks
   ↓
4. Block text is replaced with LLM extraction
   Block is marked: text_extraction_method = "gemini"
```

### Quality Checks Explained

#### 1. **Page OCR Errors** (`page.ocr_errors_detected`)
- Set by Surya's `OCRErrorPredictor` model during line building
- Analyzes entire page quality before OCR
- Location: `marker/builders/line.py:152`

#### 2. **Garbled Text Detection**
```python
def is_text_garbled(text):
    alphanum = count(char.isalnum() or char.isspace())
    special = len(text) - alphanum
    ratio = special / len(text)
    return ratio > 0.3  # 30% threshold
```
Example garbled text: `§¶∞£¢€ƒ∂∑∏π∫ª`

#### 3. **Text Length Validation**
- **min_text_length (10)**: Blocks like "a" or "12" aren't worth LLM cost
- **max_text_length (1000)**: Very long blocks are expensive to re-OCR

## 📈 Performance & Cost

### Expected Performance

| Document Type | Blocks Evaluated | Blocks Sent to LLM | Cost Estimate |
|---------------|------------------|--------------------|-----------------|
| Clean PDF | 1000 | 0-50 (5%) | $0.01 - $0.05 |
| Scanned PDF | 1000 | 100-300 (15%) | $0.10 - $0.30 |
| Poor Quality Scan | 1000 | 500-800 (60%) | $0.50 - $0.80 |
| Handwritten Notes | 1000 | 800-1000 (90%) | $0.80 - $1.00 |

*Based on Gemini API pricing (~$0.001 per block with image)*

### Cost Optimization Tips

1. **Adjust `garbled_threshold`**: Higher = fewer LLM calls
   ```python
   "garbled_threshold": 0.5  # Only very garbled text
   ```

2. **Limit block length**: Skip very long blocks
   ```python
   "max_text_length": 500  # Only short blocks
   ```

3. **Disable garbled check**: Use only page-level errors
   ```python
   "check_garbled_text": False  # Cheaper
   ```

## 🔧 Troubleshooting

### Issue: No blocks being sent to LLM

**Check:**
1. Is `use_llm: True` in config?
2. Are there any pages with `ocr_errors_detected=True`?
3. Is `garbled_threshold` too high (>0.5)?
4. Check logs for routing decisions

**Solution:**
```python
# Enable debug logging
import logging
logging.getLogger("marker.processors.llm.llm_quality_ocr").setLevel(logging.DEBUG)

# Lower threshold
config = {"garbled_threshold": 0.2}
```

### Issue: Too many blocks being sent to LLM (high cost)

**Check:**
1. Are most pages flagged with `ocr_errors_detected=True`?
2. Is `garbled_threshold` too low (<0.2)?
3. Is `max_text_length` too high?

**Solution:**
```python
# Stricter routing
config = {
    "page_ocr_error_trigger": False,  # Disable page-level routing
    "check_garbled_text": True,
    "garbled_threshold": 0.4,         # Higher threshold
    "max_text_length": 500,           # Lower limit
}
```

### Issue: LLM returning empty/short text

**Possible causes:**
1. Image quality too poor for LLM
2. LLM rate limiting
3. Incorrect prompt

**Solution:**
```python
# Include original as hint
config = {"include_original_as_hint": True}
```

Check logs for `llm_error_count` metadata on blocks.

## 📝 Logging

The processor provides detailed logging:

```
INFO  - QualityBasedLLMOCR: 45/1000 blocks selected for LLM re-OCR across 5 pages.
        Breakdown: {'page_ocr_errors_detected': 30, 'garbled_text_detected': 15,
                   'quality_acceptable': 900, 'text_too_short': 50, 'not_surya_ocr': 5}

DEBUG - Block /page/2/Text/15 selected for LLM re-OCR.
        Reason: garbled_text_detected,
        Metadata: {'text_length': 145, 'special_char_ratio': 0.412, 'garbled_threshold': 0.3}

INFO  - Block /page/2/Text/15 successfully re-OCR'd with LLM.
        Original: 145 chars, New: 142 chars
```

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🧪 Testing

### Unit Test Example

```python
from marker.processors.llm.llm_quality_ocr import QualityBasedLLMOCRProcessor

def test_garbled_detection():
    processor = QualityBasedLLMOCRProcessor(llm_service=None, config={
        "garbled_threshold": 0.3
    })

    # Normal text
    is_garbled, ratio = processor.is_text_garbled("Hello world this is normal text")
    assert not is_garbled
    assert ratio < 0.3

    # Garbled text
    is_garbled, ratio = processor.is_text_garbled("§¶∞£¢€ƒ∂∑∏π∫ª")
    assert is_garbled
    assert ratio > 0.3

def test_quality_routing(document, page, block):
    processor = QualityBasedLLMOCRProcessor(llm_service=mock_llm)

    # Good quality block
    block.text_extraction_method = "pdftext"
    should_reocr, reason, _ = processor.should_reocr_with_llm(block, page, document)
    assert not should_reocr
    assert reason == "not_surya_ocr"

    # Bad page
    block.text_extraction_method = "surya"
    page.ocr_errors_detected = True
    should_reocr, reason, _ = processor.should_reocr_with_llm(block, page, document)
    assert should_reocr
    assert reason == "page_ocr_errors_detected"
```

## 🎓 Advanced Usage

### Custom Quality Heuristic

Extend the processor to add your own quality checks:

```python
from marker.processors.llm.llm_quality_ocr import QualityBasedLLMOCRProcessor

class CustomQualityOCRProcessor(QualityBasedLLMOCRProcessor):
    """Add custom quality checks"""

    def should_reocr_with_llm(self, block, page, document):
        # Call parent logic first
        should_reocr, reason, metadata = super().should_reocr_with_llm(
            block, page, document
        )

        if should_reocr:
            return should_reocr, reason, metadata

        # Add custom check: low confidence blocks
        if hasattr(block, 'confidence') and block.confidence < 0.7:
            metadata['confidence'] = block.confidence
            return True, "low_confidence_block", metadata

        return False, reason, metadata
```

### Batch Processing with Statistics

```python
from pathlib import Path
import json

def process_batch_with_stats(pdf_dir: Path, output_dir: Path):
    """Process multiple PDFs and collect statistics"""

    stats = {
        "total_docs": 0,
        "total_blocks": 0,
        "llm_blocks": 0,
        "cost_estimate": 0.0
    }

    for pdf_path in pdf_dir.glob("*.pdf"):
        converter = PdfConverter(
            artifact_dict=models,
            config={"use_llm": True}
        )

        result = converter(str(pdf_path))

        # Extract metadata (you'd need to modify processor to store this)
        stats["total_docs"] += 1
        # ... collect stats from document metadata ...

    # Save stats
    with open(output_dir / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    return stats
```

## 🤝 Contributing

To extend or improve the quality-based routing:

1. **Add new quality indicators**: Modify `should_reocr_with_llm()` method
2. **Improve prompts**: Edit `llm_ocr_prompt` for better LLM extraction
3. **Add new block types**: Extend `block_types` tuple
4. **Custom cost models**: Track LLM usage and optimize thresholds

## 📚 References

- [Marker Documentation](https://github.com/datalab-to/marker)
- [Surya OCR](https://github.com/datalab-to/surya)
- [Google Gemini API](https://ai.google.dev/docs)

## 📄 License

GPL-3.0 (same as Marker)

## 📧 Support

For issues or questions:
1. Check logs with DEBUG level enabled
2. Review configuration parameters
3. Test with different quality thresholds
4. Open an issue on GitHub

---

**Created by**: Enhanced Marker Team
**Version**: 1.0.0
**Last Updated**: 2024
