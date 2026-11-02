# BSRM Booking : Public Booking API Specification

## 1. Objet du document

Ce document est le contrat destiné à un **site vitrine public** permettant aux visiteurs de :

- consulter les établissements ouverts à la réservation ;
- consulter les prestations réservables ;
- choisir éventuellement un professionnel ;
- consulter les créneaux réellement disponibles ;
- créer une réservation.

Il ne documente volontairement aucune fonction de gestion interne. Le frontend propriétaire doit
continuer à utiliser `API_USAGE_SPEC.md`. Le site vitrine doit utiliser exclusivement le présent
document et les futures routes `/api/v1/public/booking`.

### Statut au 17 août 2026

**Implémenté et vérifié dans le backend.**

La surface `/api/v1/public/booking` est séparée des routes administratives. Elle résout une clé
publiable hashée vers un unique tenant, applique le contexte RLS, filtre toutes les ressources par
tenant, limite le débit, impose l'idempotence du POST et exige Cloudflare Turnstile en production.

Il reste interdit de connecter un site public aux routes administratives en embarquant un JWT, un
refresh token ou les identifiants d'un propriétaire.

---

## 2. Principes permanents

### 2.1 Séparation des surfaces API

```text
Frontend propriétaire
→ /api/v1/auth
→ /api/v1/platform
→ routes tenant-scopées authentifiées

Site vitrine public
→ /api/v1/public/booking uniquement
```

Le site vitrine ne doit jamais appeler directement :

- `/api/v1/auth/*` ;
- `/api/v1/platform/*` ;
- `/api/v1/tenants/*` ;
- `/api/v1/customers/*` ;
- `/api/v1/employees/*` ;
- `/api/v1/services/*` ;
- `/api/v1/availability` ;
- `/api/v1/appointments/*` ;
- `/api/v1/setup/status`.

### 2.2 Tenant par défaut

Chaque site vitrine reçoit une **clé publiable de site** liée en base à un seul tenant :

```text
bsrm_pk_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

Le site configure cette valeur une seule fois. Le préfixe dépend du framework :

```env
# Vite
VITE_BSRM_API_URL=https://api.booking.example.com
VITE_BSRM_SITE_KEY=bsrm_pk_live_xxxxxxxxxxxxxxxxxxxxxxxx

# Next.js
NEXT_PUBLIC_BSRM_API_URL=https://api.booking.example.com
NEXT_PUBLIC_BSRM_SITE_KEY=bsrm_pk_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

Chaque appel public contient ensuite :

```http
X-BSRM-Site-Key: bsrm_pk_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

Le backend résout la clé vers le tenant, vérifie que le site, le tenant et la réservation publique
sont actifs, puis pose lui-même le contexte RLS.

Le site public n'envoie jamais :

- `X-Tenant-ID` ;
- `tenant_id` dans un body ;
- un Bearer token ;
- un refresh token.

La clé de site est **publiable et non secrète**. Elle sert au routage, à la rotation, aux quotas et
à la configuration CORS ; elle ne constitue jamais une autorisation d'administration.

### 2.3 Autorité du backend

Le backend reste la seule source de vérité pour :

- le tenant courant ;
- les ressources actives et publiques ;
- les employés réellement réservables ;
- les prix et durées effectifs ;
- les buffers ;
- les horaires, fermetures et absences ;
- les rendez-vous déjà existants ;
- le calcul de `ends_at` ;
- le statut initial du rendez-vous ;
- la prévention des chevauchements PostgreSQL.

---

## 3. Configuration frontend

Créer un client API unique configuré au démarrage :

```ts
const bookingApi = createBookingApi({
  baseUrl: publicEnvironment.bsrmApiUrl,
  siteKey: publicEnvironment.bsrmSiteKey,
});
```

Ce client ajoute automatiquement `X-BSRM-Site-Key`. Aucun composant ne doit construire lui-même
le header ou choisir un autre tenant.

Les variables publiques ne doivent contenir que :

- l'URL publique du backend ;
- la clé publiable du site.

Ne jamais y mettre de clé Mailjet, secret JWT, mot de passe PostgreSQL ou token d'un utilisateur.

### Provisionnement de la clé par le frontend propriétaire

Cette étape n'est jamais exécutée par le site vitrine. Un `owner` ou `admin` authentifié configure
le site avec les routes privées suivantes, en transmettant Bearer + `X-Tenant-ID` :

- `POST /api/v1/booking-site`: crée la configuration et retourne la clé brute une seule fois ;
- `GET /api/v1/booking-site`: relit la configuration sans révéler la clé ;
- `PATCH /api/v1/booking-site`: modifie origines, Location par défaut et règles ;
- `POST /api/v1/booking-site/rotate-key`: invalide immédiatement l'ancienne clé et retourne la nouvelle ;
- `DELETE /api/v1/booking-site`: désactive la réservation publique.

`allowed_origins` contient des origines exactes (`scheme://host[:port]`), sans wildcard ni chemin.
Une origine HTTP est refusée en production. Une seule configuration de site public est autorisée
par tenant dans cette version.

---

## 4. Protocole commun

### Base URL

Développement :

```text
http://127.0.0.1:8000/api/v1/public/booking
```

Production :

```text
https://api.booking.example.com/api/v1/public/booking
```

### Headers de lecture

```http
Accept: application/json
X-BSRM-Site-Key: <clé publiable>
```

### Headers de création d'une réservation

```http
Accept: application/json
Content-Type: application/json
X-BSRM-Site-Key: <clé publiable>
Idempotency-Key: <UUID généré pour cette tentative>
X-Booking-Challenge: <jeton Cloudflare Turnstile obtenu avec action="booking">
```

### Format des dates

- Date civile : `YYYY-MM-DD`.
- Date/heure : ISO 8601 avec offset explicite, par exemple `2026-08-18T09:30:00+02:00`.
- Le frontend ne calcule jamais seul `ends_at`.
- Les créneaux sont retournés dans la timezone de la Location.

### Format monétaire

- Montants en centimes entiers.
- Devise ISO 4217 sur trois caractères.
- Exemple : `3900` + `EUR` = `39,00 EUR`.

### Format des erreurs

```json
{
  "error": {
    "code": "appointment_conflict",
    "message": "The requested appointment time is not available."
  }
}
```

Une validation `422` ajoute :

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request data is invalid.",
    "details": [
      {
        "location": ["body", "customer", "email"],
        "message": "value is not a valid email address",
        "type": "value_error"
      }
    ]
  }
}
```

---

## 5. DTOs publics

Les DTOs publics sont distincts des DTOs administratifs. Ils ne doivent jamais exposer :

- `tenant_id` ;
- `user_id` ou `membership_id` ;
- e-mail ou téléphone d'un employé ;
- identifiant interne d'un Customer ;
- notes internes ;
- données d'autres rendez-vous ;
- champs `created_at`/`updated_at` inutiles au visiteur ;
- configuration RLS ou permissions.

### `PublicBookingContextResponse`

```json
{
  "business": {
    "name": "Salon Bosphoreum",
    "slug": "salon-bosphoreum"
  },
  "booking": {
    "enabled": true,
    "default_location_id": "22222222-2222-4222-8222-222222222222",
    "slot_interval_minutes": 15,
    "minimum_notice_minutes": 120,
    "maximum_advance_days": 90,
    "require_phone": false
  }
}
```

### `PublicLocationResponse`

```json
{
  "id": "22222222-2222-4222-8222-222222222222",
  "name": "Bruxelles Centre",
  "slug": "bruxelles-centre",
  "timezone": "Europe/Brussels",
  "address_line_1": "1 rue Exemple",
  "address_line_2": null,
  "postal_code": "1000",
  "city": "Bruxelles",
  "country_code": "BE",
  "opening_hours": [
    {
      "weekday": 0,
      "starts_at": "09:00:00",
      "ends_at": "12:30:00"
    },
    {
      "weekday": 0,
      "starts_at": "13:30:00",
      "ends_at": "18:00:00"
    }
  ]
}
```

`weekday` suit Python : `0 = lundi`, `6 = dimanche`. Plusieurs périodes le même jour sont
autorisées. Seuls les OpeningHours actifs sont exposés. Les fermetures exceptionnelles ne doivent
pas être déduites de cette liste : Availability reste la source de vérité pour une date précise.

### `PublicServiceResponse`

```json
{
  "id": "44444444-4444-4444-8444-444444444444",
  "location_id": null,
  "name": "Coupe",
  "description": "Coupe et finition.",
  "duration_minutes": 40,
  "price_cents": 3900,
  "currency": "EUR"
}
```

`location_id: null` signifie que le Service peut être proposé dans plusieurs Locations. La route
filtre malgré tout les Services pour ne retourner que ceux réellement réservables dans la Location
demandée.

### `PublicEmployeeResponse`

```json
{
  "id": "33333333-3333-4333-8333-333333333333",
  "display_name": "Ada Lovelace",
  "display_color": "#8074C8"
}
```

### `PublicAvailabilitySlotResponse`

```json
{
  "employee_id": "33333333-3333-4333-8333-333333333333",
  "service_id": "44444444-4444-4444-8444-444444444444",
  "starts_at": "2026-08-18T09:30:00+02:00",
  "ends_at": "2026-08-18T10:25:00+02:00",
  "duration_minutes": 40,
  "total_duration_minutes": 55,
  "price_cents": 3900,
  "currency": "EUR"
}
```

`total_duration_minutes` inclut les buffers. Le prix et la durée retournés sont les valeurs
effectives de l'association EmployeeService lorsqu'une personnalisation existe.

### `PublicAppointmentCustomerCreate`

```json
{
  "first_name": "Marie",
  "last_name": "Client",
  "email": "marie@example.com",
  "phone": "+32123456789",
  "marketing_consent": false
}
```

L'e-mail est obligatoire pour le MVP public afin d'envoyer la confirmation. Le téléphone devient
obligatoire seulement lorsque `booking.require_phone` vaut `true`.

### `PublicAppointmentResponse`

```json
{
  "booking_reference": "BSRM-7F4K9P",
  "status": "pending",
  "location": {
    "id": "22222222-2222-4222-8222-222222222222",
    "name": "Bruxelles Centre",
    "timezone": "Europe/Brussels"
  },
  "employee": {
    "id": "33333333-3333-4333-8333-333333333333",
    "display_name": "Ada Lovelace"
  },
  "service": {
    "id": "44444444-4444-4444-8444-444444444444",
    "name": "Coupe",
    "duration_minutes": 40,
    "price_cents": 3900,
    "currency": "EUR"
  },
  "starts_at": "2026-08-18T09:30:00+02:00",
  "ends_at": "2026-08-18T10:25:00+02:00"
}
```

La réponse publique ne contient ni `customer_id`, ni données internes du rendez-vous.

---

## 6. Endpoints publics

## `GET /api/v1/public/booking/context`

### Objectif

Initialiser le site, vérifier que la réservation est activée et récupérer ses règles générales.

### Authentification

Aucun Bearer token. `X-BSRM-Site-Key` obligatoire.

### Query et body

Aucun.

### Réponse succès

`200`: `PublicBookingContextResponse`.

### Erreurs

- `404 booking_site_not_found`: clé inconnue, site désactivé ou tenant inactif ;
- `403 origin_not_allowed`: origine non autorisée ;
- `503 service_unavailable`.

### Cache

```http
Cache-Control: no-store
Vary: Origin
```

### Notes frontend

Appeler une fois au démarrage. Si `booking.enabled` est faux, masquer totalement le module de
réservation et afficher les informations de contact habituelles du site.

---

## `GET /api/v1/public/booking/locations`

### Objectif

Lister uniquement les Locations actives proposées sur ce site et possédant une configuration
réservable.

### Query et body

Aucun.

### Réponse succès

`200`: `list[PublicLocationResponse]`.

### Erreurs

`404 booking_site_not_found`; `403 origin_not_allowed`; `429 rate_limit_exceeded`; `503`.

### Notes frontend

- Zéro Location : afficher « La réservation en ligne n'est pas encore disponible ».
- Une Location : la sélectionner automatiquement.
- Plusieurs Locations : demander explicitement au visiteur de choisir.
- Ne jamais conserver une Location provenant d'une autre clé de site.

---

## `GET /api/v1/public/booking/services`

### Objectif

Lister les prestations réellement réservables pour une Location.

### Query parameters

- `location_id`: UUID obligatoire.

Exemple :

```http
GET /api/v1/public/booking/services?location_id=22222222-2222-4222-8222-222222222222
```

### Réponse succès

`200`: `list[PublicServiceResponse]`.

Le backend ne retourne que les Services qui sont :

- actifs ;
- globaux ou rattachés à la Location ;
- associés activement à au moins un Employee actif et réservable dans cette Location.

### Erreurs

`404 public_resource_not_found`; `429`; `503`.

### Notes frontend

Afficher le prix à partir de `price_cents`. Si le prix vaut `null`, afficher « Prix sur place » ou
le libellé commercial décidé par le tenant ; ne jamais inventer `0,00`.

---

## `GET /api/v1/public/booking/employees`

### Objectif

Lister les professionnels réservables pour un Service et une Location sans exposer leurs données
privées.

### Query parameters

- `location_id`: UUID obligatoire ;
- `service_id`: UUID obligatoire.

### Réponse succès

`200`: `list[PublicEmployeeResponse]`.

### Erreurs

`404 public_resource_not_found`; `429`; `503`.

### Notes frontend

Le site peut proposer :

- « Sans préférence », puis omettre `employee_id` lors de la recherche des disponibilités ;
- un Employee précis, puis envoyer son `id`.

Ne jamais afficher ou rechercher un employé à partir des routes administratives.

---

## `GET /api/v1/public/booking/availability`

### Objectif

Calculer les créneaux réservables à partir du moteur BSRM Booking existant.

### Query parameters

- `location_id`: UUID obligatoire ;
- `service_id`: UUID obligatoire ;
- `date`: `YYYY-MM-DD`, obligatoire ;
- `employee_id`: UUID optionnel ;
- `slot_interval_minutes`: optionnel, normalement omis par le site.

Exemple :

```http
GET /api/v1/public/booking/availability?location_id=22222222-2222-4222-8222-222222222222&service_id=44444444-4444-4444-8444-444444444444&date=2026-08-18
```

### Réponse succès

`200`: `list[PublicAvailabilitySlotResponse]`.

Le calcul doit intégrer :

- horaires d'ouverture ;
- fermetures ;
- disponibilités employé ;
- Time Off approuvés ;
- Appointments `pending` et `confirmed` ;
- association EmployeeService ;
- durée et prix personnalisés ;
- buffers ;
- délai minimum et horizon maximum de réservation publique.

### Erreurs

- `404 public_resource_not_found`: ressource absente, inactive ou hors du tenant lié au site ;
- `422 validation_error` ;
- `429 rate_limit_exceeded` ;
- `503 service_unavailable`.

### Cache

```http
Cache-Control: no-store
```

### Notes frontend

- Un tableau vide est un résultat valide : afficher « Aucun créneau disponible ».
- Ne pas présenter un créneau comme garanti avant le succès du POST Appointment.
- Ne pas calculer les créneaux à partir des OpeningHours dans le navigateur.
- Lorsque `employee_id` est omis, chaque slot retourne l'Employee réellement sélectionnable.

---

## `POST /api/v1/public/booking/appointments`

### Objectif

Créer une réservation publique atomique avec un nouveau Customer tenant-scopé.

### Headers supplémentaires

- `Idempotency-Key`: UUID obligatoire, stable pendant une même tentative ;
- `X-Booking-Challenge`: jeton anti-bot obligatoire en production.

### Body

```json
{
  "location_id": "22222222-2222-4222-8222-222222222222",
  "employee_id": "33333333-3333-4333-8333-333333333333",
  "service_id": "44444444-4444-4444-8444-444444444444",
  "starts_at": "2026-08-18T09:30:00+02:00",
  "customer": {
    "first_name": "Marie",
    "last_name": "Client",
    "email": "marie@example.com",
    "phone": "+32123456789",
    "marketing_consent": false
  },
  "customer_note": "Première visite"
}
```

Contraintes :

- `service_id` est volontairement singulier pour le MVP public ;
- l'e-mail Customer est obligatoire ;
- `customer_note` est optionnel et limité à 1000 caractères ;
- aucun `customer_id`, `tenant_id`, `status`, `ends_at`, prix ou durée n'est accepté ;
- les champs inconnus sont refusés ;
- le backend normalise les noms, l'e-mail et le téléphone selon ses règles métier.

### Réponse succès

`201`: `PublicAppointmentResponse`.

Le statut initial est toujours `pending`. Le backend crée le Customer et l'Appointment dans la
même transaction, conserve les snapshots du Service et envoie ensuite la confirmation par son
mécanisme de notification.

### Idempotence

Pour une même clé de site et un même `Idempotency-Key` :

- même body : retourner la première réponse sans créer un second rendez-vous ;
- le premier appel répond `201`, un replay identique répond `200` avec la même réponse ;
- body différent : `409 idempotency_conflict` ;
- durée de conservation minimale recommandée : 24 heures.

Le frontend génère la clé lorsqu'un visiteur arrive à l'étape de confirmation et la conserve lors
des retries réseau. Il ne génère une nouvelle clé qu'après abandon ou nouvelle réservation.

### Erreurs

- `404 public_resource_not_found` ;
- `409 appointment_conflict`: le créneau vient d'être pris ou n'est plus disponible ;
- `409 idempotency_conflict` ;
- `422 validation_error` ;
- `429 rate_limit_exceeded` ;
- `403 invalid_challenge` ;
- `503 service_unavailable`.

### Cache

```http
Cache-Control: no-store
```

### Notes frontend

Après `409 appointment_conflict` :

1. conserver les informations Customer déjà saisies ;
2. recharger Availability ;
3. demander un nouveau créneau ;
4. générer une nouvelle `Idempotency-Key` uniquement pour cette nouvelle sélection.

Après `201`, afficher la page de confirmation à partir de la réponse. Ne pas appeler une route
administrative pour relire le rendez-vous.

---

## 7. Parcours frontend de référence

```text
Chargement du site
→ GET /context
→ si booking.enabled = false : masquer le module
→ GET /locations
→ sélectionner automatiquement la Location par défaut si elle est présente
→ GET /services?location_id=...
→ choisir un Service
→ GET /employees?location_id=...&service_id=...
→ choisir un Employee ou « Sans préférence »
→ GET /availability pour une date
→ choisir un slot exact
→ saisir les coordonnées Customer
→ obtenir le jeton anti-bot
→ POST /appointments avec Idempotency-Key
→ afficher la confirmation
```

### Invalidation de l'état

- Changement de Location : vider Service, Employee et slot.
- Changement de Service : vider Employee et slot.
- Changement d'Employee : vider le slot et recharger Availability.
- Changement de date : vider le slot et recharger Availability.
- `409` à la réservation : invalider immédiatement Availability.

### Gestion réseau

- Une requête de lecture peut être retentée avec backoff limité.
- Le POST peut être retenté uniquement avec la même `Idempotency-Key` et le même body.
- Ne jamais interpréter une erreur réseau comme une réservation échouée certaine ; retenter d'abord
  idempotemment ou inviter le visiteur à vérifier son e-mail.

---

## 8. Sécurité obligatoire

### Aucun credential métier dans le navigateur

Interdits dans le site public :

- access token JWT ;
- refresh token ;
- compte owner/admin/manager/staff ;
- clé SMTP ou Mailjet ;
- `DATABASE_URL` ;
- `DATABASE_MIGRATION_URL` ;
- secret d'invitation.

### Résolution tenant

Le backend doit disposer d'une entité dédiée, par exemple `BookingSite`, contenant au minimum :

```text
id
tenant_id
name
publishable_key_hash
key_prefix
is_active
booking_enabled
default_location_id nullable
allowed_origins
slot_interval_minutes
minimum_notice_minutes
maximum_advance_days
require_phone
created_at
updated_at
```

La clé brute n'est affichée qu'à sa création. Le backend stocke son hash et permet sa rotation.

La résolution de la clé doit :

1. se faire avant le contexte tenant ;
2. vérifier `BookingSite.is_active` ;
3. vérifier `booking_enabled` ;
4. vérifier `Tenant.is_active` ;
5. vérifier l'Origin lorsqu'il est présent ;
6. poser `app.tenant_id` dans la transaction ;
7. appliquer ensuite les filtres explicites tenant et la RLS.

Ne jamais fabriquer un faux User ou un faux Membership pour faire passer les dépendances internes.
Créer un objet typé `PublicBookingContext` distinct de `TenantContext`.

### Anti-abus

Le backend doit prévoir :

- rate limiting par IP et clé de site ;
- challenge anti-bot vérifié côté serveur pour le POST ;
- taille maximale du body (`16 KiB` par défaut ; la même limite doit être appliquée au reverse proxy) ;
- validation stricte et `extra="forbid"` ;
- idempotence ;
- logs sans body, e-mail, téléphone, token ou clé complète ;
- alertes sur pics de `429`, `409` et échecs de challenge.

Valeurs initiales indicatives, configurables :

```text
lectures catalogue : 120 requêtes/minute/IP/site
availability       : 60 requêtes/minute/IP/site
création booking   : 5 tentatives/10 minutes/IP/site
```

En production, le backend utilise l'endpoint Siteverify de Cloudflare et vérifie les trois éléments :
`success=true`, `action=booking` et un `hostname` présent dans les origines du `BookingSite`.
Le frontend doit donc rendre le widget avec l'action Turnstile `booking`.

### CORS

Chaque `BookingSite` possède une liste d'origines exactes, par exemple :

```text
https://www.salon-example.be
https://salon-example.be
```

Pas de wildcard avec des credentials. Les routes publiques n'utilisent pas de cookies de session.
La préflight doit autoriser seulement les méthodes et headers nécessaires :

```text
GET, POST, OPTIONS
Content-Type
X-BSRM-Site-Key
Idempotency-Key
X-Booking-Challenge
```

L'Origin n'est pas une preuve d'identité et ne remplace ni le rate limiting ni l'anti-bot.

### Données personnelles

- Ne jamais exposer les Customers existants au public.
- Toujours créer la réservation avec un objet Customer inline.
- Ne jamais proposer de recherche par e-mail ou téléphone.
- `marketing_consent` est indépendant de l'acceptation nécessaire au traitement de la réservation.
- La réponse publique contient uniquement les informations utiles à la confirmation immédiate.

### Notifications

La réservation ne doit pas être annulée si l'envoi d'e-mail échoue après le commit. En production,
préférer un outbox/worker avec retries à un envoi SMTP dans la transaction HTTP.

L'e-mail de confirmation doit reprendre la DA Bosphoreum et contenir au minimum :

- référence ;
- établissement ;
- prestation ;
- professionnel ;
- début et fin dans la timezone locale ;
- prix si connu ;
- coordonnées de contact de l'entreprise.

---

## 9. Ce qui reste privé

Le site vitrine n'obtient jamais :

- liste des Customers ;
- liste ou détail des Appointments ;
- statistiques ;
- Memberships et rôles ;
- Platform Admin ;
- invitations ;
- statut Setup ;
- Time Off bruts ;
- OpeningHours bruts si le site n'en a pas besoin pour son contenu ;
- LocationClosure ;
- notes internes ;
- transitions confirm/complete/no-show ;
- modification ou suppression de Service/Employee/Location.

L'annulation autonome par lien signé est volontairement hors MVP. Elle devra utiliser plus tard un
token opaque, haché, expirant et lié à un Appointment ; jamais le simple UUID du rendez-vous.

Les paiements en ligne, acomptes, listes d'attente et réservations multi-services sont également
hors périmètre initial.

---

## 10. Implémentation backend livrée

Le backend satisfait maintenant le contrat MVP avec des migrations nouvelles et linéaires :

1. modèle et nouvelle migration `BookingSite` ;
2. génération, hash, rotation et désactivation de clé publiable ;
3. configuration des origines et règles de réservation ;
4. `PublicBookingContext` et dépendance de résolution sécurisée ;
5. DTOs publics minimaux ;
6. repositories tenant-scopés publics ;
7. services publics réutilisant le moteur Availability et la transaction Appointment ;
8. routes `/api/v1/public/booking` ;
9. Appointment public mono-service et Customer inline ;
10. idempotence persistée ;
11. rate limiting et vérification anti-bot ;
12. notification de confirmation après commit, dont l'échec ne supprime pas le rendez-vous ;
13. CORS par site ;
14. RLS pour les nouvelles tables et résolution pré-tenant bornée ;
15. tests d'intégration PostgreSQL, RLS et sécurité.

Le service public n'appelle pas les routes HTTP internes : il réutilise directement les repositories
et règles métier existants avec un `PublicBookingContext` distinct du contexte utilisateur.

Limites connues du MVP : l'envoi SMTP de confirmation est synchrone et sans outbox/retry ; les
buckets de rate limiting et les clés d'idempotence nécessiteront une politique de purge périodique
à forte volumétrie. Ces limites n'affectent ni l'atomicité du rendez-vous ni l'isolation tenant.

---

## 11. Tests d'acceptation obligatoires

### Tenant et exposition

- une clé retourne uniquement les données de son tenant ;
- une ressource d'un autre tenant retourne `404 public_resource_not_found` ;
- modifier `location_id`, `service_id` ou `employee_id` ne permet aucune fuite ;
- une clé inconnue, désactivée ou rotée ne fonctionne plus ;
- un tenant inactif ou `booking_enabled=false` ne peut pas être réservé ;
- aucun endpoint public n'accepte `X-Tenant-ID` comme source de vérité.

### Catalogue

- seuls Locations, Services et Employees actifs/réservables sont exposés ;
- e-mails, téléphones et `user_id` des Employees n'apparaissent jamais ;
- un Service sans association active n'est pas proposé ;
- les prix/durées personnalisés sont reflétés dans les slots.

### Availability

- horaires, disponibilités, fermetures, Time Off et rendez-vous actifs sont respectés ;
- une date hors délai minimum/horizon maximum est refusée ou retourne aucun slot selon le contrat
  final retenu ;
- une ressource inter-tenant est masquée ;
- les réponses sont `no-store`.

### Appointment

- Customer et Appointment sont créés atomiquement dans le tenant résolu ;
- `tenant_id`, `customer_id`, `status`, `ends_at` et prix injectés sont refusés ;
- deux requêtes concurrentes sur le même créneau donnent un succès et un `409` ;
- deux retries identiques avec la même clé donnent un seul Appointment ;
- même clé d'idempotence + body différent donne `409 idempotency_conflict` ;
- challenge invalide et rate limit sont réellement appliqués ;
- l'échec de notification après commit ne supprime pas la réservation ;
- aucune donnée Customer n'est exposée au-delà de la réponse prévue.

### Frontend

- le client injecte automatiquement la clé de site ;
- aucune route administrative n'est appelée ;
- les sélections dépendantes sont réinitialisées correctement ;
- un `409` recharge les disponibilités sans effacer les coordonnées saisies ;
- le POST est retenté uniquement avec la même clé et le même body ;
- le build public ne contient aucun secret métier.

---

## 12. Résumé pour le développeur du site vitrine

```text
Une seule clé publique configurée par le framework : BSRM_SITE_KEY
Une seule surface API : /api/v1/public/booking
Aucun login
Aucun X-Tenant-ID
Aucun JWT
Aucun accès Customer ou Appointment administratif
Le backend choisit toujours le tenant
Le backend calcule toujours disponibilité, durée, prix et fin
Le frontend affiche puis soumet exactement le slot retourné
```

Tant que les routes publiques de ce document ne sont pas implémentées et vérifiées dans le backend,
le module de réservation du site vitrine doit être considéré comme **bloqué**.
