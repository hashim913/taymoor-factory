
"""V7 baseline migration."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_v7"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Baseline marker for databases initialized by V6.
    # Fresh deployments should use SQLAlchemy metadata or generate a full
    # environment-specific migration before production rollout.
    pass

def downgrade():
    pass
