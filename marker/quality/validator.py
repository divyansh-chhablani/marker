"""
Quality validation for OCR extraction results

This module validates the quality of OCR extraction after it's complete,
checking text quality, table quality, and layout quality.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np

from marker.schema.groups.page import PageGroup
from marker.schema.document import Document
from marker.schema import BlockTypes
from marker.logger import get_logger

logger = get_logger()


class QualityLevel(Enum):
    """Quality level classifications"""
    EXCELLENT = "excellent"  # 0.90-1.00
    GOOD = "good"            # 0.70-0.89
    POOR = "poor"            # 0.50-0.69
    TERRIBLE = "terrible"    # 0.00-0.49


@dataclass
class ExtractionQualityMetrics:
    """Metrics for measuring extraction quality"""

    # Text-level metrics
    text_confidence: float = 0.0      # OCR confidence scores (0-1)
    text_completeness: float = 0.0    # % of page covered (0-1)
    garbled_ratio: float = 0.0        # Special char ratio (0-1)

    # Table-level metrics
    table_cell_count: int = 0         # Detected cells
    table_structure_valid: bool = False  # Valid rows/cols
    table_text_quality: float = 0.0   # Cell text quality (0-1)

    # Layout metrics
    reading_order_valid: bool = False  # Logical flow
    block_overlap: float = 0.0        # Blocks shouldn't overlap (0-1)

    # Overall
    overall_score: float = 0.0        # Combined score (0-1)


@dataclass
class ValidationResult:
    """Result of quality validation"""

    passed: bool                      # Overall pass/fail
    scores: Dict[str, float]          # Individual scores
    overall: float                    # Overall score (0-1)
    method: str                       # Extraction method used
    quality_level: QualityLevel      # Quality classification
    issues: List[str]                 # List of issues found
    metrics: ExtractionQualityMetrics  # Detailed metrics


class QualityValidator:
    """
    Validates extraction quality after OCR is complete

    Performs comprehensive quality checks on:
    - Text quality (garbling, completeness, confidence)
    - Table quality (structure, cell content)
    - Layout quality (overlap, reading order, coverage)
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize quality validator

        Args:
            config: Configuration dict with thresholds
        """
        self.config = config or {}

        # Thresholds
        self.garbled_threshold = self.config.get("garbled_threshold", 0.3)
        self.min_coverage = self.config.get("min_coverage", 0.7)
        self.min_confidence = self.config.get("min_confidence", 0.6)
        self.min_table_score = self.config.get("min_table_score", 0.7)
        self.passing_score = self.config.get("passing_score", 0.7)

    def validate_extraction(
        self,
        page: PageGroup,
        document: Document,
        extraction_method: str
    ) -> ValidationResult:
        """
        Validate extraction quality

        Args:
            page: The page to validate
            document: The document
            extraction_method: Method used ("surya", "llm_direct", etc.)

        Returns:
            ValidationResult with scores and pass/fail
        """
        issues = []

        # Check text quality
        text_quality = self.check_text_quality(page, document, issues)

        # Check table quality
        table_quality = self.check_table_quality(page, document, issues)

        # Check layout quality
        layout_quality = self.check_layout_quality(page, document, issues)

        # Compute overall score
        scores = {
            "text_quality": text_quality,
            "table_quality": table_quality,
            "layout_quality": layout_quality,
        }

        overall_score = self.compute_overall_score(scores)

        # Determine quality level
        quality_level = self.classify_quality_level(overall_score)

        # Determine pass/fail
        passed = overall_score >= self.passing_score

        # Build metrics
        metrics = ExtractionQualityMetrics(
            overall_score=overall_score,
            # TODO: Populate other metrics
        )

        logger.info(
            f"Page {page.page_id} validation: "
            f"score={overall_score:.2f}, "
            f"level={quality_level.value}, "
            f"passed={passed}, "
            f"method={extraction_method}"
        )

        return ValidationResult(
            passed=passed,
            scores=scores,
            overall=overall_score,
            method=extraction_method,
            quality_level=quality_level,
            issues=issues,
            metrics=metrics
        )

    def check_text_quality(
        self,
        page: PageGroup,
        document: Document,
        issues: List[str]
    ) -> float:
        """
        Validate text extraction quality

        Checks:
        - Garbled text (high special char ratio)
        - Incomplete extraction (low coverage)
        - Low confidence scores

        Args:
            page: Page to check
            document: Document
            issues: List to append issues to

        Returns:
            Text quality score (0-1)
        """
        text_blocks = page.contained_blocks(
            document,
            [BlockTypes.Text, BlockTypes.SectionHeader, BlockTypes.ListItem]
        )

        if not text_blocks:
            issues.append("No text blocks found")
            return 0.0

        garbled_count = 0
        total_length = 0

        for block in text_blocks:
            text = block.raw_text(document)
            total_length += len(text)

            # Check for garbled text
            garbled_ratio = self.compute_garbled_ratio(text)
            if garbled_ratio > self.garbled_threshold:
                garbled_count += 1
                issues.append(
                    f"Block {block.id} is garbled "
                    f"(special char ratio: {garbled_ratio:.2f})"
                )

        # Compute garbled penalty
        garbled_penalty = garbled_count / len(text_blocks) if text_blocks else 0

        # Check coverage (placeholder - needs page analysis)
        coverage = 1.0  # TODO: Implement coverage calculation
        if coverage < self.min_coverage:
            issues.append(f"Low text coverage: {coverage:.2f}")

        # Combine scores
        text_score = (
            0.5 * (1 - garbled_penalty) +
            0.5 * coverage
        )

        return text_score

    def check_table_quality(
        self,
        page: PageGroup,
        document: Document,
        issues: List[str]
    ) -> float:
        """
        Validate table extraction quality

        Checks:
        - Table structure validity
        - Cell text quality
        - Empty cell ratio

        Args:
            page: Page to check
            document: Document
            issues: List to append issues to

        Returns:
            Table quality score (0-1)
        """
        tables = page.contained_blocks(document, [BlockTypes.Table])

        if not tables:
            return 1.0  # No tables, no problem

        table_scores = []

        for table in tables:
            cells = table.contained_blocks(document, [BlockTypes.TableCell])

            if not cells:
                issues.append(f"Table {table.id} has no cells")
                table_scores.append(0.0)
                continue

            # Check structure validity
            structure_valid = self.validate_table_structure(cells)
            if not structure_valid:
                issues.append(f"Table {table.id} has invalid structure")

            # Check cell text quality
            cell_qualities = []
            empty_count = 0

            for cell in cells:
                cell_text = cell.raw_text(document)
                if not cell_text.strip():
                    empty_count += 1
                else:
                    # Check cell text quality
                    garbled = self.compute_garbled_ratio(cell_text)
                    cell_qualities.append(1 - garbled)

            avg_cell_quality = (
                np.mean(cell_qualities) if cell_qualities else 0.0
            )
            empty_ratio = empty_count / len(cells)

            # Compute table score
            table_score = (
                0.4 * (1.0 if structure_valid else 0.0) +
                0.4 * avg_cell_quality +
                0.2 * (1 - empty_ratio)
            )

            table_scores.append(table_score)

            if table_score < self.min_table_score:
                issues.append(
                    f"Table {table.id} quality low: {table_score:.2f}"
                )

        return np.mean(table_scores)

    def check_layout_quality(
        self,
        page: PageGroup,
        document: Document,
        issues: List[str]
    ) -> float:
        """
        Validate layout detection quality

        Checks:
        - Block overlap
        - Reading order
        - Page coverage

        Args:
            page: Page to check
            document: Document
            issues: List to append issues to

        Returns:
            Layout quality score (0-1)
        """
        blocks = page.structure_blocks(document)

        if not blocks:
            issues.append("No structure blocks found")
            return 0.0

        # Check for overlapping blocks
        overlap_penalty = self.compute_overlap_penalty(blocks)
        if overlap_penalty > 0.1:
            issues.append(f"Block overlap detected: {overlap_penalty:.2f}")

        # Reading order (placeholder - needs implementation)
        reading_order_valid = True  # TODO: Implement reading order check

        # Coverage (placeholder)
        coverage = 1.0  # TODO: Implement coverage calculation

        layout_score = (
            0.3 * (1 - overlap_penalty) +
            0.4 * (1.0 if reading_order_valid else 0.0) +
            0.3 * coverage
        )

        return layout_score

    def compute_garbled_ratio(self, text: str) -> float:
        """
        Compute ratio of special/non-alphanumeric characters

        Args:
            text: Text to analyze

        Returns:
            Ratio of special chars (0-1)
        """
        if not text:
            return 0.0

        alphanum_count = sum(c.isalnum() or c.isspace() for c in text)
        special_count = len(text) - alphanum_count

        return special_count / len(text)

    def validate_table_structure(self, cells: List) -> bool:
        """
        Validate table structure (rows and columns)

        Args:
            cells: List of table cells

        Returns:
            True if structure is valid
        """
        if not cells:
            return False

        # Check if all cells have row_id and col_id
        has_row_col = all(
            hasattr(cell, 'row_id') and hasattr(cell, 'col_id')
            for cell in cells
        )

        if not has_row_col:
            return False

        # Check for consistent structure
        rows = set(cell.row_id for cell in cells)
        cols = set(cell.col_id for cell in cells)

        # Should have at least 1 row and 1 column
        return len(rows) > 0 and len(cols) > 0

    def compute_overlap_penalty(self, blocks: List) -> float:
        """
        Compute penalty for overlapping blocks

        Args:
            blocks: List of blocks

        Returns:
            Overlap penalty (0-1)
        """
        # TODO: Implement proper overlap detection
        return 0.0

    def compute_overall_score(self, scores: Dict[str, float]) -> float:
        """
        Compute overall quality score from individual scores

        Args:
            scores: Dict of individual scores

        Returns:
            Overall score (0-1)
        """
        # Weighted average
        weights = {
            "text_quality": 0.5,
            "table_quality": 0.3,
            "layout_quality": 0.2,
        }

        overall = sum(
            scores.get(key, 0) * weight
            for key, weight in weights.items()
        )

        return overall

    def classify_quality_level(self, score: float) -> QualityLevel:
        """
        Classify quality score into level

        Args:
            score: Quality score (0-1)

        Returns:
            QualityLevel enum
        """
        if score >= 0.90:
            return QualityLevel.EXCELLENT
        elif score >= 0.70:
            return QualityLevel.GOOD
        elif score >= 0.50:
            return QualityLevel.POOR
        else:
            return QualityLevel.TERRIBLE
