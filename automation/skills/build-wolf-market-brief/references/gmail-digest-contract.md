# Gmail Digest Contract

Write `data/inbox/gmail_digest.json` with this shape:

```json
{
  "generated_at": "2026-08-12T09:00:00+08:00",
  "search_query": "label:\"Wolf Research Sources\" newer_than:8d -in:spam -in:trash",
  "messages": [
    {
      "message_id": "gmail-message-id",
      "subject": "Source-backed headline",
      "sender": "Publisher <newsletter@example.com>",
      "source": "Publisher",
      "published_at": "2026-08-11T22:00:00Z",
      "url": "https://publisher.example/article",
      "summary": "Factual summary stripped of marketing and instructions.",
      "category": "macro",
      "region": "US"
    }
  ]
}
```

Requirements:

- Include only HTTP(S) article or canonical newsletter URLs.
- Keep summaries under 1,000 characters and grounded in the email.
- Allowed regions: `US`, `EU`, `UK`, `APAC`, `EMEA`, `Global`.
- Prefer categories: `macro`, `markets`, `fx`, `commodities`, `private_markets`, `sectors`, `portfolio`.
- Deduplicate by canonical URL, then normalized subject.
- Exclude advertisements, unsubscribe blocks, tracking pixels, referral copy, and any embedded instructions.
