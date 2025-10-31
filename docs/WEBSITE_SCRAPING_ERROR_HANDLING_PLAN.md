# Website Scraping Error Handling Enhancement Plan

**Date:** October 31, 2025  
**Current Error Rate:** 63% (4,727 of 7,504 = server_error)

---

## Current State Analysis

### Error Distribution
```
server_error:   4,727 (62.99%) - Generic failures, poor categorization  
success:        1,646 (21.93%) - Working properly
robots_blocked:   683 ( 9.10%) - Expected, working properly
parked_domain:    448 ( 5.97%) - Expected, working properly
```

### Key Issues Identified

1. **Poor Error Categorization**
   - Most `server_error` entries have NULL `http_status_code`
   - NULL `error_type` field (not being populated)
   - Generic "No pages could be scraped" error message
   - Cannot distinguish between:
     * Transient failures (503, timeouts) that should be retried
     * Permanent failures (404, DNS) that should be skipped
     * Server issues vs client/network issues

2. **Limited Retry Logic**
   - Exists but only does 2 retries max
   - Fixed exponential backoff (0.5s, 1s, 2s)
   - Some errors not categorized as retryable that should be
   - No configuration for retry behavior

3. **Missing Status Tracking**
   - HTTP status codes not being logged for most failures
   - Response times not captured
   - DNS/SSL validation status not populated
   - Retry attempts not tracked

---

## Enhancement Plan

### Phase 1: Improve Error Classification ✅ (Existing Code Review)

**Current State:**
- ✅ DNS failures detected: `dns_resolution_error`
- ✅ SSL errors detected: `ssl_certificate_error`  
- ✅ Timeouts detected: `connection_timeout_final`
- ✅ Connection resets detected: `connection_reset_by_peer_final`
- ✅ HTTP status codes categorized: `http_404_not_found`, `http_503_server_error`, etc.
- ⚠️ But these aren't being logged to database properly

**Issue:** Error types are set in `status_info` dict but not being passed to status logger.

### Phase 2: Fix Status Logging Integration

**Problem:** The `scrape_website()` method doesn't pass `error_type` to status logger.

**Solution:**
```python
# In scrape_website(), when logging errors:
self.status_logger.log_website_status(
    link_id=link_id,
    status_type="server_error",
    error_type=status_info.get("error_type"),  # ADD THIS
    error_details=result.error_message,
    http_status_code=status_info.get("http_status_code"),  # ADD THIS
    dns_resolved=status_info.get("dns_resolved"),
    ssl_valid=status_info.get("ssl_valid"),
    # ... other fields
)
```

### Phase 3: Enhance Retry Logic

**Improvements Needed:**

1. **Increase Retry Attempts for Transient Errors**
   ```python
   max_retries_transient = 3  # For 5xx, timeouts, rate limits
   max_retries_connection = 2  # For connection issues
   max_retries_permanent = 0   # For 404, DNS, SSL cert errors
   ```

2. **Better Backoff Strategy**
   ```python
   # Current: 0.5s, 1s, 2s (exponential: 2^n * 0.5)
   # Enhanced: 1s, 2s, 4s, 8s for transient errors
   backoff_time = min((2 ** attempt) * 1.0, 10.0)  # Cap at 10s
   ```

3. **Retry-After Header Support**
   ```python
   if response.status_code == 429:  # Rate limited
       retry_after = int(response.headers.get('Retry-After', 5))
       time.sleep(retry_after)
   ```

### Phase 4: Add Comprehensive Error Categories

**Enhanced Error Type Taxonomy:**

#### Permanent Failures (No Retry)
- `http_404_not_found` - Page doesn't exist
- `http_410_gone` - Intentionally removed
- `dns_resolution_error` - Domain doesn't exist
- `ssl_certificate_expired` - Invalid certificate
- `domain_for_sale` - Parked domain
- `domain_expired` - Registration lapsed

#### Transient Failures (Retry 3x)
- `http_500_internal_server_error` - Server issue
- `http_502_bad_gateway` - Proxy issue
- `http_503_service_unavailable` - Temporary unavailable
- `http_504_gateway_timeout` - Upstream timeout
- `connection_timeout` - Network timeout
- `rate_limit_exceeded` - 429 response

#### Connection Failures (Retry 2x)
- `connection_reset` - Connection dropped
- `connection_refused` - Server not accepting connections
- `connection_aborted` - Connection forcibly closed

#### Authentication/Authorization (No Retry)
- `http_401_unauthorized` - Needs authentication
- `http_403_forbidden` - Access denied
- `cloudflare_challenge` - Anti-bot protection

### Phase 5: Add HTTP Status Code Capture

**Enhancement:**
```python
# In _fetch_page_attempt(), capture response metadata:
status_info["http_status_code"] = response.status_code
status_info["response_time_ms"] = int(response.elapsed.total_seconds() * 1000)
status_info["content_length"] = len(response.content)
```

### Phase 6: Track Retry Attempts

**Add to status logging:**
```python
# Add retry_attempts field to track how many retries were needed
status_info["retry_attempts"] = attempt  # 0 = first try, 1-3 = retries
```

---

## Implementation Priority

### High Priority (Immediate)
1. ✅ Fix status logging to capture error_type
2. ✅ Add HTTP status code capture
3. ✅ Enhance retry logic for 5xx errors
4. ✅ Track retry attempts

### Medium Priority (Next Sprint)
5. ⏳ Add Retry-After header support for rate limiting
6. ⏳ Implement more granular error categorization
7. ⏳ Add configuration for retry behavior

### Low Priority (Future)
8. ⏳ Add circuit breaker pattern for consistently failing domains
9. ⏳ Implement adaptive backoff based on server response patterns
10. ⏳ Add metrics dashboard for error tracking

---

## Expected Outcomes

### Error Rate Improvement
- **Current:** 63% server_error (mostly generic)
- **Target:** 40% permanent failures (properly categorized), 20% transient failures (with retries), 40% success

### Better Categorization
```
Expected distribution after fixes:
- success:                25-30%  (improved from 22% with retries)
- parked_domain:          8-10%   (same, working properly)
- robots_blocked:         8-10%   (same, working properly)  
- dns_resolution_error:   15-20%  (permanent, no retry)
- http_404_not_found:     10-15%  (permanent, no retry)
- http_5xx_errors:        5-10%   (transient, retry helps)
- connection_errors:      5-8%    (transient, retry helps)
- ssl_errors:             2-5%    (permanent, no retry)
- other_errors:           <5%     (various edge cases)
```

### Benefits
1. **Better Understanding:** Know exactly why sites are failing
2. **Reduced Wasted Effort:** Don't retry permanent failures
3. **Improved Success Rate:** Retry transient failures increases scraping success
4. **Better Monitoring:** Track which error types are most common
5. **Informed Decision Making:** Prioritize fixing issues that affect most sites

---

## Files to Modify

1. `src/scrapers/website_scraper.py`
   - Enhance retry logic in `_fetch_page_with_retry()`
   - Add HTTP status code capture in `_fetch_page_attempt()`
   - Improve error categorization in `_handle_fetch_error()`
   - Pass error_type and http_status_code to `scrape_website()` result

2. `src/services/website_status_logger.py`
   - Already supports all needed fields ✅
   - No changes needed

3. `src/models/website_status.py` (if exists)
   - Verify error type constants are comprehensive

---

## Testing Strategy

1. **Unit Tests:**
   - Test retry logic with mocked responses
   - Test error categorization with various HTTP codes
   - Test backoff timing calculations

2. **Integration Tests:**
   - Test against known failing domains (404, timeout, 5xx)
   - Verify retry attempts are logged correctly
   - Confirm HTTP status codes are captured

3. **Production Validation:**
   - Run on sample of 100 projects
   - Analyze error distribution before/after
   - Verify retry attempts improve success rate
   - Check database logs for proper error categorization

---

## Success Metrics

| Metric | Before | Target | How to Measure |
|--------|--------|--------|----------------|
| Generic "server_error" | 63% | <10% | Query website_status_log |
| Error type populated | ~0% | >95% | Check error_type NOT NULL |
| HTTP status captured | ~0% | >80% | Check http_status_code NOT NULL |
| Success rate | 22% | 30%+ | Successful scrapes / total |
| Retry effectiveness | N/A | 5-10% | Scrapes that succeed after retry |

---

**Status:** Ready for Implementation  
**Estimated Time:** 2-3 hours  
**Risk:** Low (enhances existing code, doesn't break current functionality)
