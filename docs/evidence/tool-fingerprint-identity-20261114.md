# Open-handle identity during executable fingerprinting

The preview fingerprint previously compared only pathname metadata before and after reading. A substituted open handle with equal-length bytes could produce a digest for a different file while the selected path remained unchanged. Changes visible only on the opened descriptor were also missed.

Two isolated regressions fail before the fix: a selected path whose mocked open returns another same-length native-header fixture, and an opened descriptor whose ctime changes during the read. The fix checks descriptor identity against the selected file before consuming bytes, then checks descriptor metadata again before accepting the digest. ctime is compared within fstat only, preserving Windows stat/fstat differences. The existing pathname recheck, size bound, format checks, expected-hash acknowledgement and no-shell launch remain.

Validation: 100 standard-library tests, 99 passed and one native Windows junction test skipped on Linux; example manifest CLI and whitespace check passed. Windows/Linux CI remains a separate gate. Fixtures are author-created non-executable data; Popen is mocked and no real tool, user mod or profile is run or modified. This narrows fingerprint races; it does not provide publisher authentication or eliminate the later race between final checking and OS process launch.
