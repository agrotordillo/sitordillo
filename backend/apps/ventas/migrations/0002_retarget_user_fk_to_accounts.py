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
        ('ventas', '0001_venta_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_devolucioncliente_created_by_id_eb82d05f_fk_auth_user_id') THEN "
                'ALTER TABLE "ventas_devolucioncliente" DROP CONSTRAINT "ventas_devolucioncliente_created_by_id_eb82d05f_fk_auth_user_id"; '
                'ALTER TABLE "ventas_devolucioncliente" ADD CONSTRAINT "ventas_devolucioncliente_created_by_id_eb82d05f_fk_accounts_use" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_devolucioncliente_created_by_id_eb82d05f_fk_accounts_use') THEN "
                'ALTER TABLE "ventas_devolucioncliente" DROP CONSTRAINT "ventas_devolucioncliente_created_by_id_eb82d05f_fk_accounts_use"; '
                'ALTER TABLE "ventas_devolucioncliente" ADD CONSTRAINT "ventas_devolucioncliente_created_by_id_eb82d05f_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_devolucioncliente_updated_by_id_d6cb449c_fk_auth_user_id') THEN "
                'ALTER TABLE "ventas_devolucioncliente" DROP CONSTRAINT "ventas_devolucioncliente_updated_by_id_d6cb449c_fk_auth_user_id"; '
                'ALTER TABLE "ventas_devolucioncliente" ADD CONSTRAINT "ventas_devolucioncliente_updated_by_id_d6cb449c_fk_accounts_use" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_devolucioncliente_updated_by_id_d6cb449c_fk_accounts_use') THEN "
                'ALTER TABLE "ventas_devolucioncliente" DROP CONSTRAINT "ventas_devolucioncliente_updated_by_id_d6cb449c_fk_accounts_use"; '
                'ALTER TABLE "ventas_devolucioncliente" ADD CONSTRAINT "ventas_devolucioncliente_updated_by_id_d6cb449c_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_devolucioncli_created_by_id_154c3505_fk_auth_user') THEN "
                'ALTER TABLE "ventas_devolucionclientedetalle" DROP CONSTRAINT "ventas_devolucioncli_created_by_id_154c3505_fk_auth_user"; '
                'ALTER TABLE "ventas_devolucionclientedetalle" ADD CONSTRAINT "ventas_devolucioncli_created_by_id_154c3505_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_devolucioncli_created_by_id_154c3505_fk_accounts_user') THEN "
                'ALTER TABLE "ventas_devolucionclientedetalle" DROP CONSTRAINT "ventas_devolucioncli_created_by_id_154c3505_fk_accounts_user"; '
                'ALTER TABLE "ventas_devolucionclientedetalle" ADD CONSTRAINT "ventas_devolucioncli_created_by_id_154c3505_fk_auth_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_devolucioncli_updated_by_id_56a6c7e9_fk_auth_user') THEN "
                'ALTER TABLE "ventas_devolucionclientedetalle" DROP CONSTRAINT "ventas_devolucioncli_updated_by_id_56a6c7e9_fk_auth_user"; '
                'ALTER TABLE "ventas_devolucionclientedetalle" ADD CONSTRAINT "ventas_devolucioncli_updated_by_id_56a6c7e9_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_devolucioncli_updated_by_id_56a6c7e9_fk_accounts_user') THEN "
                'ALTER TABLE "ventas_devolucionclientedetalle" DROP CONSTRAINT "ventas_devolucioncli_updated_by_id_56a6c7e9_fk_accounts_user"; '
                'ALTER TABLE "ventas_devolucionclientedetalle" ADD CONSTRAINT "ventas_devolucioncli_updated_by_id_56a6c7e9_fk_auth_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_venta_created_by_id_6fc6ecbb_fk_auth_user_id') THEN "
                'ALTER TABLE "ventas_venta" DROP CONSTRAINT "ventas_venta_created_by_id_6fc6ecbb_fk_auth_user_id"; '
                'ALTER TABLE "ventas_venta" ADD CONSTRAINT "ventas_venta_created_by_id_6fc6ecbb_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_venta_created_by_id_6fc6ecbb_fk_accounts_user_id') THEN "
                'ALTER TABLE "ventas_venta" DROP CONSTRAINT "ventas_venta_created_by_id_6fc6ecbb_fk_accounts_user_id"; '
                'ALTER TABLE "ventas_venta" ADD CONSTRAINT "ventas_venta_created_by_id_6fc6ecbb_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_venta_updated_by_id_8fa58d19_fk_auth_user_id') THEN "
                'ALTER TABLE "ventas_venta" DROP CONSTRAINT "ventas_venta_updated_by_id_8fa58d19_fk_auth_user_id"; '
                'ALTER TABLE "ventas_venta" ADD CONSTRAINT "ventas_venta_updated_by_id_8fa58d19_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_venta_updated_by_id_8fa58d19_fk_accounts_user_id') THEN "
                'ALTER TABLE "ventas_venta" DROP CONSTRAINT "ventas_venta_updated_by_id_8fa58d19_fk_accounts_user_id"; '
                'ALTER TABLE "ventas_venta" ADD CONSTRAINT "ventas_venta_updated_by_id_8fa58d19_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_ventadetalle_created_by_id_4bdd8c4c_fk_auth_user_id') THEN "
                'ALTER TABLE "ventas_ventadetalle" DROP CONSTRAINT "ventas_ventadetalle_created_by_id_4bdd8c4c_fk_auth_user_id"; '
                'ALTER TABLE "ventas_ventadetalle" ADD CONSTRAINT "ventas_ventadetalle_created_by_id_4bdd8c4c_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_ventadetalle_created_by_id_4bdd8c4c_fk_accounts_user_id') THEN "
                'ALTER TABLE "ventas_ventadetalle" DROP CONSTRAINT "ventas_ventadetalle_created_by_id_4bdd8c4c_fk_accounts_user_id"; '
                'ALTER TABLE "ventas_ventadetalle" ADD CONSTRAINT "ventas_ventadetalle_created_by_id_4bdd8c4c_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_ventadetalle_updated_by_id_3e4581d6_fk_auth_user_id') THEN "
                'ALTER TABLE "ventas_ventadetalle" DROP CONSTRAINT "ventas_ventadetalle_updated_by_id_3e4581d6_fk_auth_user_id"; '
                'ALTER TABLE "ventas_ventadetalle" ADD CONSTRAINT "ventas_ventadetalle_updated_by_id_3e4581d6_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_ventadetalle_updated_by_id_3e4581d6_fk_accounts_user_id') THEN "
                'ALTER TABLE "ventas_ventadetalle" DROP CONSTRAINT "ventas_ventadetalle_updated_by_id_3e4581d6_fk_accounts_user_id"; '
                'ALTER TABLE "ventas_ventadetalle" ADD CONSTRAINT "ventas_ventadetalle_updated_by_id_3e4581d6_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_ventadetallelote_created_by_id_64f9fa51_fk_auth_user_id') THEN "
                'ALTER TABLE "ventas_ventadetallelote" DROP CONSTRAINT "ventas_ventadetallelote_created_by_id_64f9fa51_fk_auth_user_id"; '
                'ALTER TABLE "ventas_ventadetallelote" ADD CONSTRAINT "ventas_ventadetallelote_created_by_id_64f9fa51_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_ventadetallelote_created_by_id_64f9fa51_fk_accounts_user') THEN "
                'ALTER TABLE "ventas_ventadetallelote" DROP CONSTRAINT "ventas_ventadetallelote_created_by_id_64f9fa51_fk_accounts_user"; '
                'ALTER TABLE "ventas_ventadetallelote" ADD CONSTRAINT "ventas_ventadetallelote_created_by_id_64f9fa51_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_ventadetallelote_updated_by_id_1cebc167_fk_auth_user_id') THEN "
                'ALTER TABLE "ventas_ventadetallelote" DROP CONSTRAINT "ventas_ventadetallelote_updated_by_id_1cebc167_fk_auth_user_id"; '
                'ALTER TABLE "ventas_ventadetallelote" ADD CONSTRAINT "ventas_ventadetallelote_updated_by_id_1cebc167_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ventas_ventadetallelote_updated_by_id_1cebc167_fk_accounts_user') THEN "
                'ALTER TABLE "ventas_ventadetallelote" DROP CONSTRAINT "ventas_ventadetallelote_updated_by_id_1cebc167_fk_accounts_user"; '
                'ALTER TABLE "ventas_ventadetallelote" ADD CONSTRAINT "ventas_ventadetallelote_updated_by_id_1cebc167_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
