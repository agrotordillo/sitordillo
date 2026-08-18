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
        ('facturacion', '0001_empresa_factura_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'facturacion_empresa_created_by_id_1f61fa73_fk_auth_user_id') THEN "
                'ALTER TABLE "facturacion_empresa" DROP CONSTRAINT "facturacion_empresa_created_by_id_1f61fa73_fk_auth_user_id"; '
                'ALTER TABLE "facturacion_empresa" ADD CONSTRAINT "facturacion_empresa_created_by_id_1f61fa73_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'facturacion_empresa_created_by_id_1f61fa73_fk_accounts_user_id') THEN "
                'ALTER TABLE "facturacion_empresa" DROP CONSTRAINT "facturacion_empresa_created_by_id_1f61fa73_fk_accounts_user_id"; '
                'ALTER TABLE "facturacion_empresa" ADD CONSTRAINT "facturacion_empresa_created_by_id_1f61fa73_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'facturacion_empresa_updated_by_id_4898f5a0_fk_auth_user_id') THEN "
                'ALTER TABLE "facturacion_empresa" DROP CONSTRAINT "facturacion_empresa_updated_by_id_4898f5a0_fk_auth_user_id"; '
                'ALTER TABLE "facturacion_empresa" ADD CONSTRAINT "facturacion_empresa_updated_by_id_4898f5a0_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'facturacion_empresa_updated_by_id_4898f5a0_fk_accounts_user_id') THEN "
                'ALTER TABLE "facturacion_empresa" DROP CONSTRAINT "facturacion_empresa_updated_by_id_4898f5a0_fk_accounts_user_id"; '
                'ALTER TABLE "facturacion_empresa" ADD CONSTRAINT "facturacion_empresa_updated_by_id_4898f5a0_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'facturacion_factura_created_by_id_3ab095e7_fk_auth_user_id') THEN "
                'ALTER TABLE "facturacion_factura" DROP CONSTRAINT "facturacion_factura_created_by_id_3ab095e7_fk_auth_user_id"; '
                'ALTER TABLE "facturacion_factura" ADD CONSTRAINT "facturacion_factura_created_by_id_3ab095e7_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'facturacion_factura_created_by_id_3ab095e7_fk_accounts_user_id') THEN "
                'ALTER TABLE "facturacion_factura" DROP CONSTRAINT "facturacion_factura_created_by_id_3ab095e7_fk_accounts_user_id"; '
                'ALTER TABLE "facturacion_factura" ADD CONSTRAINT "facturacion_factura_created_by_id_3ab095e7_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'facturacion_factura_updated_by_id_672dbda1_fk_auth_user_id') THEN "
                'ALTER TABLE "facturacion_factura" DROP CONSTRAINT "facturacion_factura_updated_by_id_672dbda1_fk_auth_user_id"; '
                'ALTER TABLE "facturacion_factura" ADD CONSTRAINT "facturacion_factura_updated_by_id_672dbda1_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'facturacion_factura_updated_by_id_672dbda1_fk_accounts_user_id') THEN "
                'ALTER TABLE "facturacion_factura" DROP CONSTRAINT "facturacion_factura_updated_by_id_672dbda1_fk_accounts_user_id"; '
                'ALTER TABLE "facturacion_factura" ADD CONSTRAINT "facturacion_factura_updated_by_id_672dbda1_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
