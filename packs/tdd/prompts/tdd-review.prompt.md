---
mode: ask
description: Review an existing test suite for TDD discipline, coverage quality, and architectural soundness.
---

Review an existing test suite for TDD discipline, test quality, and architectural soundness.

## Instructions

Use the `tddCycle`, `testCoverage`, `testDoubles`, and `testArchitecture` skills to structure
the review.

Ask for:
1. The test files or test directory to review (paste or describe)
2. The source files being tested (for boundary and coverage analysis)
3. Any known problem areas or recent regressions the review should focus on

Then produce a structured review covering four areas:

### 1. TDD Discipline Check
- Are tests written in isolation (one behavior per test)?
- Do test names describe behavior, not implementation?
- Are there tests that can never fail (assertion is always true)?
- Are there tests asserting the wrong thing (testing the mock, not the subject)?

### 2. Coverage Quality
- Which critical paths have no test coverage?
- Which tests have weak assertions (assert only that no exception was raised)?
- Are error/edge cases tested, or only the happy path?
- What is the ratio of assertion count to line count? (Low ratio = weak tests)

### 3. Test Doubles Audit
- Are the right double types used? (Stub where return value matters; mock where call verification matters; fake where stateful behavior is needed)
- Are any tests using real external dependencies (network, database, filesystem, clock)?
- Are mocks over-specified? (asserting call order or argument details that are implementation details)

### 4. Test Architecture
- Does the test suite follow the pyramid shape? (many unit, fewer integration, few e2e)
- Are there shared mutable fixtures between tests?
- Are test files organized to mirror the source tree?
- Do tests depend on execution order?

## Output Format

Produce a numbered finding list grouped by severity:

- **Blocking**: tests that cannot fulfill their stated purpose (always-pass assertions, wrong subject)
- **Warning**: structural problems that make the suite brittle or misleading
- **Advisory**: improvement opportunities with no immediate risk

End with a one-paragraph summary verdict: what is the overall health of this test suite, and what is the single highest-priority improvement?
