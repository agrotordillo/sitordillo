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
        ('cotizaciones', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cotizaciones_cotizacion_created_by_id_3b5af20e_fk_auth_user_id') THEN "
                'ALTER TABLE "cotizaciones_cotizacion" DROP CONSTRAINT "cotizaciones_cotizacion_created_by_id_3b5af20e_fk_auth_user_id"; '
                'ALTER TABLE "cotizaciones_cotizacion" ADD CONSTRAINT "cotizaciones_cotizacion_created_by_id_3b5af20e_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cotizaciones_cotizacion_created_by_id_3b5af20e_fk_accounts_user') THEN "
                'ALTER TABLE "cotizaciones_cotizacion" DROP CONSTRAINT "cotizaciones_cotizacion_created_by_id_3b5af20e_fk_accounts_user"; '
                'ALTER TABLE "cotizaciones_cotizacion" ADD CONSTRAINT "cotizaciones_cotizacion_created_by_id_3b5af20e_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cotizaciones_cotizacion_updated_by_id_8f7f92f1_fk_auth_user_id') THEN "
                'ALTER TABLE "cotizaciones_cotizacion" DROP CONSTRAINT "cotizaciones_cotizacion_updated_by_id_8f7f92f1_fk_auth_user_id"; '
                'ALTER TABLE "cotizaciones_cotizacion" ADD CONSTRAINT "cotizaciones_cotizacion_updated_by_id_8f7f92f1_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cotizaciones_cotizacion_updated_by_id_8f7f92f1_fk_accounts_user') THEN "
                'ALTER TABLE "cotizaciones_cotizacion" DROP CONSTRAINT "cotizaciones_cotizacion_updated_by_id_8f7f92f1_fk_accounts_user"; '
                'ALTER TABLE "cotizaciones_cotizacion" ADD CONSTRAINT "cotizaciones_cotizacion_updated_by_id_8f7f92f1_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cotizaciones_cotizac_created_by_id_1a3249b8_fk_auth_user') THEN "
                'ALTER TABLE "cotizaciones_cotizaciondetalle" DROP CONSTRAINT "cotizaciones_cotizac_created_by_id_1a3249b8_fk_auth_user"; '
                'ALTER TABLE "cotizaciones_cotizaciondetalle" ADD CONSTRAINT "cotizaciones_cotizac_created_by_id_1a3249b8_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cotizaciones_cotizac_created_by_id_1a3249b8_fk_accounts_user') THEN "
                'ALTER TABLE "cotizaciones_cotizaciondetalle" DROP CONSTRAINT "cotizaciones_cotizac_created_by_id_1a3249b8_fk_accounts_user"; '
                'ALTER TABLE "cotizaciones_cotizaciondetalle" ADD CONSTRAINT "cotizaciones_cotizac_created_by_id_1a3249b8_fk_auth_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cotizaciones_cotizac_updated_by_id_e67303b7_fk_auth_user') THEN "
                'ALTER TABLE "cotizaciones_cotizaciondetalle" DROP CONSTRAINT "cotizaciones_cotizac_updated_by_id_e67303b7_fk_auth_user"; '
                'ALTER TABLE "cotizaciones_cotizaciondetalle" ADD CONSTRAINT "cotizaciones_cotizac_updated_by_id_e67303b7_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cotizaciones_cotizac_updated_by_id_e67303b7_fk_accounts_user') THEN "
                'ALTER TABLE "cotizaciones_cotizaciondetalle" DROP CONSTRAINT "cotizaciones_cotizac_updated_by_id_e67303b7_fk_accounts_user"; '
                'ALTER TABLE "cotizaciones_cotizaciondetalle" ADD CONSTRAINT "cotizaciones_cotizac_updated_by_id_e67303b7_fk_auth_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
