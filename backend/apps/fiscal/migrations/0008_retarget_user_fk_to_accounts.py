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
        ('fiscal', '0007_clave_unidad_prod_serv_sat_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_claveprodservsat_created_by_id_8ef78227_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_claveprodservsat" DROP CONSTRAINT "fiscal_claveprodservsat_created_by_id_8ef78227_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_claveprodservsat" ADD CONSTRAINT "fiscal_claveprodservsat_created_by_id_8ef78227_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_claveprodservsat_created_by_id_8ef78227_fk_accounts_user') THEN "
                'ALTER TABLE "fiscal_claveprodservsat" DROP CONSTRAINT "fiscal_claveprodservsat_created_by_id_8ef78227_fk_accounts_user"; '
                'ALTER TABLE "fiscal_claveprodservsat" ADD CONSTRAINT "fiscal_claveprodservsat_created_by_id_8ef78227_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_claveprodservsat_updated_by_id_fbcf5523_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_claveprodservsat" DROP CONSTRAINT "fiscal_claveprodservsat_updated_by_id_fbcf5523_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_claveprodservsat" ADD CONSTRAINT "fiscal_claveprodservsat_updated_by_id_fbcf5523_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_claveprodservsat_updated_by_id_fbcf5523_fk_accounts_user') THEN "
                'ALTER TABLE "fiscal_claveprodservsat" DROP CONSTRAINT "fiscal_claveprodservsat_updated_by_id_fbcf5523_fk_accounts_user"; '
                'ALTER TABLE "fiscal_claveprodservsat" ADD CONSTRAINT "fiscal_claveprodservsat_updated_by_id_fbcf5523_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_claveunidadsat_created_by_id_6b336c2f_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_claveunidadsat" DROP CONSTRAINT "fiscal_claveunidadsat_created_by_id_6b336c2f_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_claveunidadsat" ADD CONSTRAINT "fiscal_claveunidadsat_created_by_id_6b336c2f_fk_accounts_user_i" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_claveunidadsat_created_by_id_6b336c2f_fk_accounts_user_i') THEN "
                'ALTER TABLE "fiscal_claveunidadsat" DROP CONSTRAINT "fiscal_claveunidadsat_created_by_id_6b336c2f_fk_accounts_user_i"; '
                'ALTER TABLE "fiscal_claveunidadsat" ADD CONSTRAINT "fiscal_claveunidadsat_created_by_id_6b336c2f_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_claveunidadsat_updated_by_id_ade27be4_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_claveunidadsat" DROP CONSTRAINT "fiscal_claveunidadsat_updated_by_id_ade27be4_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_claveunidadsat" ADD CONSTRAINT "fiscal_claveunidadsat_updated_by_id_ade27be4_fk_accounts_user_i" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_claveunidadsat_updated_by_id_ade27be4_fk_accounts_user_i') THEN "
                'ALTER TABLE "fiscal_claveunidadsat" DROP CONSTRAINT "fiscal_claveunidadsat_updated_by_id_ade27be4_fk_accounts_user_i"; '
                'ALTER TABLE "fiscal_claveunidadsat" ADD CONSTRAINT "fiscal_claveunidadsat_updated_by_id_ade27be4_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_formapago_created_by_id_1b5c7899_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_formapago" DROP CONSTRAINT "fiscal_formapago_created_by_id_1b5c7899_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_formapago" ADD CONSTRAINT "fiscal_formapago_created_by_id_1b5c7899_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_formapago_created_by_id_1b5c7899_fk_accounts_user_id') THEN "
                'ALTER TABLE "fiscal_formapago" DROP CONSTRAINT "fiscal_formapago_created_by_id_1b5c7899_fk_accounts_user_id"; '
                'ALTER TABLE "fiscal_formapago" ADD CONSTRAINT "fiscal_formapago_created_by_id_1b5c7899_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_formapago_updated_by_id_88f04c49_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_formapago" DROP CONSTRAINT "fiscal_formapago_updated_by_id_88f04c49_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_formapago" ADD CONSTRAINT "fiscal_formapago_updated_by_id_88f04c49_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_formapago_updated_by_id_88f04c49_fk_accounts_user_id') THEN "
                'ALTER TABLE "fiscal_formapago" DROP CONSTRAINT "fiscal_formapago_updated_by_id_88f04c49_fk_accounts_user_id"; '
                'ALTER TABLE "fiscal_formapago" ADD CONSTRAINT "fiscal_formapago_updated_by_id_88f04c49_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_metodopago_created_by_id_c2cd2e1e_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_metodopago" DROP CONSTRAINT "fiscal_metodopago_created_by_id_c2cd2e1e_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_metodopago" ADD CONSTRAINT "fiscal_metodopago_created_by_id_c2cd2e1e_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_metodopago_created_by_id_c2cd2e1e_fk_accounts_user_id') THEN "
                'ALTER TABLE "fiscal_metodopago" DROP CONSTRAINT "fiscal_metodopago_created_by_id_c2cd2e1e_fk_accounts_user_id"; '
                'ALTER TABLE "fiscal_metodopago" ADD CONSTRAINT "fiscal_metodopago_created_by_id_c2cd2e1e_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_metodopago_updated_by_id_1d16d659_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_metodopago" DROP CONSTRAINT "fiscal_metodopago_updated_by_id_1d16d659_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_metodopago" ADD CONSTRAINT "fiscal_metodopago_updated_by_id_1d16d659_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_metodopago_updated_by_id_1d16d659_fk_accounts_user_id') THEN "
                'ALTER TABLE "fiscal_metodopago" DROP CONSTRAINT "fiscal_metodopago_updated_by_id_1d16d659_fk_accounts_user_id"; '
                'ALTER TABLE "fiscal_metodopago" ADD CONSTRAINT "fiscal_metodopago_updated_by_id_1d16d659_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_regimenfiscal_created_by_id_e9016082_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_regimenfiscal" DROP CONSTRAINT "fiscal_regimenfiscal_created_by_id_e9016082_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_regimenfiscal" ADD CONSTRAINT "fiscal_regimenfiscal_created_by_id_e9016082_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_regimenfiscal_created_by_id_e9016082_fk_accounts_user_id') THEN "
                'ALTER TABLE "fiscal_regimenfiscal" DROP CONSTRAINT "fiscal_regimenfiscal_created_by_id_e9016082_fk_accounts_user_id"; '
                'ALTER TABLE "fiscal_regimenfiscal" ADD CONSTRAINT "fiscal_regimenfiscal_created_by_id_e9016082_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_regimenfiscal_updated_by_id_d7b63d23_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_regimenfiscal" DROP CONSTRAINT "fiscal_regimenfiscal_updated_by_id_d7b63d23_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_regimenfiscal" ADD CONSTRAINT "fiscal_regimenfiscal_updated_by_id_d7b63d23_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_regimenfiscal_updated_by_id_d7b63d23_fk_accounts_user_id') THEN "
                'ALTER TABLE "fiscal_regimenfiscal" DROP CONSTRAINT "fiscal_regimenfiscal_updated_by_id_d7b63d23_fk_accounts_user_id"; '
                'ALTER TABLE "fiscal_regimenfiscal" ADD CONSTRAINT "fiscal_regimenfiscal_updated_by_id_d7b63d23_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_usocfdi_created_by_id_6fe8da29_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_usocfdi" DROP CONSTRAINT "fiscal_usocfdi_created_by_id_6fe8da29_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_usocfdi" ADD CONSTRAINT "fiscal_usocfdi_created_by_id_6fe8da29_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_usocfdi_created_by_id_6fe8da29_fk_accounts_user_id') THEN "
                'ALTER TABLE "fiscal_usocfdi" DROP CONSTRAINT "fiscal_usocfdi_created_by_id_6fe8da29_fk_accounts_user_id"; '
                'ALTER TABLE "fiscal_usocfdi" ADD CONSTRAINT "fiscal_usocfdi_created_by_id_6fe8da29_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_usocfdi_updated_by_id_3c0018b0_fk_auth_user_id') THEN "
                'ALTER TABLE "fiscal_usocfdi" DROP CONSTRAINT "fiscal_usocfdi_updated_by_id_3c0018b0_fk_auth_user_id"; '
                'ALTER TABLE "fiscal_usocfdi" ADD CONSTRAINT "fiscal_usocfdi_updated_by_id_3c0018b0_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fiscal_usocfdi_updated_by_id_3c0018b0_fk_accounts_user_id') THEN "
                'ALTER TABLE "fiscal_usocfdi" DROP CONSTRAINT "fiscal_usocfdi_updated_by_id_3c0018b0_fk_accounts_user_id"; '
                'ALTER TABLE "fiscal_usocfdi" ADD CONSTRAINT "fiscal_usocfdi_updated_by_id_3c0018b0_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
