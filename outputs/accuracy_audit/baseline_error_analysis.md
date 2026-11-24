# Baseline Error Analysis Report (Sample Dataset: 40 Threads)

## 1. Executive Summary

- **Total Sample Threads Evaluated:** 40
- **Exact-Match Accuracy:** 27 / 40 (67.50%)
- **Action Accuracy:** 30 / 40 (75.00%)
- **Reason-Code Accuracy:** 28 / 40 (70.00%)
- **Counter-Price Accuracy:** 35 / 40 (87.50%)

### Baseline Action Distribution
- **ACCEPT:** 9 (22.5%)
- **COUNTER:** 8 (20.0%)
- **REJECT:** 3 (7.5%)
- **ESCALATE:** 20 (50.0%)

---

## 2. Detailed Mismatch Breakdown (13 Mismatches in Baseline)

### 1. T00002
- **Thread ID:** T00002
- **Category / Supplier:** `led-lighting` / `Falcon Security Services`
- **Expected Label:** `ESCALATE:OVER_APPROVAL_LIMIT:`
- **Predicted Label:** `ESCALATE:BANNED_TERM:`
- **Incorrect Label Component:** Reason code (`BANNED_TERM` vs expected `OVER_APPROVAL_LIMIT`)
- **Relevant Playbook Provision:** `banned-terms.md`: "statements that no exclusivity is asked" are explicitly allowed.
- **Root Cause:** In `policy_engine._build_banned_term_patterns`, the exclusivity regex did not exempt "We are not asking for exclusivity", resulting in a false-positive banned term that fired at Step 4, preempting the approval limit check at Step 6.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Enhanced exclusivity regex to ignore negations like "not asking for exclusivity" and "no exclusivity".

### 2. T00006
- **Thread ID:** T00006
- **Category / Supplier:** `mobile-phones` / `Orbit Electronics`
- **Expected Label:** `REJECT:BLACKLISTED_SUPPLIER:`
- **Predicted Label:** `ACCEPT:ACCEPTABLE_PRICE:`
- **Incorrect Label Component:** Action and Reason (`ACCEPT:ACCEPTABLE_PRICE` vs `REJECT:BLACKLISTED_SUPPLIER`)
- **Relevant Playbook Provision:** `decision-procedure.md` Step 2: Blacklisted supplier -> `REJECT:BLACKLISTED_SUPPLIER:`. `suppliers/orbit-electronics.md`: `Status: BLACKLISTED — do not do business (failed audit)`.
- **Root Cause:** `policy_engine._extract_kv_pairs` did not strip markdown bold asterisks (`**`), leaving `status = '** BLACKLISTED...'`. In `_parse_supplier_file`, `status_raw.upper().startswith("BLACKLIST")` returned `False` because of leading `**`. Consequently, `Orbit Electronics` was assigned `status = 'APPROVED'`.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Stripped leading/trailing asterisks in `_extract_kv_pairs` so status values parse cleanly.

### 3. T00009
- **Thread ID:** T00009
- **Category / Supplier:** `monitors` / `Ivory Events Catering`
- **Expected Label:** `REJECT:ABOVE_WALKAWAY:`
- **Predicted Label:** `ESCALATE:OVER_APPROVAL_LIMIT:`
- **Incorrect Label Component:** Action and Reason (`ESCALATE:OVER_APPROVAL_LIMIT` vs `REJECT:ABOVE_WALKAWAY`)
- **Relevant Playbook Provision:** `decision-procedure.md` Section "Which numbers apply": "A supplier contract price cap replaces the walk-away price for that category."
- **Root Cause:** In `_parse_supplier_file`, `_parse_number` performed substring matching on `"lac"`, matching inside `"replaces"`, inflating `cap_val` by 100,000x. Additionally, category parsing in supplier contracts did not support `"price cap for <Cat> of ₹<Amt>"`, resulting in caps being defaulted to `"*"`, affecting unrelated categories with astronomical walkaway numbers and allowing price approval checks to run erroneously.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Used word boundaries (`\b(?:lakh[s]?|lac)\b`) in `_parse_number` and supported `of` in category cap extraction.

### 4. T00012
- **Thread ID:** T00012
- **Category / Supplier:** `catering` / `Vertex Mobile`
- **Expected Label:** `COUNTER:COUNTER_OFFER:270`
- **Predicted Label:** `ACCEPT:ACCEPTABLE_PRICE:`
- **Incorrect Label Component:** Action and Counter Price (`ACCEPT` vs `COUNTER:270`)
- **Relevant Playbook Provision:** `decision-procedure.md` Step 7: "Suppliers on probation. For a supplier whose status is PROBATION, Acme makes no concessions: the acceptable level L(r) equals the target price in every round."
- **Root Cause:** `Vertex Mobile` is `PROBATION` in `suppliers/vertex-mobile.md`, but bold markdown markers caused it to be parsed as `APPROVED`. When treated as `APPROVED`, round 2 concession limit was 305, so offer 300 was accepted. Under `PROBATION`, limit equals target 270, necessitating a counter at 270.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Fixed markdown extraction in `_extract_kv_pairs` so `PROBATION` status is correctly recognized.

### 5. T00014
- **Thread ID:** T00014
- **Category / Supplier:** `headsets` / `Ivory Events Catering`
- **Expected Label:** `ACCEPT:ACCEPTABLE_PRICE:`
- **Predicted Label:** `ESCALATE:BANNED_TERM:`
- **Incorrect Label Component:** Action and Reason (`ESCALATE:BANNED_TERM` vs `ACCEPT:ACCEPTABLE_PRICE`)
- **Relevant Playbook Provision:** `banned-terms.md`: statements that no exclusivity is asked are permitted.
- **Root Cause:** Supplier message stated "We are not asking for exclusivity." False positive triggered in exclusivity regex.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Refined exclusivity regex to ignore statements disclaiming exclusivity.

### 6. T00015
- **Thread ID:** T00015
- **Category / Supplier:** `training` / `GreenLeaf Facility Care`
- **Expected Label:** `REJECT:BLACKLISTED_SUPPLIER:`
- **Predicted Label:** `COUNTER:COUNTER_OFFER:6750`
- **Incorrect Label Component:** Action, Reason, and Counter Price
- **Relevant Playbook Provision:** `decision-procedure.md` Step 2: Blacklisted supplier -> `REJECT:BLACKLISTED_SUPPLIER:`.
- **Root Cause:** `GreenLeaf Facility Care` is `BLACKLISTED` in `suppliers/greenleaf-facility-care.md`, but bold asterisks prevented blacklist recognition.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Stripped bold asterisks from key-value extraction.

### 7. T00017
- **Thread ID:** T00017
- **Category / Supplier:** `office-chairs` / `Monsoon Foods`
- **Expected Label:** `COUNTER:COUNTER_OFFER:9000`
- **Predicted Label:** `ESCALATE:BANNED_TERM:`
- **Incorrect Label Component:** Action and Reason
- **Relevant Playbook Provision:** `banned-terms.md`: statements disclaiming exclusivity are allowed.
- **Root Cause:** "We are not asking for exclusivity." triggered a false-positive banned term match.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Refined exclusivity regex pattern.

### 8. T00022
- **Thread ID:** T00022
- **Category / Supplier:** `office-chairs` / `Redwood Couriers`
- **Expected Label:** `ESCALATE:BANNED_TERM:`
- **Predicted Label:** `ACCEPT:ACCEPTABLE_PRICE:`
- **Incorrect Label Component:** Action and Reason
- **Relevant Playbook Provision:** `banned-terms.md`: "Upfront or advance payment above 30% of order value".
- **Root Cause:** The supplier message stated "We need 40% of the order value upfront." The regex only looked for `40% upfront` without allowing intermediate words like `of the order value`.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Extended upfront pattern to match percentages followed by intervening descriptors before `upfront`.

### 9. T00024
- **Thread ID:** T00024
- **Category / Supplier:** `crm-licenses` / `Arvind Office Supplies`
- **Expected Label:** `ACCEPT:ACCEPTABLE_PRICE:`
- **Predicted Label:** `ESCALATE:BANNED_TERM:`
- **Incorrect Label Component:** Action and Reason
- **Relevant Playbook Provision:** `banned-terms.md`: Allowed: "renewal only by mutual agreement".
- **Root Cause:** Message said: "There is no automatic renewal; renewal only if both parties sign again." The regex matched `renewal` because `auto-` was optional, and the lookbehind for `no` did not cover the second clause.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Required `auto-` or `automatic` prefix for renewal terms, preventing mutual-agreement renewal from triggering banned terms.

### 10. T00025
- **Thread ID:** T00025
- **Category / Supplier:** `monitors` / `Jupiter Devices`
- **Expected Label:** `REJECT:ABOVE_WALKAWAY:`
- **Predicted Label:** `ESCALATE:BANNED_TERM:`
- **Incorrect Label Component:** Action and Reason
- **Relevant Playbook Provision:** `banned-terms.md`: Allowed: "statements that no exclusivity is asked".
- **Root Cause:** Message had "We are not asking for exclusivity." triggering exclusivity false positive.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Fixed exclusivity regex negation lookbehind.

### 11. T00031
- **Thread ID:** T00031
- **Category / Supplier:** `crm-licenses` / `Jade Express`
- **Expected Label:** `COUNTER:COUNTER_OFFER:18000`
- **Predicted Label:** `COUNTER:COUNTER_OFFER:18444`
- **Incorrect Label Component:** Counter price (18444 vs 18000)
- **Relevant Playbook Provision:** `decision-procedure.md` Step 7: "For a supplier whose status is PROBATION, Acme makes no concessions: the acceptable level L(r) equals the target price in every round."
- **Root Cause:** `Jade Express` is `PROBATION`, but bold asterisks caused it to be treated as `APPROVED`, applying the non-zero concession curve rather than target price (18,000).
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Fixed status extraction so `PROBATION` suppliers use target price in all rounds.

### 12. T00033
- **Thread ID:** T00033
- **Category / Supplier:** `laptops` / `Monsoon Foods`
- **Expected Label:** `COUNTER:COUNTER_OFFER:62889`
- **Predicted Label:** `ACCEPT:ACCEPTABLE_PRICE:`
- **Incorrect Label Component:** Action and Counter Price
- **Relevant Playbook Provision:** `decision-procedure.md`: price cap in supplier contracts replaces walk-away price ONLY for that category.
- **Root Cause:** Monsoon Foods has a price cap for headsets, which defaulted to a global cap (`"*"`) due to regex mismatch in supplier parsing, and was multiplied by 100,000 due to `"lac"` in `"replaces"`. This led to an astronomical walkaway price on laptops, resulting in erroneous acceptance.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Restricted walkaway caps strictly to their stated category and fixed `_parse_number`.

### 13. T00040
- **Thread ID:** T00040
- **Category / Supplier:** `led-lighting` / `Ember Telecom`
- **Expected Label:** `ESCALATE:OVER_APPROVAL_LIMIT:`
- **Predicted Label:** `ESCALATE:BANNED_TERM:`
- **Incorrect Label Component:** Reason code (`BANNED_TERM` vs `OVER_APPROVAL_LIMIT`)
- **Relevant Playbook Provision:** `banned-terms.md`: statements that no exclusivity is asked are allowed.
- **Root Cause:** "We are not asking for exclusivity." falsely triggered Step 4 before approval limit check at Step 6.
- **Responsible Module:** `src/policy_engine.py`
- **Correction:** Fixed exclusivity regex negation lookbehind.
