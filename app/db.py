import asyncio
import json
import uuid
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from .config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _conn():
    c = sqlite3.connect(settings.database_path, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA temp_store=MEMORY")
    return c


def _init():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          telegram_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT, language TEXT NOT NULL DEFAULT 'dz',
          personality TEXT NOT NULL DEFAULT '', verified INTEGER NOT NULL DEFAULT 1, phone_hash TEXT,
          plan TEXT NOT NULL DEFAULT 'free', plan_expires_at TEXT, daily_count INTEGER NOT NULL DEFAULT 0,
          daily_date TEXT NOT NULL DEFAULT '', blocked INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
          video_daily_count INTEGER NOT NULL DEFAULT 0, video_daily_date TEXT NOT NULL DEFAULT '',
          image_daily_count INTEGER NOT NULL DEFAULT 0, image_daily_date TEXT NOT NULL DEFAULT '',
          bonus_image_credits INTEGER NOT NULL DEFAULT 0, voice_reply INTEGER NOT NULL DEFAULT 0, voice_style TEXT NOT NULL DEFAULT 'female', ai_mode TEXT NOT NULL DEFAULT 'quick'
        );
        CREATE TABLE IF NOT EXISTS payments (
          id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, plan TEXT NOT NULL, stars INTEGER NOT NULL,
          telegram_charge_id TEXT UNIQUE NOT NULL, provider_charge_id TEXT, paid_at TEXT NOT NULL,
          FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        );
        CREATE TABLE IF NOT EXISTS video_jobs (
          task_id TEXT PRIMARY KEY, telegram_id INTEGER NOT NULL, task_type TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued', progress INTEGER NOT NULL DEFAULT 0,
          status_message_id INTEGER, error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL, completed_at TEXT,
          FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        );
        CREATE TABLE IF NOT EXISTS image_jobs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, model TEXT NOT NULL,
          status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        );
        CREATE TABLE IF NOT EXISTS referrals (
          referred_id INTEGER PRIMARY KEY, referrer_id INTEGER NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(referred_id) REFERENCES users(telegram_id), FOREIGN KEY(referrer_id) REFERENCES users(telegram_id)
        );
        CREATE TABLE IF NOT EXISTS coupons (
          code TEXT PRIMARY KEY, plan TEXT NOT NULL DEFAULT 'free', duration_days INTEGER NOT NULL DEFAULT 0,
          image_bonus INTEGER NOT NULL DEFAULT 0, max_uses INTEGER NOT NULL DEFAULT 1,
          uses INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS coupon_redemptions (
          code TEXT NOT NULL, telegram_id INTEGER NOT NULL, redeemed_at TEXT NOT NULL,
          PRIMARY KEY(code,telegram_id), FOREIGN KEY(code) REFERENCES coupons(code),
          FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        );
        CREATE TABLE IF NOT EXISTS creator_jobs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, platform TEXT NOT NULL,
          duration INTEGER NOT NULL, status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        );
        CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY,telegram_id INTEGER,kind TEXT NOT NULL,status TEXT NOT NULL,stage TEXT NOT NULL DEFAULT '',progress INTEGER NOT NULL DEFAULT 0,detail TEXT NOT NULL DEFAULT '',generation_status TEXT NOT NULL DEFAULT 'pending',delivery_status TEXT NOT NULL DEFAULT 'not_started',error_code TEXT NOT NULL DEFAULT '',error TEXT NOT NULL DEFAULT '',file_path TEXT NOT NULL DEFAULT '',file_size INTEGER NOT NULL DEFAULT 0,language TEXT NOT NULL DEFAULT '',voice_profile TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,completed_at TEXT);
        CREATE TABLE IF NOT EXISTS system_events (id INTEGER PRIMARY KEY AUTOINCREMENT,level TEXT NOT NULL,source TEXT NOT NULL,event TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '',operation_id TEXT,telegram_id INTEGER,metadata TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY,operation_id TEXT,telegram_id INTEGER NOT NULL,kind TEXT NOT NULL,file_path TEXT NOT NULL,filename TEXT NOT NULL,caption TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '',telegram_message_id INTEGER,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,expires_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS session_context (telegram_id INTEGER NOT NULL,context_key TEXT NOT NULL,kind TEXT NOT NULL,content TEXT NOT NULL,expires_at TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(telegram_id,context_key));
        CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status,updated_at);
        CREATE INDEX IF NOT EXISTS idx_events_created ON system_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries(status,updated_at);
        CREATE INDEX IF NOT EXISTS idx_users_plan ON users(plan);
        CREATE INDEX IF NOT EXISTS idx_payments_paid ON payments(paid_at);
        CREATE INDEX IF NOT EXISTS idx_video_jobs_user_status ON video_jobs(telegram_id,status);
        """)
        columns = {row[1] for row in c.execute("PRAGMA table_info(users)")}
        if "video_daily_count" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN video_daily_count INTEGER NOT NULL DEFAULT 0")
        if "video_daily_date" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN video_daily_date TEXT NOT NULL DEFAULT ''")
        if "image_daily_count" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN image_daily_count INTEGER NOT NULL DEFAULT 0")
        if "image_daily_date" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN image_daily_date TEXT NOT NULL DEFAULT ''")
        if "bonus_image_credits" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN bonus_image_credits INTEGER NOT NULL DEFAULT 0")
        if "voice_reply" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN voice_reply INTEGER NOT NULL DEFAULT 0")
        if "voice_style" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN voice_style TEXT NOT NULL DEFAULT 'female'")
        if "ai_mode" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN ai_mode TEXT NOT NULL DEFAULT 'quick'")
        if "voice_language_mode" not in columns:
            c.execute("ALTER TABLE users ADD COLUMN voice_language_mode TEXT NOT NULL DEFAULT 'auto'")
        # Phone verification was removed. Keep existing members, discard old phone hashes.
        c.execute("UPDATE users SET verified=1, phone_hash=NULL")
        c.execute("UPDATE users SET voice_style=CASE WHEN voice_style IN ('male','deep','sports_energy','sports_calm') THEN 'male' ELSE 'female' END WHERE voice_style NOT IN ('male','female')")


async def init_db(): await asyncio.to_thread(_init)


def _execute(sql: str, params=(), fetchone=False, fetchall=False):
    with _conn() as c:
        cur = c.execute(sql, params)
        if fetchone:
            row = cur.fetchone(); return dict(row) if row else None
        if fetchall: return [dict(r) for r in cur.fetchall()]
        return cur.rowcount


async def upsert_user(tg_id: int, username: str | None, name: str):
    now = utcnow().isoformat()
    sql = """INSERT INTO users(telegram_id,username,display_name,created_at,last_seen_at) VALUES(?,?,?,?,?)
    ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,display_name=excluded.display_name,last_seen_at=excluded.last_seen_at"""
    await asyncio.to_thread(_execute, sql, (tg_id, username, name, now, now))


async def get_user(tg_id: int) -> dict[str, Any] | None:
    row = await asyncio.to_thread(_execute, "SELECT * FROM users WHERE telegram_id=?", (tg_id,), True)
    if row and row['plan'] != 'free' and row['plan_expires_at'] and datetime.fromisoformat(row['plan_expires_at']) <= utcnow():
        await asyncio.to_thread(_execute, "UPDATE users SET plan='free',plan_expires_at=NULL WHERE telegram_id=?", (tg_id,))
        row['plan'], row['plan_expires_at'] = 'free', None
    return row


async def update_user(tg_id: int, **fields):
    allowed = {'language','personality','verified','phone_hash','blocked','plan','plan_expires_at','voice_reply','voice_style','ai_mode','voice_language_mode'}
    fields = {k:v for k,v in fields.items() if k in allowed}
    if not fields: return
    sql = "UPDATE users SET " + ",".join(f"{k}=?" for k in fields) + " WHERE telegram_id=?"
    await asyncio.to_thread(_execute, sql, (*fields.values(), tg_id))


async def consume_quota(tg_id: int) -> tuple[bool,int,int]:
    user = await get_user(tg_id)
    if not user or user['blocked']: return False, 0, 0
    today = utcnow().date().isoformat()
    limit = {'free': settings.free_daily_limit, 'pro': settings.pro_daily_limit, 'vip': settings.vip_daily_limit}.get(user['plan'], settings.free_daily_limit)
    count = user['daily_count'] if user['daily_date'] == today else 0
    if count >= limit: return False, count, limit
    count += 1
    await asyncio.to_thread(_execute, "UPDATE users SET daily_count=?,daily_date=?,last_seen_at=? WHERE telegram_id=?", (count,today,utcnow().isoformat(),tg_id))
    return True, count, limit


async def reserve_video_quota(tg_id: int) -> tuple[bool, int, int]:
    def tx():
        today = utcnow().date().isoformat()
        with _conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT plan,blocked,video_daily_count,video_daily_date FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
            if not row or row['blocked']:
                return False, 0, 0
            limit = {'free': settings.free_video_daily_limit, 'pro': settings.pro_video_daily_limit, 'vip': settings.vip_video_daily_limit}.get(row['plan'], settings.free_video_daily_limit)
            count = row['video_daily_count'] if row['video_daily_date'] == today else 0
            if count >= limit:
                return False, count, limit
            count += 1
            c.execute("UPDATE users SET video_daily_count=?,video_daily_date=? WHERE telegram_id=?", (count,today,tg_id))
            return True, count, limit
    return await asyncio.to_thread(tx)


async def refund_video_quota(tg_id: int):
    today = utcnow().date().isoformat()
    await asyncio.to_thread(_execute, "UPDATE users SET video_daily_count=MAX(video_daily_count-1,0) WHERE telegram_id=? AND video_daily_date=?", (tg_id,today))


async def create_video_job(tg_id: int, task_id: str, task_type: str, status_message_id: int | None):
    now = utcnow().isoformat()
    await asyncio.to_thread(_execute, "INSERT INTO video_jobs(task_id,telegram_id,task_type,status,progress,status_message_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (task_id,tg_id,task_type,'queued',0,status_message_id,now,now))


async def get_video_job(task_id: str):
    return await asyncio.to_thread(_execute, "SELECT * FROM video_jobs WHERE task_id=?", (task_id,), True)


async def get_active_video_job(tg_id: int):
    return await asyncio.to_thread(_execute, "SELECT * FROM video_jobs WHERE telegram_id=? AND status IN ('queued','pending','running') ORDER BY created_at DESC LIMIT 1", (tg_id,), True)


async def list_active_video_jobs():
    return await asyncio.to_thread(_execute, "SELECT * FROM video_jobs WHERE status IN ('queued','pending','running') ORDER BY created_at", (), False, True)


async def update_video_job(task_id: str, completed: bool = False, **fields):
    allowed = {'status','progress','error','status_message_id'}
    values = {k:v for k,v in fields.items() if k in allowed}
    values['updated_at'] = utcnow().isoformat()
    if completed: values['completed_at'] = utcnow().isoformat()
    sql = "UPDATE video_jobs SET " + ",".join(f"{k}=?" for k in values) + " WHERE task_id=?"
    await asyncio.to_thread(_execute, sql, (*values.values(), task_id))


async def activate_plan(tg_id: int, plan: str, stars: int, tg_charge: str, provider_charge: str):
    expires = (utcnow() + timedelta(days=settings.subscription_days)).isoformat()
    def tx():
        with _conn() as c:
            c.execute("INSERT OR IGNORE INTO payments(telegram_id,plan,stars,telegram_charge_id,provider_charge_id,paid_at) VALUES(?,?,?,?,?,?)", (tg_id,plan,stars,tg_charge,provider_charge,utcnow().isoformat()))
            c.execute("UPDATE users SET plan=?,plan_expires_at=? WHERE telegram_id=?", (plan,expires,tg_id))
    await asyncio.to_thread(tx)


async def stats():
    def q():
        with _conn() as c:
            total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            verified = c.execute("SELECT COUNT(*) FROM users WHERE verified=1").fetchone()[0]
            paid = c.execute("SELECT COUNT(*) FROM users WHERE plan IN ('pro','vip')").fetchone()[0]
            stars = c.execute("SELECT COALESCE(SUM(stars),0) FROM payments").fetchone()[0]
            videos = c.execute("SELECT COUNT(*) FROM video_jobs WHERE status='completed'").fetchone()[0]
            images = c.execute("SELECT COUNT(*) FROM image_jobs WHERE status='completed'").fetchone()[0]
            referrals = c.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
            running = c.execute("SELECT COUNT(*) FROM video_jobs WHERE status IN ('queued','pending','running')").fetchone()[0]
            return {'users':total,'verified':verified,'paid':paid,'stars':stars,'videos':videos,'videos_running':running,'images':images,'referrals':referrals}
    return await asyncio.to_thread(q)


async def list_users(limit=100):
    return await asyncio.to_thread(_execute, "SELECT telegram_id,username,display_name,language,verified,plan,plan_expires_at,daily_count,daily_date,video_daily_count,video_daily_date,image_daily_count,image_daily_date,bonus_image_credits,blocked,created_at,last_seen_at FROM users ORDER BY last_seen_at DESC LIMIT ?", (limit,), False, True)


async def reserve_image_quota(tg_id: int) -> tuple[bool, int, int, bool]:
    def tx():
        today = utcnow().date().isoformat()
        with _conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT plan,blocked,image_daily_count,image_daily_date,bonus_image_credits FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
            if not row or row['blocked']:
                return False, 0, 0, False
            if row['bonus_image_credits'] > 0:
                c.execute("UPDATE users SET bonus_image_credits=bonus_image_credits-1 WHERE telegram_id=?", (tg_id,))
                return True, row['image_daily_count'], -1, True
            limit = {'free': settings.free_image_daily_limit, 'pro': settings.pro_image_daily_limit, 'vip': settings.vip_image_daily_limit}.get(row['plan'], settings.free_image_daily_limit)
            count = row['image_daily_count'] if row['image_daily_date'] == today else 0
            if count >= limit:
                return False, count, limit, False
            count += 1
            c.execute("UPDATE users SET image_daily_count=?,image_daily_date=? WHERE telegram_id=?", (count,today,tg_id))
            return True, count, limit, False
    return await asyncio.to_thread(tx)


async def refund_image_quota(tg_id: int, used_bonus: bool = False):
    if used_bonus:
        await asyncio.to_thread(_execute, "UPDATE users SET bonus_image_credits=bonus_image_credits+1 WHERE telegram_id=?", (tg_id,))
    else:
        today = utcnow().date().isoformat()
        await asyncio.to_thread(_execute, "UPDATE users SET image_daily_count=MAX(image_daily_count-1,0) WHERE telegram_id=? AND image_daily_date=?", (tg_id,today))


async def log_image_job(tg_id: int, model: str, status: str, error: str = ''):
    await asyncio.to_thread(_execute, "INSERT INTO image_jobs(telegram_id,model,status,error,created_at) VALUES(?,?,?,?,?)", (tg_id,model,status,error[:900],utcnow().isoformat()))


async def apply_referral(referred_id: int, referrer_id: int) -> bool:
    if referred_id == referrer_id:
        return False
    def tx():
        with _conn() as c:
            c.execute("BEGIN IMMEDIATE")
            if not c.execute("SELECT 1 FROM users WHERE telegram_id=?", (referrer_id,)).fetchone():
                return False
            if c.execute("SELECT 1 FROM referrals WHERE referred_id=?", (referred_id,)).fetchone():
                return False
            c.execute("INSERT INTO referrals(referred_id,referrer_id,created_at) VALUES(?,?,?)", (referred_id,referrer_id,utcnow().isoformat()))
            c.execute("UPDATE users SET bonus_image_credits=bonus_image_credits+? WHERE telegram_id=?", (settings.referral_inviter_bonus,referrer_id))
            c.execute("UPDATE users SET bonus_image_credits=bonus_image_credits+? WHERE telegram_id=?", (settings.referral_new_user_bonus,referred_id))
            return True
    return await asyncio.to_thread(tx)


async def referral_summary(tg_id: int):
    count = await asyncio.to_thread(_execute, "SELECT COUNT(*) AS n FROM referrals WHERE referrer_id=?", (tg_id,), True)
    user = await get_user(tg_id)
    return {'count': (count or {}).get('n',0), 'bonus': (user or {}).get('bonus_image_credits',0)}


async def create_coupon(code: str, plan: str, days: int, max_uses: int, image_bonus: int = 0):
    code = code.strip().upper()
    if not code or plan not in {'free','pro','vip'} or days < 0 or max_uses < 1 or image_bonus < 0:
        raise ValueError('Invalid coupon fields')
    await asyncio.to_thread(_execute, "INSERT OR REPLACE INTO coupons(code,plan,duration_days,image_bonus,max_uses,uses,active,created_at) VALUES(?,?,?,?,?,0,1,?)", (code,plan,days,image_bonus,max_uses,utcnow().isoformat()))


async def redeem_coupon(tg_id: int, code: str) -> tuple[bool, str]:
    code = code.strip().upper()
    def tx():
        with _conn() as c:
            c.execute("BEGIN IMMEDIATE")
            coupon = c.execute("SELECT * FROM coupons WHERE code=?", (code,)).fetchone()
            if not coupon or not coupon['active'] or coupon['uses'] >= coupon['max_uses']:
                return False, 'invalid'
            if c.execute("SELECT 1 FROM coupon_redemptions WHERE code=? AND telegram_id=?", (code,tg_id)).fetchone():
                return False, 'used'
            expires = None
            if coupon['plan'] != 'free' and coupon['duration_days'] > 0:
                expires = (utcnow() + timedelta(days=coupon['duration_days'])).isoformat()
                c.execute("UPDATE users SET plan=?,plan_expires_at=?,bonus_image_credits=bonus_image_credits+? WHERE telegram_id=?", (coupon['plan'],expires,coupon['image_bonus'],tg_id))
            else:
                c.execute("UPDATE users SET bonus_image_credits=bonus_image_credits+? WHERE telegram_id=?", (coupon['image_bonus'],tg_id))
            c.execute("INSERT INTO coupon_redemptions(code,telegram_id,redeemed_at) VALUES(?,?,?)", (code,tg_id,utcnow().isoformat()))
            c.execute("UPDATE coupons SET uses=uses+1 WHERE code=?", (code,))
            return True, f"{coupon['plan']}:{coupon['duration_days']}:{coupon['image_bonus']}"
    return await asyncio.to_thread(tx)


async def create_creator_job(tg_id: int, platform: str, duration: int) -> int:
    now = utcnow().isoformat()
    def insert():
        with _conn() as c:
            cur = c.execute("INSERT INTO creator_jobs(telegram_id,platform,duration,status,created_at,updated_at) VALUES(?,?,?,?,?,?)", (tg_id,platform,duration,"running",now,now))
            return int(cur.lastrowid)
    return await asyncio.to_thread(insert)


async def update_creator_job(job_id: int, status: str, error: str = "") -> None:
    await asyncio.to_thread(_execute, "UPDATE creator_jobs SET status=?,error=?,updated_at=? WHERE id=?", (status,error[:900],utcnow().isoformat(),job_id))


async def create_operation(telegram_id,kind,language=''):
    oid=uuid.uuid4().hex; now=utcnow().isoformat(); await asyncio.to_thread(_execute,"INSERT INTO operations(id,telegram_id,kind,status,stage,progress,generation_status,delivery_status,language,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(oid,telegram_id,kind,'running','queued',0,'pending','not_started',language,now,now)); return oid
async def update_operation(oid,**fields):
    allowed={'status','stage','progress','detail','generation_status','delivery_status','error_code','error','file_path','file_size','language','voice_profile','completed_at'}; v={k:x for k,x in fields.items() if k in allowed}; v['updated_at']=utcnow().isoformat()
    if v.get('status') in {'completed','failed','cancelled'}: v.setdefault('completed_at',utcnow().isoformat())
    await asyncio.to_thread(_execute,"UPDATE operations SET "+",".join(f"{k}=?" for k in v)+" WHERE id=?",(*v.values(),oid))
async def log_system_event(level,source,event,detail='',operation_id=None,telegram_id=None,metadata=None):
    await asyncio.to_thread(_execute,"INSERT INTO system_events(level,source,event,detail,operation_id,telegram_id,metadata,created_at) VALUES(?,?,?,?,?,?,?,?)",(level,source,event,detail[:2000],operation_id,telegram_id,json.dumps(metadata or {},ensure_ascii=False)[:6000],utcnow().isoformat()))
async def register_delivery(operation_id,telegram_id,kind,file_path,filename,caption,retention):
    did=uuid.uuid4().hex; now=utcnow(); exp=(now+timedelta(seconds=retention)).isoformat(); await asyncio.to_thread(_execute,"INSERT INTO deliveries(id,operation_id,telegram_id,kind,file_path,filename,caption,created_at,updated_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(did,operation_id,telegram_id,kind,file_path,filename,caption[:1000],now.isoformat(),now.isoformat(),exp)); return did
async def update_delivery(did,**fields):
    allowed={'status','attempts','error','telegram_message_id','file_path'};v={k:x for k,x in fields.items() if k in allowed};v['updated_at']=utcnow().isoformat();await asyncio.to_thread(_execute,"UPDATE deliveries SET "+",".join(f"{k}=?" for k in v)+" WHERE id=?",(*v.values(),did))
async def list_pending_deliveries(limit=20): return await asyncio.to_thread(_execute,"SELECT * FROM deliveries WHERE status IN ('pending','failed') AND expires_at>? ORDER BY updated_at LIMIT ?",(utcnow().isoformat(),limit),False,True)
async def list_recent_operations(limit=50): return await asyncio.to_thread(_execute,"SELECT * FROM operations ORDER BY updated_at DESC LIMIT ?",(limit,),False,True)
async def list_recent_events(limit=100): return await asyncio.to_thread(_execute,"SELECT * FROM system_events ORDER BY id DESC LIMIT ?",(limit,),False,True)
async def list_recent_deliveries(limit=50): return await asyncio.to_thread(_execute,"SELECT * FROM deliveries ORDER BY updated_at DESC LIMIT ?",(limit,),False,True)
async def dashboard_overview():
    def q():
        with _conn() as c:
            one=lambda sql:c.execute(sql).fetchone()[0]
            return {'operations_running':one("SELECT COUNT(*) FROM operations WHERE status='running'"),'operations_failed':one("SELECT COUNT(*) FROM operations WHERE status='failed'"),'deliveries_pending':one("SELECT COUNT(*) FROM deliveries WHERE status IN ('pending','failed')"),'errors':one("SELECT COUNT(*) FROM system_events WHERE level IN ('error','critical')")}
    return await asyncio.to_thread(q)
async def save_session_context(uid,key,kind,content,ttl):
    now=utcnow();exp=(now+timedelta(minutes=ttl)).isoformat();await asyncio.to_thread(_execute,"INSERT INTO session_context VALUES(?,?,?,?,?,?) ON CONFLICT(telegram_id,context_key) DO UPDATE SET content=excluded.content,expires_at=excluded.expires_at,updated_at=excluded.updated_at",(uid,key,kind,content[:60000],exp,now.isoformat()))
async def load_session_context(uid): return await asyncio.to_thread(_execute,"SELECT * FROM session_context WHERE telegram_id=? AND expires_at>? ORDER BY updated_at",(uid,utcnow().isoformat()),False,True)
async def clear_session_context(uid): await asyncio.to_thread(_execute,"DELETE FROM session_context WHERE telegram_id=?",(uid,))


async def claim_delivery(delivery_id: str) -> bool:
    changed = await asyncio.to_thread(_execute, "UPDATE deliveries SET status='sending',updated_at=? WHERE id=? AND status IN ('pending','failed')", (utcnow().isoformat(), delivery_id))
    return changed == 1
