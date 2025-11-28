# hospital-ai

## Local setup

1. Create an environment file based on `env.example` and update the values for your environment (database, secret key, allowed hosts, etc.).
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Apply migrations (requires the Postgres instance defined in your env file to be running):
   ```bash
   python manage.py migrate
   ```
4. Create a Django superuser so you can manage hospitals/patients through the admin:
   ```bash
   python manage.py createsuperuser
   ```

## Authentication

- `POST /api/auth/login/` – accepts `username` and `password` and returns a JWT access/refresh token pair along with the signed-in user's role.
- `POST /api/auth/refresh/` – accepts a valid refresh token and returns a new access token.
- `POST /api/hospitals/auth/login/` – same as above but restricted to users whose role is `Hospital`.
- `POST /api/hospitals/auth/refresh/` – refresh endpoint for hospital access tokens.
- `GET /api/hospitals/me/` – returns the authenticated hospital’s profile (name, description, administrator, timestamps).

All other API routes are JWT-protected by default. Use the access token in the `Authorization: Bearer <token>` header. Super admins can create hospital users directly from the Django admin – selecting the `Hospital` role exposes the related hospital profile inline so all hospital data, including user passwords, can be managed in one place.

## Hospital patient API

Authenticated hospital accounts can fully manage their own patients:

- `GET /api/hospitals/patients/` – paginated list with the key fields shown in the UI (name, phone, assigned doctor, surgery, risk level, status).
- `POST /api/hospitals/patients/` – create a patient; the hospital relationship is inferred from the authenticated user.
- `GET /api/hospitals/patients/<id>/` – detail view that expands all patient information, including surgery metadata, medications, and medical records.
- `PATCH|PUT /api/hospitals/patients/<id>/` – update an existing patient belonging to the hospital.
- `DELETE /api/hospitals/patients/<id>/` – remove a patient owned by the hospital.

### AI-generated care plans

- Set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`, default `gpt-4o-mini`) in your `.env`.
- When a hospital creates a patient, the backend sends the patient’s profile to OpenAI and stores the structured response (`care_plan`, `diet_plan`, `activities`, `ai_insights`) in `PatientCarePlan`.
- The patient detail endpoint returns the cached AI output so the UI can render care-plan, diet, activities, and AI insight tabs without additional API calls to OpenAI.

### Hospital surgery API

- `GET /api/hospitals/surgeries/` – list all surgeries configured for the signed-in hospital user.
- `POST /api/hospitals/surgeries/` – create a surgery and its supporting plans (diet + activities). Payloads accept nested structures for allowed/restricted items and meal plans, mirroring the UI layouts shown above.
- `GET /api/hospitals/surgeries/<id>/` – fetch full detail including diet plan summary, allowed/forbidden foods, meal plan entries, and categorized activity recommendations.
- `PATCH|PUT /api/hospitals/surgeries/<id>/` – update the surgery and completely replace associated diet/activity plan entries with the provided lists.
- `DELETE /api/hospitals/surgeries/<id>/` – remove the surgery (patients referencing it should be reassigned first).

Diet and activity plans are now normalized: each allowed/forbidden food, meal entry, or activity is stored as a dedicated row so the UI can add/edit/remove individual bullets without juggling JSON blobs.