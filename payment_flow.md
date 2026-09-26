# V9 Payment Flow

Plans:
- Free: 90 days, $0
- 3 months: $15
- 1 year: $40

Manual Zain Cash:
1. User selects a paid plan.
2. Bot creates a unique order ID.
3. Bot shows Zain Cash wallet: +9647881313006.
4. User transfers the exact amount.
5. User sends transaction/reference number and optionally receipt.
6. Order becomes `review`.
7. Admin approves or rejects.
8. Approval extends `subscription_expires_at` and queues bot start.
9. Expired subscriptions are stopped by the subscription worker.
10. User is prompted to renew.

This is intentionally manual until merchant/API credentials are available.
