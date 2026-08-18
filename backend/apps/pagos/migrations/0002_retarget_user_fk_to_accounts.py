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
        ('pagos', '0001_cuenta_por_pagar_pago_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pagos_cuentaporpagar_created_by_id_2372ffc5_fk_auth_user_id') THEN "
                'ALTER TABLE "pagos_cuentaporpagar" DROP CONSTRAINT "pagos_cuentaporpagar_created_by_id_2372ffc5_fk_auth_user_id"; '
                'ALTER TABLE "pagos_cuentaporpagar" ADD CONSTRAINT "pagos_cuentaporpagar_created_by_id_2372ffc5_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pagos_cuentaporpagar_created_by_id_2372ffc5_fk_accounts_user_id') THEN "
                'ALTER TABLE "pagos_cuentaporpagar" DROP CONSTRAINT "pagos_cuentaporpagar_created_by_id_2372ffc5_fk_accounts_user_id"; '
                'ALTER TABLE "pagos_cuentaporpagar" ADD CONSTRAINT "pagos_cuentaporpagar_created_by_id_2372ffc5_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pagos_cuentaporpagar_updated_by_id_c57a59b3_fk_auth_user_id') THEN "
                'ALTER TABLE "pagos_cuentaporpagar" DROP CONSTRAINT "pagos_cuentaporpagar_updated_by_id_c57a59b3_fk_auth_user_id"; '
                'ALTER TABLE "pagos_cuentaporpagar" ADD CONSTRAINT "pagos_cuentaporpagar_updated_by_id_c57a59b3_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pagos_cuentaporpagar_updated_by_id_c57a59b3_fk_accounts_user_id') THEN "
                'ALTER TABLE "pagos_cuentaporpagar" DROP CONSTRAINT "pagos_cuentaporpagar_updated_by_id_c57a59b3_fk_accounts_user_id"; '
                'ALTER TABLE "pagos_cuentaporpagar" ADD CONSTRAINT "pagos_cuentaporpagar_updated_by_id_c57a59b3_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pagos_pago_created_by_id_3ec79e12_fk_auth_user_id') THEN "
                'ALTER TABLE "pagos_pago" DROP CONSTRAINT "pagos_pago_created_by_id_3ec79e12_fk_auth_user_id"; '
                'ALTER TABLE "pagos_pago" ADD CONSTRAINT "pagos_pago_created_by_id_3ec79e12_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pagos_pago_created_by_id_3ec79e12_fk_accounts_user_id') THEN "
                'ALTER TABLE "pagos_pago" DROP CONSTRAINT "pagos_pago_created_by_id_3ec79e12_fk_accounts_user_id"; '
                'ALTER TABLE "pagos_pago" ADD CONSTRAINT "pagos_pago_created_by_id_3ec79e12_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pagos_pago_updated_by_id_322df457_fk_auth_user_id') THEN "
                'ALTER TABLE "pagos_pago" DROP CONSTRAINT "pagos_pago_updated_by_id_322df457_fk_auth_user_id"; '
                'ALTER TABLE "pagos_pago" ADD CONSTRAINT "pagos_pago_updated_by_id_322df457_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pagos_pago_updated_by_id_322df457_fk_accounts_user_id') THEN "
                'ALTER TABLE "pagos_pago" DROP CONSTRAINT "pagos_pago_updated_by_id_322df457_fk_accounts_user_id"; '
                'ALTER TABLE "pagos_pago" ADD CONSTRAINT "pagos_pago_updated_by_id_322df457_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
