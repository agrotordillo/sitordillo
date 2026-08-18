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
        ('proveedores', '0002_descuento_pronto_pago'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'proveedores_proveedor_created_by_id_bb9cd856_fk_auth_user_id') THEN "
                'ALTER TABLE "proveedores_proveedor" DROP CONSTRAINT "proveedores_proveedor_created_by_id_bb9cd856_fk_auth_user_id"; '
                'ALTER TABLE "proveedores_proveedor" ADD CONSTRAINT "proveedores_proveedor_created_by_id_bb9cd856_fk_accounts_user_i" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'proveedores_proveedor_created_by_id_bb9cd856_fk_accounts_user_i') THEN "
                'ALTER TABLE "proveedores_proveedor" DROP CONSTRAINT "proveedores_proveedor_created_by_id_bb9cd856_fk_accounts_user_i"; '
                'ALTER TABLE "proveedores_proveedor" ADD CONSTRAINT "proveedores_proveedor_created_by_id_bb9cd856_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'proveedores_proveedor_updated_by_id_6652b933_fk_auth_user_id') THEN "
                'ALTER TABLE "proveedores_proveedor" DROP CONSTRAINT "proveedores_proveedor_updated_by_id_6652b933_fk_auth_user_id"; '
                'ALTER TABLE "proveedores_proveedor" ADD CONSTRAINT "proveedores_proveedor_updated_by_id_6652b933_fk_accounts_user_i" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'proveedores_proveedor_updated_by_id_6652b933_fk_accounts_user_i') THEN "
                'ALTER TABLE "proveedores_proveedor" DROP CONSTRAINT "proveedores_proveedor_updated_by_id_6652b933_fk_accounts_user_i"; '
                'ALTER TABLE "proveedores_proveedor" ADD CONSTRAINT "proveedores_proveedor_updated_by_id_6652b933_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
