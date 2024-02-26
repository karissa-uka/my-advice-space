"""Adding the likes and comments

Revision ID: 0d4db4108102
Revises: 
Create Date: 2024-02-16 16:42:43.385941

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d4db4108102'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    if op.get_bind().dialect.has_table(op.get_bind(), 'friends'):
        op.drop_table('friends')

    with op.batch_alter_table('friends_association', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(None, 'users', ['friend_id'], ['id'])

    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('friend_id')

    # ### end Alembic commands ###



def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('friend_id', sa.VARCHAR(length=32), nullable=True))
        batch_op.create_foreign_key(None, 'friends', ['friend_id'], ['id'])

    with op.batch_alter_table('friends_association', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(None, 'friends', ['friend_id'], ['id'])

    op.create_table('friends',
    sa.Column('id', sa.VARCHAR(length=32), nullable=False),
    sa.Column('first_name', sa.VARCHAR(length=300), nullable=True),
    sa.Column('last_name', sa.VARCHAR(length=300), nullable=True),
    sa.Column('email', sa.VARCHAR(length=345), nullable=True),
    sa.Column('password', sa.TEXT(), nullable=False),
    sa.Column('picture_path', sa.VARCHAR(length=255), nullable=True),
    sa.Column('occupation', sa.VARCHAR(length=100), nullable=True),
    sa.Column('location', sa.VARCHAR(length=100), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('id')
    )
    # ### end Alembic commands ###