# Osteoporosis Risk Prediction API

A Flask backend for user authentication, medical image upload, and osteoporosis risk prediction using a ResNet50-based PyTorch model.

The API stores user accounts and prediction records in MongoDB, uses JWTs for authentication, uses Redis only as an optional metadata cache, uploads images to Amazon S3, downloads the trained model from Google Drive when needed, and returns a positive/negative osteoporosis prediction with a confidence percentage.

> Medical disclaimer: this project is for educational and research use only. It is not a substitute for professional medical advice, diagnosis, or treatment.

## Features

- User registration with email verification
- JWT login, refresh, and logout
- Password reset by email
- Optional Redis caching for MongoDB metadata
- Image upload for prediction (`jpg`, `jpeg`, `png`)
- S3 image storage with temporary pre-signed URLs
- PyTorch ResNet50 inference
- User dashboard with prediction history
- Admin endpoints for users, records, statistics, verification, promotion, and deletion
- Vercel and WSGI entry points

## Tech Stack

- Python
- Flask
- Flask-PyMongo / MongoDB
- Flask-JWT-Extended
- Flask-Mail
- Flask-Redis
- Flask-CORS
- boto3 / Amazon S3
- PyTorch, torchvision, Pillow
- gdown for Google Drive model download

## Project Structure

```text
Osteoporosis-Risk-Prediction/
|-- app.py                    # Flask app entry point for local run/Vercel
|-- run.py                    # App factory, extension setup, config, blueprints
|-- wsgi.py                   # WSGI entry point
|-- requirements.txt          # Python dependencies
|-- vercel.json               # Vercel deployment config
|-- routes/
|   |-- auth.py               # Register, login, email verification, password reset
|   |-- predict.py            # Image upload and prediction result endpoints
|   |-- dashboard.py          # User prediction history
|   |-- admin.py              # Admin user/record management
|   `-- admin_bootstrap.py    # First admin bootstrap endpoint
|-- services/
|   |-- ml_service.py         # Model download, load, preprocessing, prediction
|   `-- s3_service.py         # S3 upload, download, delete, pre-signed URLs
`-- utils/
    |-- db_helpers.py         # Mongo ObjectId lookup helpers
    |-- security.py           # Password hashing wrappers
    `-- validators.py         # JWT/session/admin decorators and user helpers
```

## Requirements

- Python 3.10+ recommended
- MongoDB connection string
- Optional Redis instance for metadata caching
- AWS S3 bucket and credentials
- SMTP credentials for email verification and password reset
- Google Drive file ID for the trained model

## Environment Variables

Create a `.env` file in the project root:

```env
SECRET_KEY=change-me
JWT_SECRET_KEY=change-me-too
MONGO_URI=mongodb+srv://user:password@cluster/dbname
REDIS_URL=redis://localhost:6379/0
MONGO_METADATA_CACHE_TTL=60

FRONTEND_URL=http://localhost:3000
ADMIN_EMAIL=admin@example.com

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@example.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@example.com

AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-south-1
S3_BUCKET_NAME=your-bucket-name

MODEL_FILE_ID=google-drive-model-file-id
```

Notes:

- `MONGO_URI` is required at startup.
- Redis is optional. If unavailable, authentication, predictions, and MongoDB operations continue normally; only metadata caching is bypassed.
- `MONGO_METADATA_CACHE_TTL` controls the Redis TTL (seconds) for MongoDB metadata used by `/admin/stats` and dashboard record metadata. S3 image files and temporary pre-signed URLs are not cached.
- `MODEL_FILE_ID` is required the first time inference runs if `ml_models/knee_model2.pth` is not already present.
- `FRONTEND_URL` is used as the allowed CORS origin.
- The model is saved locally at `ml_models/knee_model2.pth` after download.

## Installation

```bash
git clone https://github.com/Shyam414/Osteoporosis-Risk-Prediction.git
cd Osteoporosis-Risk-Prediction

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

On macOS/Linux, activate the virtual environment with:

```bash
source venv/bin/activate
```

## Running Locally

```bash
python app.py
```

The API starts on:

```text
http://localhost:5000
```

Health check:

```http
GET /
```

Response:

```json
{
  "msg": "API is running. Use /auth/login to authenticate."
}
```

## API Endpoints

### Authentication

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | No | Create a user and send verification email |
| `GET` | `/auth/confirm/<token>` | No | Verify user email |
| `POST` | `/auth/login` | No | Login and return access/refresh tokens |
| `POST` | `/auth/refresh` | Refresh token | Issue a new access token |
| `POST` | `/auth/logout` | Access token | Return logout success; frontend removes stored tokens |
| `POST` | `/auth/forgot-password` | No | Send password reset email |
| `GET` | `/auth/reset-password/<token>` | No | Render reset password form |
| `POST` | `/auth/reset-password` | No | Reset password with token |

### Prediction

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/predict`, `/predict/`, `/predict/upload` | Access token | Upload image, store it in S3, run prediction |
| `GET` | `/predict/result/<job_id>` | Access token | Fetch one prediction record |

Upload field name:

```text
file
```

Supported file extensions:

```text
jpg, jpeg, png
```

Prediction response includes:

- `job_id`
- `filename`
- `image_key`
- `image_url`
- `prediction` (`Positive` or `Negative`)
- `probability`
- `status`
- `uploaded_at`

### Dashboard

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/dashboard` | Access token | Return current user's email and prediction records |

### Admin

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/admin/bootstrap` | Access token | Promote the configured `ADMIN_EMAIL` user to admin |
| `GET` | `/admin/stats` | Admin | Return user and record counts |
| `GET` | `/admin/users` | Admin | List all users without passwords |
| `GET` | `/admin/records` | Admin | List all prediction records |
| `DELETE` | `/admin/records/<record_id>` | Admin | Delete one record and its S3 image |
| `DELETE` | `/admin/users/<user_id>` | Admin | Delete a non-admin user, records, and images |
| `POST` | `/admin/users/<user_id>/verify` | Admin | Mark a user as verified |
| `POST` | `/admin/users/<user_id>/promote` | Admin | Promote a verified user to admin |
| `POST` | `/admin/users/<user_id>/demote` | Admin | Demote an admin user, except self/last admin |

## Example Requests

Register:

```bash
curl -X POST http://localhost:5000/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"user@example.com\",\"password\":\"StrongPass@123\"}"
```

Login:

```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"user@example.com\",\"password\":\"StrongPass@123\"}"
```

Upload an image:

```bash
curl -X POST http://localhost:5000/predict/upload \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@sample.jpg"
```

Get dashboard:

```bash
curl http://localhost:5000/dashboard \
  -H "Authorization: Bearer <access_token>"
```

## Model Details

The prediction service in `services/ml_service.py` uses:

- `torchvision.models.resnet50(weights=None)`
- A final fully connected layer with 2 output classes
- Image resize to `224 x 224`
- ImageNet normalization values
- Labels:
  - `0`: `Negative`
  - `1`: `Positive`

The model file is expected at:

```text
ml_models/knee_model2.pth
```

If the file is missing, the service downloads it from Google Drive using `MODEL_FILE_ID`.

## Deployment

This repository includes:

- `wsgi.py` for WSGI servers such as Gunicorn
- `vercel.json` for Vercel Python deployment

Gunicorn example:

```bash
gunicorn wsgi:app
```

Vercel uses `app.py` as configured in `vercel.json`.

## Security Notes

- Do not commit `.env` or real credentials.
- Use strong values for `SECRET_KEY` and `JWT_SECRET_KEY`.
- Use app-specific SMTP passwords where possible.
- Restrict S3 bucket permissions to only what the API needs.
- Configure Redis and MongoDB with authentication in production.

## Status

This project currently contains the backend API only. A separate frontend can consume the JSON endpoints and use `FRONTEND_URL` as the allowed CORS origin.
