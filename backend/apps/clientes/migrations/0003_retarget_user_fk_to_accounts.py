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
        ('clientes', '0002_seed_cliente_publico_general'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'clientes_cliente_created_by_id_488ce7ca_fk_auth_user_id') THEN "
                'ALTER TABLE "clientes_cliente" DROP CONSTRAINT "clientes_cliente_created_by_id_488ce7ca_fk_auth_user_id"; '
                'ALTER TABLE "clientes_cliente" ADD CONSTRAINT "clientes_cliente_created_by_id_488ce7ca_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'clientes_cliente_created_by_id_488ce7ca_fk_accounts_user_id') THEN "
                'ALTER TABLE "clientes_cliente" DROP CONSTRAINT "clientes_cliente_created_by_id_488ce7ca_fk_accounts_user_id"; '
                'ALTER TABLE "clientes_cliente" ADD CONSTRAINT "clientes_cliente_created_by_id_488ce7ca_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'clientes_cliente_updated_by_id_b21e0106_fk_auth_user_id') THEN "
                'ALTER TABLE "clientes_cliente" DROP CONSTRAINT "clientes_cliente_updated_by_id_b21e0106_fk_auth_user_id"; '
                'ALTER TABLE "clientes_cliente" ADD CONSTRAINT "clientes_cliente_updated_by_id_b21e0106_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'clientes_cliente_updated_by_id_b21e0106_fk_accounts_user_id') THEN "
                'ALTER TABLE "clientes_cliente" DROP CONSTRAINT "clientes_cliente_updated_by_id_b21e0106_fk_accounts_user_id"; '
                'ALTER TABLE "clientes_cliente" ADD CONSTRAINT "clientes_cliente_updated_by_id_b21e0106_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
