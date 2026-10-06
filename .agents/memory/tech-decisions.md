# Tech Decisions

No entries yet. Architecture and technology decisions and why they were made
get appended here by `/remember` or other harness work, one entry per line,
newest last.

- 2026-10-06 (spec 006): User-generated tool output (e.g. Site Crawler projects) is stored in a RustFS (S3-compatible) container integrated like Crawl4AI/OpenSandbox (compose + config + service client + health). Fixed docker volume only; files reach the user's PC via zip download from the UI, not host bind-mounts.
