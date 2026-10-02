import json
import math
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from flask import Flask, request, jsonify
from instagram_service import InstagramService
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from flask_cors import CORS
import jwt
from jwt import InvalidTokenError
from werkzeug.security import check_password_hash, generate_password_hash

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")


SAMPLE_CREATORS = [
    {
        "id": 1,
        "name": "Aisha Kapoor",
        "category": "Fashion",
        "city": "Delhi",
        "followers": 185000,
        "engagement": 7.8,
        "likes": 18800,
        "views": 2400000,
        "price": 3500,
        "rating": 4.9,
        "handle": "@aishakapoor",
        "contactEmail": "aisha@example.com",
        "image": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=900&q=80",
        "bio": "Style-forward creator with premium fashion edits and reels.",
        "platforms": ["Instagram", "YouTube", "TikTok"],
        "socialLinks": [
            {"name": "Instagram", "url": "https://instagram.com/aishakapoor"},
            {"name": "YouTube", "url": "https://youtube.com/@aishakapoor"},
            {"name": "TikTok", "url": "https://www.tiktok.com/@aishakapoor"},
        ],
    },
    {
        "id": 2,
        "name": "Rohan Menon",
        "category": "Travel",
        "city": "Bengaluru",
        "followers": 260000,
        "engagement": 6.4,
        "likes": 24300,
        "views": 3200000,
        "price": 4200,
        "rating": 4.8,
        "handle": "@travelwithrohan",
        "contactEmail": "rohan@example.com",
        "image": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=900&q=80",
        "bio": "Travel documentary creator blending city stories and adventure.",
        "platforms": ["Instagram", "Blog"],
        "socialLinks": [
            {"name": "Instagram", "url": "https://instagram.com/travelwithrohan"},
            {"name": "Blog", "url": "https://travelwithrohan.com"},
        ],
    },
    {
        "id": 3,
        "name": "Naina Shah",
        "category": "Beauty",
        "city": "Mumbai",
        "followers": 132000,
        "engagement": 8.9,
        "likes": 17100,
        "views": 1800000,
        "price": 3000,
        "rating": 4.9,
        "handle": "@nainabeauty",
        "contactEmail": "naina@example.com",
        "image": "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=900&q=80",
        "bio": "Skincare and glam tutorials with strong community trust.",
        "platforms": ["Instagram", "Reels"],
        "socialLinks": [
            {"name": "Instagram", "url": "https://instagram.com/nainabeauty"},
            {"name": "Reels", "url": "https://instagram.com/nainabeauty/reels"},
        ],
    },
    {
        "id": 4,
        "name": "Kabir Sethi",
        "category": "Fitness",
        "city": "Hyderabad",
        "followers": 320000,
        "engagement": 5.9,
        "likes": 28700,
        "views": 4100000,
        "price": 5000,
        "rating": 4.7,
        "handle": "@kabirstrong",
        "contactEmail": "kabir@example.com",
        "image": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=900&q=80",
        "bio": "Strength and wellness coach promoting performance-based lifestyle.",
        "platforms": ["Instagram", "YouTube"],
        "socialLinks": [
            {"name": "Instagram", "url": "https://instagram.com/kabirstrong"},
            {"name": "YouTube", "url": "https://youtube.com/@kabirstrong"},
        ],
    },
    {
        "id": 5,
        "name": "Meher Ali",
        "category": "Food",
        "city": "Lucknow",
        "followers": 98000,
        "engagement": 9.2,
        "likes": 14600,
        "views": 1200000,
        "price": 2600,
        "rating": 4.8,
        "handle": "@meherbites",
        "contactEmail": "meher@example.com",
        "image": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=900&q=80",
        "bio": "Food storytelling through creator-led restaurant reviews.",
        "platforms": ["Instagram", "TikTok"],
        "socialLinks": [
            {"name": "Instagram", "url": "https://instagram.com/meherbites"},
            {"name": "TikTok", "url": "https://www.tiktok.com/@meherbites"},
        ],
    },
    {
        "id": 6,
        "name": "Vihaan Roy",
        "category": "Lifestyle",
        "city": "Pune",
        "followers": 214000,
        "engagement": 7.1,
        "likes": 21200,
        "views": 2800000,
        "price": 3900,
        "rating": 4.9,
        "handle": "@vihaanlives",
        "contactEmail": "vihaan@example.com",
        "image": "https://images.unsplash.com/photo-1504593811423-6dd665756598?auto=format&fit=crop&w=900&q=80",
        "bio": "Lifestyle and daily vlogs with polished storytelling.",
        "platforms": ["Instagram", "YouTube", "Podcast"],
        "socialLinks": [
            {"name": "Instagram", "url": "https://instagram.com/vihaanlives"},
            {"name": "YouTube", "url": "https://youtube.com/@vihaanlives"},
            {"name": "Podcast", "url": "https://open.spotify.com/user/vihaanlives"},
        ],
    },
]

CREATOR_FIELDS = (
    "name",
    "category",
    "city",
    "followers",
    "engagement",
    "likes",
    "views",
    "price",
    "rating",
    "handle",
    "contactEmail",
    "image",
    "bio",
    "platforms",
    "socialLinks",
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app_config_database())
        g.db.row_factory = sqlite3.Row
    return g.db


def current_app_config_database():
    from flask import current_app

    return current_app.config["DATABASE"]


def serialize_creator(row):
    creator = dict(row)
    creator["platforms"] = json.loads(creator.pop("platforms_json"))
    creator["socialLinks"] = json.loads(creator.pop("social_links_json"))
    return creator


def creator_for_viewer(row, account):
    creator = serialize_creator(row)
    if account["role"] == "influencer" and account["creator_id"] != creator["id"]:
        creator["contactEmail"] = ""
        creator["handle"] = ""
        creator["socialLinks"] = []
    return creator


def normalize_instagram_id(social_links):
    for link in social_links:
        if not isinstance(link, dict) or "instagram" not in link.get("name", "").lower():
            continue
        value = str(link.get("url", "")).strip()
        if not value:
            return None
        if "://" not in value:
            value = f"https://instagram.com/{value.lstrip('@/')}"
        path_parts = [part for part in urlsplit(value).path.split("/") if part]
        if not path_parts or path_parts[0].lower() in {
            "p", "reel", "reels", "stories", "explore", "accounts"
        }:
            return None
        return unquote(path_parts[0]).lstrip("@").casefold() or None
    return None


def migrate_instagram_ids(db):
    columns = {row["name"] for row in db.execute("PRAGMA table_info(creators)")}
    if "instagram_id" not in columns:
        db.execute("ALTER TABLE creators ADD COLUMN instagram_id TEXT")

    seen_ids = set()
    creators = db.execute(
        "SELECT id, instagram_id, social_links_json FROM creators ORDER BY id"
    ).fetchall()
    for creator in creators:
        instagram_id = creator["instagram_id"] or normalize_instagram_id(
            json.loads(creator["social_links_json"])
        )
        if not instagram_id or instagram_id in seen_ids:
            continue
        seen_ids.add(instagram_id)
        if creator["instagram_id"] != instagram_id:
            db.execute(
                "UPDATE creators SET instagram_id = ? WHERE id = ?",
                (instagram_id, creator["id"]),
            )

    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_creators_instagram_id_unique
        ON creators(instagram_id COLLATE NOCASE)
        WHERE instagram_id IS NOT NULL AND instagram_id <> ''
        """
    )


def initialize_database(app):
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS creators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                city TEXT NOT NULL,
                followers INTEGER NOT NULL DEFAULT 0,
                engagement REAL NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                views INTEGER NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                rating REAL NOT NULL DEFAULT 0,
                handle TEXT NOT NULL DEFAULT '',
                contactEmail TEXT NOT NULL DEFAULT '',
                image TEXT NOT NULL DEFAULT '',
                bio TEXT NOT NULL DEFAULT '',
                platforms_json TEXT NOT NULL DEFAULT '[]',
                social_links_json TEXT NOT NULL DEFAULT '[]',
                instagram_id TEXT
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                creator_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(role, email),
                FOREIGN KEY (creator_id) REFERENCES creators(id)
            )
            """
        )
        migrate_instagram_ids(db)
        if db.execute("SELECT COUNT(*) FROM creators").fetchone()[0] == 0:
            for creator in SAMPLE_CREATORS:
                insert_creator(db, creator, creator_id=creator["id"])
        db.commit()


def insert_creator(db, creator, creator_id=None):
    columns = [
        "name",
        "category",
        "city",
        "followers",
        "engagement",
        "likes",
        "views",
        "price",
        "rating",
        "handle",
        "contactEmail",
        "image",
        "bio",
        "platforms_json",
        "social_links_json",
        "instagram_id",
    ]
    values = [
        creator["name"],
        creator["category"],
        creator["city"],
        creator.get("followers", 0),
        creator.get("engagement", 0),
        creator.get("likes", 0),
        creator.get("views", 0),
        creator.get("price", 0),
        creator.get("rating", 0),
        creator.get("handle", ""),
        creator.get("contactEmail", ""),
        creator.get("image", ""),
        creator.get("bio", ""),
        json.dumps(creator.get("platforms", [])),
        json.dumps(creator.get("socialLinks", [])),
        normalize_instagram_id(creator.get("socialLinks", [])),
    ]
    if creator_id is not None:
        columns.insert(0, "id")
        values.insert(0, creator_id)
    placeholders = ", ".join("?" for _ in columns)
    cursor = db.execute(
        f"INSERT INTO creators ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )
    return cursor.lastrowid


def validate_creator(payload):
    if not isinstance(payload, dict):
        return "Request body must be a JSON object."

    for field in ("name", "category", "city"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            return f"'{field}' is required and must be a non-empty string."

    for field in ("platforms", "socialLinks"):
        value = payload.get(field, [])
        if not isinstance(value, list):
            return f"'{field}' must be an array."
        if field == "socialLinks" and any(
            not isinstance(link, dict)
            or not isinstance(link.get("name"), str)
            or not isinstance(link.get("url"), str)
            for link in value
        ):
            return "Each socialLinks item must include string 'name' and 'url' fields."

    return None


def validate_registration(payload, required_fields):
    if not isinstance(payload, dict):
        return "Request body must be a JSON object."

    for field in required_fields:
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            return f"'{field}' is required and must be a non-empty string."

    email = payload["email"].strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return "'email' must be a valid email address."

    if len(payload["password"]) < 8:
        return "'password' must be at least 8 characters long."

    return None


def parse_non_negative_integer(payload, field):
    value = payload.get(field, 0)
    if isinstance(value, bool):
        raise ValueError
    number = float(value or 0)
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        raise ValueError
    return int(number)


def load_or_create_secret(database_path):
    secret_path = Path(database_path).parent / ".auth_secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        file_descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        return secret_path.read_text(encoding="utf-8")

    secret = secrets.token_urlsafe(48)
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as secret_file:
        secret_file.write(secret)
    return secret


def registration_response(account_id, role, email, creator_id=None):
    result = {"id": account_id, "role": role, "email": email}
    if creator_id is not None:
        result["creatorId"] = creator_id
    return jsonify({"data": result}), 201


def create_app(test_config=None):
    app = Flask(__name__)
    instagram_service = InstagramService()
    database_path = Path(
        os.environ.get("CREATOR_DB_PATH", "instance/creators.sqlite3")
    )
    if not database_path.is_absolute():
        database_path = BACKEND_DIR / database_path

    app.config.from_mapping(
        DATABASE=str(database_path)
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or load_or_create_secret(
            app.config["DATABASE"]
        )

    allowed_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
    CORS(app, resources={r"/api/*": {"origins": [origin.strip() for origin in allowed_origins]}})

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    def authenticated_account():
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        try:
            token_data = jwt.decode(
                token,
                app.config["SECRET_KEY"],
                algorithms=["HS256"],
                issuer="influs-api",
            )
            account_id = int(token_data["sub"])
        except (InvalidTokenError, KeyError, TypeError, ValueError):
            return None
        return get_db().execute(
            "SELECT * FROM accounts WHERE id = ? AND role = ?",
            (account_id, token_data.get("role")),
        ).fetchone()

    def unauthorized_response():
        return jsonify({"error": "Sign in to continue."}), 401

    @app.get("/api/profile")
    def get_instagram_profile():
        print("Request args:", request.args)  # Debugging line
        username = request.args.get("username", "").strip()

        # Remove @ if user sends @username
        username = username.lstrip("@")

        if not username:
            return jsonify({
                "success": False,
                "message": "username is required"
            }), 400

        try:
            profile = instagram_service.get_profile(username)

            if not profile:
                return jsonify({
                    "success": False,
                    "message": "Instagram profile not found"
                }), 404

            return jsonify({
                "success": True,
                "data": profile
            }), 200

        except Exception as e:
            return jsonify({
                "success": False,
                "message": "Failed to fetch Instagram profile",
                "error": str(e)
            }), 500


    @app.post("/api/auth/login")
    def login():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400

        role = payload.get("role")
        email = payload.get("email")
        password = payload.get("password")
        if role not in ("influencer", "sponsor"):
            return jsonify({"error": "Choose a valid account type."}), 400
        if not isinstance(email, str) or not isinstance(password, str):
            return jsonify({"error": "Email and password are required."}), 400

        account = get_db().execute(
            "SELECT * FROM accounts WHERE role = ? AND email = ? COLLATE NOCASE",
            (role, email.strip()),
        ).fetchone()
        if account is None or not check_password_hash(account["password_hash"], password):
            return jsonify({"error": "Email or password is incorrect."}), 401

        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(account["id"]),
                "role": account["role"],
                "iss": "influs-api",
                "iat": now,
                "exp": now + timedelta(days=7),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return jsonify(
            {
                "data": {
                    "token": token,
                    "account": {
                        "id": account["id"],
                        "role": account["role"],
                        "email": account["email"],
                    },
                }
            }
        )

    @app.get("/api/me")
    def get_my_profile():
        account = authenticated_account()
        if account is None:
            return unauthorized_response()

        profile = json.loads(account["profile_json"])
        if account["role"] == "influencer":
            creator = get_db().execute(
                "SELECT * FROM creators WHERE id = ?", (account["creator_id"],)
            ).fetchone()
            if creator is None:
                return jsonify({"error": "Creator profile not found."}), 404
            profile = serialize_creator(creator)

        return jsonify(
            {
                "data": {
                    "account": {
                        "id": account["id"],
                        "role": account["role"],
                        "email": account["email"],
                    },
                    "profile": profile,
                }
            }
        )

    @app.put("/api/me")
    def update_my_profile():
        account = authenticated_account()
        if account is None:
            return unauthorized_response()
        if account["role"] != "influencer" or account["creator_id"] is None:
            return jsonify({"error": "Only influencer profiles can be edited here."}), 403

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400

        db = get_db()
        creator_row = db.execute(
            "SELECT * FROM creators WHERE id = ?", (account["creator_id"],)
        ).fetchone()
        if creator_row is None:
            return jsonify({"error": "Creator profile not found."}), 404

        current = serialize_creator(creator_row)
        profile = {
            field: payload.get(field, current[field])
            for field in CREATOR_FIELDS
        }
        profile["contactEmail"] = account["email"]
        validation_error = validate_creator(profile)
        if validation_error:
            return jsonify({"error": validation_error}), 400

        try:
            profile["followers"] = parse_non_negative_integer(profile, "followers")
            profile["likes"] = parse_non_negative_integer(profile, "likes")
            profile["views"] = parse_non_negative_integer(profile, "views")
            profile["engagement"] = float(profile["engagement"])
            profile["price"] = float(profile["price"])
            if (
                not math.isfinite(profile["engagement"])
                or not 0 <= profile["engagement"] <= 100
                or not math.isfinite(profile["price"])
                or profile["price"] < 0
            ):
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Metrics must be valid non-negative numbers, with engagement between 0 and 100."}), 400

        instagram_id = normalize_instagram_id(profile["socialLinks"])
        conflict = db.execute(
            "SELECT id FROM creators WHERE instagram_id = ? COLLATE NOCASE AND id <> ?",
            (instagram_id, account["creator_id"]),
        ).fetchone() if instagram_id else None
        if conflict:
            return jsonify({"error": "That Instagram account is already linked to another creator."}), 409

        try:
            db.execute(
            """
            UPDATE creators SET
                name = ?, category = ?, city = ?, followers = ?, engagement = ?,
                likes = ?, views = ?, price = ?, handle = ?, contactEmail = ?,
                image = ?, bio = ?, platforms_json = ?, social_links_json = ?,
                instagram_id = ?
            WHERE id = ?
            """,
            (
                profile["name"].strip(),
                profile["category"].strip(),
                profile["city"].strip(),
                profile["followers"],
                profile["engagement"],
                profile["likes"],
                profile["views"],
                profile["price"],
                profile["handle"],
                profile["contactEmail"],
                profile["image"],
                profile["bio"],
                json.dumps(profile["platforms"]),
                json.dumps(profile["socialLinks"]),
                instagram_id,
                account["creator_id"],
            ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            return jsonify({"error": "That Instagram account is already linked to another creator."}), 409
        saved = db.execute(
            "SELECT * FROM creators WHERE id = ?", (account["creator_id"],)
        ).fetchone()
        return jsonify({"data": serialize_creator(saved)})

    @app.get("/api/creators")
    def list_creators():
        account = authenticated_account()
        if account is None:
            return unauthorized_response()
        creators = get_db().execute("SELECT * FROM creators ORDER BY id").fetchall()
        return jsonify({"data": [creator_for_viewer(row, account) for row in creators]})

    @app.get("/api/creators/<int:creator_id>")
    def get_creator(creator_id):
        account = authenticated_account()
        if account is None:
            return unauthorized_response()
        creator = get_db().execute(
            "SELECT * FROM creators WHERE id = ?", (creator_id,)
        ).fetchone()
        if creator is None:
            return jsonify({"error": "Creator not found."}), 404
        return jsonify({"data": creator_for_viewer(creator, account)})

    @app.post("/api/creators")
    def create_creator():
        account = authenticated_account()
        if account is None:
            return unauthorized_response()
        if account["role"] != "sponsor":
            return jsonify({"error": "Only sponsors can create creator listings."}), 403

        payload = request.get_json(silent=True)
        validation_error = validate_creator(payload)
        if validation_error:
            return jsonify({"error": validation_error}), 400

        creator = {field: payload[field] for field in CREATOR_FIELDS if field in payload}
        for field in ("platforms", "socialLinks"):
            creator.setdefault(field, [])

        db = get_db()
        instagram_id = normalize_instagram_id(creator["socialLinks"])
        if instagram_id and db.execute(
            "SELECT id FROM creators WHERE instagram_id = ? COLLATE NOCASE",
            (instagram_id,),
        ).fetchone():
            return jsonify({"error": "That Instagram account is already linked to another creator."}), 409

        try:
            creator_id = insert_creator(db, creator)
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            return jsonify({"error": "That Instagram account is already linked to another creator."}), 409
        saved = db.execute(
            "SELECT * FROM creators WHERE id = ?", (creator_id,)
        ).fetchone()
        return jsonify({"data": serialize_creator(saved)}), 201

    @app.post("/api/auth/register/influencer")
    def register_influencer():
        payload = request.get_json(silent=True)
        validation_error = validate_registration(
            payload, ("name", "email", "password", "city", "niche")
        )
        if validation_error:
            return jsonify({"error": validation_error}), 400

        email = payload["email"].strip().lower()
        instagram = payload.get("instagram", "").strip().lstrip("@/")
        youtube = payload.get("youtube", "").strip().lstrip("@/")
        social_links = []
        platforms = []
        if instagram:
            platforms.append("Instagram")
            social_links.append(
                {"name": "Instagram", "url": f"https://instagram.com/{instagram}"}
            )
        if youtube:
            platforms.append("YouTube")
            social_links.append(
                {"name": "YouTube", "url": f"https://youtube.com/@{youtube}"}
            )

        try:
            followers = parse_non_negative_integer(payload, "followers")
            likes = parse_non_negative_integer(payload, "likes")
            views = parse_non_negative_integer(payload, "views")
            engagement = float(payload.get("engagement") or 0)
            rate = float(payload.get("rate") or 0)
            if (
                not math.isfinite(engagement)
                or engagement < 0
                or engagement > 100
                or not math.isfinite(rate)
                or rate < 0
            ):
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"error": "Audience metrics must be non-negative numbers, with engagement between 0 and 100."}), 400

        creator = {
            "name": payload["name"].strip(),
            "category": payload["niche"].strip(),
            "city": payload["city"].strip(),
            "followers": followers,
            "engagement": engagement,
            "likes": likes,
            "views": views,
            "price": rate,
            "rating": 0,
            "handle": payload.get("handle", "").strip(),
            "contactEmail": email,
            "image": payload.get("image", "").strip(),
            "bio": payload.get("bio", "").strip(),
            "platforms": platforms,
            "socialLinks": social_links,
        }
        instagram_id = normalize_instagram_id(social_links)
        if instagram_id and get_db().execute(
            "SELECT id FROM creators WHERE instagram_id = ? COLLATE NOCASE",
            (instagram_id,),
        ).fetchone():
            return jsonify({"error": "That Instagram account is already linked to another creator."}), 409
        profile = {
            "name": creator["name"],
            "handle": creator["handle"],
            "city": creator["city"],
            "niche": creator["category"],
            "bio": creator["bio"],
            "platforms": platforms,
        }

        db = get_db()
        try:
            creator_id = insert_creator(db, creator)
            cursor = db.execute(
                """
                INSERT INTO accounts (role, email, password_hash, profile_json, creator_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "influencer",
                    email,
                    generate_password_hash(payload["password"]),
                    json.dumps(profile),
                    creator_id,
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            email_exists = db.execute(
                "SELECT 1 FROM accounts WHERE role = 'influencer' AND email = ? COLLATE NOCASE",
                (email,),
            ).fetchone()
            error = (
                "An influencer account with this email already exists."
                if email_exists
                else "That Instagram account is already linked to another creator."
            )
            return jsonify({"error": error}), 409

        return registration_response(cursor.lastrowid, "influencer", email, creator_id)

    @app.post("/api/auth/register/sponsor")
    def register_sponsor():
        payload = request.get_json(silent=True)
        validation_error = validate_registration(
            payload,
            ("companyName", "email", "password", "industry", "companySize"),
        )
        if validation_error:
            return jsonify({"error": validation_error}), 400

        email = payload["email"].strip().lower()
        profile = {
            "companyName": payload["companyName"].strip(),
            "industry": payload["industry"].strip(),
            "companySize": payload["companySize"].strip(),
            "website": payload.get("website", "").strip(),
        }
        db = get_db()
        try:
            cursor = db.execute(
                """
                INSERT INTO accounts (role, email, password_hash, profile_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "sponsor",
                    email,
                    generate_password_hash(payload["password"]),
                    json.dumps(profile),
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            return jsonify({"error": "A sponsor account with this email already exists."}), 409

        return registration_response(cursor.lastrowid, "sponsor", email)

    initialize_database(app)
    return app


app = create_app()


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=debug_mode,
    )