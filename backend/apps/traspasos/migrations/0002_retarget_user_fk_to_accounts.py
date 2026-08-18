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
        ('traspasos', '0001_traspaso_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspaso_created_by_id_e004e7d7_fk_auth_user_id') THEN "
                'ALTER TABLE "traspasos_traspaso" DROP CONSTRAINT "traspasos_traspaso_created_by_id_e004e7d7_fk_auth_user_id"; '
                'ALTER TABLE "traspasos_traspaso" ADD CONSTRAINT "traspasos_traspaso_created_by_id_e004e7d7_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspaso_created_by_id_e004e7d7_fk_accounts_user_id') THEN "
                'ALTER TABLE "traspasos_traspaso" DROP CONSTRAINT "traspasos_traspaso_created_by_id_e004e7d7_fk_accounts_user_id"; '
                'ALTER TABLE "traspasos_traspaso" ADD CONSTRAINT "traspasos_traspaso_created_by_id_e004e7d7_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspaso_updated_by_id_8f304098_fk_auth_user_id') THEN "
                'ALTER TABLE "traspasos_traspaso" DROP CONSTRAINT "traspasos_traspaso_updated_by_id_8f304098_fk_auth_user_id"; '
                'ALTER TABLE "traspasos_traspaso" ADD CONSTRAINT "traspasos_traspaso_updated_by_id_8f304098_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspaso_updated_by_id_8f304098_fk_accounts_user_id') THEN "
                'ALTER TABLE "traspasos_traspaso" DROP CONSTRAINT "traspasos_traspaso_updated_by_id_8f304098_fk_accounts_user_id"; '
                'ALTER TABLE "traspasos_traspaso" ADD CONSTRAINT "traspasos_traspaso_updated_by_id_8f304098_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspasode_created_by_id_3ccb1c96_fk_auth_user') THEN "
                'ALTER TABLE "traspasos_traspasodetalle" DROP CONSTRAINT "traspasos_traspasode_created_by_id_3ccb1c96_fk_auth_user"; '
                'ALTER TABLE "traspasos_traspasodetalle" ADD CONSTRAINT "traspasos_traspasode_created_by_id_3ccb1c96_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspasode_created_by_id_3ccb1c96_fk_accounts_user') THEN "
                'ALTER TABLE "traspasos_traspasodetalle" DROP CONSTRAINT "traspasos_traspasode_created_by_id_3ccb1c96_fk_accounts_user"; '
                'ALTER TABLE "traspasos_traspasodetalle" ADD CONSTRAINT "traspasos_traspasode_created_by_id_3ccb1c96_fk_auth_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspasode_updated_by_id_c7e8d678_fk_auth_user') THEN "
                'ALTER TABLE "traspasos_traspasodetalle" DROP CONSTRAINT "traspasos_traspasode_updated_by_id_c7e8d678_fk_auth_user"; '
                'ALTER TABLE "traspasos_traspasodetalle" ADD CONSTRAINT "traspasos_traspasode_updated_by_id_c7e8d678_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspasode_updated_by_id_c7e8d678_fk_accounts_user') THEN "
                'ALTER TABLE "traspasos_traspasodetalle" DROP CONSTRAINT "traspasos_traspasode_updated_by_id_c7e8d678_fk_accounts_user"; '
                'ALTER TABLE "traspasos_traspasodetalle" ADD CONSTRAINT "traspasos_traspasode_updated_by_id_c7e8d678_fk_auth_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspasolote_created_by_id_8fdaf919_fk_auth_user_id') THEN "
                'ALTER TABLE "traspasos_traspasolote" DROP CONSTRAINT "traspasos_traspasolote_created_by_id_8fdaf919_fk_auth_user_id"; '
                'ALTER TABLE "traspasos_traspasolote" ADD CONSTRAINT "traspasos_traspasolote_created_by_id_8fdaf919_fk_accounts_user_" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspasolote_created_by_id_8fdaf919_fk_accounts_user_') THEN "
                'ALTER TABLE "traspasos_traspasolote" DROP CONSTRAINT "traspasos_traspasolote_created_by_id_8fdaf919_fk_accounts_user_"; '
                'ALTER TABLE "traspasos_traspasolote" ADD CONSTRAINT "traspasos_traspasolote_created_by_id_8fdaf919_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspasolote_updated_by_id_58cf3ee4_fk_auth_user_id') THEN "
                'ALTER TABLE "traspasos_traspasolote" DROP CONSTRAINT "traspasos_traspasolote_updated_by_id_58cf3ee4_fk_auth_user_id"; '
                'ALTER TABLE "traspasos_traspasolote" ADD CONSTRAINT "traspasos_traspasolote_updated_by_id_58cf3ee4_fk_accounts_user_" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'traspasos_traspasolote_updated_by_id_58cf3ee4_fk_accounts_user_') THEN "
                'ALTER TABLE "traspasos_traspasolote" DROP CONSTRAINT "traspasos_traspasolote_updated_by_id_58cf3ee4_fk_accounts_user_"; '
                'ALTER TABLE "traspasos_traspasolote" ADD CONSTRAINT "traspasos_traspasolote_updated_by_id_58cf3ee4_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
