# V7 Production Checklist

- [ ] Change PostgreSQL password
- [ ] Generate TOKEN_ENCRYPTION_KEY
- [ ] Generate WEB_SECRET_KEY
- [ ] Generate WEBHOOK_SECRET_TOKEN
- [ ] HTTPS configured
- [ ] WEB_BASE_URL uses HTTPS
- [ ] Redis private/internal only
- [ ] PostgreSQL private/internal only
- [ ] Backups configured
- [ ] Alembic migration reviewed
- [ ] Worker IDs unique
- [ ] Prometheus scraping workers
- [ ] Alerts configured
- [ ] DLQ monitoring configured
- [ ] Payment webhook signature verification implemented
- [ ] Rate limiting enabled
- [ ] CSRF protection enabled
- [ ] Secret rotation procedure documented
