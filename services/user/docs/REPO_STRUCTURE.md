


├── .env                          ← Environment variables

├── pyproject.toml                ← Project config (already set up)

├── README.md

│

├── certs/                        ← RSA keys (created in Step 4)

│   ├── private.pem

│   └── public.pem

│

├── app/

│   ├── __init__.py

│   ├── main.py                   ← App entry point & factory

│   │

│   ├── core/                     ← Foundation layer

│   │   ├── __init__.py

│   │   ├── config.py             ← Settings (reads .env)

│   │   ├── logging.py            ← Logging configuration

│   │   ├── database.py           ← Async engine + session

│   │   ├── security.py           ← Password hashing + JWT (RS256)

│   │   └── dependencies.py       ← Shared DI providers

│   │

│   ├── models/                   ← SQLAlchemy ORM models

│   │   ├── __init__.py

│   │   ├── user.py

│   │   └── post.py

│   │

│   ├── schemas/                  ← Pydantic request/response schemas

│   │   ├── __init__.py

│   │   ├── user.py

│   │   └── post.py

│   │

│   ├── repositories/             ← Data access layer (DB queries)

│   │   ├── __init__.py

│   │   ├── user_repo.py

│   │   └── post_repo.py

│   │

│   ├── services/                 ← Business logic layer

│   │   ├── __init__.py

│   │   ├── auth_service.py

│   │   └── post_service.py

│   │

│   ├── api/                      ← Route definitions

│   │   ├── __init__.py

│   │   ├── deps.py               ← Auth dependencies (get_current_user)

│   │   └── v1/

│   │       ├── __init__.py

│   │       ├── auth.py

│   │       └── posts.py

│   │

│   ├── middleware/                ← Custom middleware

│   │   ├── __init__.py

│   │   └── auth_middleware.py

│   │

│   └── utils/                    ← Helpers

│       ├── __init__.py

│       └── token.py

│

└── tests/

    └── __init__.py