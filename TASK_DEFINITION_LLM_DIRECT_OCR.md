# Task Definition: Direct LLM-Based OCR with Quality Validation

## Executive Summary

**Problem**: Current Marker architecture uses Surya OCR first, then LLM for correction. This two-pass approach fails for complex content (tables, handwriting) because LLM corrections are limited by poor initial Surya results.

**Solution**: Implement quality-based routing that predicts extraction quality BEFORE OCR and routes problematic pages directly to LLM, bypassing Surya entirely for difficult content.

**Expected Impact**:
- 📈 Table extraction accuracy: 80% → 95%
- 📈 Overall quality: 85% → 92%
- 💰 Cost control: <$0.50 per document
- ⚡ Performance: <10s per page

---

## Current vs Proposed Architecture

### Current Architecture
```
PDF → Surya OCR → Quality Check → {
    Good: Use Surya results ✅
    Bad: LLM corrects Surya OCR 🔄
}
```

**Problems**:
1. ❌ Surya OCR errors compound (structure + text errors)
2. ❌ LLM correction limited by bad OCR input
3. ❌ Two-pass processing doesn't always work
4. ❌ Tables and complex text still fail

### Proposed Architecture
```
PDF → Quality Pre-Check → {
    Predicted Good: Surya OCR (fast, cheap) ✅
    Predicted Bad: LLM Direct Extraction 🎯
} → Post-Validation → {
    Quality OK: Accept ✅
    Quality Bad: Retry/Fallback 🔄
}
```

**Benefits**:
1. ✅ Skip problematic Surya OCR entirely
2. ✅ LLM extracts from clean images
3. ✅ Single-pass for difficult content
4. ✅ Post-validation catches remaining issues

---

## Detailed Task Breakdown

### Phase 1: Quality Pre-Assessment (Week 1)

**Objective**: Predict page quality BEFORE any OCR

#### Tasks

**1.1 Leverage Existing Quality Detection**
- ✅ Use `OCRErrorPredictor` from Surya (already exists)
- ✅ Accessible at `marker/builders/line.py:152`
- ✅ Sets `page.ocr_errors_detected` flag

**1.2 Add Image Quality Heuristics**
```python
class ImageQualityAnalyzer:
    def analyze(self, page_image) -> ImageQuality:
        return ImageQuality(
            resolution_dpi=self.get_dpi(page_image),
            contrast_ratio=self.get_contrast(page_image),
            blur_score=self.get_blur_score(page_image),  # Laplacian
            noise_level=self.get_noise_level(page_image),  # SNR
        )
```

**1.3 Add Content Complexity Heuristics**
```python
class ContentComplexityAnalyzer:
    def analyze(self, page_image) -> ContentComplexity:
        return ContentComplexity(
            has_tables=self.detect_tables(page_image),
            has_handwriting=self.detect_handwriting(page_image),
            has_complex_layout=self.detect_complex_layout(page_image),
            text_density=self.compute_text_density(page_image),
        )
```

**1.4 Create Quality Scoring System**
```python
class PageQualityScorer:
    def score_page(self, page_image) -> QualityScore:
        # Combine all signals
        ocr_error_score = self.ocr_error_predictor(page_image)
        image_quality = self.image_analyzer.analyze(page_image)
        content_complexity = self.content_analyzer.analyze(page_image)

        # Predict success probability
        success_prob = self.model.predict(
            ocr_error_score, image_quality, content_complexity
        )

        return QualityScore(
            success_probability=success_prob,
            recommendation="surya" if success_prob > 0.7 else "llm",
            confidence=success_prob,
        )
```

**Deliverables**:
- [ ] `marker/quality/predictor.py` - Quality prediction module
- [ ] `marker/quality/features.py` - Feature extraction
- [ ] Integration with existing OCRErrorPredictor
- [ ] Unit tests for quality scoring
- [ ] Benchmark on sample PDFs

---

### Phase 2: Direct LLM Extraction Builder (Week 2)

**Objective**: Create builder for LLM-based primary OCR

#### Tasks

**2.1 Create LLMOcrBuilder Class**
```python
class LLMOcrBuilder(BaseBuilder):
    """
    Performs OCR using LLM instead of Surya

    Extracts:
    - Text blocks with positions
    - Tables with structure
    - Equations in LaTeX
    - Forms with fields
    - Figures with descriptions
    """

    def __call__(self, document: Document, provider: PdfProvider):
        # Get pages that need LLM extraction
        llm_pages = [p for p in document.pages if p.needs_llm_ocr]

        for page in llm_pages:
            page_image = page.get_image(highres=True)
            extraction = self.llm_extract_page(page_image)
            self.build_blocks_from_extraction(page, extraction)
```

**2.2 Design LLM Prompts**
```python
FULL_PAGE_EXTRACTION_PROMPT = """
You are an expert OCR system. Extract ALL content from this page.

Return JSON with:
{
  "text_blocks": [
    {"text": "...", "bbox": [x1, y1, x2, y2], "type": "paragraph"},
    ...
  ],
  "tables": [
    {"rows": [[...]], "bbox": [x1, y1, x2, y2]},
    ...
  ],
  "equations": [
    {"latex": "...", "bbox": [x1, y1, x2, y2], "display": true},
    ...
  ],
  "figures": [
    {"description": "...", "bbox": [x1, y1, x2, y2]},
    ...
  ]
}

Maintain reading order and spatial layout.
"""

TABLE_EXTRACTION_PROMPT = """
Extract this table completely.

Return JSON:
{
  "headers": ["col1", "col2", ...],
  "rows": [["val1", "val2", ...], ...],
  "merged_cells": [{"row": 0, "col": 0, "rowspan": 2, "colspan": 1}]
}
"""
```

**2.3 Handle Block Type Extraction**
- Text extraction with layout preservation
- Table extraction (structure + content in one pass)
- Equation extraction with LaTeX conversion
- Form extraction with field detection
- Figure description generation

**Deliverables**:
- [ ] `marker/builders/llm_ocr.py` - LLM OCR builder
- [ ] `marker/prompts/extraction.py` - LLM prompts
- [ ] `marker/schema/llm_extraction.py` - Response schemas
- [ ] Block builders for each content type
- [ ] Integration tests

---

### Phase 3: Conditional Routing Logic (Week 3)

**Objective**: Route pages to Surya OR LLM based on quality

#### Tasks

**3.1 Create Routing Coordinator**
```python
class OcrRoutingCoordinator:
    """Routes pages to appropriate extraction method"""

    def route_document(self, document: Document):
        for page in document.pages:
            # Predict quality
            quality = self.quality_scorer.score_page(page.get_image())

            # Make routing decision
            if quality.recommendation == "surya":
                page.ocr_method = "surya"
                logger.info(f"Page {page.page_id}: Routing to Surya "
                           f"(confidence: {quality.confidence:.2f})")
            else:
                page.ocr_method = "llm_direct"
                logger.info(f"Page {page.page_id}: Routing to LLM "
                           f"(confidence: {quality.confidence:.2f})")
```

**3.2 Modify Document Builder Pipeline**
```python
# In marker/builders/document.py

def build_document(self, provider):
    document = Document(filepath=provider.filepath)

    # Step 1: Layout detection (unchanged)
    self.layout_builder(document, provider)

    # Step 2: QUALITY PRE-CHECK (NEW)
    self.quality_scorer.score_all_pages(document)

    # Step 3: CONDITIONAL OCR ROUTING (NEW)
    self.routing_coordinator.route_document(document)

    # Execute based on routing
    for page in document.pages:
        if page.ocr_method == "surya":
            self.surya_ocr_builder(page, provider)
        else:
            self.llm_ocr_builder(page, provider)

    # Step 4: Structure building (unchanged)
    self.structure_builder(document)

    return document
```

**3.3 Implement Fallback Strategies**
```python
class FallbackHandler:
    """Handle extraction failures with fallback logic"""

    def handle_failed_extraction(
        self,
        page: PageGroup,
        primary_method: str,
        validation_score: float
    ) -> str:
        """
        Decide fallback strategy

        Returns: fallback method to try
        """
        if primary_method == "surya" and validation_score < 0.6:
            return "llm_direct"  # Escalate to LLM

        elif primary_method == "llm_direct" and validation_score < 0.6:
            return "surya"  # Try Surya as fallback

        else:
            return "accept_best_effort"  # No good options
```

**Deliverables**:
- [ ] `marker/routing/coordinator.py` - Routing logic
- [ ] Modified `marker/builders/document.py`
- [ ] `marker/routing/fallback.py` - Fallback handling
- [ ] Decision logging and metrics
- [ ] Integration tests

---

### Phase 4: Quality Validation & Optimization (Week 4)

**Objective**: Validate extraction quality and optimize costs

#### Tasks

**4.1 Implement Post-Validation**
```python
class ExtractionValidator:
    """Validate extraction after it's complete"""

    def validate_and_decide(
        self,
        page: PageGroup,
        extraction_method: str
    ) -> ValidationDecision:
        # Check quality
        quality = self.quality_validator.validate_extraction(page)

        if quality.overall >= 0.8:
            return ValidationDecision("accept", quality.overall)

        # Quality too low - retry?
        if extraction_method == "surya":
            return ValidationDecision("retry_with_llm", quality.overall)
        else:
            return ValidationDecision("try_fallback", quality.overall)
```

**4.2 Add Block-Level LLM Extraction**
Instead of full page, extract only problematic regions:
```python
class HybridExtractor:
    """Mix Surya and LLM at block level"""

    def extract_page(self, page):
        # Use Surya for simple text
        simple_blocks = self.detect_simple_blocks(page)
        self.surya_ocr(simple_blocks)

        # Use LLM for complex regions
        complex_blocks = self.detect_complex_blocks(page)  # Tables, etc.
        self.llm_extract(complex_blocks)
```

**4.3 Implement Caching**
```python
class LLMResultCache:
    """Cache LLM results to avoid re-processing"""

    def get_or_extract(self, page_hash: str, page_image):
        if page_hash in self.cache:
            logger.info(f"Cache hit for page {page_hash}")
            return self.cache[page_hash]

        result = self.llm_service.extract(page_image)
        self.cache[page_hash] = result
        return result
```

**4.4 Cost Tracking**
```python
class CostTracker:
    """Track LLM API costs"""

    def track_extraction(self, method: str, page_size: tuple):
        if method == "llm_direct":
            # Estimate cost based on image size
            cost = self.estimate_cost(page_size)
            self.total_cost += cost
            self.llm_pages += 1
        else:
            self.surya_pages += 1

    def get_report(self) -> CostReport:
        return CostReport(
            total_cost=self.total_cost,
            llm_pages=self.llm_pages,
            surya_pages=self.surya_pages,
            avg_cost_per_page=self.total_cost / (self.llm_pages + self.surya_pages)
        )
```

**Deliverables**:
- [ ] `marker/quality/validator.py` - Post-validation
- [ ] `marker/extraction/hybrid.py` - Block-level extraction
- [ ] `marker/cache/llm_cache.py` - Result caching
- [ ] `marker/metrics/cost_tracker.py` - Cost tracking
- [ ] Performance benchmarks

---

## Special Focus: Tables

Tables are a primary pain point. Special handling:

### Option A: Direct LLM Table Extraction
```python
class LLMDirectTableExtractor:
    """Skip Surya TableRec, use LLM for everything"""

    def extract_table(self, table_image) -> Table:
        prompt = """
        Extract this table completely.

        Return JSON with:
        - headers: first row if present
        - rows: array of arrays
        - merged_cells: cells with rowspan/colspan
        - structure: row and column count
        """

        result = self.llm_service(prompt, table_image, TableSchema)
        return self.build_table_from_json(result)
```

### Option B: Hybrid Table Approach (Recommended)
```python
class HybridTableExtractor:
    """Use Surya for structure, LLM for content"""

    def extract_table(self, table_image) -> Table:
        # Step 1: Structure detection with Surya (fast, accurate)
        structure = self.surya_table_rec.detect_structure(table_image)

        # Step 2: Cell content with LLM (better than OCR)
        for cell in structure.cells:
            cell_image = self.crop_cell(table_image, cell.bbox)
            cell.text = self.llm_service.extract_text(cell_image)

        return structure
```

---

## Implementation Roadmap

### Week 1: Quality Pre-Assessment
- [ ] Day 1-2: Implement ImageQualityAnalyzer
- [ ] Day 3-4: Implement ContentComplexityAnalyzer
- [ ] Day 5: Integrate with OCRErrorPredictor
- [ ] Day 6-7: Build PageQualityScorer & test

### Week 2: LLM Direct Extraction
- [ ] Day 1-2: Create LLMOcrBuilder skeleton
- [ ] Day 3-4: Design and test LLM prompts
- [ ] Day 5: Implement block builders
- [ ] Day 6-7: Integration and testing

### Week 3: Routing Logic
- [ ] Day 1-2: Implement OcrRoutingCoordinator
- [ ] Day 3-4: Modify DocumentBuilder pipeline
- [ ] Day 5: Implement fallback strategies
- [ ] Day 6-7: End-to-end testing

### Week 4: Validation & Optimization
- [ ] Day 1-2: Implement post-validation
- [ ] Day 3-4: Add block-level extraction
- [ ] Day 5: Implement caching
- [ ] Day 6-7: Performance tuning & cost optimization

---

## Success Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Table extraction accuracy | 80% | 95% | Manual review + ground truth |
| Overall extraction quality | 85% | 92% | Automated validation scores |
| Quality prediction accuracy | N/A | 80% | Prediction vs actual quality |
| Cost per document | Variable | <$0.50 | API usage tracking |
| Processing time | ~5s/page | <10s/page | Performance benchmarks |
| Failed page rate | ~15% | <5% | Pages with quality <0.7 |
| Surya usage rate | 100% | >70% | Routing decision tracking |

---

## Key Decisions & Rationale

### Decision 1: Pre-Check vs Post-Check Routing

**Chosen**: Pre-check routing
**Rationale**:
- Avoids wasting compute on Surya OCR that will fail
- Faster single-pass extraction for difficult pages
- More cost-effective

### Decision 2: Full Page vs Block-Level LLM

**Chosen**: Start with full page, optimize to block-level later
**Rationale**:
- Simpler to implement initially
- Better context for LLM
- Can optimize in Phase 4

### Decision 3: Always-LLM vs Hybrid for Tables

**Chosen**: Hybrid approach (Surya structure + LLM content)
**Rationale**:
- Surya TableRec is good at structure detection
- LLM is better at cell text
- Most cost-effective combination

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM costs too high | High | Implement strict routing, caching, cost tracking |
| Quality prediction inaccurate | Medium | Start conservative, improve with feedback loop |
| LLM extraction slower | Medium | Parallel processing, optimize prompts |
| LLM API failures | Medium | Implement fallback to Surya, retry logic |
| Integration complexity | Low | Incremental rollout, extensive testing |

---

## Testing Strategy

### Unit Tests
- Quality predictor accuracy
- Routing decision logic
- Validation score calculation
- Fallback handling

### Integration Tests
- End-to-end pipeline with routing
- Mixed Surya/LLM document processing
- Failure and fallback scenarios

### Benchmark Tests
- Sample PDFs (clean, scanned, complex)
- Ground truth comparison
- Performance benchmarks
- Cost analysis

### A/B Tests
- Run both methods on same pages
- Compare quality scores
- Validate routing decisions
- Build training data

---

## Deployment Plan

### Phase 1: Internal Testing (Week 5)
- Deploy to development environment
- Process sample documents
- Collect metrics and feedback
- Tune thresholds

### Phase 2: Limited Rollout (Week 6)
- Enable for 10% of documents
- Monitor quality and costs
- Gather comparison data
- Refine prediction model

### Phase 3: Full Deployment (Week 7)
- Enable for all documents
- Continuous monitoring
- Feedback loop active
- Ongoing optimization

---

## Documentation

All components documented in:
- [Quality Validation Framework](QUALITY_VALIDATION_FRAMEWORK.md)
- [Quality-Based LLM OCR](QUALITY_BASED_LLM_OCR.md)
- [Integration Guide](INTEGRATION_GUIDE.md)
- [Developer Summary](DEVELOPER_SUMMARY.md)

---

## Next Actions

1. ✅ **Review this task definition** with team
2. ✅ **Prioritize phases** based on needs
3. ✅ **Allocate resources** (developers, API budget)
4. ✅ **Set up development environment**
5. ✅ **Begin Phase 1 implementation**

---

**Version**: 1.0.0
**Last Updated**: 2024
**Author**: Enhanced Marker Team
**Status**: Ready for Implementation
