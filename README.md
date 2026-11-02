# BSRM Booking

BSRM Booking est une API FastAPI de réservation multi-tenant. Elle gère les établissements,
employés, prestations, horaires, disponibilités, clients et rendez-vous, ainsi qu’un parcours
de réservation publique destiné aux sites vitrines. PostgreSQL stocke les données et Alembic
gère les évolutions du schéma.

## Prérequis

- Python 3.13
- PostgreSQL 17, localement ou avec Docker
- PowerShell 7 recommandé sous Windows

## Installation locale (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Le fichier local `.env` est directement utilisé par l'application. Adaptez-y les URLs PostgreSQL,
les deux mots de passe, `JWT_SECRET_KEY` et `CORS_ORIGINS`. Ne versionnez jamais ce fichier.
En production, `JWT_SECRET_KEY` doit être un
secret aléatoire d'au moins 32 caractères et `CORS_ORIGINS` ne peut pas contenir `*`.

## Configuration

| Variable | Rôle | Valeur indicative |
| --- | --- | --- |
| `APP_NAME` | Nom OpenAPI de l'application | `Bosphoreum Booking API` |
| `APP_ENVIRONMENT` | Environnement courant | `development` ou `production` |
| `APP_DEBUG` | Mode debug FastAPI | `false` |
| `DATABASE_URL` | URL SQLAlchemy PostgreSQL | `postgresql+psycopg://...` |
| `DATABASE_MIGRATION_URL` | URL propriétaire réservée à Alembic | `postgresql+psycopg://...` |
| `DATABASE_APPLICATION_ROLE` | Rôle effectif runtime soumis à RLS | `bsrm_booking_app` |
| `JWT_SECRET_KEY` | Clé de signature JWT | secret aléatoire, 32 caractères minimum en production |
| `JWT_ALGORITHM` | Algorithme JWT autorisé | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Durée de l'access token | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Durée du refresh token | `30` |
| `CORS_ORIGINS` | Origines JSON autorisées | `["https://app.example.com"]` |
| `ALLOWED_HOSTS` | Hosts HTTP acceptés | `["api.example.com"]` |
| `EXPOSE_API_DOCS` | Expose Swagger/OpenAPI | `true` en développement, `false` en production |
| `INVITATION_EXPIRE_HOURS` | Durée d'une invitation | `48` |
| `INVITATION_FRONTEND_URL` | Page frontend d'acceptation | `https://app.example.com/accept-invitation` |
| `EMAIL_DELIVERY_MODE` | Livraison des invitations | `console` en développement, `smtp` en production |
| `PUBLIC_BOOKING_CHALLENGE_MODE` | Protection anti-bot des réservations publiques | `disabled` en développement, `turnstile` obligatoire en production |
| `TURNSTILE_SECRET_KEY` | Secret serveur Cloudflare Turnstile | vide en développement, secret injecté en production |
| `TURNSTILE_EXPECTED_ACTION` | Action Turnstile attendue et vérifiée | `booking` |
| `PUBLIC_BOOKING_*_RATE_LIMIT` | Quotas publics par IP hashée et site | `120`, `60`, `5` selon l'opération |
| `PUBLIC_BOOKING_MAX_BODY_BYTES` | Taille maximale du POST public | `16384` |

Les variables PostgreSQL `POSTGRES_DB`, `POSTGRES_USER` et `POSTGRES_PASSWORD` configurent
le rôle de migration. `POSTGRES_APP_USER` et `POSTGRES_APP_PASSWORD` configurent un login
runtime distinct, membre du rôle non privilégié `bsrm_booking_app`.

## Base de données et migrations

Démarrer uniquement PostgreSQL avec Docker, puis appliquer les migrations :

```powershell
docker compose up -d postgres
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe check
```

Créer une nouvelle migration après une modification explicite des modèles :

```powershell
.\.venv\Scripts\alembic.exe revision --autogenerate -m "describe schema change"
```

Une migration déjà appliquée ne doit jamais être modifiée.

## Row-Level Security PostgreSQL

Les tables tenant-scopées utilisent des policies RLS en complément des filtres applicatifs.
Le rôle propriétaire/migration ne doit être utilisé que par Alembic. L'application se connecte
avec `POSTGRES_APP_USER`, puis adopte le rôle `bsrm_booking_app`, qui n'est ni propriétaire,
ni superuser, ni `BYPASSRLS`.

Après validation du JWT, l'identifiant utilisateur est limité à la transaction. Après validation
du membership, le tenant est appliqué avec `SET LOCAL app.tenant_id`. Le contexte est réappliqué
automatiquement si un service ouvre une nouvelle transaction après `commit()` ou `rollback()`.
Une connexion sans tenant ne voit aucune ligne protégée.

Sur un volume PostgreSQL déjà initialisé, le script `docker/postgres/init-app-role.sh` ne sera pas
rejoué automatiquement. Créez alors le login runtime manuellement avec un secret fourni hors Git,
puis accordez-lui le rôle :

```sql
CREATE ROLE bsrm_booking_runtime LOGIN PASSWORD '<secret-fort>'
    NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOBYPASSRLS;
GRANT bsrm_booking_app TO bsrm_booking_runtime;
```

## Lancer l'API

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

Points d'accès utiles :

- documentation Swagger : `http://127.0.0.1:8000/docs`
- contrôle de vie : `GET /health`
- contrôle de disponibilité PostgreSQL : `GET /ready`

Les réponses incluent `X-Request-ID`. Les journaux contiennent la méthode, le chemin sans
query string, le statut et la durée, sans corps de requête, jeton ou donnée client.

## Provisioning, authentification et multi-tenant

Il n'existe aucun register public. Un opérateur crée une première fois le compte Platform Admin
avec la commande locale privilégiée suivante :

```powershell
.\.venv\Scripts\python.exe -m app.cli create-platform-admin `
  --email admin@example.com `
  --first-name Platform `
  --last-name Admin
```

La commande exige `DATABASE_MIGRATION_URL` et demande le mot de passe sans l'afficher. Le
Platform Admin provisionne ensuite un tenant sous `/api/v1/platform/tenants`, puis crée une
invitation liée à ce tenant et à un rôle. En production, le lien unique est envoyé par SMTP ;
seul son hash est stocké. Le token expire, peut être révoqué et ne peut être consommé qu'une fois.

Un nouveau User accepte avec `/api/v1/auth/invitations/accept`. Un User déjà existant se connecte
puis utilise `/api/v1/auth/invitations/accept-existing`. La connexion émet ensuite un access token
JWT et un refresh token opaque hashé ; rotation et logout restent inchangés.

Pour les routes tenant-scopées, envoyez :

```text
Authorization: Bearer <access-token>
X-Tenant-ID: <tenant-uuid>
```

Le serveur recharge toujours l'utilisateur et son membership actif en base. Il ne fait pas
confiance à un `tenant_id` fourni dans un DTO ou dans le JWT. Les rôles sont `owner`, `admin`,
`manager` et `staff`. Une ressource appartenant à un autre tenant répond `404`; un rôle
insuffisant répond `403`.

## Routes principales

- `/api/v1/platform/tenants` et invitations, réservés au `platform_admin`
- `/api/v1/auth/invitations/accept`, login, refresh, logout et me
- `/api/v1/tenants` et `/api/v1/tenants/{tenant_id}/locations`
- `/api/v1/employees` et associations employé-prestation
- `/api/v1/services`
- horaires, fermetures, disponibilités et absences sous les routes Location/Employee
- `/api/v1/customers`
- `/api/v1/availability`
- `/api/v1/setup/status` pour la checklist de configuration tenant
- `/api/v1/appointments` et transitions de statut
- `/api/v1/booking-site` pour configurer/faire tourner la clé publiable (`owner`/`admin`)
- `/api/v1/public/booking/*` pour un site vitrine, sans JWT ni `X-Tenant-ID`

Les listes Employees, Services, Customers et Appointments acceptent `page` et `page_size`
(`1..100`) et renvoient `{items, page, page_size, total}`. Les filtres métier documentés dans
Swagger restent combinables avec la pagination.

## Documentation du projet

- [`API_USAGE_SPEC.md`](API_USAGE_SPEC.md) décrit les routes authentifiées et leurs contrats ;
- [`PUBLIC_BOOKING_API_SPEC.md`](PUBLIC_BOOKING_API_SPEC.md) documente le parcours de réservation publique ;
- [`BACKEND_IMPLEMENTATION_SPEC.md`](BACKEND_IMPLEMENTATION_SPEC.md) présente l’architecture et les phases de réalisation ;
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md) conserve le bilan technique de la vérification du 17 août 2026.

## Réservation depuis un site vitrine

Un owner/admin crée une configuration tenant-scopée avec `POST /api/v1/booking-site`, en envoyant
son Bearer token et `X-Tenant-ID`. La réponse retourne une clé `bsrm_pk_test_...` en développement
ou `bsrm_pk_live_...` en production. La clé brute n'est affichée qu'à la création ou lors d'une
rotation ; seul son hash est conservé en base.

Le site vitrine utilise ensuite exclusivement `/api/v1/public/booking` et transmet :

```text
X-BSRM-Site-Key: <clé-publiable>
```

Il ne doit contenir aucun JWT, refresh token, `tenant_id`, secret SMTP ou secret Turnstile. Les
origines navigateur sont configurées exactement sur le `BookingSite`. En production, le frontend
obtient un jeton Cloudflare Turnstile et l'envoie dans `X-Booking-Challenge` lors du POST, avec une
`Idempotency-Key` UUID. Le contrat frontend complet est dans `PUBLIC_BOOKING_API_SPEC.md`.

## Tests et qualité

La suite crée une base PostgreSQL de test dédiée et lui applique les migrations.

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
git diff --check
```

## Docker Compose : développement

Après avoir créé et renseigné `.env` :

```powershell
docker compose build
docker compose up -d postgres
docker compose run --rm api alembic upgrade head
docker compose up -d api
docker compose ps
```

Le profil de développement expose PostgreSQL sur `localhost:5432`, conserve Swagger et autorise
le mode invitation `console` : le lien est alors retourné uniquement au Platform Admin.

## Docker Compose : production

Compléter directement `.env.production`, notamment `CORS_ORIGINS`, `ALLOWED_HOSTS`,
`INVITATION_FRONTEND_URL` et `TURNSTILE_SECRET_KEY`, puis laisser `EXPOSE_API_DOCS=false`.
La configuration production refuse au démarrage : secret JWT
faible, wildcard CORS/hosts, URL d'invitation non HTTPS, debug, docs publiques, SMTP absent ou
protection Turnstile publique absente.

```powershell
docker compose --env-file .env.production -f docker-compose.production.yaml `
  --profile tools run --rm migrate
docker compose --env-file .env.production -f docker-compose.production.yaml up -d api postgres
```

Le processus API ne reçoit que le compte PostgreSQL runtime. Le credential propriétaire est
injecté uniquement dans le service ponctuel `migrate`. PostgreSQL n'est pas publié sur l'hôte
dans la composition production.

L'image exécute l'application avec un utilisateur non-root. Les secrets restent injectés par
l'environnement et ne sont présents ni dans le Dockerfile ni dans l'image.

## Structure

```text
app/
  api/            routes, dépendances et gestionnaires d'erreurs
  core/           configuration, sécurité, base, logs et contexte tenant
  models/         modèles SQLAlchemy
  repositories/   accès aux données, sans commit
  schemas/        DTOs Pydantic
  services/       règles métier et transactions
migrations/       historique Alembic
tests/            tests d'intégration PostgreSQL et API
```

## Copyright and License

Ce dépôt est publié à des fins de portfolio et de démonstration. Sa publication ne constitue pas une autorisation générale de réutiliser le code original. Toute reproduction, modification, adaptation, redistribution, réutilisation ou exploitation commerciale nécessite l’autorisation écrite préalable du titulaire des droits. Toute utilisation non autorisée est interdite, sous réserve des droits accordés par GitHub aux utilisateurs de ses dépôts publics et des exceptions prévues par la loi applicable. Consultez le fichier `LICENSE`.

Les logiciels, polices, images, vidéos, logos, icônes et autres ressources de tiers restent soumis à leurs droits et licences respectifs. Leur présence dans le dépôt ne constitue pas une revendication de propriété.
#   B S R M _ B o o k i n g  
 