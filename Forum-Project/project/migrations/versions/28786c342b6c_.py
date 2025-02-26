"""empty message

Revision ID: 28786c342b6c
Revises: 3d4845663f7a
Create Date: 2024-07-16 14:36:39.541106

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '28786c342b6c'
down_revision = '3d4845663f7a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('address', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('gender', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('country_code_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'country_codes', ['country_code_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('country_code_id')
        batch_op.drop_column('phone')
        batch_op.drop_column('gender')
        batch_op.drop_column('address')

    # ### end Alembic commands ###
