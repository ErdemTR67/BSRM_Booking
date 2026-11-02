# BSRM Booking : État du projet au 17 août 2026

## État actuel

Le backend FastAPI implémente les phases 1 à 16. Le self-service a été retiré : les tenants sont
provisionnés par un Platform Admin global et les comptes clients sont créés/rattachés uniquement
via une invitation tenant-scopée, expirante, révocable et à usage unique. Le filtrage applicatif,
les rôles tenant et la RLS PostgreSQL restent la double barrière d'isolation.
Une surface distincte de réservation publique est maintenant disponible pour les sites vitrines :
elle résout une clé publiable vers un tenant sans exposer de JWT ni accepter de `tenant_id` client.

## Réalisé

- Socle, configuration, SQLAlchemy synchrone, Alembic et FastAPI : terminé et vérifié.
- User/Auth : bcrypt, JWT, refresh rotation, logout et `/auth/me` : terminé et vérifié.
- Tenant, Location, Membership, rôles et `TenantContext` : terminé et vérifié.
- Employee, Service et EmployeeService : terminé et vérifié.
- OpeningHour, LocationClosure, EmployeeAvailability et TimeOff : terminé et vérifié.
- Customer, calcul des disponibilités et Appointments : terminé et vérifié.
- Statut de configuration tenant `/api/v1/setup/status` : terminé et vérifié ; la progression
  est recalculée depuis les données actives et exige une chaîne réservable cohérente.
- Anti-chevauchement PostgreSQL par exclusion GiST : terminé et vérifié.
- Tests et durcissement transversal : terminé et vérifié.
- Production readiness : pagination, CORS, health/ready, logs, Docker et README : terminé et vérifié.
- Extension post-spec : réservation publique pour site vitrine : terminé et vérifié.
  - `BookingSite`, clé publiable hashée, rotation/désactivation et origines exactes : terminé et vérifié ;
  - `PublicBookingContext` distinct, résolution pré-tenant bornée et contexte RLS : terminé et vérifié ;
  - catalogue public Location/Service/Employee sans données privées : terminé et vérifié ;
  - Availability publique avec délais, horizon, prix/durée effectifs et créneau exact : terminé et vérifié ;
  - Appointment public mono-service, Customer inline, référence et idempotence persistée : terminé et vérifié ;
  - rate limiting PostgreSQL par IP hashée/site, CORS par site et Turnstile obligatoire en production : terminé et vérifié ;
  - confirmation multipart Bosphoreum après commit, sans rollback du rendez-vous en cas d'échec : implémenté et vérifié pour le rendu et le mode console ; livraison SMTP distante non vérifiée.
- PHASE 16 : Provisioning administré et invitations
  - `PlatformRole` global et bootstrap opérateur hors HTTP : terminé et vérifié ;
  - provisioning Tenant réservé au Platform Admin : terminé et vérifié ;
  - invitations hashées, expirantes, révocables et à usage unique : terminé et vérifié ;
  - création atomique User + Membership et rattachement d'un User existant : terminé et vérifié ;
  - retrait du register et du `POST /tenants` self-service : terminé et vérifié ;
  - SMTP obligatoire, e-mail d'invitation multipart aux couleurs Bosphoreum, docs désactivées et
    hosts/CORS explicites en production : terminé et vérifié.
- PHASE 14 : RLS PostgreSQL
  - rôle effectif `bsrm_booking_app` non propriétaire, non-superuser, sans `BYPASSRLS` : terminé et vérifié ;
  - RLS `ENABLE` + `FORCE` et policies tenant : terminé et vérifié dans les catalogues ;
  - `SET LOCAL ROLE`, `SET LOCAL app.user_id` et `SET LOCAL app.tenant_id` : terminé et vérifié ;
  - réapplication après nouvelle transaction et absence de fuite du pool : terminé et vérifié ;
  - bootstrap Auth/Tenant/Membership avant TenantContext : terminé et vérifié avec fonctions limitées ;
  - tests avec un vrai login PostgreSQL non privilégié : terminé et vérifié.

## Partiellement réalisé

- Aucun module prévu par `BACKEND_IMPLEMENTATION_SPEC.md` n'est actuellement classé partiel.

## Non commencé

- Aucune phase restante dans `BACKEND_IMPLEMENTATION_SPEC.md`.

## Database / Alembic

- 18 migrations linéaires, de `d7c0c91d421f` à `c8a42d61ef30`.
- Révision courante : `c8a42d61ef30 (head)`.
- `alembic upgrade head` : succès.
- `alembic check` : aucun drift détecté.
- Nouvelles migrations : `c4a91e8d7f20_enable_tenant_row_level_security.py` et
  `e7b2d40a6c31_harden_application_role_privileges.py`, puis
  `f4c8a1d2e903_add_platform_admin_and_invitations.py`.
- Extension publique : `9d2f6c7a81b4_add_public_booking_api.py`, migration corrective
  `b7e1a4c920df_remove_redundant_booking_site_constraints.py`, puis
  `c8a42d61ef30_name_public_booking_rls_policies.py`.
- Tables avec RLS forcée et policy stable `tenant_isolation_<table>` :
  - `tenants` avec `id` comme périmètre tenant ;
  - `locations`, `memberships`, `employees`, `services`, `opening_hours` ;
  - `employee_availabilities`, `time_off`, `location_closures`, `customers`, `appointments` ;
  - `employee_services` et `appointment_services` via leurs parents tenant-scopés.
  - `booking_sites`, `public_booking_idempotency` et `public_booking_rate_limits` avec RLS forcée.
- `appointments.public_reference` est nullable pour l'historique et unique lorsqu'il est renseigné.
- `app_resolve_booking_site(text)` est `SECURITY DEFINER`, son `search_path` est fixé, PUBLIC ne
  peut pas l'exécuter et le rôle applicatif ne peut résoudre qu'un site/tenant actifs.
- Les policies directes utilisent
  `NULLIF(current_setting('app.tenant_id', true), '')::uuid` afin qu'un contexte absent ou
  remis à zéro ferme l'accès sans provoquer de cast invalide.
- Downgrade réellement vérifié sur la base de test : fonctions/policies supprimées et RLS
  désactivée sur les 13 tables, puis upgrade à nouveau vérifié.
- Le rôle cluster `bsrm_booking_app` est volontairement conservé au downgrade ; ses privilèges
  dans la base, fonctions et default privileges sont révoqués.
- Le rôle runtime n'a aucun droit sur `alembic_version` et ne reçoit aucun privilège par défaut
  sur les futures tables ou séquences.

## Authentication

- `users`, `refresh_tokens` et `platform_roles` sont globaux ; `platform_roles` est en lecture seule
  pour le rôle runtime.
- Aucun register public n'est enregistré dans FastAPI.
- Un nouveau User est créé via `/auth/invitations/accept`; un User existant utilise
  `/auth/invitations/accept-existing` après login.
- Login, refresh, logout et `/auth/me` fonctionnent sans TenantContext avec le rôle runtime.
- Les invitations stockent uniquement un SHA-256 du token brut et sont verrouillées/consommées
  par des fonctions `SECURITY DEFINER` bornées.
- Après validation du JWT et relecture du User actif, `app.user_id` est posé localement.
- La lecture du Membership actif utilise `app_get_active_membership`, fonction
  `SECURITY DEFINER` dont l'exécution est retirée à PUBLIC et accordée uniquement au rôle app.
- La fonction exige que le `user_id` demandé corresponde à `app.user_id`.

## Multi-tenant

- Les filtres tenant explicites des repositories et les validations services restent en place.
- Le membership actif et le Tenant actif sont vérifiés avant la pose de `app.tenant_id`.
- Le contexte est stocké dans `Session.info`, puis réappliqué par événement SQLAlchemy au début
  de toute nouvelle transaction après `commit()` ou `rollback()`.
- `SET LOCAL` garantit que le contexte disparaît à la fin de la transaction et ne fuit pas lors
  du retour de la connexion au pool.
- Une ressource d'un autre tenant reste en 404 au niveau API ; une permission insuffisante reste en 403.
- Le site vitrine ne fournit ni `X-Tenant-ID` ni JWT. La clé publiable est hashée en base, résolue
  avant le contexte tenant par une fonction bornée, puis toutes les requêtes métier utilisent à la
  fois des filtres `tenant_id` explicites et la RLS.
- L'ancienne fonction self-service `app_create_tenant_with_owner` n'est plus exécutable par le
  rôle applicatif.
- La création Tenant est autorisée par une policy RLS uniquement si `app.user_id` possède un
  `PlatformRole` actif.
- La création/réactivation du Membership est atomique avec la consommation de l'invitation.
- La liste des tenants autorisés passe par `app_list_active_tenants`, également bornée au User authentifié.

## API routes

- `/health`, `/ready`, `/docs`, `/openapi.json`.
- Auth sous `/api/v1/auth` : acceptation d'invitation, login, refresh, logout, me.
- Control plane sous `/api/v1/platform` : CRUD Tenant, création/listing/révocation d'invitations.
- Tenant/Location, Employee/EmployeeService, Service, horaires, fermetures,
  disponibilités employés, absences, Customer, disponibilité calculée et Appointment.
- Setup sous `/api/v1/setup/status` : checklist tenant-scopée accessible à tous les rôles actifs.
- Configuration privée du site sous `/api/v1/booking-site` : create/get/patch/rotate/delete pour
  `owner` et `admin`, avec Bearer + `X-Tenant-ID`.
- Réservation publique sous `/api/v1/public/booking` : context, locations, services, employees,
  availability et création Appointment ; aucun Bearer ni `X-Tenant-ID`.
- Les routes publiques n'acceptent toujours aucun `tenant_id` dérivable dans leurs DTOs.
- La RLS ne change pas les contrats HTTP ni les routes enregistrées.

## Tests

- Dernière exécution : **149 réussis, 0 échoué, 0 erreur**.
- `tests/test_rls.py` utilise un login PostgreSQL aléatoire réel, non-superuser, sans
  `BYPASSRLS`, membre du rôle effectif `bsrm_booking_app`.
- Cas RLS vérifiés :
  - lecture des données propres et masquage du tenant étranger ;
  - update étranger affectant zéro ligne ;
  - insert avec un autre `tenant_id` refusé par PostgreSQL ;
  - absence de tenant donnant zéro ligne ;
  - même backend PostgreSQL réutilisé successivement pour deux tenants sans fuite ;
  - rollback effaçant le contexte de connexion ;
  - nouvelle transaction de la même Session réappliquant le contexte de requête ;
  - API inter-tenant en 404 ;
  - flux login/me/refresh/logout sans TenantContext ;
  - provisioning Platform Admin, invitation et acceptation avec le rôle réel ;
  - expiration, révocation, non-réutilisation et vérification d'email ;
  - création Tenant/Location et probes health/ready/docs avec le rôle réel.
  - résolution d'une clé de site sans contexte préalable puis cloisonnement RLS du tenant résolu ;
  - CORS dynamique, Host validation, origine refusée, limite de body, rotation/désactivation de clé ;
  - absence de données privées Employee, ressource inter-tenant en 404 et créneau non offert rejeté ;
  - idempotence, body divergent en 409, rate limiting 429 et challenge Turnstile validé par hostname/action.
- Ruff : succès.
- Non couvert : performance RLS à très grande volumétrie et déploiement distant réel.

## Phase actuelle

- **PHASE 16 : Provisioning administré et invitations** : terminé et vérifié.
- Toutes les phases de `BACKEND_IMPLEMENTATION_SPEC.md` ont été réalisées et vérifiées.
- Extension post-spec : statut de configuration tenant : terminé et vérifié.
- Extension post-spec : API de réservation publique pour sites vitrines : terminé et vérifié.

## Prochaine étape recommandée

Créer la configuration du premier site avec `POST /api/v1/booking-site`, enregistrer la clé
publiable dans le frontend vitrine, configurer le widget Cloudflare Turnstile et réaliser un test
de bout en bout sur le domaine de staging réellement déclaré dans `allowed_origins`.

## Points techniques à traiter

- Le `.env` local historique utilise encore les identifiants propriétaires comme session login ;
  l'Engine adopte néanmoins `bsrm_booking_app` avec `SET LOCAL ROLE` avant chaque transaction.
  Les fichiers Docker Compose prévoient un login runtime réellement distinct pour la production.
- Les fonctions `SECURITY DEFINER` sont une surface sensible, mais leur portée est limitée au
  bootstrap Membership/Tenant, leur `search_path` est fixé, PUBLIC n'a aucun droit d'exécution
  et l'identité demandée doit correspondre à `app.user_id`.
- Le rôle partagé `bsrm_booking_app` reste présent au niveau cluster après downgrade afin de ne
  pas casser d'autres bases du même cluster.
- Mypy n'est pas configuré.
- Les performances RLS/pagination n'ont pas été testées en charge à grande volumétrie.
- L'envoi SMTP est synchrone ; un outbox/worker sera préférable si le volume d'invitations augmente.
- La confirmation de réservation est envoyée après commit et sans outbox/retry ; son échec est
  journalisé mais ne supprime pas le rendez-vous.
- Les buckets de rate limiting et enregistrements d'idempotence sont persistants mais aucune tâche
  de purge périodique n'est encore fournie ; elle sera nécessaire à forte volumétrie.

## Dernier contrôle

Date : **2026-08-17** (Europe/Brussels).

Commandes et vérifications réellement exécutées :

- lecture complète de `BACKEND_IMPLEMENTATION_SPEC.md`, `PROJECT_STATUS.md` et inspection du dépôt : succès ;
- inspection `pg_roles` : propriétaire `bosphoreum` superuser/BYPASSRLS et rôle effectif
  `bsrm_booking_app` non-superuser/sans BYPASSRLS ;
- inspection `pg_class` et `pg_policies` : 16 tables forcées et 16 policies présentes ;
- downgrade/upgrade historique du socle RLS : 0 puis 13 tables/policies avant l'extension publique ;
- tests RLS avec login non privilégié, incluant la résolution publique : 5 réussis ;
- tests Setup : tenant vide, chaîne complète, durée incompatible, employé inactif,
  authentification et isolation inter-tenant, 6 réussis ;
- tests e-mail : invitations et confirmation multipart Bosphoreum, échappement HTML et transport SMTP Mailjet, 3 réussis ;
- compilation, imports, Alembic, Ruff et `git diff --check` : succès ;
- migrations publiques appliquées jusqu'à `c8a42d61ef30`, `alembic check` sans drift ;
- tests publics ciblés : 7 réussis ; test catalogue RLS réel : réussi ;
- suite complète PostgreSQL : 149 réussis ;
- `/health`, `/ready` et `/docs` : succès via le flux applicatif RLS.
