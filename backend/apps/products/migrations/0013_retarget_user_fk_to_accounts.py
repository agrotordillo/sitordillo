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
        ('products', '0012_producto_impuestos'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_almacen_created_by_id_9dfaca4d_fk_auth_user_id') THEN "
                'ALTER TABLE "products_almacen" DROP CONSTRAINT "products_almacen_created_by_id_9dfaca4d_fk_auth_user_id"; '
                'ALTER TABLE "products_almacen" ADD CONSTRAINT "products_almacen_created_by_id_9dfaca4d_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_almacen_created_by_id_9dfaca4d_fk_accounts_user_id') THEN "
                'ALTER TABLE "products_almacen" DROP CONSTRAINT "products_almacen_created_by_id_9dfaca4d_fk_accounts_user_id"; '
                'ALTER TABLE "products_almacen" ADD CONSTRAINT "products_almacen_created_by_id_9dfaca4d_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_almacen_updated_by_id_4fe4c83f_fk_auth_user_id') THEN "
                'ALTER TABLE "products_almacen" DROP CONSTRAINT "products_almacen_updated_by_id_4fe4c83f_fk_auth_user_id"; '
                'ALTER TABLE "products_almacen" ADD CONSTRAINT "products_almacen_updated_by_id_4fe4c83f_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_almacen_updated_by_id_4fe4c83f_fk_accounts_user_id') THEN "
                'ALTER TABLE "products_almacen" DROP CONSTRAINT "products_almacen_updated_by_id_4fe4c83f_fk_accounts_user_id"; '
                'ALTER TABLE "products_almacen" ADD CONSTRAINT "products_almacen_updated_by_id_4fe4c83f_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_categoria_created_by_id_db985ef7_fk_auth_user_id') THEN "
                'ALTER TABLE "products_categoria" DROP CONSTRAINT "products_categoria_created_by_id_db985ef7_fk_auth_user_id"; '
                'ALTER TABLE "products_categoria" ADD CONSTRAINT "products_categoria_created_by_id_db985ef7_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_categoria_created_by_id_db985ef7_fk_accounts_user_id') THEN "
                'ALTER TABLE "products_categoria" DROP CONSTRAINT "products_categoria_created_by_id_db985ef7_fk_accounts_user_id"; '
                'ALTER TABLE "products_categoria" ADD CONSTRAINT "products_categoria_created_by_id_db985ef7_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_categoria_updated_by_id_1d60f147_fk_auth_user_id') THEN "
                'ALTER TABLE "products_categoria" DROP CONSTRAINT "products_categoria_updated_by_id_1d60f147_fk_auth_user_id"; '
                'ALTER TABLE "products_categoria" ADD CONSTRAINT "products_categoria_updated_by_id_1d60f147_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_categoria_updated_by_id_1d60f147_fk_accounts_user_id') THEN "
                'ALTER TABLE "products_categoria" DROP CONSTRAINT "products_categoria_updated_by_id_1d60f147_fk_accounts_user_id"; '
                'ALTER TABLE "products_categoria" ADD CONSTRAINT "products_categoria_updated_by_id_1d60f147_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_marca_created_by_id_ae7ca6b2_fk_auth_user_id') THEN "
                'ALTER TABLE "products_marca" DROP CONSTRAINT "products_marca_created_by_id_ae7ca6b2_fk_auth_user_id"; '
                'ALTER TABLE "products_marca" ADD CONSTRAINT "products_marca_created_by_id_ae7ca6b2_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_marca_created_by_id_ae7ca6b2_fk_accounts_user_id') THEN "
                'ALTER TABLE "products_marca" DROP CONSTRAINT "products_marca_created_by_id_ae7ca6b2_fk_accounts_user_id"; '
                'ALTER TABLE "products_marca" ADD CONSTRAINT "products_marca_created_by_id_ae7ca6b2_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_marca_updated_by_id_46e46e50_fk_auth_user_id') THEN "
                'ALTER TABLE "products_marca" DROP CONSTRAINT "products_marca_updated_by_id_46e46e50_fk_auth_user_id"; '
                'ALTER TABLE "products_marca" ADD CONSTRAINT "products_marca_updated_by_id_46e46e50_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_marca_updated_by_id_46e46e50_fk_accounts_user_id') THEN "
                'ALTER TABLE "products_marca" DROP CONSTRAINT "products_marca_updated_by_id_46e46e50_fk_accounts_user_id"; '
                'ALTER TABLE "products_marca" ADD CONSTRAINT "products_marca_updated_by_id_46e46e50_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_paquetecomp_created_by_id_f291c16d_fk_auth_user') THEN "
                'ALTER TABLE "products_paquetecomponente" DROP CONSTRAINT "products_paquetecomp_created_by_id_f291c16d_fk_auth_user"; '
                'ALTER TABLE "products_paquetecomponente" ADD CONSTRAINT "products_paquetecomp_created_by_id_f291c16d_fk_accounts_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_paquetecomp_created_by_id_f291c16d_fk_accounts_user') THEN "
                'ALTER TABLE "products_paquetecomponente" DROP CONSTRAINT "products_paquetecomp_created_by_id_f291c16d_fk_accounts_user"; '
                'ALTER TABLE "products_paquetecomponente" ADD CONSTRAINT "products_paquetecomp_created_by_id_f291c16d_fk_auth_user" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_paquetecomp_updated_by_id_346d2188_fk_auth_user') THEN "
                'ALTER TABLE "products_paquetecomponente" DROP CONSTRAINT "products_paquetecomp_updated_by_id_346d2188_fk_auth_user"; '
                'ALTER TABLE "products_paquetecomponente" ADD CONSTRAINT "products_paquetecomp_updated_by_id_346d2188_fk_accounts_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_paquetecomp_updated_by_id_346d2188_fk_accounts_user') THEN "
                'ALTER TABLE "products_paquetecomponente" DROP CONSTRAINT "products_paquetecomp_updated_by_id_346d2188_fk_accounts_user"; '
                'ALTER TABLE "products_paquetecomponente" ADD CONSTRAINT "products_paquetecomp_updated_by_id_346d2188_fk_auth_user" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_producto_created_by_id_510d8933_fk_auth_user_id') THEN "
                'ALTER TABLE "products_producto" DROP CONSTRAINT "products_producto_created_by_id_510d8933_fk_auth_user_id"; '
                'ALTER TABLE "products_producto" ADD CONSTRAINT "products_producto_created_by_id_510d8933_fk_accounts_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_producto_created_by_id_510d8933_fk_accounts_user_id') THEN "
                'ALTER TABLE "products_producto" DROP CONSTRAINT "products_producto_created_by_id_510d8933_fk_accounts_user_id"; '
                'ALTER TABLE "products_producto" ADD CONSTRAINT "products_producto_created_by_id_510d8933_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_producto_updated_by_id_9dd493d5_fk_auth_user_id') THEN "
                'ALTER TABLE "products_producto" DROP CONSTRAINT "products_producto_updated_by_id_9dd493d5_fk_auth_user_id"; '
                'ALTER TABLE "products_producto" ADD CONSTRAINT "products_producto_updated_by_id_9dd493d5_fk_accounts_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_producto_updated_by_id_9dd493d5_fk_accounts_user_id') THEN "
                'ALTER TABLE "products_producto" DROP CONSTRAINT "products_producto_updated_by_id_9dd493d5_fk_accounts_user_id"; '
                'ALTER TABLE "products_producto" ADD CONSTRAINT "products_producto_updated_by_id_9dd493d5_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_subcategoria_created_by_id_1e11744f_fk_auth_user_id') THEN "
                'ALTER TABLE "products_subcategoria" DROP CONSTRAINT "products_subcategoria_created_by_id_1e11744f_fk_auth_user_id"; '
                'ALTER TABLE "products_subcategoria" ADD CONSTRAINT "products_subcategoria_created_by_id_1e11744f_fk_accounts_user_i" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_subcategoria_created_by_id_1e11744f_fk_accounts_user_i') THEN "
                'ALTER TABLE "products_subcategoria" DROP CONSTRAINT "products_subcategoria_created_by_id_1e11744f_fk_accounts_user_i"; '
                'ALTER TABLE "products_subcategoria" ADD CONSTRAINT "products_subcategoria_created_by_id_1e11744f_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_subcategoria_updated_by_id_5f12084c_fk_auth_user_id') THEN "
                'ALTER TABLE "products_subcategoria" DROP CONSTRAINT "products_subcategoria_updated_by_id_5f12084c_fk_auth_user_id"; '
                'ALTER TABLE "products_subcategoria" ADD CONSTRAINT "products_subcategoria_updated_by_id_5f12084c_fk_accounts_user_i" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_subcategoria_updated_by_id_5f12084c_fk_accounts_user_i') THEN "
                'ALTER TABLE "products_subcategoria" DROP CONSTRAINT "products_subcategoria_updated_by_id_5f12084c_fk_accounts_user_i"; '
                'ALTER TABLE "products_subcategoria" ADD CONSTRAINT "products_subcategoria_updated_by_id_5f12084c_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_unidadmedida_created_by_id_f97f4981_fk_auth_user_id') THEN "
                'ALTER TABLE "products_unidadmedida" DROP CONSTRAINT "products_unidadmedida_created_by_id_f97f4981_fk_auth_user_id"; '
                'ALTER TABLE "products_unidadmedida" ADD CONSTRAINT "products_unidadmedida_created_by_id_f97f4981_fk_accounts_user_i" '
                'FOREIGN KEY ("created_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_unidadmedida_created_by_id_f97f4981_fk_accounts_user_i') THEN "
                'ALTER TABLE "products_unidadmedida" DROP CONSTRAINT "products_unidadmedida_created_by_id_f97f4981_fk_accounts_user_i"; '
                'ALTER TABLE "products_unidadmedida" ADD CONSTRAINT "products_unidadmedida_created_by_id_f97f4981_fk_auth_user_id" '
                'FOREIGN KEY ("created_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_unidadmedida_updated_by_id_a4060c7a_fk_auth_user_id') THEN "
                'ALTER TABLE "products_unidadmedida" DROP CONSTRAINT "products_unidadmedida_updated_by_id_a4060c7a_fk_auth_user_id"; '
                'ALTER TABLE "products_unidadmedida" ADD CONSTRAINT "products_unidadmedida_updated_by_id_a4060c7a_fk_accounts_user_i" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "accounts_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "DO $$ BEGIN "
                "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'products_unidadmedida_updated_by_id_a4060c7a_fk_accounts_user_i') THEN "
                'ALTER TABLE "products_unidadmedida" DROP CONSTRAINT "products_unidadmedida_updated_by_id_a4060c7a_fk_accounts_user_i"; '
                'ALTER TABLE "products_unidadmedida" ADD CONSTRAINT "products_unidadmedida_updated_by_id_a4060c7a_fk_auth_user_id" '
                'FOREIGN KEY ("updated_by_id") REFERENCES "auth_user" ("id") '
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
        ),
    ]
