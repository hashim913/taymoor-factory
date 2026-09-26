-- V9 payment tables/columns. Review against your existing Alembic schema before production.
CREATE TABLE IF NOT EXISTS payment_orders (
  id BIGSERIAL PRIMARY KEY,
  order_id VARCHAR(64) UNIQUE NOT NULL,
  user_id BIGINT NOT NULL,
  bot_id BIGINT NOT NULL,
  plan VARCHAR(16) NOT NULL,
  provider VARCHAR(32) NOT NULL,
  amount_usd NUMERIC(10,2) NOT NULL,
  currency VARCHAR(8) NOT NULL DEFAULT 'USD',
  status VARCHAR(16) NOT NULL DEFAULT 'pending',
  transaction_ref VARCHAR(255),
  receipt_file TEXT,
  submitted_at TIMESTAMP,
  reviewed_by BIGINT,
  reviewed_at TIMESTAMP,
  review_note TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE bots ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMP NULL;
CREATE INDEX IF NOT EXISTS ix_payment_orders_status ON payment_orders(status);
CREATE INDEX IF NOT EXISTS ix_payment_orders_user ON payment_orders(user_id);
