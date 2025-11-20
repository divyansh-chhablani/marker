"""
Quality-based LLM OCR Processor

This processor intelligently routes blocks to LLM for re-OCR based on quality indicators.
It only processes blocks where Surya OCR quality is questionable, optimizing for cost/quality balance.

Quality Indicators Used:
1. page.ocr_errors_detected - Page-level OCR quality from OCRErrorPredictor
2. Text garbling detection - High ratio of non-alphanumeric characters
3. Text length - Avoid too short (not worth cost) or too long (cost control)

Author: Enhanced Marker Team
License: GPL-3.0
"""

from typing import List, Annotated, Tuple, Dict
from marker.processors.llm import BaseLLMSimpleBlockProcessor, PromptData, BlockData
from marker.schema import BlockTypes
from marker.schema.document import Document
from pydantic import BaseModel
from marker.logger import get_logger

logger = get_logger()


class QualityBasedLLMOCRProcessor(BaseLLMSimpleBlockProcessor):
    """
    Routes blocks to LLM for re-OCR based on quality indicators.

    This processor analyzes OCR quality using multiple heuristics and only sends
    problematic blocks to the LLM for re-extraction, balancing quality and cost.

    Quality Checks:
    - Page-level OCR errors (from OCRErrorPredictor model)
    - Text garbling detection (special character ratio)
    - Text length validation (cost control)

    The processor marks re-OCR'd blocks with text_extraction_method="gemini"
    """

    block_types = (
        BlockTypes.Text,
        BlockTypes.SectionHeader,
        BlockTypes.ListItem,
        BlockTypes.Footnote,
        BlockTypes.Caption,
        BlockTypes.Code,
    )

    # Quality thresholds for routing to LLM
    page_ocr_error_trigger: Annotated[
        bool,
        "If True, route blocks to LLM when page.ocr_errors_detected=True"
    ] = True

    min_text_length: Annotated[
        int,
        "Minimum text length to bother re-OCRing with LLM (cost control)"
    ] = 10

    max_text_length: Annotated[
        int,
        "Maximum text length to re-OCR with LLM (cost control)"
    ] = 1000

    check_garbled_text: Annotated[
        bool,
        "Enable garbled text detection based on special character ratio"
    ] = True

    garbled_threshold: Annotated[
        float,
        "If more than this ratio of chars are non-alphanumeric, consider garbled (0.0-1.0)"
    ] = 0.3

    include_original_as_hint: Annotated[
        bool,
        "Include original Surya OCR text in prompt as hint to LLM"
    ] = False

    llm_ocr_prompt = """You are an expert OCR system specializing in accurate text extraction from images.

**Instructions:**
1. Carefully examine the provided image
2. Extract ALL visible text from the image
3. Preserve formatting, line breaks, and structure exactly as shown
4. For mathematical expressions, use <math>LaTeX</math> tags
5. For bold text, use <b>text</b> tags
6. For italic text, use <i>text</i> tags
7. If text is unclear or illegible, do your best estimation
8. Maintain paragraph structure with <p> tags

**Output Format:**
- Clean, accurate HTML representation of the text
- Preserve all content visible in the image
- Use appropriate formatting tags

**Output only the extracted text in HTML format.**
"""

    def is_text_garbled(self, text: str) -> Tuple[bool, float]:
        """
        Check if text looks garbled based on special character ratio.

        Args:
            text: The text to analyze

        Returns:
            Tuple of (is_garbled, special_char_ratio)
        """
        if len(text) == 0:
            return False, 0.0

        # Count alphanumeric vs special chars
        alphanum_count = sum(c.isalnum() or c.isspace() for c in text)
        special_count = len(text) - alphanum_count

        special_ratio = special_count / len(text)
        is_garbled = special_ratio > self.garbled_threshold

        return is_garbled, special_ratio

    def should_reocr_with_llm(
        self, block, page, document: Document
    ) -> Tuple[bool, str, Dict]:
        """
        Determine if a block should be re-OCR'd with LLM.

        Args:
            block: The block to evaluate
            page: The page containing the block
            document: The document

        Returns:
            Tuple of (should_reocr, reason, metadata)
        """
        metadata = {}

        # Only re-OCR blocks that were OCR'd by Surya
        if block.text_extraction_method != "surya":
            return False, "not_surya_ocr", metadata

        # Check page-level quality
        if self.page_ocr_error_trigger and page.ocr_errors_detected:
            metadata["page_errors"] = True
            return True, "page_ocr_errors_detected", metadata

        # Get block text
        raw_text = block.raw_text(document)
        text_length = len(raw_text.strip())
        metadata["text_length"] = text_length

        # Too short - not worth LLM cost
        if text_length < self.min_text_length:
            return False, "text_too_short", metadata

        # Too long - cost control
        if text_length > self.max_text_length:
            return False, "text_too_long_cost_control", metadata

        # Check for garbled text
        if self.check_garbled_text:
            is_garbled, special_ratio = self.is_text_garbled(raw_text)
            metadata["special_char_ratio"] = round(special_ratio, 3)
            metadata["garbled_threshold"] = self.garbled_threshold

            if is_garbled:
                return True, "garbled_text_detected", metadata

        # Default: don't re-OCR, quality seems acceptable
        return False, "quality_acceptable", metadata

    def inference_blocks(self, document: Document) -> List[BlockData]:
        """
        Select blocks that need LLM re-OCR based on quality analysis.

        Args:
            document: The document to process

        Returns:
            List of BlockData for blocks that should be re-OCR'd
        """
        blocks = super().inference_blocks(document)
        out_blocks = []

        # Statistics tracking
        stats = {
            "total_evaluated": 0,
            "selected_for_llm": 0,
            "reasons": {},
            "pages_with_errors": set()
        }

        for block_data in blocks:
            block = block_data["block"]
            page = block_data["page"]
            stats["total_evaluated"] += 1

            # Evaluate quality
            should_reocr, reason, metadata = self.should_reocr_with_llm(
                block, page, document
            )

            # Track statistics
            stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1

            if should_reocr:
                out_blocks.append(block_data)
                stats["selected_for_llm"] += 1
                stats["pages_with_errors"].add(page.page_id)

                logger.debug(
                    f"Block {block.id} selected for LLM re-OCR. "
                    f"Reason: {reason}, Metadata: {metadata}"
                )

        # Log summary
        logger.info(
            f"QualityBasedLLMOCR: {stats['selected_for_llm']}/{stats['total_evaluated']} "
            f"blocks selected for LLM re-OCR across {len(stats['pages_with_errors'])} pages. "
            f"Breakdown: {stats['reasons']}"
        )

        return out_blocks

    def block_prompts(self, document: Document) -> List[PromptData]:
        """
        Generate prompts for LLM OCR.

        Args:
            document: The document to process

        Returns:
            List of prompt data for LLM processing
        """
        prompt_data = []

        for block_data in self.inference_blocks(document):
            block = block_data["block"]
            image = self.extract_image(document, block)

            # Get existing text
            existing_text = block.raw_text(document)

            # Build prompt
            prompt = self.llm_ocr_prompt

            # Optionally include original text as hint
            if self.include_original_as_hint and existing_text.strip():
                prompt += f"\n\n**Original OCR Result (may contain errors):**\n```\n{existing_text}\n```\n\nPlease provide the corrected extraction."

            prompt_data.append({
                "prompt": prompt,
                "image": image,
                "block": block,
                "schema": LLMOCRSchema,
                "page": block_data["page"],
                "additional_data": {
                    "original_text": existing_text,
                    "block_id": str(block.id)
                }
            })

        return prompt_data

    def rewrite_block(
        self, response: dict, prompt_data: PromptData, document: Document
    ):
        """
        Replace Surya OCR text with LLM OCR text.

        Args:
            response: LLM response containing extracted text
            prompt_data: Original prompt data
            document: The document being processed
        """
        block = prompt_data["block"]
        additional_data = prompt_data.get("additional_data", {})
        original_text = additional_data.get("original_text", "")
        block_id = additional_data.get("block_id", "unknown")

        # Validate response
        if not response or "extracted_text" not in response:
            block.update_metadata(llm_error_count=1)
            logger.warning(f"LLM OCR failed for block {block_id} - no response")
            return

        extracted_text = response["extracted_text"].strip()

        # Sanity checks
        if len(extracted_text) < 5:
            block.update_metadata(llm_error_count=1)
            logger.warning(
                f"LLM OCR returned very short text for block {block_id}: "
                f"'{extracted_text}' (original: {len(original_text)} chars)"
            )
            return

        # Check if extraction is suspiciously different in length
        length_ratio = len(extracted_text) / max(1, len(original_text))
        if length_ratio < 0.3 or length_ratio > 3.0:
            logger.warning(
                f"LLM OCR text length differs significantly for block {block_id}: "
                f"Original={len(original_text)} chars, New={len(extracted_text)} chars "
                f"(ratio={length_ratio:.2f})"
            )
            # Still proceed, but log the warning

        # Replace the block's text
        block.html = extracted_text
        block.text_extraction_method = "gemini"  # Mark as LLM-extracted

        logger.info(
            f"Block {block_id} successfully re-OCR'd with LLM. "
            f"Original: {len(original_text)} chars, New: {len(extracted_text)} chars"
        )


class LLMOCRSchema(BaseModel):
    """Schema for LLM OCR response."""
    extracted_text: str
