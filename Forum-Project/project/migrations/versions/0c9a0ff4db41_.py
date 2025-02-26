"""empty message

Revision ID: 0c9a0ff4db41
Revises: 77ac3c54b36d
Create Date: 2024-08-01 15:20:22.369450

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0c9a0ff4db41'
down_revision = '77ac3c54b36d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('vat', sa.Integer(), nullable=False),
    sa.Column('report_limitation_rows', sa.Integer(), nullable=False),
    sa.Column('send_email_template_background_color', sa.String(length=255), nullable=False),
    sa.Column('send_email_template_text_align', sa.String(length=255), nullable=False),
    sa.Column('send_email_template_border', sa.Integer(), nullable=False),
    sa.Column('send_email_template_border_collapse', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )

    settings = sa.table('settings',
       sa.column('vat', sa.Integer()),
       sa.column('report_limitation_rows', sa.Integer()),
       sa.column('send_email_template_background_color', sa.String(255)),
       sa.column('send_email_template_text_align', sa.String(255)),
       sa.column('send_email_template_border', sa.Integer()),
       sa.column('send_email_template_border_collapse', sa.String(255)),
    )

    op.bulk_insert(settings, [{
       'vat': 25, 
       'report_limitation_rows': 10000, 
       'send_email_template_background_color': '#02153b',
       'send_email_template_text_align': 'right',
       'send_email_template_border': 4,
       'send_email_template_border_collapse': 'collapse'}])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('settings')
    # ### end Alembic commands ###
