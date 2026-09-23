"""Academic dashboard, reviewed imports and learning project context."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "personal_chats",
        sa.Column(
            "owner_id",
            sa.Integer,
            sa.ForeignKey("workspace_owners.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("history", sa.JSON, nullable=False),
        sa.Column("transcript", sa.JSON, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
    )
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            "\nCREATE TABLE workspace_cache_revisions (\n\tid INTEGER NOT NULL, \n\tvalue VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n"
        )
        op.execute(
            "\nCREATE TABLE academic_profiles (\n\towner_id INTEGER NOT NULL, \n\tprogram VARCHAR(100) NOT NULL, \n\tcurrent_semester VARCHAR(40) NOT NULL, \n\ttotal_credits FLOAT, \n\ttarget_sgpa FLOAT, \n\tsgpa_scale FLOAT NOT NULL, \n\tPRIMARY KEY (owner_id), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "\nCREATE TABLE semester_results (\n\tid INTEGER NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tsemester VARCHAR(40) NOT NULL, \n\tsgpa FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (owner_id, semester), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_semester_results_owner_id ON semester_results (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE subject_syllabi (\n\tid INTEGER NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tsubject_id INTEGER NOT NULL, \n\tcontent TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(subject_id, owner_id) REFERENCES personal_subjects (id, owner_id) ON DELETE CASCADE, \n\tUNIQUE (owner_id, subject_id)\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_subject_syllabi_owner_id ON subject_syllabi (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE academic_imports (\n\tid INTEGER NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tfilename VARCHAR(200) NOT NULL, \n\tmime VARCHAR(60) NOT NULL, \n\tsource BLOB NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\tdraft JSON, \n\terror TEXT, \n\tstarted_at FLOAT NOT NULL, \n\tlease VARCHAR(36) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_academic_imports_owner_id ON academic_imports (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE learning_projects (\n\tid INTEGER NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tname VARCHAR(150) NOT NULL, \n\tdescription TEXT NOT NULL, \n\tsubject_ids JSON NOT NULL, \n\tcreated_at FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (id, owner_id), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_learning_projects_owner_id ON learning_projects (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE project_materials (\n\tid INTEGER NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tproject_id INTEGER NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tkind VARCHAR(20) NOT NULL, \n\tcontent TEXT NOT NULL, \n\tsource_url VARCHAR(500), \n\tcreated_at FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(project_id, owner_id) REFERENCES learning_projects (id, owner_id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_project_materials_owner_id ON project_materials (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE github_profiles (\n\towner_id INTEGER NOT NULL, \n\thandle VARCHAR(40) NOT NULL, \n\tsnapshot JSON NOT NULL, \n\tfetched_at FLOAT NOT NULL, \n\tPRIMARY KEY (owner_id), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
    if dialect == "postgresql":
        op.execute(
            "\nCREATE TABLE workspace_cache_revisions (\n\tid SERIAL NOT NULL, \n\tvalue VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n"
        )
        op.execute(
            "\nCREATE TABLE academic_profiles (\n\towner_id INTEGER NOT NULL, \n\tprogram VARCHAR(100) NOT NULL, \n\tcurrent_semester VARCHAR(40) NOT NULL, \n\ttotal_credits FLOAT, \n\ttarget_sgpa FLOAT, \n\tsgpa_scale FLOAT NOT NULL, \n\tPRIMARY KEY (owner_id), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "\nCREATE TABLE semester_results (\n\tid SERIAL NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tsemester VARCHAR(40) NOT NULL, \n\tsgpa FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (owner_id, semester), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_semester_results_owner_id ON semester_results (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE subject_syllabi (\n\tid SERIAL NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tsubject_id INTEGER NOT NULL, \n\tcontent TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(subject_id, owner_id) REFERENCES personal_subjects (id, owner_id) ON DELETE CASCADE, \n\tUNIQUE (owner_id, subject_id)\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_subject_syllabi_owner_id ON subject_syllabi (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE academic_imports (\n\tid SERIAL NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tfilename VARCHAR(200) NOT NULL, \n\tmime VARCHAR(60) NOT NULL, \n\tsource BYTEA NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\tdraft JSON, \n\terror TEXT, \n\tstarted_at FLOAT NOT NULL, \n\tlease VARCHAR(36) NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_academic_imports_owner_id ON academic_imports (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE learning_projects (\n\tid SERIAL NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tname VARCHAR(150) NOT NULL, \n\tdescription TEXT NOT NULL, \n\tsubject_ids JSON NOT NULL, \n\tcreated_at FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (id, owner_id), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_learning_projects_owner_id ON learning_projects (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE project_materials (\n\tid SERIAL NOT NULL, \n\towner_id INTEGER NOT NULL, \n\tproject_id INTEGER NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tkind VARCHAR(20) NOT NULL, \n\tcontent TEXT NOT NULL, \n\tsource_url VARCHAR(500), \n\tcreated_at FLOAT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(project_id, owner_id) REFERENCES learning_projects (id, owner_id) ON DELETE CASCADE\n)\n\n"
        )
        op.execute(
            "CREATE INDEX ix_project_materials_owner_id ON project_materials (owner_id)"
        )
        op.execute(
            "\nCREATE TABLE github_profiles (\n\towner_id INTEGER NOT NULL, \n\thandle VARCHAR(40) NOT NULL, \n\tsnapshot JSON NOT NULL, \n\tfetched_at FLOAT NOT NULL, \n\tPRIMARY KEY (owner_id), \n\tFOREIGN KEY(owner_id) REFERENCES workspace_owners (id) ON DELETE CASCADE\n)\n\n"
        )
    op.execute(
        text("INSERT INTO workspace_cache_revisions (id, value) VALUES (1, 'initial')")
    )


def downgrade():
    raise RuntimeError("Restore a backup instead of deleting personal records.")
