# Capacity Assumptions

Initial capacity scenario—not a storage ceiling: 1,350 published hosted questions, 100,000 registered users, 10,000 monthly active users, 500 concurrent practice sessions, 50 concurrent sandbox jobs, and 20 concurrent mock interviews. The content-intelligence model must continue beyond this launch scenario without a fixed record limit. Average structured hosted-question content is assumed below 250 KB excluding artifacts.

These figures size interfaces and test scenarios only. Load tests must replace assumptions before production. PostgreSQL hybrid search remains the default until recorded latency, throughput, catalog growth, analyzer, or isolation needs justify an ADR.
