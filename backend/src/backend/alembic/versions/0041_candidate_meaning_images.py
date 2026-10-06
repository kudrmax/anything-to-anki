"""Keep the picked picture of a target apart from the video frame.

Revision ID: 0041
Revises: 0040

A picture picked from the search results or pasted used to replace the video
frame in candidate_media.screenshot_path. It is the meaning of the target and
now lives in candidate_meaning_images. Such pictures are told apart from
frames by their file name: `{id}_screenshot.{digest}.webp` against
`{id}_screenshot.webp`. The frames they replaced are gone and stay gone.
"""
import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

PICKED_PICTURE_GLOB = "*_screenshot." + "[0-9a-f]" * 10 + ".webp"


def upgrade() -> None:
    op.create_table(
        "candidate_meaning_images",
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("image_path", sa.Text(), nullable=False),
    )
    with op.batch_alter_table("enrichment_cache") as batch:
        batch.add_column(sa.Column("meaning_image_path", sa.Text(), nullable=True))

    connection = op.get_bind()
    picked = {"picked": PICKED_PICTURE_GLOB}
    connection.execute(
        sa.text(
            "INSERT INTO candidate_meaning_images (candidate_id, image_path) "
            "SELECT candidate_id, screenshot_path FROM candidate_media "
            "WHERE screenshot_path GLOB :picked"
        ),
        picked,
    )
    connection.execute(
        sa.text(
            "UPDATE candidate_media SET screenshot_path = NULL "
            "WHERE screenshot_path GLOB :picked"
        ),
        picked,
    )
    connection.execute(
        sa.text(
            "UPDATE enrichment_cache "
            "SET meaning_image_path = screenshot_path, screenshot_path = NULL "
            "WHERE screenshot_path GLOB :picked"
        ),
        picked,
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE candidate_media SET screenshot_path = ("
            "  SELECT image_path FROM candidate_meaning_images"
            "  WHERE candidate_meaning_images.candidate_id = candidate_media.candidate_id"
            ") WHERE candidate_id IN (SELECT candidate_id FROM candidate_meaning_images)"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE enrichment_cache SET screenshot_path = meaning_image_path "
            "WHERE meaning_image_path IS NOT NULL"
        )
    )
    with op.batch_alter_table("enrichment_cache") as batch:
        batch.drop_column("meaning_image_path")
    op.drop_table("candidate_meaning_images")
