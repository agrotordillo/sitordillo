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
        ('inventario', '0003_devolucion_choice'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventario_lote_created_by_id_bff85fc8_fk_auth_user_id') THEN "
                'ALTER TABLE "inventario_lote" DROP CONSTRAINT "inventario_lote_created_by_id_bff85fc8_fk_auth_user_id"; '
                'ALTER TABLE "inventario_lote" ADD CONSTRAINT "inventario_lote_created_by_id_bff85fc8_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventario_lote_created_by_id_bff85fc8_fk_accounts_user_id') THEN "
                'ALTER TABLE "inventario_lote" DROP CONSTRAINT "inventario_lote_created_by_id_bff85fc8_fk_accounts_user_id"; '
                'ALTER TABLE "inventario_lote" ADD CONSTRAINT "inventario_lote_created_by_id_bff85fc8_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventario_lote_updated_by_id_4f04629f_fk_auth_user_id') THEN "
                'ALTER TABLE "inventario_lote" DROP CONSTRAINT "inventario_lote_updated_by_id_4f04629f_fk_auth_user_id"; '
                'ALTER TABLE "inventario_lote" ADD CONSTRAINT "inventario_lote_updated_by_id_4f04629f_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventario_lote_updated_by_id_4f04629f_fk_accounts_user_id') THEN "
                'ALTER TABLE "inventario_lote" DROP CONSTRAINT "inventario_lote_updated_by_id_4f04629f_fk_accounts_user_id"; '
                'ALTER TABLE "inventario_lote" ADD CONSTRAINT "inventario_lote_updated_by_id_4f04629f_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventario_movimient_created_by_id_aa44a8be_fk_auth_user') THEN "
                'ALTER TABLE "inventario_movimientoinventario" DROP CONSTRAINT "inventario_movimient_created_by_id_aa44a8be_fk_auth_user"; '
                'ALTER TABLE "inventario_movimientoinventario" ADD CONSTRAINT "inventario_movimient_created_by_id_aa44a8be_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventario_movimient_created_by_id_aa44a8be_fk_accounts_user') THEN "
                'ALTER TABLE "inventario_movimientoinventario" DROP CONSTRAINT "inventario_movimient_created_by_id_aa44a8be_fk_accounts_user"; '
                'ALTER TABLE "inventario_movimientoinventario" ADD CONSTRAINT "inventario_movimient_created_by_id_aa44a8be_fk_auth_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventario_movimient_updated_by_id_485fc9c0_fk_auth_user') THEN "
                'ALTER TABLE "inventario_movimientoinventario" DROP CONSTRAINT "inventario_movimient_updated_by_id_485fc9c0_fk_auth_user"; '
                'ALTER TABLE "inventario_movimientoinventario" ADD CONSTRAINT "inventario_movimient_updated_by_id_485fc9c0_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventario_movimient_updated_by_id_485fc9c0_fk_accounts_user') THEN "
                'ALTER TABLE "inventario_movimientoinventario" DROP CONSTRAINT "inventario_movimient_updated_by_id_485fc9c0_fk_accounts_user"; '
                'ALTER TABLE "inventario_movimientoinventario" ADD CONSTRAINT "inventario_movimient_updated_by_id_485fc9c0_fk_auth_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
