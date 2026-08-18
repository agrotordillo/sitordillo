from django.db import migrations


class Migration(migrations.Migration):
    """Repoints created_by/updated_by FKs from the old auth_user table to
    accounts_user now that AUTH_USER_MODEL is accounts.User. Guarded so it is a
    no-op on a fresh database (where the initial migration already targets
    accounts_user directly) and only acts on a pre-existing dev DB that still
    carries the original auth_user-named constraints. Safe either way because
    every affected column is NULL (no auth.User rows ever existed here)."""

    dependencies = [
        ('accounts', '0001_initial'),
        ('compras', '0003_ordencompra_documento_ordencompra_es_fiscal_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_ordencompra_created_by_id_a8fb4c6a_fk_auth_user_id') THEN "
                'ALTER TABLE "compras_ordencompra" DROP CONSTRAINT "compras_ordencompra_created_by_id_a8fb4c6a_fk_auth_user_id"; '
                'ALTER TABLE "compras_ordencompra" ADD CONSTRAINT "compras_ordencompra_created_by_id_a8fb4c6a_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_ordencompra_created_by_id_a8fb4c6a_fk_accounts_user_id') THEN "
                'ALTER TABLE "compras_ordencompra" DROP CONSTRAINT "compras_ordencompra_created_by_id_a8fb4c6a_fk_accounts_user_id"; '
                'ALTER TABLE "compras_ordencompra" ADD CONSTRAINT "compras_ordencompra_created_by_id_a8fb4c6a_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_ordencompra_updated_by_id_b8f7c126_fk_auth_user_id') THEN "
                'ALTER TABLE "compras_ordencompra" DROP CONSTRAINT "compras_ordencompra_updated_by_id_b8f7c126_fk_auth_user_id"; '
                'ALTER TABLE "compras_ordencompra" ADD CONSTRAINT "compras_ordencompra_updated_by_id_b8f7c126_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_ordencompra_updated_by_id_b8f7c126_fk_accounts_user_id') THEN "
                'ALTER TABLE "compras_ordencompra" DROP CONSTRAINT "compras_ordencompra_updated_by_id_b8f7c126_fk_accounts_user_id"; '
                'ALTER TABLE "compras_ordencompra" ADD CONSTRAINT "compras_ordencompra_updated_by_id_b8f7c126_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_ordencomprad_created_by_id_1a43524c_fk_auth_user') THEN "
                'ALTER TABLE "compras_ordencompradetalle" DROP CONSTRAINT "compras_ordencomprad_created_by_id_1a43524c_fk_auth_user"; '
                'ALTER TABLE "compras_ordencompradetalle" ADD CONSTRAINT "compras_ordencomprad_created_by_id_1a43524c_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_ordencomprad_created_by_id_1a43524c_fk_accounts_user') THEN "
                'ALTER TABLE "compras_ordencompradetalle" DROP CONSTRAINT "compras_ordencomprad_created_by_id_1a43524c_fk_accounts_user"; '
                'ALTER TABLE "compras_ordencompradetalle" ADD CONSTRAINT "compras_ordencomprad_created_by_id_1a43524c_fk_auth_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_ordencomprad_updated_by_id_bce9fc53_fk_auth_user') THEN "
                'ALTER TABLE "compras_ordencompradetalle" DROP CONSTRAINT "compras_ordencomprad_updated_by_id_bce9fc53_fk_auth_user"; '
                'ALTER TABLE "compras_ordencompradetalle" ADD CONSTRAINT "compras_ordencomprad_updated_by_id_bce9fc53_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_ordencomprad_updated_by_id_bce9fc53_fk_accounts_user') THEN "
                'ALTER TABLE "compras_ordencompradetalle" DROP CONSTRAINT "compras_ordencomprad_updated_by_id_bce9fc53_fk_accounts_user"; '
                'ALTER TABLE "compras_ordencompradetalle" ADD CONSTRAINT "compras_ordencomprad_updated_by_id_bce9fc53_fk_auth_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_promocionpro_created_by_id_b28b7203_fk_auth_user') THEN "
                'ALTER TABLE "compras_promocionproveedor" DROP CONSTRAINT "compras_promocionpro_created_by_id_b28b7203_fk_auth_user"; '
                'ALTER TABLE "compras_promocionproveedor" ADD CONSTRAINT "compras_promocionpro_created_by_id_b28b7203_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_promocionpro_created_by_id_b28b7203_fk_accounts_user') THEN "
                'ALTER TABLE "compras_promocionproveedor" DROP CONSTRAINT "compras_promocionpro_created_by_id_b28b7203_fk_accounts_user"; '
                'ALTER TABLE "compras_promocionproveedor" ADD CONSTRAINT "compras_promocionpro_created_by_id_b28b7203_fk_auth_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_promocionpro_updated_by_id_8e131918_fk_auth_user') THEN "
                'ALTER TABLE "compras_promocionproveedor" DROP CONSTRAINT "compras_promocionpro_updated_by_id_8e131918_fk_auth_user"; '
                'ALTER TABLE "compras_promocionproveedor" ADD CONSTRAINT "compras_promocionpro_updated_by_id_8e131918_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'compras_promocionpro_updated_by_id_8e131918_fk_accounts_user') THEN "
                'ALTER TABLE "compras_promocionproveedor" DROP CONSTRAINT "compras_promocionpro_updated_by_id_8e131918_fk_accounts_user"; '
                'ALTER TABLE "compras_promocionproveedor" ADD CONSTRAINT "compras_promocionpro_updated_by_id_8e131918_fk_auth_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
