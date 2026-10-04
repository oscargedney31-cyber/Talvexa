# V20 Architecture Direction

Core systems:
1. Identity/authentication
2. Job ingestion
3. Employer/company identity
4. Job normalisation
5. Search/indexing
6. Matching
7. Applications
8. Trust and safety
9. Notifications
10. Analytics
11. Billing
12. Administration

Scale strategy:
Start as a modular application with clean boundaries. High-load components can later be separated into independent services.

The AI should not handle every search request. Jobs should be converted into structured attributes first. Database indexes/search infrastructure handle straightforward filtering; AI is used for semantic understanding, classification, enrichment and ranking.

Data strategy:
Use employer submissions, authorised APIs/feeds, public employment services, licensed sources and other sources whose terms permit the intended use. Retain source and verification metadata and continuously check vacancy status.

Sensitive profile information:
Accessibility/disability information is optional and sensitive. Minimise collection, protect it carefully and use it only for user-directed matching. Do not expose it to employers by default.

Reliability:
Add automated tests, background queues, monitoring/error tracking, backups, rate limiting, authentication, audit logging, search indexing, caching, expiry checks and fraud/scam detection as the platform grows.
