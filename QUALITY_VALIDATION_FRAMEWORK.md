# Quality Validation Framework for LLM-Based OCR

## Overview

This document defines a comprehensive quality validation framework for the enhanced Marker architecture that uses direct LLM extraction with intelligent routing based on quality pre-checks and post-validation.

## Architecture

### Quality Check Points

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PRE-CHECK (Before OCR)                                   │
│    ↓ Predict: "Will Surya work well here?"                 │
│                                                              │
│ 2. EXTRACTION (Surya OR LLM)                                │
│    ↓ Perform OCR/extraction                                 │
│                                                              │
│ 3. POST-VALIDATION (After OCR)                              │
│    ↓ Verify: "Did the extraction work well?"               │
│                                                              │
│ 4. COMPARISON (Optional)                                    │
│    ↓ Compare: "Which method was better?"                    │
│                                                              │
│ 5. FEEDBACK LOOP                                            │
│    ↓ Learn: "Update quality predictor"                      │
└─────────────────────────────────────────────────────────────┘
```

## Quality Metrics

### 1. Extraction Quality Metrics

```python
class ExtractionQualityMetrics:
    """Measure quality of extracted content"""

    # Text-level metrics
    text_confidence: float          # OCR confidence scores (0-1)
    text_completeness: float        # % of page covered (0-1)
    garbled_ratio: float           # Special char ratio (0-1)

    # Table-level metrics
    table_cell_count: int          # Detected cells
    table_structure_valid: bool    # Valid rows/cols
    table_text_quality: float      # Cell text quality (0-1)

    # Layout metrics
    reading_order_valid: bool      # Logical flow
    block_overlap: float           # Blocks shouldn't overlap (0-1)

    # Comparison metrics
    surya_vs_llm_diff: float       # If both run, how different?
    ground_truth_match: float      # If GT available
```

### 2. Quality Levels

| Level | Score Range | Description | Action |
|-------|-------------|-------------|--------|
| EXCELLENT | 0.90 - 1.00 | Perfect extraction | Accept immediately |
| GOOD | 0.70 - 0.89 | Minor issues | Accept with monitoring |
| POOR | 0.50 - 0.69 | Significant issues | Consider retry |
| TERRIBLE | 0.00 - 0.49 | Unusable extraction | Retry with different method |

## Components

### 1. Quality Predictor (Pre-Check)

**Purpose**: Predict extraction quality BEFORE running OCR

**Input**: Page image
**Output**: Prediction of whether Surya will succeed

```python
class QualityPredictor:
    def predict_surya_success(self, page_image) -> Prediction:
        """
        Predict if Surya OCR will produce good results

        Features considered:
        - Image quality (resolution, contrast, blur, noise)
        - Content complexity (tables, handwriting, layout)
        - Historical performance (OCRErrorPredictor)

        Returns:
            Prediction with:
            - surya_will_succeed: bool
            - confidence: float (0-1)
            - recommendation: "surya" or "llm"
        """
```

**Features**:
- **Image Quality**
  - Resolution (DPI)
  - Contrast ratio
  - Blur score (Laplacian variance)
  - Noise level (SNR)

- **Content Complexity**
  - Has tables (YOLO/layout detection)
  - Has handwriting (ML classifier)
  - Complex layout (column detection)
  - Text density (% of page)

- **Historical**
  - OCRErrorPredictor score (existing Surya model)
  - Document type classifier
  - Previous success rate for similar pages

### 2. Quality Validator (Post-Check)

**Purpose**: Validate extraction quality AFTER it's complete

**Input**: Extracted page data
**Output**: Quality score and validation decision

```python
class QualityValidator:
    def validate_extraction(
        self,
        page: PageGroup,
        extraction_method: str
    ) -> ValidationResult:
        """
        Check if extraction meets quality standards

        Checks:
        - Text quality (garbling, completeness, confidence)
        - Table quality (structure, cell content)
        - Layout quality (overlap, reading order, coverage)

        Returns:
            ValidationResult with:
            - passed: bool
            - scores: dict
            - overall: float (0-1)
        """
```

**Validation Checks**:

#### Text Quality
```python
def check_text_quality(self, page) -> float:
    issues = []

    # Garbled text detection
    for block in page.text_blocks():
        garbled_ratio = compute_garbled_ratio(block.text)
        if garbled_ratio > 0.3:
            issues.append(f"Block {block.id} garbled")

    # Coverage check
    coverage = compute_text_coverage(page)
    if coverage < 0.7:
        issues.append(f"Low coverage: {coverage}")

    # Confidence check (if available)
    avg_confidence = get_average_confidence(page)
    if avg_confidence < 0.6:
        issues.append(f"Low confidence: {avg_confidence}")

    return 1.0 - (len(issues) / 10)
```

#### Table Quality
```python
def check_table_quality(self, page) -> float:
    tables = page.get_tables()
    scores = []

    for table in tables:
        cells = table.get_cells()

        # Structure validation
        has_valid_structure = validate_table_structure(cells)

        # Cell text quality
        cell_quality = mean([
            check_cell_text_quality(cell) for cell in cells
        ])

        # Empty cell ratio
        empty_ratio = count_empty_cells(cells) / len(cells)

        score = (
            0.4 * has_valid_structure +
            0.4 * cell_quality +
            0.2 * (1 - empty_ratio)
        )
        scores.append(score)

    return mean(scores)
```

#### Layout Quality
```python
def check_layout_quality(self, page) -> float:
    blocks = page.structure_blocks()

    # Overlap penalty
    overlap = compute_block_overlap(blocks)

    # Reading order validation
    reading_order_valid = validate_reading_order(blocks)

    # Coverage
    coverage = compute_block_coverage(blocks, page)

    return (
        0.3 * (1 - overlap) +
        0.4 * reading_order_valid +
        0.3 * coverage
    )
```

### 3. Extraction Comparator (A/B Testing)

**Purpose**: Compare Surya vs LLM on same pages

**Use Cases**:
- Validate routing decisions
- Build training data
- Improve quality predictor

```python
class ExtractionComparator:
    def compare_methods(
        self,
        page_image,
        ground_truth=None
    ) -> ComparisonResult:
        """
        Run BOTH methods, compare results

        Returns:
            ComparisonResult with:
            - surya_score: float
            - llm_score: float
            - winner: "surya" or "llm"
            - score_diff: float
            - surya_accuracy: float (if GT available)
            - llm_accuracy: float (if GT available)
        """
```

### 4. Quality Learner (Feedback Loop)

**Purpose**: Learn from results to improve predictions

```python
class QualityLearner:
    def record_result(
        self,
        prediction: Prediction,
        actual_quality: ValidationResult
    ):
        """Record prediction vs actual outcome"""

    def retrain_predictor(self):
        """Retrain quality predictor based on collected data"""
```

**Learning Process**:
1. Record every prediction and outcome
2. Store features and actual quality scores
3. Periodically retrain predictor model
4. Evaluate prediction accuracy
5. Deploy improved model

## Complete Pipeline

### Quality-Aware OCR Pipeline

```python
class QualityAwareOcrPipeline:
    def process_page(
        self,
        page: PageGroup,
        validate_quality: bool = True,
        compare_methods: bool = False
    ) -> ProcessingResult:
        """
        Process page with quality checks at every stage

        Steps:
        1. Pre-check: Predict quality
        2. Extract: Run Surya or LLM
        3. Validate: Check extraction quality
        4. Decide: Accept, retry, or fallback
        5. Learn: Record results
        6. Compare: Optional A/B test
        """
```

**Flow Diagram**:
```
Page Image
    ↓
┌───────────────────┐
│ Quality Predictor │
└───────────────────┘
    ↓
Prediction: Surya (0.8 confidence) or LLM (0.2 confidence)
    ↓
┌─────────────┐         ┌──────────────┐
│ Surya OCR   │   OR    │ LLM Direct   │
└─────────────┘         └──────────────┘
    ↓
Extracted Content
    ↓
┌───────────────────┐
│ Quality Validator │
└───────────────────┘
    ↓
Validation: PASSED (0.85) or FAILED (0.45)
    ↓
┌────────────────────┐
│ Decision:          │
│ - Accept           │
│ - Retry with LLM   │
│ - Fallback         │
└────────────────────┘
    ↓
┌───────────────────┐
│ Quality Learner   │
│ (Record result)   │
└───────────────────┘
```

## Decision Logic

### Routing Decision Tree

```python
def decide_extraction_method(page_image) -> str:
    """Decide which extraction method to use"""

    prediction = quality_predictor.predict_surya_success(page_image)

    if prediction.surya_will_succeed:
        if prediction.confidence > 0.8:
            return "surya"  # High confidence
        else:
            return "surya_with_validation"  # Medium confidence
    else:
        if has_tables(page_image):
            return "llm_direct"  # Tables often fail with Surya
        elif has_handwriting(page_image):
            return "llm_direct"  # Handwriting needs LLM
        else:
            return "llm_direct"  # Low confidence in Surya
```

### Post-Validation Decision Tree

```python
def decide_after_validation(
    validation: ValidationResult,
    extraction_method: str
) -> str:
    """Decide what to do after validation"""

    if validation.overall >= 0.8:
        return "accept"  # Good quality

    if validation.overall >= 0.6:
        if extraction_method == "surya":
            return "accept_with_warning"  # Acceptable
        else:
            return "accept"  # LLM result is acceptable

    # Poor quality
    if extraction_method == "surya":
        return "retry_with_llm"  # Escalate to LLM
    elif extraction_method == "llm_direct":
        return "try_fallback"  # Try Surya as fallback

    return "accept_best_effort"  # All methods failed
```

## Metrics & Monitoring

### Key Performance Indicators

| KPI | Target | Measurement |
|-----|--------|-------------|
| Prediction Accuracy | >80% | Compare prediction vs actual quality |
| Overall Quality Score | >90% | Average validation score |
| Table Extraction Accuracy | >95% | Manual review + ground truth |
| Cost per Document | <$0.50 | Track LLM API usage |
| Failed Page Rate | <5% | Pages with quality <0.7 |
| Surya Usage Rate | >70% | Routing decisions |

### Quality Reports

```python
class QualityReporter:
    def generate_document_report(self, document: Document) -> Report:
        """
        Generate comprehensive quality report

        Includes:
        - Extraction method breakdown
        - Quality score distribution
        - Failed pages details
        - Cost estimation
        - Success rate
        """
```

**Sample Report**:
```
Quality Report: document.pdf
============================================================

Pages: 50
Average Quality: 87.5%
Success Rate: 94.0%
Estimated Cost: $0.35

Extraction Methods:
  Surya: 38 pages (76%)
  LLM Direct: 12 pages (24%)

Quality Distribution:
  Excellent (>90%): 30 pages
  Good (70-90%):    17 pages
  Poor (<70%):      3 pages

Failed Pages (3):
  Page 12: 0.65 (surya) - Complex table
  Page 28: 0.58 (surya) - Handwriting detected
  Page 45: 0.62 (llm_direct) - Poor image quality
```

## Implementation Phases

### Phase 1: Basic Quality Validation (Week 1)
- ✅ Implement `QualityValidator`
- ✅ Add post-validation to existing pipeline
- ✅ Track quality metrics
- ✅ Generate reports

### Phase 2: Quality Prediction (Week 2)
- ✅ Implement `QualityPredictor`
- ✅ Extract image quality features
- ✅ Extract content complexity features
- ✅ Integrate with OCRErrorPredictor
- ✅ Build initial prediction model

### Phase 3: Intelligent Routing (Week 3)
- ✅ Implement routing logic
- ✅ Add fallback strategies
- ✅ Implement retry mechanisms
- ✅ Add decision logging

### Phase 4: Learning & Optimization (Week 4)
- ✅ Implement `QualityLearner`
- ✅ Build training data collection
- ✅ Implement model retraining
- ✅ Add A/B testing framework

## Testing Strategy

### Unit Tests

```python
def test_quality_validator():
    """Test quality validation logic"""
    # Test text quality check
    # Test table quality check
    # Test layout quality check
    # Test overall scoring

def test_quality_predictor():
    """Test quality prediction"""
    # Test feature extraction
    # Test prediction accuracy
    # Test edge cases

def test_routing_logic():
    """Test routing decisions"""
    # Test Surya routing
    # Test LLM routing
    # Test fallback logic
```

### Integration Tests

```python
def test_end_to_end_pipeline():
    """Test complete pipeline with quality checks"""
    # Process sample PDFs
    # Validate all quality checks run
    # Verify routing decisions
    # Check quality scores

def test_ab_comparison():
    """Test A/B comparison framework"""
    # Run both methods on same pages
    # Compare results
    # Validate winner selection
```

### Quality Benchmarks

Create benchmark dataset with:
- Clean PDFs (expect Surya success)
- Scanned PDFs (expect mixed results)
- Complex tables (expect LLM routing)
- Handwritten pages (expect LLM routing)
- Poor quality scans (expect LLM routing)

## Cost Optimization

### Cost Control Strategies

1. **Prediction-Based Routing**
   - Use cheap Surya for predicted-good pages
   - Use expensive LLM only when needed

2. **Block-Level Extraction**
   - Extract only problematic regions with LLM
   - Use Surya for simple text

3. **Caching**
   - Cache LLM results by page hash
   - Avoid re-processing identical pages

4. **Batch Processing**
   - Batch LLM requests
   - Reduce API call overhead

### Cost Estimation

| Scenario | Pages | Surya % | LLM % | Cost |
|----------|-------|---------|-------|------|
| Clean PDFs | 100 | 95% | 5% | $0.05 |
| Scanned PDFs | 100 | 70% | 30% | $0.30 |
| Complex Documents | 100 | 40% | 60% | $0.60 |

## Validation Checklist

Before deployment, verify:

- [ ] Quality predictor accuracy >80%
- [ ] Post-validation catches bad extractions
- [ ] A/B tests validate routing decisions
- [ ] Feedback loop is active
- [ ] All metrics are tracked
- [ ] Reports are generated correctly
- [ ] Cost is within budget
- [ ] Fallback mechanisms work
- [ ] Error handling is robust
- [ ] Logging is comprehensive

## Success Criteria

| Criterion | Metric | Target | Validation |
|-----------|--------|--------|------------|
| Extraction Quality | Avg validation score | >90% | Automated checks |
| Table Accuracy | Manual review | >95% | Ground truth comparison |
| Prediction Accuracy | Prediction vs actual | >80% | Historical data |
| Cost Efficiency | Cost per document | <$0.50 | API usage tracking |
| Reliability | Failed page rate | <5% | Quality scores |
| Performance | Processing time | <10s/page | Benchmarks |

## Next Steps

1. **Implement basic validation** (Week 1)
2. **Add quality prediction** (Week 2)
3. **Integrate routing logic** (Week 3)
4. **Enable feedback loop** (Week 4)
5. **Optimize and tune** (Ongoing)

## References

- [Quality-Based LLM OCR Documentation](QUALITY_BASED_LLM_OCR.md)
- [Integration Guide](INTEGRATION_GUIDE.md)
- [Task Definition](TASK_DEFINITION_LLM_DIRECT_OCR.md)

---

**Version**: 1.0.0
**Last Updated**: 2024
**Author**: Enhanced Marker Team
