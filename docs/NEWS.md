# LEON News & Personal Briefings

News endpoints live under `/api/news`. Create a subscription with `topic`, `schedule` (`morning`, `evening`, or `custom:HH:MM@Area/Location`), and `preference` (`critical`, `important`, or `all`). A topic is unique case-insensitively and custom topic input is length and character validated.

The collector searches only configured source domains through the existing read-only browser tool. It never accepts arbitrary source URLs from a subscription, downloads files, or posts externally. Results are URL validated and deduplicated before insertion into SQLite.

The scheduler creates one durable recurring job per enabled subscription. Morning is 08:00 UTC and evening is 18:00 UTC unless a custom timezone is supplied. The scheduler's existing running-job recovery handles process restarts; active jobs are checked before creation to avoid duplicates.

Briefings are stored even if desktop, push, or email delivery fails. Each delivery attempt has its own status and error. The source URL is retained for every included item. Email uses the existing configured email provider and recipient; desktop uses the configured notification provider. Push remains a replaceable provider interface.

Current limitations: source search is intentionally bounded and read-only, published times are only populated when the search adapter exposes them, and the default desktop provider must be configured/available on the host. RSS/API adapters and remote push implementations remain future work.
