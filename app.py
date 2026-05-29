"""
Invitely — Secure Edition
Implements:
  Phase 1: Flask-Login user accounts, is_admin, login-based event management
  Phase 2: Flask-WTF CSRF, Flask-Limiter rate limits, input sanitisation
  Phase 3: Flask-Migrate migrations, PostgreSQL-ready DATABASE_URL
  Phase 4: Privacy controls (delete event/RSVP, retention), AuditLog
  Phase 5: Config hardening (.env, cookie flags, no plaintext secrets)
"""

import os, uuid, re, urllib.parse, urllib.request, json as _json
import csv, io, base64, zipfile, time
from collections import Counter
from datetime import datetime, date, timedelta
from functools import wraps

from PIL import Image
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from flask import (Flask, render_template, request, url_for, jsonify,
                   abort, Response, redirect, flash, session, g)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

load_dotenv()

# ── App & extensions ──────────────────────────────────────────
app = Flask(__name__)
app.config.from_object('config.Config')

db           = SQLAlchemy(app)
migrate      = Migrate(app, db)
login_manager = LoginManager(app)
csrf         = CSRFProtect(app)
mail         = Mail(app)
limiter      = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],  # no global limit; apply per-route
    storage_uri=app.config['RATELIMIT_STORAGE_URL'],
)
scheduler    = BackgroundScheduler(daemon=True)

login_manager.login_view    = 'login'
login_manager.login_message = 'Please sign in to continue.'

# ── Constants ─────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_IMG_TYPES  = {'image/jpeg', 'image/png', 'image/webp'}

EVENT_TYPES = [
    'Birthday','Graduation','Umgidi','Umemulo','Wedding','Lobola',
    'Baby Shower','Matric Farewell','Memorial','Corporate Event',
    'Bridal Shower','Kitchen Tea','Imbeleko','Umkhosi woMhlanga',
    'Matric Rage','Stokvel','Gender Reveal','Engagement Party','Other',
]
DRESS_CODES = [
    'Smart Casual','Formal','Black Tie','Traditional / Cultural',
    'All White','Casual','Semi-Formal','African Attire','Cocktail',
    'Beach Casual','Custom...',
]
THEMES = [
    'Old Hollywood Glamour','Garden Party','Celestial / Galaxy','Afro Luxe',
    'Tropical Paradise','Winter Wonderland','Black & Gold','Vintage',
    'Bohemian','Royal','Xhosa Tradition','Zulu Heritage','Safari','Custom...',
]
COLOUR_PALETTES = [
    'Black & Gold','Black & White','Purple & Silver','Green & Gold',
    'All White','Red & Gold','Navy & Gold','Blush & Rose','Earth Tones',
    'Emerald & Gold','Midnight Blue & Silver','Burnt Orange & Brown','Custom...',
]
ACCENT_COLOURS = [
    ('#e8d5a3','Gold'),('#c4b5fd','Lavender'),('#86efac','Sage Green'),
    ('#f9a8d4','Rose Pink'),('#7dd3fc','Sky Blue'),('#fcd34d','Amber'),
    ('#f87171','Coral Red'),('#c084fc','Purple'),('#2dd4bf','Teal'),
    ('#fb923c','Orange'),('#ec4899','Pink'),('#ffffff','White'),
    ('#dc2626','Crimson'),('#1e40af','Royal Blue'),('#065f46','Forest Green'),
    ('#7c2d12','Burnt Umber'),('#4c1d95','Deep Violet'),('#134e4a','Deep Teal'),
    ('#fbbf24','Honey'),('#6d28d9','Indigo'),('#be185d','Magenta'),
    ('#92400e','Caramel'),('#0f766e','Jade'),('#1d4ed8','Sapphire'),
    ('#b45309','Bronze'),('#9f1239','Ruby'),('#0369a1','Steel Blue'),
    ('#166534','Emerald'),('#d97706','Saffron'),('#831843','Plum'),
    ('#374151','Graphite'),('#b8860b','Dark Gold'),
]
DESIGNS = [
    ('classic_dark','Classic Dark','Black & gold — timeless elegance'),
    ('celestial','Celestial','Deep purple & stars — dreamy'),
    ('blanc','Blanc','Clean white & serif — refined'),
    ('ubuntu','Ubuntu','Forest green & gold — cultural'),
    ('blush','Blush Romance','Pink, ivory & rose gold — bridal'),
    ('ocean_dusk','Ocean Dusk','Deep navy & teal — formal'),
    ('ndebele_fire','Ndebele Fire','Bold red & geometric — vibrant'),
    ('kalahari','Kalahari Sun','Terracotta & sand — earthy SA'),
    ('amethyst','Midnight Amethyst','Purple & silver — opulent'),
    ('cape_botanica','Cape Botanica','Sage & cream — garden party'),
    ('mono_edge','Monochrome Edge','Black & white — modern'),
    ('soweto_summer','Soweto Summer','Yellow & orange — festive'),
    ('neon_nights','Neon Nights','Electric neon on deep black'),
    ('art_deco','Art Deco Gatsby','Gold geometric — 1920s glamour'),
    ('afrofuturism','Afrofuturism','Deep purple & bold future'),
    ('lobola_red','Lobola Red','Rich burgundy & warm gold'),
    ('cape_fynbos','Cape Fynbos','Blush & sage — botanical'),
    ('kente_gold','Kente Gold','Deep kente with bright accents'),
    ('galaxy_dream','Galaxy Dream','Deep space with nebula hues'),
    ('safari_dusk','Safari Dusk','Amber & burnt orange — bush sunset'),
    ('boho_dream','Boho Dream','Warm terracotta & dusty rose'),
    ('editorial_black','Editorial Black','Stark black & white — editorial'),
    ('ocean_deep','Ocean Deep','Deep teal & midnight blue'),
]
FONTS = [
    ('Modern',"'Helvetica Neue', Helvetica, Arial, sans-serif"),
    ('Elegant Serif',"Georgia, 'Times New Roman', serif"),
    ('Cormorant',"'Cormorant Garamond', Georgia, serif"),
    ('Jakarta',"'Plus Jakarta Sans', 'Helvetica Neue', sans-serif"),
    ('Playful Script',"'Brush Script MT', cursive"),
    ('Classic Mono',"'Courier New', monospace"),
    ('Cinzel',"'Cinzel', Georgia, serif"),
    ('Great Vibes',"'Great Vibes', cursive"),
    ('Montserrat',"'Montserrat', 'Helvetica Neue', sans-serif"),
    ('Dancing Script',"'Dancing Script', cursive"),
    ('Raleway',"'Raleway', 'Helvetica Neue', sans-serif"),
    ('Space Mono',"'Space Mono', 'Courier New', monospace"),
    ('Josefin Sans',"'Josefin Sans', 'Helvetica Neue', sans-serif"),
]
PATTERNS = [
    ('none','No Pattern'),('xhosa','Xhosa Heritage'),
    ('venda','Venda Tradition'),('royal','Royal Gold Border'),
    ('fine_grid','Fine Grid'),('dot_matrix','Dot Matrix'),
    ('ndebele','Ndebele Chevron'),('soft_glow','Soft Glow'),
    ('diagonal','Diagonal Lines'),('cape_malay','Cape Malay Mosaic'),
    ('linen','Linen Texture'),('corner_frame','Corner Frame'),
    ('celestial_swirl','Celestial Swirl'),('zulu_shield','Zulu Shield Lines'),
    ('zulu_beads','Zulu Beadwork'),('kanga_print','Kanga Print'),
    ('san_art','San Rock Art'),('venda_spiral','Venda Spiral'),
    ('hexagon','Honeycomb'),('waves','Ocean Waves'),
]
DECORATIONS = [
    ('none','None'),('flowers','Flowers'),
    ('balloons','Balloons'),('both','Flowers & Balloons'),
]
EFFECTS = [
    ('none','No Effect'),
    ('confetti','Confetti Rain'),
    ('particles','Floating Particles'),
    ('petals','Falling Petals'),
    ('stars','Twinkling Stars'),
    ('fireflies','Fireflies'),
    ('bokeh','Bokeh Circles'),
    ('glitter','Gold Glitter'),
    ('neon_glow','Neon Glow Pulse'),
    ('gold_foil','Gold Foil Shimmer'),
    ('typewriter','Typewriter Title'),
    ('aurora','Aurora Waves'),
    ('bubbles','Rising Bubbles'),
    ('snow','Snow Drift'),
]
PHOTO_FILTERS = [
    ('none','Original'),
    ('warm','Warm Glow'),
    ('cool','Cool Blue'),
    ('noir','Noir / B&W'),
    ('vintage','Vintage Film'),
    ('vivid','Vivid Boost'),
    ('fade','Faded Matte'),
    ('golden','Golden Hour'),
    ('dreamy','Dreamy Soft'),
]


# ── Models ────────────────────────────────────────────────────

class User(db.Model, UserMixin):
    """Registered host account."""
    __tablename__ = 'user'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin      = db.Column(db.Boolean, default=False, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    events        = db.relationship('Event', backref='owner', lazy=True,
                                    foreign_keys='Event.user_id')

    def set_password(self, pw: str):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)


class Event(db.Model):
    __tablename__ = 'event'
    id             = db.Column(db.Integer, primary_key=True)
    token          = db.Column(db.String(16), unique=True, nullable=False)
    # owner — nullable so legacy PIN-only events still work
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    host_name      = db.Column(db.String(120), nullable=False)
    host_email     = db.Column(db.String(200), nullable=False)
    host_pin       = db.Column(db.String(10), default='')
    guest_name     = db.Column(db.String(120), default='')
    event_type     = db.Column(db.String(60), default='Birthday')
    event_title    = db.Column(db.String(200), nullable=False)
    event_date     = db.Column(db.String(60), nullable=False)
    event_date_iso = db.Column(db.String(20), default='')
    event_time     = db.Column(db.String(40), nullable=False)
    rsvp_deadline  = db.Column(db.String(20), default='')
    capacity       = db.Column(db.Integer, default=0)
    save_the_date  = db.Column(db.Boolean, default=False)
    venue_name     = db.Column(db.String(200), nullable=False)
    venue_address  = db.Column(db.String(300), nullable=False)
    venue_lat      = db.Column(db.Float, default=-26.2041)
    venue_lng      = db.Column(db.Float, default=28.0473)
    dress_code     = db.Column(db.String(120), default='')
    theme          = db.Column(db.String(120), default='')
    colour_palette = db.Column(db.String(120), default='')
    accent_colour  = db.Column(db.String(20), default='#e8d5a3')
    design         = db.Column(db.String(40), default='classic_dark')
    font           = db.Column(db.String(100), default='Modern')
    pattern        = db.Column(db.String(100), default='none')
    pattern_opacity = db.Column(db.Integer, default=40)
    decorations    = db.Column(db.String(40), default='none')
    effect         = db.Column(db.String(40), default='none')
    photo_filter   = db.Column(db.String(40), default='none')
    extra_notes    = db.Column(db.Text, default='')
    music_url      = db.Column(db.String(400), default='')
    music_title    = db.Column(db.String(200), default='')
    music_artist   = db.Column(db.String(200), default='')
    # ── Phase 2 additions ─────────────────────────────────────
    accent_colour_2 = db.Column(db.String(20), default='')
    video_note     = db.Column(db.String(300), default='')
    programme      = db.Column(db.Text, default='')
    spotify_url    = db.Column(db.String(400), default='')
    whatsapp_group = db.Column(db.String(400), default='')
    hashtag        = db.Column(db.String(80), default='')
    greeting_lang  = db.Column(db.String(30), default='English')
    image_1        = db.Column(db.String(300), default='')
    image_2        = db.Column(db.String(300), default='')
    image_3        = db.Column(db.String(300), default='')
    view_count     = db.Column(db.Integer, default=0)
    is_archived    = db.Column(db.Boolean, default=False, nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    rsvps          = db.relationship('RSVP', backref='event', lazy=True,
                                     cascade='all, delete-orphan')
    gifts          = db.relationship('Gift', backref='event', lazy=True,
                                     cascade='all, delete-orphan')
    links          = db.relationship('InviteLink', backref='event', lazy=True,
                                     cascade='all, delete-orphan')
    announcements  = db.relationship('Announcement', backref='event', lazy=True,
                                     cascade='all, delete-orphan')
    reactions      = db.relationship('Reaction', backref='event', lazy=True,
                                     cascade='all, delete-orphan')


class RSVP(db.Model):
    __tablename__ = 'rsvp'
    id        = db.Column(db.Integer, primary_key=True)
    event_id  = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    name      = db.Column(db.String(120), nullable=False)
    email     = db.Column(db.String(200), default='')
    attending = db.Column(db.String(10), nullable=False)
    dietary   = db.Column(db.String(300), default='')
    plus_one  = db.Column(db.String(120), default='')
    plus_ones = db.Column(db.Integer, default=0)
    waitlist  = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Gift(db.Model):
    __tablename__ = 'gift'
    id       = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    name     = db.Column(db.String(200), nullable=False)
    store    = db.Column(db.String(200), default='')
    taken    = db.Column(db.Boolean, default=False)
    taken_by = db.Column(db.String(120), default='')


class InviteLink(db.Model):
    __tablename__ = 'invite_link'
    id           = db.Column(db.Integer, primary_key=True)
    event_id     = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    rsvp_id      = db.Column(db.Integer, db.ForeignKey('rsvp.id'), nullable=True)
    link_token   = db.Column(db.String(16), unique=True, nullable=False)
    guest_name   = db.Column(db.String(120), default='Friend')
    guest_surname = db.Column(db.String(120), default='')
    personal_msg = db.Column(db.Text, default='')
    opened       = db.Column(db.Boolean, default=False)
    opened_at    = db.Column(db.DateTime, nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    rsvp         = db.relationship('RSVP', foreign_keys=[rsvp_id])


class Announcement(db.Model):
    __tablename__ = 'announcement'
    id         = db.Column(db.Integer, primary_key=True)
    event_id   = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class GuestComment(db.Model):
    """Guest messages on an invitation page."""
    __tablename__ = 'guest_comment'
    id         = db.Column(db.Integer, primary_key=True)
    event_id   = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    approved   = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Reaction(db.Model):
    """Emoji reactions on an invitation page — one per emoji per IP."""
    __tablename__ = 'reaction'
    id         = db.Column(db.Integer, primary_key=True)
    event_id   = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    emoji      = db.Column(db.String(10), nullable=False)
    ip_hash    = db.Column(db.String(64), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    """Immutable record of important actions for security review."""
    __tablename__ = 'audit_log'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action     = db.Column(db.String(80), nullable=False)
    detail     = db.Column(db.Text, default='')
    ip_addr    = db.Column(db.String(80), default='')
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('audit_logs', lazy=True))


# ── Flask-Login loader ────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))  # SQLAlchemy 2.x


# ── Audit helper ──────────────────────────────────────────────

def _audit(action: str, detail: str = '', user_id=None):
    """Write an audit log entry. Never raises — log failures must not break requests."""
    try:
        uid = user_id
        if uid is None and current_user and current_user.is_authenticated:
            uid = current_user.id
        ip = (request.headers.get('X-Forwarded-For', '') or '').split(',')[0].strip() \
             or request.remote_addr or ''
        entry = AuditLog(user_id=uid, action=action,
                         detail=detail[:1000], ip_addr=ip[:80])
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:
        app.logger.warning(f"Audit log failed: {exc}")


# ── Auth decorators ───────────────────────────────────────────

def admin_required(f):
    """Route decorator: requires a logged-in admin user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please sign in as admin.', 'error')
            return redirect(url_for('login', next=request.url))
        if not current_user.is_admin:
            _audit('admin_access_denied', f'route={request.path}')
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _can_manage(event) -> bool:
    """True if the current request is authorised to manage this event."""
    if current_user.is_authenticated and current_user.is_admin:
        return True
    if current_user.is_authenticated and event.user_id == current_user.id:
        return True
    # Email match — handles events created before the user registered,
    # or events where host_email matches the logged-in account.
    # Auto-links legacy events to the account on first access.
    if current_user.is_authenticated and event.host_email:
        if current_user.email.lower() == event.host_email.lower():
            if not event.user_id:
                event.user_id = current_user.id
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            return True
    # Legacy PIN access for events without a user_id
    if not event.user_id:
        pin = request.args.get('pin') or request.view_args.get('pin', '')
        return bool(pin) and pin == event.host_pin
    return False


# ── Input sanitisation helpers ────────────────────────────────

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_HEX_COL  = re.compile(r'^#[0-9a-fA-F]{6}$')

def _clean(s: str, maxlen: int = 300) -> str:
    """Strip and truncate a string."""
    return (s or '').strip()[:maxlen]

def _valid_email(s: str) -> bool:
    return bool(_EMAIL_RE.match(s or ''))

def _valid_colour(s: str) -> bool:
    return bool(_HEX_COL.match(s or ''))

def _clean_name(s: str) -> str:
    """Strip, limit, remove control characters from a name field."""
    return re.sub(r'[\x00-\x1f]', '', _clean(s, 120))


# ── Image helpers ─────────────────────────────────────────────

def allowed_file(fn: str) -> bool:
    return '.' in fn and fn.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file, token: str, compressed_b64: str = None):
    folder = os.path.join(app.config['UPLOAD_FOLDER'], token)
    os.makedirs(folder, exist_ok=True)
    name = secure_filename(f"{uuid.uuid4().hex}.jpg")
    dest = os.path.join(folder, name)

    if compressed_b64 and compressed_b64.startswith('data:image'):
        try:
            _, b64data = compressed_b64.split(',', 1)
            img_bytes = base64.b64decode(b64data)
            # Validate it's actually an image before saving
            import io as _io
            Image.open(_io.BytesIO(img_bytes)).verify()
            with open(dest, 'wb') as fh:
                fh.write(img_bytes)
            return f"{token}/{name}"
        except Exception as e:
            app.logger.warning(f"Base64 image save failed: {e}")

    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    try:
        img = Image.open(file.stream)
        img = img.convert('RGB')
        img.thumbnail((1800, 1800), Image.LANCZOS)
        img.save(dest, 'JPEG', quality=82, optimize=True)
    except Exception as e:
        app.logger.warning(f"Image resize failed: {e}")
        try:
            file.stream.seek(0)
            file.save(dest)
        except Exception:
            return None
    return f"{token}/{name}"


def save_video(file, token: str) -> str:
    """Save a short video note (max 30s enforced client-side). Returns relative path or ''."""
    if not file or file.filename == '':
        return ''
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in {'mp4', 'webm', 'mov', 'ogg'}:
        return ''
    folder = os.path.join(app.config['UPLOAD_FOLDER'], token)
    os.makedirs(folder, exist_ok=True)
    name = secure_filename(f"vidnote_{uuid.uuid4().hex[:8]}.{ext}")
    dest = os.path.join(folder, name)
    try:
        file.save(dest)
        return f"{token}/{name}"
    except Exception as e:
        app.logger.warning(f"Video save failed: {e}")
        return ''


# ── YouTube helpers ───────────────────────────────────────────

def yt_embed(raw: str):
    if not raw:
        return None
    if '/search?' in raw or 'music.youtube.com/search' in raw:
        return None
    if 'youtube.com/embed/' in raw:
        return raw.split('?')[0]
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', raw)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', raw)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
    return None


def yt_meta(raw: str):
    if not raw:
        return '', ''
    vid_id = None
    m = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', raw)
    if m:
        vid_id = m.group(1)
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{11})', raw)
    if m:
        vid_id = m.group(1)
    if not vid_id:
        return '', ''
    try:
        url = (f"https://www.youtube.com/oembed?"
               f"url=https://www.youtube.com/watch?v={vid_id}&format=json")
        req = urllib.request.Request(url, headers={'User-Agent': 'Invitely/1.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = _json.loads(r.read())
        return data.get('title', ''), data.get('author_name', '')
    except Exception:
        return '', ''


# ── Date / time helpers ───────────────────────────────────────

def parse_iso(s: str):
    try:
        return datetime.strptime(s.strip(), '%Y-%m-%d').date()
    except Exception:
        return None


def fmt_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, '%Y-%m-%d').strftime('%A, %d %B %Y')
    except Exception:
        return iso


def fmt_time(t: str) -> str:
    try:
        return datetime.strptime(t, '%H:%M').strftime('%I:%M %p').lstrip('0')
    except Exception:
        return t


# ── Event business logic helpers ──────────────────────────────

def _rsvp_open(event) -> bool:
    if not event.rsvp_deadline:
        return True
    d = parse_iso(event.rsvp_deadline)
    return d is None or date.today() <= d


def _event_passed(event) -> bool:
    d = parse_iso(event.event_date_iso or event.event_date)
    return d is not None and date.today() > d


def _yes_count(event) -> int:
    return sum(1 + (r.plus_ones or 0) for r in event.rsvps if r.attending == 'yes' and not r.waitlist)


def _capacity_full(event) -> bool:
    if not event.capacity:
        return False
    return _yes_count(event) >= event.capacity


def _unique_link_token() -> str:
    for _ in range(8):
        token = uuid.uuid4().hex[:12]
        if not InviteLink.query.filter_by(link_token=token).first():
            return token
    return uuid.uuid4().hex


def _invite_link_url(event, link) -> str:
    return url_for('personalised_invitation',
                   token=event.token, link_token=link.link_token, _external=True)


def _invitation_context(event, link=None, existing_rsvp=None):
    yes_count = _yes_count(event)
    no_count  = sum(1 for r in event.rsvps if r.attending == 'no')
    recent = [
        {'name': r.name.split()[0], 'time': r.timestamp.isoformat()}
        for r in sorted(
            [r for r in event.rsvps if r.attending == 'yes' and not r.waitlist],
            key=lambda r: r.timestamp, reverse=True,
        )[:5]
    ]
    guest_name = ''
    if link:
        guest_name = f"{link.guest_name} {link.guest_surname or ''}".strip()
    return dict(
        event=event, link=link, existing_rsvp=existing_rsvp,
        yes_count=yes_count, no_count=no_count,
        rsvp_open=_rsvp_open(event),
        event_passed=_event_passed(event),
        capacity_full=_capacity_full(event),
        recent_rsvps=recent,
        guest_name_prefill=guest_name,
    )


def _popular(items, limit: int = 6):
    cleaned = [i for i in items if i]
    total = len(cleaned) or 1
    return [
        {'label': label, 'count': count, 'pct': round((count / total) * 100)}
        for label, count in Counter(cleaned).most_common(limit)
    ]


def _build_event_from_form(f, files, token: str, existing=None):
    dress_code     = _clean(f.get('dress_code_custom', '')) or _clean(f.get('dress_code', ''))
    theme          = _clean(f.get('theme_custom', ''))      or _clean(f.get('theme', ''))
    colour_palette = _clean(f.get('palette_custom', ''))    or _clean(f.get('colour_palette', ''))

    try:
        vlat = float(f.get('venue_lat') or -26.2041)
        vlng = float(f.get('venue_lng') or 28.0473)
    except (ValueError, TypeError):
        vlat, vlng = -26.2041, 28.0473

    raw_date  = _clean(f.get('event_date', ''))
    raw_time  = _clean(f.get('event_time', ''))
    raw_music = _clean(f.get('music_url', ''), 400)
    embed     = yt_embed(raw_music) or ''
    auto_title, auto_artist = yt_meta(raw_music) if embed else ('', '')

    accent = f.get('accent_colour', '#e8d5a3')
    if not _valid_colour(accent):
        accent = '#e8d5a3'

    ev = existing or Event(token=token)
    ev.host_name      = _clean_name(f.get('host_name', ''))
    ev.host_email     = _clean(f.get('host_email', ''), 200).lower()
    ev.host_pin       = _clean(f.get('host_pin', ''), 8) or ev.host_pin or str(uuid.uuid4().int)[:4]
    ev.guest_name     = _clean_name(f.get('guest_name', ''))
    ev.event_type     = _clean(f.get('event_type_custom', '')) or _clean(f.get('event_type', 'Birthday'))
    ev.event_title    = _clean(f.get('event_title', ''), 200)
    ev.event_date     = fmt_date(raw_date)
    ev.event_date_iso = raw_date
    ev.event_time     = fmt_time(raw_time)
    ev.rsvp_deadline  = _clean(f.get('rsvp_deadline', ''), 20)
    ev.capacity       = max(0, int(f.get('capacity') or 0))
    ev.save_the_date  = bool(f.get('save_the_date'))
    ev.venue_name     = _clean(f.get('venue_name', ''), 200)
    ev.venue_address  = _clean(f.get('venue_address', ''), 300)
    ev.venue_lat      = vlat
    ev.venue_lng      = vlng
    ev.dress_code     = _clean(dress_code, 120)
    ev.theme          = _clean(theme, 120)
    ev.colour_palette = _clean(colour_palette, 120)
    ev.accent_colour  = accent
    ev.design         = f.get('design', 'classic_dark')
    ev.font           = f.get('font', 'Modern')
    ev.pattern        = f.get('pattern', 'none')
    ev.pattern_opacity = max(10, min(100, int(f.get('pattern_opacity') or 40)))
    ev.decorations    = f.get('decorations', 'none')
    ev.effect         = f.get('effect', 'none')
    ev.photo_filter   = f.get('photo_filter', 'none')
    ev.extra_notes    = _clean(f.get('extra_notes', ''), 1000)
    ev.music_url      = embed
    ev.music_title    = auto_title
    ev.music_artist   = auto_artist
    # Phase 2 fields
    accent2 = f.get('accent_colour_2', '')
    ev.accent_colour_2 = accent2 if _valid_colour(accent2) else ''
    ev.programme      = _clean(f.get('programme', ''), 2000)
    ev.spotify_url    = _clean(f.get('spotify_url', ''), 400)
    ev.whatsapp_group = _clean(f.get('whatsapp_group', ''), 400)
    ev.hashtag        = re.sub(r'[^a-zA-Z0-9_]', '', f.get('hashtag', ''))[:60]
    ev.greeting_lang  = f.get('greeting_lang', 'English')
    return ev


# ── Email helpers ─────────────────────────────────────────────

def send_host_notification(event, rsvp):
    emoji = '🎉' if rsvp.attending == 'yes' else '😢'
    tag = ' [WAITLIST]' if rsvp.waitlist else ''
    try:
        mail.send(Message(
            subject=f"{emoji} New RSVP{tag} — {event.event_title}",
            recipients=[event.host_email],
            html=render_template('email_host_notification.html',
                                 event=event, rsvp=rsvp, emoji=emoji),
        ))
    except Exception as e:
        app.logger.warning(f"Host notify failed: {e}")


def send_guest_confirmation(event, rsvp):
    if not rsvp.email:
        return
    try:
        subj = ('On the waitlist' if rsvp.waitlist
                else ('Confirmed' if rsvp.attending == 'yes' else 'Noted'))
        mail.send(Message(
            subject=f"{subj} — {event.event_title}",
            recipients=[rsvp.email],
            html=render_template('email_guest_confirmation.html', event=event, rsvp=rsvp),
        ))
    except Exception as e:
        app.logger.warning(f"Guest confirm failed: {e}")


def send_rsvp_summary(event) -> bool:
    yes_list  = [r for r in event.rsvps if r.attending == 'yes' and not r.waitlist]
    no_list   = [r for r in event.rsvps if r.attending == 'no']
    wait_list = [r for r in event.rsvps if r.waitlist]
    try:
        mail.send(Message(
            subject=f"Daily RSVP Summary — {event.event_title}",
            recipients=[event.host_email],
            html=render_template('email_rsvp_summary.html', event=event,
                                 yes_list=yes_list, no_list=no_list, wait_list=wait_list),
        ))
        return True
    except Exception as e:
        app.logger.warning(f"Summary failed: {e}")
        return False


def send_announcement(event, message: str) -> int:
    yes_emails = [r.email for r in event.rsvps
                  if r.attending == 'yes' and r.email and not r.waitlist]
    if not yes_emails:
        return 0
    sent = 0
    for email in yes_emails:
        try:
            mail.send(Message(
                subject=f"Update for {event.event_title}",
                recipients=[email],
                html=render_template('email_announcement.html',
                                     event=event, message=message),
            ))
            sent += 1
        except Exception:
            pass
    return sent


# ── Scheduled jobs ────────────────────────────────────────────

def daily_digest():
    with app.app_context():
        today = date.today()
        for event in Event.query.filter_by(is_archived=False).all():
            if not event.rsvps:
                continue
            ev_date = parse_iso(event.event_date_iso or event.event_date)
            if ev_date and (ev_date - today).days < -7:
                continue
            send_rsvp_summary(event)


def auto_archive():
    """Archive events older than ARCHIVE_AFTER_DAYS."""
    days = app.config.get('ARCHIVE_AFTER_DAYS', 365)
    if not days:
        return
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(days=days)
        old = Event.query.filter(
            Event.created_at < cutoff, Event.is_archived == False
        ).all()
        for ev in old:
            ev.is_archived = True
        if old:
            db.session.commit()
            app.logger.info(f"Auto-archived {len(old)} events")


# ─────────────────────────────────────────────────────────────
# ── Routes: Auth ─────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name     = _clean_name(request.form.get('name', ''))
        email    = _clean(request.form.get('email', ''), 200).lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        if not name:
            errors.append('Name is required.')
        if not _valid_email(email):
            errors.append('Please enter a valid email address.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if User.query.filter_by(email=email).first():
            errors.append('An account with that email already exists.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html', name=name, email=email)

        user = User(name=name, email=email)
        user.set_password(password)

        # Auto-promote if this is the configured first admin email
        first_admin = app.config.get('FIRST_ADMIN_EMAIL', '').lower()
        if first_admin and email == first_admin:
            user.is_admin = True

        db.session.add(user)
        db.session.commit()
        _audit('user_register', f'email={email}', user_id=user.id)

        login_user(user, remember=True)
        flash(f'Welcome to Invitely, {user.name}! 🎉', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    next_url = request.args.get('next', '')

    if request.method == 'POST':
        email    = _clean(request.form.get('email', ''), 200).lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            _audit('login_failed', f'email={email}')
            flash('Incorrect email or password.', 'error')
            return render_template('login.html', email=email, next=next_url)

        # Promote to admin if first_admin env var matches and not already admin
        first_admin = app.config.get('FIRST_ADMIN_EMAIL', '').lower()
        if first_admin and email == first_admin and not user.is_admin:
            user.is_admin = True
            db.session.commit()

        login_user(user, remember=remember)
        _audit('user_login', f'email={email}')

        # Safe redirect — only allow relative paths
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return redirect(next_url)
        return redirect(url_for('dashboard'))

    return render_template('login.html', next=next_url)


@app.route('/logout')
@login_required
def logout():
    _audit('user_logout')
    logout_user()
    flash('You have been signed out.', 'success')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    events = (Event.query
              .filter_by(user_id=current_user.id, is_archived=False)
              .order_by(Event.created_at.desc())
              .all())
    today_dt = date.today()
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    event_meta = {}
    for ev in events:
        yes_count   = sum(1 for r in ev.rsvps if r.attending == 'yes' and not r.waitlist)
        new_today   = sum(1 for r in ev.rsvps if r.timestamp and r.timestamp >= cutoff_24h)
        days_left   = None
        if ev.event_date_iso:
            try:
                ev_date   = date.fromisoformat(ev.event_date_iso)
                days_left = (ev_date - today_dt).days
            except ValueError:
                pass
        event_meta[ev.token] = {
            'yes_count': yes_count,
            'new_today': new_today,
            'days_left': days_left,
        }
    return render_template('dashboard.html', events=events,
                           today=today_dt.isoformat(),
                           event_meta=event_meta)


# ── Password reset helpers ────────────────────────────────────

def _make_reset_token(email: str) -> str:
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return s.dumps(email, salt='pw-reset')


def _verify_reset_token(token: str, max_age: int = 3600):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        return s.loads(token, salt='pw-reset', max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None


@app.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = _clean(request.form.get('email', ''), 200).lower()
        user  = User.query.filter_by(email=email).first()
        # Always show the same message — never reveal whether email exists
        if user:
            token     = _make_reset_token(email)
            reset_url = url_for('reset_password', token=token, _external=True)
            try:
                mail.send(Message(
                    subject='Reset your Invitely password',
                    recipients=[email],
                    html=render_template('email_password_reset.html',
                                         user=user, reset_url=reset_url),
                ))
            except Exception as e:
                app.logger.warning(f"Password reset email failed: {e}")
            _audit('password_reset_request', f'email={email}', user_id=user.id)
        flash('If that email is registered, a reset link is on its way.', 'success')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    email = _verify_reset_token(token)
    if not email:
        return render_template('reset_password.html', expired=True, token=token)

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('reset_password.html', expired=False, token=token)
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html', expired=False, token=token)
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Account not found.', 'error')
            return redirect(url_for('login'))
        user.set_password(password)
        db.session.commit()
        _audit('password_reset_complete', f'email={email}', user_id=user.id)
        flash('Password updated. You can now sign in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html', expired=False, token=token)


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account_settings():
    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'update_name':
            new_name = _clean_name(request.form.get('name', ''))
            if not new_name:
                flash('Name cannot be empty.', 'error')
            else:
                current_user.name = new_name
                db.session.commit()
                _audit('account_update_name')
                flash('Name updated successfully.', 'success')

        elif action == 'change_password':
            old = request.form.get('old_password', '')
            new = request.form.get('new_password', '')
            confirm = request.form.get('confirm_new_password', '')
            if not current_user.check_password(old):
                flash('Current password is incorrect.', 'error')
            elif len(new) < 8:
                flash('New password must be at least 8 characters.', 'error')
            elif new != confirm:
                flash('New passwords do not match.', 'error')
            else:
                current_user.set_password(new)
                db.session.commit()
                _audit('password_change')
                flash('Password updated successfully.', 'success')

        elif action == 'delete_account':
            if request.form.get('confirm_delete') != 'yes':
                flash('Please confirm account deletion.', 'error')
            else:
                name = current_user.name
                # Cascade via SQLAlchemy relationships
                for ev in current_user.events:
                    db.session.delete(ev)
                db.session.delete(current_user)
                db.session.commit()
                logout_user()
                _audit('account_deleted', f'name={name}')
                flash('Your account and all data have been permanently deleted.', 'success')
                return redirect(url_for('index'))

    return render_template('account.html')


# ─────────────────────────────────────────────────────────────
# ── Routes: Public ───────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ─────────────────────────────────────────────────────────────
# ── Routes: Event creation / editing ─────────────────────────
# ─────────────────────────────────────────────────────────────

def _form_ctx():
    return dict(
        event_types=EVENT_TYPES, dress_codes=DRESS_CODES, themes=THEMES,
        colour_palettes=COLOUR_PALETTES, accent_colours=ACCENT_COLOURS,
        designs=DESIGNS, fonts=FONTS, patterns=PATTERNS, decorations=DECORATIONS,
        effects=EFFECTS, photo_filters=PHOTO_FILTERS,
    )


@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    ctx = {**_form_ctx(), 'event': None, 'edit_mode': False}

    if request.method == 'GET':
        return render_template('create.html', **ctx)

    f     = request.form
    token = uuid.uuid4().hex[:12]
    event = _build_event_from_form(f, request.files, token)
    event.user_id = current_user.id
    db.session.add(event)
    db.session.flush()

    for i in range(1, 4):
        compressed = f.get(f'image_{i}_compressed', '').strip()
        path = save_image(request.files.get(f'image_{i}'), token,
                          compressed_b64=compressed or None)
        if path:
            setattr(event, f'image_{i}', path)

    # Video note
    vid_path = save_video(request.files.get('video_note'), token)
    if vid_path:
        event.video_note = vid_path

    for gname, gstore in zip(f.getlist('gift_name'), f.getlist('gift_store')):
        gname = _clean(gname, 200)
        if gname:
            db.session.add(Gift(event_id=event.id, name=gname,
                                store=_clean(gstore, 200)))

    db.session.commit()
    _audit('event_create', f'token={token} title={event.event_title!r}')

    invite_url = url_for('invitation', token=token, _external=True)
    manage_url = url_for('manage', token=token, _external=True)
    return render_template('created.html', event=event,
                           invite_url=invite_url, manage_url=manage_url,
                           host_pin=event.host_pin)


@app.route('/preview-draft', methods=['POST'])
@login_required
def preview_draft():
    """Render a full invitation preview from form data without saving to DB."""
    from types import SimpleNamespace
    f = request.form
    raw_date  = _clean(f.get('event_date', ''))
    raw_time  = _clean(f.get('event_time', ''))
    raw_music = _clean(f.get('music_url', ''), 400)
    embed     = yt_embed(raw_music) or ''
    accent    = f.get('accent_colour', '#e8d5a3')
    if not _valid_colour(accent):
        accent = '#e8d5a3'
    accent2 = f.get('accent_colour_2', '')
    if not _valid_colour(accent2):
        accent2 = ''

    event = SimpleNamespace(
        token='preview',
        host_name=_clean_name(f.get('host_name', 'Your Name')),
        host_email='',
        guest_name=_clean_name(f.get('guest_name', '')),
        event_type=_clean(f.get('event_type_custom', '')) or _clean(f.get('event_type', 'Birthday')),
        event_title=_clean(f.get('event_title', 'Your Event Title'), 200) or 'Your Event Title',
        event_date=fmt_date(raw_date) if raw_date else 'Date TBD',
        event_date_iso=raw_date,
        event_time=fmt_time(raw_time) if raw_time else '',
        rsvp_deadline='',
        capacity=0,
        save_the_date=bool(f.get('save_the_date')),
        venue_name=_clean(f.get('venue_name', ''), 200) or 'Venue TBD',
        venue_address=_clean(f.get('venue_address', ''), 300),
        venue_lat=float(f.get('venue_lat') or -26.2041),
        venue_lng=float(f.get('venue_lng') or 28.0473),
        dress_code=_clean(f.get('dress_code_custom', '')) or _clean(f.get('dress_code', '')),
        theme=_clean(f.get('theme_custom', '')) or _clean(f.get('theme', '')),
        colour_palette=_clean(f.get('palette_custom', '')) or _clean(f.get('colour_palette', '')),
        accent_colour=accent,
        accent_colour_2=accent2,
        design=f.get('design', 'classic_dark'),
        font=f.get('font', 'Modern'),
        pattern=f.get('pattern', 'none'),
        pattern_opacity=max(10, min(100, int(f.get('pattern_opacity') or 40))),
        decorations=f.get('decorations', 'none'),
        effect=f.get('effect', 'none'),
        photo_filter=f.get('photo_filter', 'none'),
        extra_notes=_clean(f.get('extra_notes', ''), 1000),
        music_url=embed,
        music_title=_clean(f.get('music_title', ''), 200),
        music_artist=_clean(f.get('music_artist', ''), 200),
        programme=_clean(f.get('programme', ''), 2000),
        spotify_url='',
        whatsapp_group='',
        hashtag='',
        greeting_lang=f.get('greeting_lang', 'English'),
        image_1='',
        image_2='',
        image_3='',
        video_note='',
        view_count=0,
        gifts=[],
        rsvps=[],
        links=[],
        announcements=[],
    )

    ctx = dict(
        event=event, link=None, existing_rsvp=None,
        yes_count=0, no_count=0,
        rsvp_open=False, event_passed=False, capacity_full=False,
        recent_rsvps=[], guest_name_prefill='',
        is_preview=True,
    )
    return render_template('invitation.html', **ctx)


@app.route('/edit/<token>', methods=['GET', 'POST'])
@login_required
def edit_event(token):
    event = Event.query.filter_by(token=token).first_or_404()
    if not _can_manage(event):
        abort(403)

    ctx = {**_form_ctx(), 'event': event, 'edit_mode': True}

    if request.method == 'GET':
        return render_template('create.html', **ctx)

    _build_event_from_form(request.form, request.files, token, existing=event)

    for i in range(1, 4):
        compressed = request.form.get(f'image_{i}_compressed', '').strip()
        path = save_image(request.files.get(f'image_{i}'), token,
                          compressed_b64=compressed or None)
        if path:
            setattr(event, f'image_{i}', path)

    new_names = [_clean(n, 200) for n in request.form.getlist('gift_name')
                 if _clean(n, 200)]
    if new_names:
        for g in event.gifts:
            db.session.delete(g)
        for gname, gstore in zip(request.form.getlist('gift_name'),
                                  request.form.getlist('gift_store')):
            gname = _clean(gname, 200)
            if gname:
                db.session.add(Gift(event_id=event.id, name=gname,
                                    store=_clean(gstore, 200)))

    db.session.commit()
    _audit('event_edit', f'token={token}')

    invite_url = url_for('invitation', token=token, _external=True)
    manage_url = url_for('manage', token=token, _external=True)
    return render_template('created.html', event=event,
                           invite_url=invite_url, manage_url=manage_url,
                           host_pin=event.host_pin)


# Legacy PIN-based edit (backward compat for old bookmarked URLs)
@app.route('/edit/<token>/<pin>', methods=['GET', 'POST'])
def edit_event_pin(token, pin):
    event = Event.query.filter_by(token=token).first_or_404()
    # If the event now has a user_id, require login instead of PIN
    if event.user_id:
        flash('Please sign in to edit your event.', 'error')
        return redirect(url_for('login', next=url_for('edit_event', token=token)))
    if not event.host_pin or pin != event.host_pin:
        abort(403)
    # Reuse authenticated route logic by faking the session via a redirect
    # (simpler: just duplicate the logic with pin guard)
    ctx = {**_form_ctx(), 'event': event, 'edit_mode': True, 'pin': pin}
    if request.method == 'GET':
        return render_template('create.html', **ctx)

    _build_event_from_form(request.form, request.files, token, existing=event)
    for i in range(1, 4):
        compressed = request.form.get(f'image_{i}_compressed', '').strip()
        path = save_image(request.files.get(f'image_{i}'), token,
                          compressed_b64=compressed or None)
        if path:
            setattr(event, f'image_{i}', path)
    new_names = [_clean(n, 200) for n in request.form.getlist('gift_name')
                 if _clean(n, 200)]
    if new_names:
        for g in event.gifts:
            db.session.delete(g)
        for gname, gstore in zip(request.form.getlist('gift_name'),
                                  request.form.getlist('gift_store')):
            gname = _clean(gname, 200)
            if gname:
                db.session.add(Gift(event_id=event.id, name=gname,
                                    store=_clean(gstore, 200)))
    db.session.commit()
    _audit('event_edit_pin', f'token={token}')
    invite_url = url_for('invitation', token=token, _external=True)
    manage_url = url_for('manage_pin', token=token, pin=pin, _external=True)
    return render_template('created.html', event=event,
                           invite_url=invite_url, manage_url=manage_url,
                           host_pin=pin)


# ─────────────────────────────────────────────────────────────
# ── Routes: Invitations (public) ─────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.route('/invite/<token>')
def invitation(token):
    event = Event.query.filter_by(token=token, is_archived=False).first_or_404()
    event.view_count = (event.view_count or 0) + 1
    db.session.commit()
    return render_template('invitation.html', **_invitation_context(event))


@app.route('/invite/<token>/<link_token>')
def personalised_invitation(token, link_token):
    event = Event.query.filter_by(token=token, is_archived=False).first_or_404()
    link  = InviteLink.query.filter_by(link_token=link_token,
                                       event_id=event.id).first_or_404()
    event.view_count = (event.view_count or 0) + 1
    if not link.opened:
        link.opened    = True
        link.opened_at = datetime.utcnow()
    db.session.commit()

    original_name = event.guest_name
    event.guest_name = f"{link.guest_name} {link.guest_surname or ''}".strip()
    existing_rsvp = link.rsvp if link.rsvp_id else None
    out = render_template('invitation.html',
                          **_invitation_context(event, link=link,
                                                existing_rsvp=existing_rsvp))
    event.guest_name = original_name
    return out


@app.route('/invite/<token>/<link_token>/rsvp')
def personalised_rsvp_status(token, link_token):
    event = Event.query.filter_by(token=token, is_archived=False).first_or_404()
    link  = InviteLink.query.filter_by(link_token=link_token,
                                       event_id=event.id).first_or_404()
    if not link.rsvp_id:
        return redirect(url_for('personalised_invitation',
                                token=token, link_token=link_token))
    original_name = event.guest_name
    event.guest_name = f"{link.guest_name} {link.guest_surname or ''}".strip()
    out = render_template('invitation.html',
                          **_invitation_context(event, link=link,
                                                existing_rsvp=link.rsvp))
    event.guest_name = original_name
    return out


# ─────────────────────────────────────────────────────────────
# ── Routes: Manage ───────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.route('/manage/<token>')
@login_required
def manage(token):
    event = Event.query.filter_by(token=token).first_or_404()
    if not _can_manage(event):
        abort(403)
    return _render_manage(event)


@app.route('/manage/<token>/<pin>')
def manage_pin(token, pin):
    """Legacy PIN-based manage access — kept for backward compatibility."""
    event = Event.query.filter_by(token=token).first_or_404()
    if event.user_id:
        # Event has moved to account-based auth — redirect to login
        flash('Please sign in to manage your event.', 'error')
        return redirect(url_for('login', next=url_for('manage', token=token)))
    if not event.host_pin or pin != event.host_pin:
        abort(403)
    return _render_manage(event, legacy_pin=pin)


def _render_manage(event, legacy_pin: str = None):
    yes_list     = [r for r in event.rsvps if r.attending == 'yes' and not r.waitlist]
    no_list      = [r for r in event.rsvps if r.attending == 'no']
    wait_list    = [r for r in event.rsvps if r.waitlist]
    invite_links = sorted(event.links, key=lambda x: x.created_at, reverse=True)
    invite_url   = url_for('invitation', token=event.token, _external=True)

    if legacy_pin:
        edit_url = url_for('edit_event_pin', token=event.token, pin=legacy_pin, _external=True)
    else:
        edit_url = url_for('edit_event', token=event.token, _external=True)

    return render_template('manage.html', event=event,
                           yes_list=yes_list, no_list=no_list,
                           wait_list=wait_list, invite_links=invite_links,
                           invite_url=invite_url, edit_url=edit_url,
                           legacy_pin=legacy_pin)


# ─────────────────────────────────────────────────────────────
# ── Routes: Delete / privacy ─────────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.route('/delete-event/<token>', methods=['POST'])
@login_required
def delete_event(token):
    event = Event.query.filter_by(token=token).first_or_404()
    if not _can_manage(event):
        abort(403)
    title = event.event_title
    db.session.delete(event)
    db.session.commit()
    _audit('event_delete', f'token={token} title={title!r}')
    flash(f'"{title}" has been permanently deleted.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/duplicate-event/<token>', methods=['POST'])
@login_required
def duplicate_event(token):
    """Copy all event settings into a new draft event with a blank date + RSVP list."""
    src = Event.query.filter_by(token=token).first_or_404()
    if not _can_manage(src):
        abort(403)

    new_token = uuid.uuid4().hex[:12]
    new_event = Event(
        token=new_token,
        user_id=current_user.id,
        host_name=src.host_name,
        host_email=src.host_email,
        host_pin=str(uuid.uuid4().int)[:4],
        guest_name=src.guest_name,
        event_type=src.event_type,
        event_title=f"{src.event_title} (Copy)",
        # Leave date/time blank — host must fill in
        event_date='',
        event_date_iso='',
        event_time='',
        rsvp_deadline='',
        capacity=src.capacity,
        save_the_date=False,
        venue_name=src.venue_name,
        venue_address=src.venue_address,
        venue_lat=src.venue_lat,
        venue_lng=src.venue_lng,
        dress_code=src.dress_code,
        theme=src.theme,
        colour_palette=src.colour_palette,
        accent_colour=src.accent_colour,
        design=src.design,
        font=src.font,
        pattern=src.pattern,
        decorations=src.decorations,
        extra_notes=src.extra_notes,
        music_url=src.music_url,
        music_title=src.music_title,
        music_artist=src.music_artist,
        # Images not copied — host should upload fresh ones
    )
    db.session.add(new_event)
    db.session.flush()

    # Copy gift registry
    for g in src.gifts:
        db.session.add(Gift(event_id=new_event.id, name=g.name, store=g.store))

    db.session.commit()
    _audit('event_duplicate', f'src={token} new={new_token}')
    flash(f'"{src.event_title}" duplicated. Update the date and details before publishing.', 'success')
    return redirect(url_for('edit_event', token=new_token))


@app.route('/api/delete-rsvp/<int:rsvp_id>', methods=['POST'])
@login_required
def delete_rsvp(rsvp_id):
    rsvp  = RSVP.query.get_or_404(rsvp_id)
    event = Event.query.get_or_404(rsvp.event_id)
    if not _can_manage(event):
        abort(403)
    name = rsvp.name
    db.session.delete(rsvp)
    db.session.commit()
    _audit('rsvp_delete', f'event={event.token} guest={name!r}')
    return jsonify({'status': 'ok'})


# ─────────────────────────────────────────────────────────────
# ── Routes: Admin ────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin():
    _audit('admin_view_dashboard')
    events = Event.query.order_by(Event.created_at.desc()).all()
    rsvps  = RSVP.query.all()
    links  = InviteLink.query.all()

    total_views    = sum(e.view_count or 0 for e in events)
    opened_links   = sum(1 for l in links if l.opened)
    yes_rsvps      = sum(1 for r in rsvps if r.attending == 'yes' and not r.waitlist)
    no_rsvps       = sum(1 for r in rsvps if r.attending == 'no')
    wait_rsvps     = sum(1 for r in rsvps if r.waitlist)
    total_users    = User.query.count()
    conv_rate      = round((len(rsvps) / total_views) * 100, 1) if total_views else 0
    link_open_rate = round((opened_links / len(links)) * 100, 1) if links else 0

    recent_audit   = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(20).all()

    return render_template(
        'admin.html',
        events=events,
        total_events=len(events),
        total_users=total_users,
        total_rsvps=len(rsvps),
        total_views=total_views,
        total_links=len(links),
        opened_links=opened_links,
        yes_rsvps=yes_rsvps,
        no_rsvps=no_rsvps,
        wait_rsvps=wait_rsvps,
        conversion_rate=conv_rate,
        link_open_rate=link_open_rate,
        top_events=sorted(events, key=lambda e: e.view_count or 0, reverse=True)[:8],
        recent_rsvps=sorted(rsvps, key=lambda r: r.timestamp, reverse=True)[:10],
        recent_audit=recent_audit,
        popular_patterns=_popular([e.pattern for e in events]),
        popular_colours=_popular([e.accent_colour for e in events]),
        popular_designs=_popular([e.design for e in events]),
        popular_types=_popular([e.event_type for e in events]),
        today_str=date.today().isoformat(),
        date=date,
    )


@app.route('/admin/edit/<token>', methods=['GET', 'POST'])
@admin_required
def admin_edit_event(token):
    event = Event.query.filter_by(token=token).first_or_404()
    ctx   = {**_form_ctx(), 'event': event, 'edit_mode': True, 'admin_mode': True}

    if request.method == 'GET':
        return render_template('create.html', **ctx)

    _build_event_from_form(request.form, request.files, token, existing=event)
    for i in range(1, 4):
        compressed = request.form.get(f'image_{i}_compressed', '').strip()
        path = save_image(request.files.get(f'image_{i}'), token,
                          compressed_b64=compressed or None)
        if path:
            setattr(event, f'image_{i}', path)
    db.session.commit()
    _audit('admin_event_edit', f'token={token}')
    flash('Event updated.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/delete/<token>', methods=['POST'])
@admin_required
def admin_delete_event(token):
    event = Event.query.filter_by(token=token).first_or_404()
    title = event.event_title
    db.session.delete(event)
    db.session.commit()
    _audit('admin_event_delete', f'token={token} title={title!r}')
    flash(f'Event "{title}" deleted.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/toggle-admin/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    if user_id == current_user.id:
        return jsonify({'status': 'error', 'message': 'Cannot change your own admin status.'}), 400
    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    _audit('admin_toggle_admin', f'target_user={user.email} is_admin={user.is_admin}')
    return jsonify({'status': 'ok', 'is_admin': user.is_admin})


@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)


# ─────────────────────────────────────────────────────────────
# ── Routes: API ──────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

# Guest-facing public APIs are CSRF-exempt (no session available for guests)
@csrf.exempt
@app.route('/api/rsvp/<token>', methods=['POST'])
@limiter.limit("8 per minute; 30 per hour")
def api_rsvp(token):
    event = Event.query.filter_by(token=token, is_archived=False).first_or_404()

    if not _rsvp_open(event):
        return jsonify({'status': 'closed', 'message': 'RSVP deadline has passed.'}), 200

    data      = request.get_json(silent=True) or {}
    link_token = _clean(data.get('link_token', ''), 32)
    invite_link = None
    if link_token:
        invite_link = InviteLink.query.filter_by(event_id=event.id,
                                                link_token=link_token).first()
        if not invite_link:
            return jsonify({'status': 'error',
                            'message': 'This personalised invite link is invalid.'}), 404
        if invite_link.rsvp_id:
            return jsonify({
                'status': 'duplicate',
                'message': "This invite link has already been used to RSVP.",
                'redirect': url_for('personalised_rsvp_status',
                                    token=event.token,
                                    link_token=invite_link.link_token),
            }), 200

    name        = _clean_name(data.get('name', ''))
    email       = _clean(data.get('email', ''), 200).lower()
    attending   = data.get('attending')
    dietary     = _clean(data.get('dietary', ''), 300)
    plus_one    = _clean_name(data.get('plus_one', ''))
    plus_ones   = max(0, min(9, int(data.get('plus_ones', 0) or 0)))

    if invite_link and not name:
        name = f"{invite_link.guest_name} {invite_link.guest_surname or ''}".strip()

    if not name or attending not in ('yes', 'no'):
        return jsonify({'status': 'error',
                        'message': 'Please enter your name and select Yes or No.'}), 400

    if email and not _valid_email(email):
        return jsonify({'status': 'error', 'message': 'Please enter a valid email.'}), 400

    existing = RSVP.query.filter_by(event_id=event.id, email=email).first() if email else None
    if existing:
        if invite_link and not invite_link.rsvp_id:
            invite_link.rsvp_id = existing.id
            db.session.commit()
        payload = {'status': 'duplicate', 'message': "You have already RSVP'd."}
        if invite_link:
            payload['redirect'] = url_for('personalised_rsvp_status',
                                          token=event.token,
                                          link_token=invite_link.link_token)
        return jsonify(payload), 200

    on_waitlist = attending == 'yes' and _capacity_full(event)

    rsvp = RSVP(event_id=event.id, name=name, email=email,
                attending=attending, dietary=dietary,
                plus_one=plus_one, plus_ones=plus_ones, waitlist=on_waitlist)
    db.session.add(rsvp)
    db.session.flush()
    if invite_link:
        invite_link.rsvp_id = rsvp.id
    db.session.commit()

    send_host_notification(event, rsvp)
    send_guest_confirmation(event, rsvp)

    return jsonify({
        'status': 'ok',
        'yes': _yes_count(event),
        'no': sum(1 for r in event.rsvps if r.attending == 'no'),
        'waitlist': on_waitlist,
        'redirect': url_for('personalised_rsvp_status',
                            token=event.token,
                            link_token=invite_link.link_token) if invite_link else '',
    })


@csrf.exempt
@app.route('/api/react/<token>', methods=['POST'])
@limiter.limit("60 per minute")
def api_react(token):
    import hashlib
    event = Event.query.filter_by(token=token, is_archived=False).first_or_404()
    data  = request.get_json(silent=True) or {}
    emoji = data.get('emoji', '')
    allowed = ['🔥', '❤️', '😍', '🎉', '🥳']
    if emoji not in allowed:
        return jsonify({'error': 'invalid emoji'}), 400
    ip      = (request.headers.get('X-Forwarded-For', '') or '').split(',')[0].strip() or request.remote_addr or ''
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:40]
    existing = Reaction.query.filter_by(event_id=event.id, emoji=emoji, ip_hash=ip_hash).first()
    toggled = False
    if existing:
        db.session.delete(existing)
        toggled = False
    else:
        db.session.add(Reaction(event_id=event.id, emoji=emoji, ip_hash=ip_hash))
        toggled = True
    db.session.commit()
    counts = _reaction_counts(event.id)
    return jsonify({'counts': counts, 'toggled': toggled})


@app.route('/api/reactions/<token>')
def api_reactions(token):
    event = Event.query.filter_by(token=token, is_archived=False).first_or_404()
    return jsonify({'counts': _reaction_counts(event.id)})


def _reaction_counts(event_id: int) -> dict:
    rows = (db.session.query(Reaction.emoji, db.func.count(Reaction.id))
            .filter_by(event_id=event_id)
            .group_by(Reaction.emoji).all())
    return {emoji: cnt for emoji, cnt in rows}


@csrf.exempt
@app.route('/api/claim-gift/<int:gift_id>', methods=['POST'])
@limiter.limit("20 per hour")
def claim_gift(gift_id):
    gift = Gift.query.get_or_404(gift_id)
    if gift.taken:
        return jsonify({'status': 'error', 'message': 'Already taken.'}), 409
    data = request.get_json(silent=True) or {}
    gift.taken    = True
    gift.taken_by = _clean_name(data.get('name', '') or 'A guest')
    db.session.commit()
    return jsonify({'status': 'ok'})


@app.route('/api/unclaim-gift/<int:gift_id>', methods=['POST'])
def unclaim_gift(gift_id):
    gift = Gift.query.get_or_404(gift_id)
    event = Event.query.get_or_404(gift.event_id)
    data = request.get_json(silent=True) or {}
    pin = data.get('pin', '')
    authed = (current_user.is_authenticated and
              (current_user.is_admin or event.user_id == current_user.id))
    if not authed and pin != event.host_pin:
        abort(403)
    gift.taken    = False
    gift.taken_by = ''
    db.session.commit()
    return jsonify({'status': 'ok'})


@app.route('/api/send-summary/<token>', methods=['POST'])
def send_summary(token):
    event = Event.query.filter_by(token=token).first_or_404()
    # Allow if logged-in owner, admin, or legacy PIN in body
    data = request.get_json(silent=True) or {}
    pin  = data.get('pin', '')
    authed = (current_user.is_authenticated and
              (current_user.is_admin or event.user_id == current_user.id))
    if not authed and pin != event.host_pin:
        abort(403)
    ok = send_rsvp_summary(event)
    return jsonify({
        'status': 'ok' if ok else 'error',
        'message': f'Sent to {event.host_email}' if ok else 'Email failed.',
    })


@app.route('/api/broadcast/<token>', methods=['POST'])
@limiter.limit("10 per hour")
def broadcast(token):
    event = Event.query.filter_by(token=token).first_or_404()
    data  = request.get_json(silent=True) or {}
    pin   = data.get('pin', '')
    authed = (current_user.is_authenticated and
              (current_user.is_admin or event.user_id == current_user.id))
    if not authed and pin != event.host_pin:
        abort(403)

    message = _clean(data.get('message', ''), 2000)
    if not message:
        return jsonify({'status': 'error', 'message': 'Message required.'}), 400

    ann = Announcement(event_id=event.id, message=message)
    db.session.add(ann)
    db.session.commit()
    sent = send_announcement(event, message)
    _audit('broadcast', f'token={token} sent={sent}')
    return jsonify({'status': 'ok', 'sent': sent})


@app.route('/api/create-link/<token>', methods=['POST'])
@limiter.limit("60 per hour")
def create_link(token):
    event = Event.query.filter_by(token=token).first_or_404()
    data  = request.get_json(silent=True) or {}
    pin   = data.get('pin', '')
    authed = (current_user.is_authenticated and
              (current_user.is_admin or event.user_id == current_user.id))
    if not authed and pin != event.host_pin:
        abort(403)

    guest   = _clean_name(data.get('guest_name', '') or 'Friend')
    surname = _clean_name(data.get('guest_surname', ''))
    message = _clean(data.get('personal_msg', ''), 300)
    ltoken  = _unique_link_token()

    db.session.add(InviteLink(
        event_id=event.id, link_token=ltoken,
        guest_name=guest, guest_surname=surname, personal_msg=message,
    ))
    db.session.commit()
    url = _invite_link_url(event, InviteLink.query.filter_by(link_token=ltoken).first())
    return jsonify({'status': 'ok', 'url': url,
                    'guest_name': guest, 'guest_surname': surname})


@app.route('/api/bulk-links/<token>', methods=['POST'])
@limiter.limit("10 per hour")
def bulk_create_links(token):
    event = Event.query.filter_by(token=token).first_or_404()
    data  = request.get_json(silent=True) or {}
    pin   = data.get('pin', '')
    authed = (current_user.is_authenticated and
              (current_user.is_admin or event.user_id == current_user.id))
    if not authed and pin != event.host_pin:
        abort(403)

    guests = data.get('guests') or []
    if not isinstance(guests, list) or not guests:
        return jsonify({'status': 'error', 'message': 'Add at least one guest.'}), 400
    if len(guests) > 250:
        return jsonify({'status': 'error',
                        'message': 'Max 250 links per batch.'}), 400

    created = []
    for g in guests:
        if not isinstance(g, dict):
            continue
        first   = _clean_name(g.get('first', '') or g.get('guest_name', ''))
        last    = _clean_name(g.get('last', '')  or g.get('guest_surname', ''))
        message = _clean(g.get('message', '') or g.get('personal_msg', ''), 300)
        if not first and not last:
            continue
        link = InviteLink(
            event_id=event.id, link_token=_unique_link_token(),
            guest_name=first or 'Friend', guest_surname=last, personal_msg=message,
        )
        db.session.add(link)
        created.append(link)

    db.session.commit()
    _audit('bulk_links', f'token={token} count={len(created)}')
    return jsonify({
        'status': 'ok',
        'created': len(created),
        'links': [
            {'name': f"{l.guest_name} {l.guest_surname or ''}".strip(),
             'url': _invite_link_url(event, l), 'token': l.link_token}
            for l in created
        ],
    })


@csrf.exempt
@app.route('/api/location-search')
@limiter.limit("30 per minute")
def location_search():
    q = _clean(request.args.get('q', ''), 200)
    if not q:
        return jsonify([])
    url = (f"https://nominatim.openstreetmap.org/search"
           f"?format=json&q={urllib.parse.quote(q)}&limit=6&addressdetails=1")
    req = urllib.request.Request(url, headers={'User-Agent': 'Invitely/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            return jsonify(_json.loads(r.read()))
    except Exception:
        return jsonify([])


@csrf.exempt
@app.route('/api/yt-meta')
@limiter.limit("30 per minute")
def api_yt_meta():
    raw = _clean(request.args.get('url', ''), 400)
    if '/search?' in raw or 'music.youtube.com/search' in raw:
        return jsonify({'error': 'search_url', 'title': '', 'author': ''})
    title, author = yt_meta(raw)
    return jsonify({'title': title, 'author': author})


@csrf.exempt
@app.route('/api/recent-rsvps/<token>')
def recent_rsvps(token):
    event = Event.query.filter_by(token=token).first_or_404()
    recent = sorted(
        [r for r in event.rsvps if r.attending == 'yes' and not r.waitlist],
        key=lambda r: r.timestamp, reverse=True,
    )[:5]
    return jsonify([{'name': r.name.split()[0], 'time': r.timestamp.isoformat()}
                    for r in recent])


# ── Guest Comments API ────────────────────────────────────────

@csrf.exempt
@app.route('/api/comments/<token>', methods=['GET'])
def get_comments(token):
    event = Event.query.filter_by(token=token, is_archived=False).first_or_404()
    comments = (GuestComment.query
                .filter_by(event_id=event.id, approved=True)
                .order_by(GuestComment.created_at.desc())
                .limit(50).all())
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'message': c.message,
        'time': c.created_at.strftime('%d %b %Y') if c.created_at else '',
    } for c in comments])


@csrf.exempt
@app.route('/api/comments/<token>', methods=['POST'])
@limiter.limit("5 per minute; 20 per hour")
def post_comment(token):
    event = Event.query.filter_by(token=token, is_archived=False).first_or_404()
    data  = request.get_json(silent=True) or {}
    name  = _clean_name(data.get('name', ''))
    msg   = _clean(data.get('message', ''), 500)
    if not name or not msg:
        return jsonify({'status': 'error', 'message': 'Name and message are required.'}), 400
    comment = GuestComment(event_id=event.id, name=name, message=msg)
    db.session.add(comment)
    db.session.commit()
    return jsonify({'status': 'ok', 'id': comment.id, 'name': name,
                    'message': msg, 'time': 'Just now'})


@app.route('/api/delete-comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = GuestComment.query.get_or_404(comment_id)
    event   = Event.query.get_or_404(comment.event_id)
    if not _can_manage(event):
        abort(403)
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'status': 'ok'})


# ─────────────────────────────────────────────────────────────
# ── Routes: Exports ──────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.route('/manage/<token>/export-csv')
@login_required
def export_csv(token):
    event = Event.query.filter_by(token=token).first_or_404()
    if not _can_manage(event):
        abort(403)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Attending', 'Plus One',
                     'Dietary', 'Waitlist', 'RSVPd At'])
    for r in sorted(event.rsvps, key=lambda x: x.timestamp):
        writer.writerow([
            r.name, r.email, r.attending, r.plus_one,
            r.dietary, 'Yes' if r.waitlist else 'No',
            r.timestamp.strftime('%d %b %Y %H:%M'),
        ])
    output.seek(0)
    filename = f"{re.sub(r'[^a-zA-Z0-9_-]', '_', event.event_title)}_RSVPs.csv"
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment;filename={filename}'})


# Legacy PIN export
@app.route('/manage/<token>/<pin>/export-csv')
def export_csv_pin(token, pin):
    event = Event.query.filter_by(token=token).first_or_404()
    if event.user_id:
        abort(403)
    if not event.host_pin or pin != event.host_pin:
        abort(403)
    return export_csv(token)  # reuse without the login_required wrapper


# ─────────────────────────────────────────────────────────────
# ── CLI commands ─────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.cli.command('create-admin')
def create_admin_cmd():
    """Promote an existing user to admin, or create one interactively."""
    import click
    email = click.prompt('User email')
    user  = User.query.filter_by(email=email).first()
    if not user:
        name = click.prompt('Full name (new account)')
        pw   = click.prompt('Password', hide_input=True, confirmation_prompt=True)
        user = User(name=name, email=email, is_admin=True)
        user.set_password(pw)
        db.session.add(user)
        click.echo(f'Created admin account for {email}')
    else:
        user.is_admin = True
        click.echo(f'Promoted {email} to admin')
    db.session.commit()


# ─────────────────────────────────────────────────────────────
# ── Error handlers ────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

@app.errorhandler(CSRFError)
def csrf_error(e):
    if request.is_json or request.headers.get('X-Requested-With'):
        return jsonify({'status': 'error', 'message': 'CSRF token missing or invalid.'}), 400
    flash('Your session expired. Please try again.', 'error')
    return redirect(request.referrer or url_for('index'))


@app.errorhandler(429)
def rate_limit_error(e):
    if request.is_json:
        return jsonify({'status': 'error',
                        'message': 'Too many requests. Please slow down.'}), 429
    flash('Too many requests. Please wait a moment and try again.', 'error')
    return redirect(request.referrer or url_for('index'))


@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403,
                           message='You are not authorised to access this page.'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404,
                           message='This page could not be found.'), 404


@app.errorhandler(413)
def too_large(e):
    return jsonify({'status': 'error',
                    'message': 'File too large. Please use images under 10 MB each.'}), 413


# ─────────────────────────────────────────────────────────────
# ── Boot ─────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

scheduler.add_job(daily_digest, 'cron', hour=17, minute=0)
scheduler.add_job(auto_archive, 'cron', hour=2, minute=0)


def day_of_reminder():
    """Send reminder emails to all confirmed guests on the morning of the event."""
    with app.app_context():
        today_str = date.today().isoformat()
        events = Event.query.filter_by(event_date_iso=today_str, is_archived=False).all()
        for event in events:
            confirmed = [r for r in event.rsvps
                         if r.attending == 'yes' and not r.waitlist and r.email]
            for rsvp in confirmed:
                try:
                    mail.send(Message(
                        subject=f"Today's the day! 🎉 {event.event_title}",
                        recipients=[rsvp.email],
                        html=render_template('email_day_of_reminder.html',
                                             event=event, rsvp=rsvp),
                    ))
                except Exception as e:
                    app.logger.warning(f"Day-of reminder failed for {rsvp.email}: {e}")


scheduler.add_job(day_of_reminder, 'cron', hour=8, minute=0)
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))

# ── Auto-run migrations on startup (Render free tier has no shell) ──
with app.app_context():
    try:
        from flask_migrate import upgrade
        upgrade()
        app.logger.info("DB migrations applied successfully.")
    except Exception as _e:
        app.logger.warning(f"Migration on startup skipped/failed: {_e}")

if __name__ == '__main__':
    app.run(debug=False)
