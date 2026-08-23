#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     ربات پیام ناشناس تلگرام — نسخه حرفه‌ای ۳.۰ (telebot)   ║
╠══════════════════════════════════════════════════════════════╣
║  ✅ پنل ادمین کامل    ✅ سیستم VIP ⭐   ✅ ری‌اکشن 👍❤️😂  ║
║  ✅ فیلتر کلمات/لینک  ✅ DND Mode      ✅ سیستم رفرال      ║
║  ✅ یادداشت ادمین     ✅ ادمین داینامیک ✅ بلاک پیشرفته     ║
║  ✅ Broadcast+تأیید   ✅ جستجو ID/user  ✅ گزارش روزانه     ║
╚══════════════════════════════════════════════════════════════╝
pip install pyTelegramBotAPI
"""
import telebot
from telebot import types
import sqlite3, threading, hashlib, secrets, time, logging, csv, io, shutil, re
from datetime import datetime
from typing import Optional

# ─── CONFIG ──────────────────────────────────────────────────
TOKEN        = ""
BOT_USERNAME = "@Hhhhhhh88Adfffbot"
ROOT_ADMINS  = {467034986}
DB_PATH      = "anon_v3.db"

# ─── LOGGING ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(message)s", level=logging.INFO,
    handlers=[logging.FileHandler("bot_v3.log", encoding="utf-8"), logging.StreamHandler()])
log = logging.getLogger("AnonV3")
S_T = time.time()

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ─── FSM ─────────────────────────────────────────────────────
class S:
    IDLE="idle"; ANON="anon"; REPORT="report"
    BC_WAIT="bc"; BAN="ban"; SEARCH_ID="sid"; SEARCH_UN="sun"
    NOTE="note"; WORD_ADD="wa"; ADD_ADMIN="aa"; VIP="vip"
    SET_RL="rl"; SET_VRL="vrl"; SET_WELCOME="sw"

_states:dict={};_ctxd:dict={};_lk=threading.Lock()
def st_get(u):
    with _lk: return _states.get(u,S.IDLE)
def st_set(u,s,**kw):
    with _lk:
        _states[u]=s
        if kw: _ctxd.setdefault(u,{}).update(kw)
def st_ctx(u)->dict:
    with _lk: return dict(_ctxd.get(u,{}))
def st_clr(u):
    with _lk: _states.pop(u,None);_ctxd.pop(u,None)

# ─── DATABASE ────────────────────────────────────────────────
class Database:
    def __init__(self,p):
        self.path=p;self._lk=threading.Lock();self._boot()
    def _c(self):
        c=sqlite3.connect(self.path,check_same_thread=False)
        c.row_factory=sqlite3.Row;c.execute("PRAGMA journal_mode=WAL");return c
    def _boot(self):
        with self._c() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,username TEXT DEFAULT '',first_name TEXT DEFAULT '',
                token TEXT UNIQUE NOT NULL,is_banned INTEGER DEFAULT 0,ban_reason TEXT,
                banned_by INTEGER,banned_at REAL,is_vip INTEGER DEFAULT 0,vip_expires REAL,
                is_paused INTEGER DEFAULT 0,referrer_id INTEGER,
                created_at REAL NOT NULL,last_active REAL NOT NULL,
                msg_sent INTEGER DEFAULT 0,msg_received INTEGER DEFAULT 0,reputation INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY,added_by INTEGER,added_at REAL,is_root INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,sender_id INTEGER,receiver_id INTEGER,
                msg_type TEXT DEFAULT 'text',content_preview TEXT DEFAULT '',reply_to_id INTEGER,sent_at REAL);
            CREATE TABLE IF NOT EXISTS reactions(
                msg_id INTEGER,reactor_id INTEGER,emoji TEXT,added_at REAL,
                PRIMARY KEY(msg_id,reactor_id));
            CREATE TABLE IF NOT EXISTS reports(
                id INTEGER PRIMARY KEY AUTOINCREMENT,reporter_id INTEGER,message_id INTEGER,
                reason TEXT,status TEXT DEFAULT 'pending',reported_at REAL,
                resolved_by INTEGER,resolved_at REAL);
            CREATE TABLE IF NOT EXISTS rate_limits(user_id INTEGER,sent_at REAL);
            CREATE INDEX IF NOT EXISTS idx_rl ON rate_limits(user_id,sent_at);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE IF NOT EXISTS broadcasts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,admin_id INTEGER,preview TEXT,
                msg_type TEXT,target TEXT DEFAULT 'all',sent_ok INTEGER DEFAULT 0,failed INTEGER DEFAULT 0,sent_at REAL);
            CREATE TABLE IF NOT EXISTS blocks(blocker_id INTEGER,blocked_id INTEGER,blocked_at REAL,PRIMARY KEY(blocker_id,blocked_id));
            CREATE TABLE IF NOT EXISTS admin_notes(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,admin_id INTEGER,note TEXT,added_at REAL);
            CREATE TABLE IF NOT EXISTS word_filter(word TEXT PRIMARY KEY,added_by INTEGER,added_at REAL);
            CREATE TABLE IF NOT EXISTS referrals(referrer_id INTEGER,referred_id INTEGER UNIQUE,joined_at REAL);
            INSERT OR IGNORE INTO settings VALUES('maintenance','0');
            INSERT OR IGNORE INTO settings VALUES('rate_limit_count','10');
            INSERT OR IGNORE INTO settings VALUES('rate_limit_window','60');
            INSERT OR IGNORE INTO settings VALUES('vip_rate_count','50');
            INSERT OR IGNORE INTO settings VALUES('link_filter','1');
            INSERT OR IGNORE INTO settings VALUES('notify_reaction','1');
            INSERT OR IGNORE INTO settings VALUES('welcome_msg','به ربات پیام ناشناس خوش آمدید');
            """)
        log.info("DB v3 ready.")
    def _q(self,sql,p=()):
        with self._c() as c: return c.execute(sql,p).fetchall()
    def _q1(self,sql,p=()):
        with self._c() as c: return c.execute(sql,p).fetchone()
    def _ex(self,sql,p=()):
        with self._lk,self._c() as c: return c.execute(sql,p).lastrowid
    # ── Users ──
    def _tok(self,uid): return hashlib.sha256(f"{uid}:{secrets.token_hex(16)}:{time.time()}".encode()).hexdigest()[:24]
    def register(self,uid,uname,fname,ref=None):
        now=time.time()
        with self._lk,self._c() as c:
            row=c.execute("SELECT token FROM users WHERE user_id=?",(uid,)).fetchone()
            if row:
                c.execute("UPDATE users SET username=?,first_name=?,last_active=? WHERE user_id=?",(uname,fname,now,uid))
                return row["token"]
            tok=self._tok(uid)
            c.execute("INSERT INTO users(user_id,username,first_name,token,referrer_id,created_at,last_active) VALUES(?,?,?,?,?,?,?)",(uid,uname,fname,tok,ref,now,now))
            if ref and ref!=uid:
                try: c.execute("INSERT OR IGNORE INTO referrals VALUES(?,?,?)",(ref,uid,now))
                except: pass
            return tok
    def user(self,uid): return self._q1("SELECT * FROM users WHERE user_id=?",(uid,))
    def by_token(self,t): return self._q1("SELECT * FROM users WHERE token=?",(t,))
    def by_username(self,un): return self._q1("SELECT * FROM users WHERE LOWER(username)=LOWER(?)",(un.lstrip("@"),))
    def touch(self,uid): self._ex("UPDATE users SET last_active=? WHERE user_id=?",(time.time(),uid))
    def regen_token(self,uid):
        tok=self._tok(uid);self._ex("UPDATE users SET token=? WHERE user_id=?",(tok,uid));return tok
    def ban(self,uid,reason,by): self._ex("UPDATE users SET is_banned=1,ban_reason=?,banned_by=?,banned_at=? WHERE user_id=?",(reason,by,time.time(),uid))
    def unban(self,uid): self._ex("UPDATE users SET is_banned=0,ban_reason=NULL,banned_by=NULL,banned_at=NULL WHERE user_id=?",(uid,))
    def grant_vip(self,uid,days): self._ex("UPDATE users SET is_vip=1,vip_expires=? WHERE user_id=?",(time.time()+days*86400,uid))
    def revoke_vip(self,uid): self._ex("UPDATE users SET is_vip=0,vip_expires=NULL WHERE user_id=?",(uid,))
    def is_vip(self,uid):
        u=self.user(uid)
        if not u or not u["is_vip"]: return False
        if u["vip_expires"] and u["vip_expires"]<time.time(): self.revoke_vip(uid);return False
        return True
    def set_paused(self,uid,v): self._ex("UPDATE users SET is_paused=? WHERE user_id=?",(1 if v else 0,uid))
    def add_rep(self,uid,d): self._ex("UPDATE users SET reputation=reputation+? WHERE user_id=?",(d,uid))
    def ref_count(self,uid): r=self._q1("SELECT COUNT(*) FROM referrals WHERE referrer_id=?",(uid,));return r[0] if r else 0
    def users_page(self,page=0,per=8,flt="all"):
        w={"banned":"WHERE is_banned=1","vip":"WHERE is_vip=1","active":f"WHERE last_active>{time.time()-86400}"}.get(flt,"")
        with self._c() as c:
            tot=c.execute(f"SELECT COUNT(*) FROM users {w}").fetchone()[0]
            rows=c.execute(f"SELECT * FROM users {w} ORDER BY last_active DESC LIMIT ? OFFSET ?",(per,page*per)).fetchall()
        return list(rows),tot
    def all_ids(self,target="all"):
        if target=="active": return [r[0] for r in self._q("SELECT user_id FROM users WHERE is_banned=0 AND last_active>?",(time.time()-604800,))]
        if target=="vip": return [r[0] for r in self._q("SELECT user_id FROM users WHERE is_banned=0 AND is_vip=1")]
        return [r[0] for r in self._q("SELECT user_id FROM users WHERE is_banned=0")]
    def top_users(self,col="msg_sent",n=5): return self._q(f"SELECT user_id,first_name,{col} v FROM users WHERE is_banned=0 ORDER BY {col} DESC LIMIT ?",(n,))
    # ── Admins ──
    def is_admin(self,uid): return uid in ROOT_ADMINS or self._q1("SELECT 1 FROM admins WHERE user_id=?",(uid,)) is not None
    def add_admin(self,uid,by): self._ex("INSERT OR IGNORE INTO admins VALUES(?,?,?,0)",(uid,by,time.time()))
    def del_admin(self,uid):
        if uid in ROOT_ADMINS: return False
        self._ex("DELETE FROM admins WHERE user_id=?",(uid,));return True
    def list_admins(self): return self._q("SELECT a.*,u.first_name fname,u.username uname FROM admins a LEFT JOIN users u ON a.user_id=u.user_id ORDER BY a.added_at")
    # ── Messages ──
    def log_msg(self,sndr,rcvr,mt,prev=""):
        with self._lk,self._c() as c:
            cur=c.execute("INSERT INTO messages(sender_id,receiver_id,msg_type,content_preview,sent_at) VALUES(?,?,?,?,?)",(sndr,rcvr,mt,prev[:60],time.time()))
            c.execute("UPDATE users SET msg_sent=msg_sent+1 WHERE user_id=?",(sndr,))
            c.execute("UPDATE users SET msg_received=msg_received+1 WHERE user_id=?",(rcvr,))
            return cur.lastrowid
    def recent_msgs(self,n=15): return self._q("SELECT m.*,s.first_name sn,r.first_name rn FROM messages m LEFT JOIN users s ON m.sender_id=s.user_id LEFT JOIN users r ON m.receiver_id=r.user_id ORDER BY m.sent_at DESC LIMIT ?",(n,))
    # ── Reactions ──
    def react(self,mid,uid,emoji):
        REP={"👍":1,"❤️":2,"😂":1,"😮":1,"👎":-1}
        with self._lk,self._c() as c:
            old=c.execute("SELECT emoji FROM reactions WHERE msg_id=? AND reactor_id=?",(mid,uid)).fetchone()
            if old and old["emoji"]==emoji:
                c.execute("DELETE FROM reactions WHERE msg_id=? AND reactor_id=?",(mid,uid))
                return old["emoji"],-REP.get(emoji,0)
            if old:
                d=REP.get(emoji,0)-REP.get(old["emoji"],0)
                c.execute("UPDATE reactions SET emoji=?,added_at=? WHERE msg_id=? AND reactor_id=?",(emoji,time.time(),mid,uid))
                return old["emoji"],d
            c.execute("INSERT INTO reactions VALUES(?,?,?,?)",(mid,uid,emoji,time.time()))
            return None,REP.get(emoji,0)
    def rcounts(self,mid): return {r["emoji"]:r["cnt"] for r in self._q("SELECT emoji,COUNT(*) cnt FROM reactions WHERE msg_id=? GROUP BY emoji",(mid,))}
    # ── Rate limit ──
    def rate_ok(self,uid):
        v=self.is_vip(uid)
        lim=int(self.cfg("vip_rate_count" if v else "rate_limit_count") or (50 if v else 10))
        win=float(self.cfg("rate_limit_window") or 60);cut=time.time()-win
        with self._lk,self._c() as c:
            c.execute("DELETE FROM rate_limits WHERE sent_at<?",(cut,))
            cnt=c.execute("SELECT COUNT(*) FROM rate_limits WHERE user_id=? AND sent_at>=?",(uid,cut)).fetchone()[0]
            if cnt>=lim: return False
            c.execute("INSERT INTO rate_limits VALUES(?,?)",(uid,time.time()));return True
    # ── Reports ──
    def add_report(self,rep,mid,reason): return self._ex("INSERT INTO reports(reporter_id,message_id,reason,reported_at) VALUES(?,?,?,?)",(rep,mid,reason,time.time()))
    def reports(self,status="pending"): return self._q("SELECT * FROM reports WHERE status=? ORDER BY reported_at DESC",(status,))
    def get_report(self,rid): return self._q1("SELECT * FROM reports WHERE id=?",(rid,))
    def resolve(self,rid,by): self._ex("UPDATE reports SET status='resolved',resolved_by=?,resolved_at=? WHERE id=?",(by,time.time(),rid))
    # ── Blocks ──
    def block(self,a,b): self._ex("INSERT OR IGNORE INTO blocks VALUES(?,?,?)",(a,b,time.time()))
    def unblock(self,a,b): self._ex("DELETE FROM blocks WHERE blocker_id=? AND blocked_id=?",(a,b))
    def is_blocked(self,a,b): return self._q1("SELECT 1 FROM blocks WHERE blocker_id=? AND blocked_id=?",(a,b)) is not None
    def my_blocks(self,uid): return self._q("SELECT b.*,u.first_name fn FROM blocks b LEFT JOIN users u ON b.blocked_id=u.user_id WHERE b.blocker_id=?",(uid,))
    # ── Notes ──
    def add_note(self,uid,admin,note): return self._ex("INSERT INTO admin_notes(user_id,admin_id,note,added_at) VALUES(?,?,?,?)",(uid,admin,note,time.time()))
    def get_notes(self,uid): return self._q("SELECT * FROM admin_notes WHERE user_id=? ORDER BY added_at DESC",(uid,))
    # ── Word filter ──
    def filter_words(self): return {r["word"] for r in self._q("SELECT word FROM word_filter")}
    def add_word(self,word,by): self._ex("INSERT OR IGNORE INTO word_filter VALUES(?,?,?)",(word.lower(),by,time.time()))
    def del_word(self,word): self._ex("DELETE FROM word_filter WHERE word=?",(word.lower(),))
    def list_words(self): return self._q("SELECT * FROM word_filter ORDER BY added_at DESC")
    # ── Settings ──
    def cfg(self,key): r=self._q1("SELECT value FROM settings WHERE key=?",(key,));return r["value"] if r else None
    def set_cfg(self,key,val): self._ex("INSERT OR REPLACE INTO settings VALUES(?,?)",(key,val))
    # ── Broadcasts ──
    def log_bc(self,aid,prev,mt,tgt,ok,fail): self._ex("INSERT INTO broadcasts(admin_id,preview,msg_type,target,sent_ok,failed,sent_at) VALUES(?,?,?,?,?,?,?)",(aid,prev,mt,tgt,ok,fail,time.time()))
    def bc_hist(self,n=8): return self._q("SELECT * FROM broadcasts ORDER BY sent_at DESC LIMIT ?",(n,))
    # ── Stats ──
    def stats(self):
        d=time.time()-86400;w=time.time()-604800
        with self._c() as c:
            return {k:c.execute(v[0],v[1] if len(v)>1 else ()).fetchone()[0] for k,v in {
                "users":["SELECT COUNT(*) FROM users"],"new_today":[f"SELECT COUNT(*) FROM users WHERE created_at>{d}"],
                "active":[f"SELECT COUNT(*) FROM users WHERE last_active>{d}"],"banned":["SELECT COUNT(*) FROM users WHERE is_banned=1"],
                "vip":["SELECT COUNT(*) FROM users WHERE is_vip=1"],"paused":["SELECT COUNT(*) FROM users WHERE is_paused=1"],
                "msgs":["SELECT COUNT(*) FROM messages"],f"msgs_day":[f"SELECT COUNT(*) FROM messages WHERE sent_at>{d}"],
                "msgs_week":[f"SELECT COUNT(*) FROM messages WHERE sent_at>{w}"],
                "reports":["SELECT COUNT(*) FROM reports WHERE status='pending'"],
                "reactions":["SELECT COUNT(*) FROM reactions"],"referrals":["SELECT COUNT(*) FROM referrals"],
                "words":["SELECT COUNT(*) FROM word_filter"],"admins":["SELECT COUNT(*) FROM admins"]}.items()}
    # ── Export ──
    def export_csv(self):
        rows=self._q("SELECT user_id,username,first_name,is_banned,is_vip,reputation,msg_sent,msg_received,created_at,last_active FROM users ORDER BY created_at DESC")
        buf=io.StringIO();w=csv.writer(buf)
        w.writerow(["ID","Username","Name","Banned","VIP","Rep","Sent","Recv","Joined","LastActive"])
        for r in rows: w.writerow([r["user_id"],r["username"],r["first_name"],"yes"if r["is_banned"]else"no","yes"if r["is_vip"]else"no",r["reputation"],r["msg_sent"],r["msg_received"],ft(r["created_at"]),ft(r["last_active"])])
        return buf.getvalue().encode("utf-8-sig")

db=Database(DB_PATH)

# ─── HELPERS ─────────────────────────────────────────────────
def ft(ts): return datetime.fromtimestamp(ts).strftime("%y/%m/%d %H:%M")
def uptime():
    s=int(time.time()-S_T);d,s=divmod(s,86400);h,s=divmod(s,3600);m=s//60
    return f"{d}روز {h}ساعت {m}دق"
def alink(tok): return f"https://t.me/{BOT_USERNAME}?start={tok}"
def rlink(tok): return f"https://t.me/{BOT_USERNAME}?start=ref_{tok}"
def vbadge(uid): return " ⭐" if db.is_vip(uid) else ""
def filtered(text):
    if not text: return False
    wds=db.filter_words()
    if any(w in text.lower() for w in wds): return True
    if db.cfg("link_filter")=="1" and re.search(r"(https?://|t\.me/|@\w{5,})",text): return True
    return False

# ─── KEYBOARDS ───────────────────────────────────────────────
def ik(*rows):
    kb=types.InlineKeyboardMarkup()
    for row in rows: kb.add(*[types.InlineKeyboardButton(t,callback_data=d) for t,d in row])
    return kb

def kb_user(uid):
    u=db.user(uid);paused=u["is_paused"] if u else 0
    return ik(
        [("🔗 لینک ناشناس","u:link"),("🔄 لینک جدید","u:newlink")],
        [("📊 آمار من","u:stats"),("🎁 رفرال","u:ref")],
        [("🚫 بلاک‌هایم","u:blocks"),("⏸ DND" if not paused else "▶️ ادامه","u:pause")],
        [("❓ راهنما","u:help")])

def kb_rxn(mid,sndr,cnt=None):
    cnt=cnt or {}
    kb=types.InlineKeyboardMarkup(row_width=5)
    emojis=["👍","❤️","😂","😮","👎"]
    kb.add(*[types.InlineKeyboardButton(f"{e}{cnt[e]}" if cnt.get(e) else e,callback_data=f"rx:{mid}:{sndr}:{e}") for e in emojis])
    kb.add(types.InlineKeyboardButton("↩️ پاسخ",callback_data=f"rpl:{sndr}"),
           types.InlineKeyboardButton("🚫 بلاک",callback_data=f"blk:{sndr}"),
           types.InlineKeyboardButton("🚨 گزارش",callback_data=f"rep:{mid}"))
    return kb

def kb_admin():
    return ik(
        [("📊 آمار","a:stats"),("📈 آمار پیشرفته","a:adv")],
        [("👥 کاربران","a:ul:0"),("⭐ VIP‌ها","a:vl:0")],
        [("🚫 مسدودی‌ها","a:bl:0"),("📋 گزارش‌ها","a:reps")],
        [("📢 ارسال همگانی","a:bc"),("📝 لاگ پیام","a:logs")],
        [("🔍 جستجو ID","a:sid"),("🔍 جستجو یوزر","a:sun")],
        [("🔞 فیلتر کلمات","a:wf"),("👑 ادمین‌ها","a:admins")],
        [("📡 تاریخچه BC","a:bch"),("⚙️ تنظیمات","a:cfg")],
        [("💾 پشتیبان","a:backup"),("📤 CSV","a:csv")])

def kb_back(d="a:main",lbl="↩️ بازگشت"): return ik([(lbl,d)])

def kb_profile(uid,banned,vip):
    return ik(
        [("✅ آنبن" if banned else "🚫 بن",f"a:unban:{uid}" if banned else f"a:ban:{uid}"),
         ("❌ لغو VIP" if vip else "⭐ VIP",f"a:rvip:{uid}" if vip else f"a:gvip:{uid}")],
        [("📝 یادداشت",f"a:note:{uid}"),("📋 یادداشت‌ها",f"a:notes:{uid}")],
        [("↩️ بازگشت","a:main")])

def kb_pager(page,tot,cmd,per=8):
    pages=max(1,(tot-1)//per+1);nav=[]
    if page>0: nav.append(("◀️",f"a:{cmd}:{page-1}"))
    nav.append((f"{page+1}/{pages}","noop"))
    if (page+1)*per<tot: nav.append(("▶️",f"a:{cmd}:{page+1}"))
    return ik(nav,[("↩️ بازگشت","a:main")])

def kb_cfg():
    m=db.cfg("maintenance")=="1"; lf=db.cfg("link_filter")=="1"; nr=db.cfg("notify_reaction")=="1"
    rl=db.cfg("rate_limit_count") or "10"; rw=db.cfg("rate_limit_window") or "60"; vr=db.cfg("vip_rate_count") or "50"
    return ik(
        [("🔴 تعمیر فعال" if m else "🟢 تعمیر غیرفعال","a:cm:0" if m else "a:cm:1")],
        [("🔗 فیلتر لینک: "+"✅" if lf else "🔗 فیلتر لینک: ❌","a:clf:0" if lf else "a:clf:1")],
        [("🔔 اعلان ری‌اکشن: "+"✅" if nr else "🔔 اعلان ری‌اکشن: ❌","a:cnr:0" if nr else "a:cnr:1")],
        [(f"⏱ عادی: {rl}/{rw}s","a:crl"),(f"⭐ VIP: {vr}/{rw}s","a:cvrl")],
        [("💬 پیام خوش‌آمد","a:cw")],
        [("↩️ بازگشت","a:main")])

def kb_bc_target():
    return ik([("📡 همه کاربران","a:bc:all")],[("🟢 فعال ۷ روز","a:bc:active")],[("⭐ فقط VIP","a:bc:vip")],[("❌ لغو","a:main")])

def kb_blocks(uid):
    bls=db.my_blocks(uid)[:10]
    rows=[[f"🔓 {r['fn'] or r['blocked_id']}",f"ub:{r['blocked_id']}"] for r in bls]
    return ik(*[[r] for r in rows],[("↩️ بازگشت","u:back")])

def kb_admins(admins):
    rows=[[f"👤 {r['fname'] or r['user_id']}",f"a:admd:{r['user_id']}"] for r in admins]
    return ik(*[[r] for r in rows],[("➕ افزودن","a:adda")],[("↩️ بازگشت","a:main")])

def kb_reps(reps):
    rows=[[f"📋 #{r['id']} — {ft(r['reported_at'])}",f"a:rep:{r['id']}"] for r in reps[:10]]
    return ik(*[[r] for r in rows],[("↩️ بازگشت","a:main")])

# ─── DELIVERY ────────────────────────────────────────────────
MEDIA=["text","photo","video","voice","audio","document","sticker","video_note","animation"]

def deliver(target,sender,msg):
    h="📩 *پیام ناشناس:*\n\n";mt="text";prev=""
    ct=msg.content_type
    if ct=="text":
        txt=msg.text or ""
        if filtered(txt): raise ValueError("filtered")
        bot.send_message(target,h+txt)
        mt="text";prev=txt[:60]
    elif ct=="photo":
        cap=msg.caption or ""
        if filtered(cap): raise ValueError("filtered")
        bot.send_photo(target,msg.photo[-1].file_id,caption=(h+cap).strip() or h.strip())
        mt="photo";prev=cap[:60]
    elif ct=="video":
        cap=msg.caption or ""
        if filtered(cap): raise ValueError("filtered")
        bot.send_video(target,msg.video.file_id,caption=(h+cap).strip() or h.strip())
        mt="video";prev=cap[:60]
    elif ct=="voice":
        bot.send_message(target,h.strip());bot.send_voice(target,msg.voice.file_id);mt="voice"
    elif ct=="audio":
        cap=msg.caption or ""
        bot.send_audio(target,msg.audio.file_id,caption=(h+cap).strip() or h.strip());mt="audio"
    elif ct=="document":
        cap=msg.caption or ""
        if filtered(cap): raise ValueError("filtered")
        bot.send_document(target,msg.document.file_id,caption=(h+cap).strip() or h.strip())
        mt="document";prev=cap[:60]
    elif ct=="sticker":
        bot.send_message(target,h.strip());bot.send_sticker(target,msg.sticker.file_id);mt="sticker"
    elif ct=="video_note":
        bot.send_message(target,h.strip());bot.send_video_note(target,msg.video_note.file_id);mt="video_note"
    elif ct=="animation":
        cap=msg.caption or ""
        bot.send_animation(target,msg.animation.file_id,caption=(h+cap).strip() or h.strip());mt="animation"
    else:
        raise ValueError("unsupported")
    mid=db.log_msg(sender,target,mt,prev)
    bot.send_message(target,"↩️ واکنش یا پاسخ:",reply_markup=kb_rxn(mid,sender))
    return mid

# ─── USER COMMANDS ───────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    uid=msg.from_user.id
    args=msg.text.split()[1:]
    if db.cfg("maintenance")=="1" and not db.is_admin(uid):
        bot.reply_to(msg,"🔧 ربات در حال تعمیر است.");return
    ref=None;arg=args[0] if args else ""
    if arg.startswith("ref_"):
        ru=db.by_token(arg[4:])
        if ru and ru["user_id"]!=uid: ref=ru["user_id"]
    tok=db.register(uid,msg.from_user.username or "",msg.from_user.first_name or "کاربر",ref)
    db.touch(uid);u=db.user(uid)
    if u["is_banned"]:
        bot.reply_to(msg,f"⛔ *حساب شما مسدود شده*\n📌 {u['ban_reason'] or '—'}");return
    if arg and not arg.startswith("ref_"):
        tu=db.by_token(arg)
        if not tu: bot.reply_to(msg,"❌ لینک نامعتبر.");return
        if tu["user_id"]==uid: bot.reply_to(msg,"😅 نمی‌توانید به خودتان پیام بفرستید!");return
        if tu["is_banned"]: bot.reply_to(msg,"❌ کاربر در دسترس نیست.");return
        if tu["is_paused"]: bot.reply_to(msg,"⏸ این کاربر موقتاً پیام نمی‌گیرد.");return
        st_set(uid,S.ANON,target=tu["user_id"])
        bot.reply_to(msg,"✉️ *حالت پیام ناشناس فعال شد*\n\nپیام، عکس، ویدیو... بفرستید.\n🔒 هویت شما مخفی است.\n\n❌ /cancel");return
    if ref: bot.reply_to(msg,"🎉 از طریق دعوت یک دوست عضو شدید!")
    w=db.cfg("welcome_msg") or "سلام!"
    bot.reply_to(msg,f"{w}\n\n👋 *{msg.from_user.first_name}{vbadge(uid)}*\n\n🔗 لینک ناشناس:\n`{alink(tok)}`",reply_markup=kb_user(uid))

@bot.message_handler(commands=["mylink"])
def cmd_mylink(msg):
    uid=msg.from_user.id;u=db.user(uid)
    if not u: return cmd_start(msg)
    bot.reply_to(msg,f"🔗 *لینک ناشناس:*\n\n`{alink(u['token'])}`")

@bot.message_handler(commands=["newlink"])
def cmd_newlink(msg):
    uid=msg.from_user.id
    if not db.user(uid): return cmd_start(msg)
    tok=db.regen_token(uid)
    bot.reply_to(msg,f"✅ *لینک جدید:*\n\n`{alink(tok)}`\n\n⚠️ لینک قبلی حذف شد.")

@bot.message_handler(commands=["cancel"])
def cmd_cancel(msg): st_clr(msg.from_user.id);bot.reply_to(msg,"❌ لغو شد.")

@bot.message_handler(commands=["pause"])
def cmd_pause(msg):
    uid=msg.from_user.id;u=db.user(uid)
    if not u: return
    v=not u["is_paused"];db.set_paused(uid,v)
    bot.reply_to(msg,"⏸ DND فعال — دیگر پیام دریافت نمی‌کنید." if v else "▶️ DND غیرفعال شد.")

@bot.message_handler(commands=["report"])
def cmd_report(msg):
    uid=msg.from_user.id;mid=st_ctx(uid).get("last_msg_id")
    if not mid: bot.reply_to(msg,"ابتدا پیام ناشناس دریافت کنید.");return
    st_set(uid,S.REPORT,rmid=mid)
    bot.reply_to(msg,"📋 دلیل گزارش را بنویسید:\n❌ /cancel")

@bot.message_handler(commands=["admin"])
def cmd_admin(msg):
    uid=msg.from_user.id
    if not db.is_admin(uid): bot.reply_to(msg,"⛔ دسترسی ممنوع.");return
    s=db.stats()
    bot.reply_to(msg,f"🎛️ *پنل مدیریت*\n\n👥`{s['users']:,}` 🟢`{s['active']:,}` ⭐`{s['vip']:,}`\n📩`{s['msgs']:,}` امروز:`{s['msgs_day']:,}`\n⏱ `{uptime()}`",reply_markup=kb_admin())

@bot.message_handler(commands=["backup"])
def cmd_backup(msg):
    if not db.is_admin(msg.from_user.id): return
    try:
        bp=f"/tmp/bk_{int(time.time())}.db";shutil.copy2(DB_PATH,bp)
        with open(bp,"rb") as f: bot.send_document(msg.chat.id,f,caption="💾 پشتیبان دیتابیس",visible_file_name=f"anon_{datetime.now():%Y%m%d}.db")
        import os;os.remove(bp)
    except Exception as e: bot.reply_to(msg,f"❌ خطا: {e}")

@bot.message_handler(commands=["export"])
def cmd_export(msg):
    if not db.is_admin(msg.from_user.id): return
    bot.send_document(msg.chat.id,io.BytesIO(db.export_csv()),caption="📊 خروجی کاربران",visible_file_name=f"users_{datetime.now():%Y%m%d}.csv")

# ─── MESSAGE ROUTER ──────────────────────────────────────────
@bot.message_handler(content_types=MEDIA)
def router(msg):
    uid=msg.from_user.id;state=st_get(uid)
    if db.cfg("maintenance")=="1" and not db.is_admin(uid): bot.reply_to(msg,"🔧 ربات در تعمیر است.");return
    if not db.user(uid): return cmd_start(msg)
    u=db.user(uid)
    if u["is_banned"]: bot.reply_to(msg,"⛔ حساب شما مسدود است.");return
    db.touch(uid)
    # Admin input
    if db.is_admin(uid) and state not in (S.IDLE,S.ANON,S.REPORT):
        _adm_input(msg,state);return
    # Report
    if state==S.REPORT:
        reason=msg.text or "بدون متن";rmid=st_ctx(uid).get("rmid");st_clr(uid)
        rid=db.add_report(uid,rmid,reason)
        bot.reply_to(msg,f"✅ گزارش #{rid} ثبت شد.")
        for aid in ROOT_ADMINS:
            try: bot.send_message(aid,f"🚨 *گزارش #{rid}*\n👤 از: `{uid}`\n📌 {reason}")
            except: pass
        return
    # Anon send
    if state==S.ANON:
        ctx=st_ctx(uid);tid=ctx.get("target")
        if not tid: st_clr(uid);bot.reply_to(msg,"خطا. دوباره از لینک وارد شوید.");return
        if db.is_blocked(tid,uid): bot.reply_to(msg,"❌ این کاربر شما را بلاک کرده.");return
        tu=db.user(tid)
        if tu and tu["is_paused"]: bot.reply_to(msg,"⏸ این کاربر موقتاً پیام نمی‌گیرد.");return
        if not db.rate_ok(uid):
            w=db.cfg("rate_limit_window") or "60"
            bot.reply_to(msg,f"⏳ سرعت ارسال بالاست. {w} ثانیه صبر کنید.");return
        try:
            mid=deliver(tid,uid,msg)
            st_set(uid,S.ANON,last_msg_id=mid,target=tid)
            bot.reply_to(msg,"✅ پیام ناشناس ارسال شد! ادامه دهید یا /cancel")
            log.info(f"[{msg.content_type}] {uid}→{tid}")
        except ValueError as e:
            if str(e)=="filtered": bot.reply_to(msg,"🚫 پیام شما حاوی محتوای فیلترشده است.")
            elif str(e)=="unsupported": bot.reply_to(msg,"❌ این نوع محتوا پشتیبانی نمی‌شود.")
        except Exception as e:
            err=str(e).lower()
            if any(x in err for x in ["blocked","not found","deactivated"]): bot.reply_to(msg,"❌ این کاربر ربات را بلاک کرده.")
            else: bot.reply_to(msg,"❌ خطا در ارسال.");log.error(f"deliver err: {e}")
        return
    # Default
    u2=db.user(uid)
    bot.reply_to(msg,f"🏠 *منوی اصلی*\n\n🔗 لینک:\n`{alink(u2['token'])}`",reply_markup=kb_user(uid))

# ─── ADMIN INPUT ─────────────────────────────────────────────
def _adm_input(msg,state):
    uid=msg.from_user.id;txt=(msg.text or "").strip()
    if state==S.BC_WAIT:
        ctx=st_ctx(uid);tgt=ctx.get("bc_target","all");cnt=len(db.all_ids(tgt))
        st_set(uid,"bc_confirm",bc_target=tgt,bc_cid=msg.chat.id,bc_mid=msg.message_id,bc_type=msg.content_type,bc_prev=(msg.text or msg.caption or "رسانه")[:80])
        bot.reply_to(msg,f"📢 *پیش‌نمایش ارسال همگانی*\n\n📋 نوع: {msg.content_type}\n👥 هدف: {tgt} ({cnt:,} نفر)\n📝 {(msg.text or msg.caption or 'رسانه')[:60]}\n\nآیا ارسال شود؟",
            reply_markup=ik([("✅ ارسال کن","a:bcgo"),("❌ لغو","a:main")]))
        return
    if state==S.BAN:
        ctx=st_ctx(uid);tid=ctx.get("ban_target");reason=txt or "بدون دلیل";st_clr(uid)
        if not tid: bot.reply_to(msg,"خطا.");return
        db.ban(tid,reason,uid)
        bot.reply_to(msg,f"✅ کاربر `{tid}` مسدود شد.\n📌 {reason}",reply_markup=kb_back())
        try: bot.send_message(tid,f"⛔ حساب شما مسدود شد.\n📌 دلیل: {reason}")
        except: pass
        return
    if state==S.SEARCH_ID:
        st_clr(uid)
        if not txt.isdigit(): bot.reply_to(msg,"❌ آیدی باید عدد باشد.",reply_markup=kb_back());return
        _show_profile(msg.chat.id,int(txt));return
    if state==S.SEARCH_UN:
        st_clr(uid);u2=db.by_username(txt)
        if not u2: bot.reply_to(msg,f"❌ کاربر @{txt} یافت نشد.",reply_markup=kb_back());return
        _show_profile(msg.chat.id,u2["user_id"]);return
    if state==S.NOTE:
        ctx=st_ctx(uid);tid=ctx.get("note_target");st_clr(uid)
        db.add_note(tid,uid,txt)
        bot.reply_to(msg,"✅ یادداشت ثبت شد.",reply_markup=kb_back());return
    if state==S.WORD_ADD:
        st_clr(uid);words=[w.strip().lower() for w in txt.split(",") if w.strip()]
        for w in words: db.add_word(w,uid)
        bot.reply_to(msg,f"✅ {len(words)} کلمه اضافه شد:\n"+"، ".join(words),reply_markup=kb_back());return
    if state==S.ADD_ADMIN:
        st_clr(uid)
        if not txt.isdigit(): bot.reply_to(msg,"❌ آیدی باید عدد باشد.");return
        db.add_admin(int(txt),uid)
        bot.reply_to(msg,f"✅ ادمین `{txt}` اضافه شد.")
        try: bot.send_message(int(txt),"👑 شما به ادمین‌های ربات اضافه شدید!")
        except: pass
        return
    if state==S.VIP:
        ctx=st_ctx(uid);tid=ctx.get("vip_target");st_clr(uid)
        if not txt.isdigit(): bot.reply_to(msg,"❌ تعداد روز باید عدد باشد.");return
        db.grant_vip(tid,int(txt))
        bot.reply_to(msg,f"⭐ VIP برای {txt} روز به `{tid}` اعطا شد.",reply_markup=kb_back())
        try: bot.send_message(tid,f"⭐ تبریک! دسترسی VIP برای {txt} روز فعال شد!")
        except: pass
        return
    if state==S.SET_RL:
        st_clr(uid);parts=txt.split(":")
        if len(parts)==2 and all(p.isdigit() for p in parts):
            db.set_cfg("rate_limit_count",parts[0]);db.set_cfg("rate_limit_window",parts[1])
            bot.reply_to(msg,f"✅ نرخ عادی: {parts[0]}/{parts[1]}s",reply_markup=kb_back())
        else: bot.reply_to(msg,"فرمت نادرست. مثال: `10:60`")
        return
    if state==S.SET_VRL:
        st_clr(uid)
        if txt.isdigit(): db.set_cfg("vip_rate_count",txt);bot.reply_to(msg,f"✅ نرخ VIP: {txt}",reply_markup=kb_back())
        else: bot.reply_to(msg,"فرمت نادرست. مثال: `50`")
        return
    if state==S.SET_WELCOME:
        st_clr(uid);db.set_cfg("welcome_msg",txt)
        bot.reply_to(msg,"✅ پیام خوش‌آمد بروز شد.",reply_markup=kb_back());return

def _show_profile(cid,uid):
    u=db.user(uid)
    if not u: bot.send_message(cid,f"❌ کاربر `{uid}` یافت نشد.");return
    st="🚫 مسدود" if u["is_banned"] else "✅ فعال"
    vp=f"\n🕐 انقضا VIP: {ft(u['vip_expires'])}" if u["is_vip"] and u["vip_expires"] else ""
    notes=db.get_notes(uid)
    txt=(f"👤 *پروفایل کاربر*\n\n🆔 `{u['user_id']}`{vbadge(uid)}\n"
         f"👤 {u['first_name'] or '—'} (@{u['username'] or '—'})\n"
         f"📊 {st} {'⏸DND' if u['is_paused'] else ''}\n"
         f"⭐ رپوتیشن: {u['reputation']:+}\n"
         f"📤 ارسالی: {u['msg_sent']:,} | 📥 دریافتی: {u['msg_received']:,}\n"
         f"👫 رفرال: {db.ref_count(uid)}\n"
         f"📅 عضویت: {ft(u['created_at'])}\n"
         f"🕐 آخرین فعالیت: {ft(u['last_active'])}{vp}")
    if u["is_banned"]: txt+=f"\n⛔ دلیل بن: {u['ban_reason'] or '—'}"
    if notes: txt+=f"\n📝 یادداشت: {len(notes)} مورد"
    bot.send_message(cid,txt,reply_markup=kb_profile(uid,bool(u["is_banned"]),bool(u["is_vip"])))

# ─── CALLBACK HANDLER ────────────────────────────────────────
def edit(cid,mid,txt,kb=None):
    try: bot.edit_message_text(txt,cid,mid,reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c:True)
def cb(call):
    uid=call.from_user.id;cid=call.message.chat.id;mid=call.message.message_id;d=call.data
    bot.answer_callback_query(call.id)
    if d=="noop": return

    # ── Reaction ──
    if d.startswith("rx:"):
        p=d.split(":");msg_db=int(p[1]);sndr=int(p[2]);emoji=p[3]
        prev,delta=db.react(msg_db,uid,emoji)
        if delta!=0:
            db.add_rep(sndr,delta)
            if delta>0 and db.cfg("notify_reaction")=="1":
                em={"👍":"😊+1","❤️":"💖+2","😂":"😄+1","😮":"😮+1"}
                try: bot.send_message(sndr,f"🔔 کسی به پیام شما واکنش داد: {emoji} ({em.get(emoji,'')})")
                except: pass
        cnt=db.rcounts(msg_db)
        try: bot.edit_message_reply_markup(cid,mid,reply_markup=kb_rxn(msg_db,sndr,cnt))
        except: pass
        bot.answer_callback_query(call.id,f"{emoji} ثبت شد!")
        return

    # ── Reply ──
    if d.startswith("rpl:"):
        orig=int(d[4:])
        if db.user(uid) and db.user(uid)["is_banned"]: return
        st_set(uid,S.ANON,target=orig)
        bot.send_message(cid,"↩️ *پاسخ ناشناس فعال شد*\nپیام بفرستید. /cancel برای لغو")
        return

    # ── Block ──
    if d.startswith("blk:"):
        sndr=int(d[4:]);db.block(uid,sndr)
        try:
            bot.edit_message_reply_markup(cid,mid,reply_markup=ik(
                [("↩️ پاسخ",f"rpl:{sndr}"),("✅ بلاک شد","noop"),("🚨 گزارش",f"rep:0")]))
        except: pass
        bot.answer_callback_query(call.id,"🚫 بلاک شد.",show_alert=True)
        return

    # ── Report button ──
    if d.startswith("rep:"):
        p=d.split(":");msg_db=int(p[1]) if len(p)>1 else 0
        st_set(uid,S.REPORT,rmid=msg_db)
        bot.send_message(cid,"📋 دلیل گزارش را بنویسید:\n❌ /cancel")
        return

    # ── Unblock ──
    if d.startswith("ub:"):
        bid=int(d.split(":")[1]);db.unblock(uid,bid)
        bot.answer_callback_query(call.id,"✅ بلاک برداشته شد.",show_alert=True)
        bls=db.my_blocks(uid)
        if bls: edit(cid,mid,"🚫 *بلاک‌های شما:*\n\n"+"".join(f"• {r['fn'] or r['blocked_id']}\n" for r in bls[:15]),kb_blocks(uid))
        else: edit(cid,mid,"هیچ بلاکی ندارید. ✅",kb_back("u:back"))
        return

    # ── Admin remove word ──
    if d.startswith("a:wfd:"):
        if not db.is_admin(uid): return
        db.del_word(d[6:]);bot.answer_callback_query(call.id,"✅ حذف شد.")
        words=db.list_words();ws=", ".join(r["word"] for r in words[:30]) or "—"
        edit(cid,mid,f"🔞 *فیلتر کلمات* ({len(words)} کلمه):\n`{ws}`",_kb_wf_full(words))
        return

    # ── Admin remove admin ──
    if d.startswith("a:admd:"):
        if not db.is_admin(uid): return
        tid=int(d[7:])
        if db.del_admin(tid):
            bot.answer_callback_query(call.id,f"✅ ادمین {tid} حذف شد.")
            try: bot.send_message(tid,"❌ دسترسی ادمین شما لغو شد.")
            except: pass
        else: bot.answer_callback_query(call.id,"❌ ادمین اصلی قابل حذف نیست.",show_alert=True)
        return

    # ── User buttons ──
    if d.startswith("u:"): _ucb(call,uid,cid,mid,d);return

    # ── Admin buttons ──
    if d.startswith("a:"):
        if not db.is_admin(uid): bot.answer_callback_query(call.id,"⛔ دسترسی ممنوع.",show_alert=True);return
        _acb(call,uid,cid,mid,d);return

def _kb_wf_full(words):
    rows=[[f"❌ {r['word']}",f"a:wfd:{r['word']}"] for r in words[:20]]
    return ik([("➕ افزودن کلمه","a:wfa")],*[[r] for r in rows],[("↩️ بازگشت","a:main")])

# ─── USER CALLBACKS ───────────────────────────────────────────
def _ucb(call,uid,cid,mid,d):
    u=db.user(uid)
    if not u: return
    if d=="u:link":
        edit(cid,mid,f"🔗 *لینک ناشناس:*\n\n`{alink(u['token'])}`\n\nبه اشتراک بگذارید.",kb_back("u:back","↩️ بازگشت"))
    elif d=="u:newlink":
        tok=db.regen_token(uid);edit(cid,mid,f"✅ *لینک جدید:*\n\n`{alink(tok)}`\n\n⚠️ لینک قبلی حذف شد.",kb_back("u:back","↩️ بازگشت"))
    elif d=="u:stats":
        u2=db.user(uid)
        edit(cid,mid,f"📊 *آمار شما{vbadge(uid)}*\n\n📤 ارسالی: {u2['msg_sent']:,}\n📥 دریافتی: {u2['msg_received']:,}\n⭐ رپوتیشن: {u2['reputation']:+}\n👫 دعوت‌ها: {db.ref_count(uid)}\n📅 عضویت: {ft(u2['created_at'])}",kb_back("u:back","↩️ بازگشت"))
    elif d=="u:ref":
        tok=u["token"];edit(cid,mid,f"🎁 *لینک رفرال:*\n\n`{rlink(tok)}`\n\n👫 دعوت‌های موفق: {db.ref_count(uid)}\n\nوقتی دیگران با این لینک عضو شوند در آمار شما ثبت می‌شود.",kb_back("u:back","↩️ بازگشت"))
    elif d=="u:pause":
        v=not u["is_paused"];db.set_paused(uid,v)
        bot.answer_callback_query(call.id,"⏸ DND فعال شد." if v else "▶️ DND غیرفعال شد.",show_alert=True)
        edit(cid,mid,f"🏠 *منوی اصلی*\n\n🔗 لینک:\n`{alink(db.user(uid)['token'])}`",kb_user(uid))
    elif d=="u:blocks":
        bls=db.my_blocks(uid)
        if not bls: edit(cid,mid,"هیچ کاربری بلاک نشده. ✅",kb_back("u:back"));return
        lines=["🚫 *بلاک‌های شما:*\n"]+[f"• {r['fn'] or r['blocked_id']}" for r in bls[:15]]
        edit(cid,mid,"\n".join(lines),kb_blocks(uid))
    elif d=="u:help":
        edit(cid,mid,
            "❓ *راهنما:*\n\n"
            "۱. لینک ناشناس خود را به اشتراک بگذارید\n"
            "۲. پیام‌ها ناشناس دریافت کنید\n"
            "۳. با ↩️ پاسخ ناشناس بدهید\n"
            "۴. 👍❤️😂😮👎 واکنش بگذارید\n"
            "۵. 🚫 فرستنده را بلاک کنید\n"
            "۶. لینک رفرال برای دعوت دوستان\n\n"
            "📌 *دستورات:*\n/mylink /newlink /pause /report /cancel",
            kb_back("u:back","↩️ بازگشت"))
    elif d=="u:back":
        u2=db.user(uid);edit(cid,mid,f"🏠 *منوی اصلی*\n\n🔗 لینک:\n`{alink(u2['token'])}`",kb_user(uid))

# ─── ADMIN CALLBACKS ──────────────────────────────────────────
def _acb(call,uid,cid,mid,d):
    if d=="a:main":
        s=db.stats()
        edit(cid,mid,f"🎛️ *پنل مدیریت*\n\n👥`{s['users']:,}` 🟢`{s['active']:,}` ⭐`{s['vip']:,}`\n📩`{s['msgs']:,}` امروز:`{s['msgs_day']:,}` | ⏱`{uptime()}`",kb_admin())

    elif d=="a:stats":
        s=db.stats()
        edit(cid,mid,
            f"📊 *آمار کلی*\n\n"
            f"👥 کاربران: `{s['users']:,}` | جدید امروز: `{s['new_today']:,}`\n"
            f"🟢 فعال امروز: `{s['active']:,}`\n"
            f"🚫 مسدود: `{s['banned']:,}` | ⭐ VIP: `{s['vip']:,}` | ⏸ DND: `{s['paused']:,}`\n"
            f"────────────────\n"
            f"📩 کل پیام: `{s['msgs']:,}` | امروز: `{s['msgs_day']:,}`\n"
            f"این هفته: `{s['msgs_week']:,}`\n"
            f"────────────────\n"
            f"📋 گزارش معلق: `{s['reports']:,}`\n"
            f"👍 ری‌اکشن: `{s['reactions']:,}`\n"
            f"👫 رفرال: `{s['referrals']:,}`\n"
            f"🔞 کلمات فیلتر: `{s['words']:,}` | 👑 ادمین: `{s['admins']:,}`\n"
            f"⏱ آپتایم: `{uptime()}`",
            ik([("🔄","a:stats"),("↩️","a:main")]))

    elif d=="a:adv":
        ts=db.top_users("msg_sent",5);tr=db.top_users("msg_received",5);tp=db.top_users("reputation",5)
        lines=["📈 *آمار پیشرفته*\n","🏆 *پرارسال‌ترین:*"]
        for r in ts: lines.append(f"  `{r['user_id']}` {r['first_name'] or '—'} — {r['v']:,}")
        lines.append("\n📥 *پردریافت‌ترین:*")
        for r in tr: lines.append(f"  `{r['user_id']}` {r['first_name'] or '—'} — {r['v']:,}")
        lines.append("\n⭐ *بالاترین رپوتیشن:*")
        for r in tp: lines.append(f"  `{r['user_id']}` {r['first_name'] or '—'} — {r['v']:+}")
        edit(cid,mid,"\n".join(lines),kb_back())

    elif d.startswith("a:ul:") or d.startswith("a:bl:") or d.startswith("a:vl:"):
        cmd=d[2:4];page=int(d.split(":")[-1])
        flt={"ul":"all","bl":"banned","vl":"vip"}[cmd]
        users,tot=db.users_page(page,flt=flt)
        ic={"ul":"👥","bl":"🚫","vl":"⭐"}[cmd]
        lines=[f"{ic} *کاربران ({tot:,}) — صفحه {page+1}*\n"]
        for u2 in users:
            ico="🚫" if u2["is_banned"] else "⭐" if u2["is_vip"] else "✅"
            lines.append(f"{ico}`{u2['user_id']}` {u2['first_name'] or '—'}\n  📤{u2['msg_sent']} 📥{u2['msg_received']} ⭐{u2['reputation']:+} | {ft(u2['last_active'])}")
        edit(cid,mid,"\n".join(lines) or "خالی.",kb_pager(page,tot,cmd))

    elif d=="a:sid": st_set(uid,S.SEARCH_ID);edit(cid,mid,"🔍 آیدی عددی کاربر را وارد کنید:")
    elif d=="a:sun": st_set(uid,S.SEARCH_UN);edit(cid,mid,"🔍 یوزرنیم کاربر را وارد کنید:")

    elif d=="a:reps":
        reps=db.reports()
        if not reps: edit(cid,mid,"هیچ گزارش معلقی وجود ندارد. ✅",kb_back());return
        edit(cid,mid,f"📋 *گزارش‌های معلق ({len(reps)}):*",kb_reps(reps))

    elif d.startswith("a:rep:") and d.count(":")==2:
        rid=int(d.split(":")[-1]);r=db.get_report(rid)
        if not r: bot.answer_callback_query(call.id,"یافت نشد.",show_alert=True);return
        edit(cid,mid,f"📋 *گزارش #{r['id']}*\n\n👤 گزارش‌دهنده: `{r['reporter_id']}`\n🕐 {ft(r['reported_at'])}\n📌 دلیل: {r['reason'] or '—'}",
            ik([("✅ حل شده",f"a:res:{rid}")],[("↩️ بازگشت","a:reps")]))

    elif d.startswith("a:res:"):
        rid=int(d[6:]);db.resolve(rid,uid)
        bot.answer_callback_query(call.id,f"✅ گزارش #{rid} حل شد.")
        edit(cid,mid,"✅ گزارش حل‌شده ثبت شد.",kb_back())

    elif d.startswith("a:ban:"):
        tid=int(d[6:]);st_set(uid,S.BAN,ban_target=tid)
        edit(cid,mid,f"✍️ دلیل مسدود کردن `{tid}` را بنویسید:")

    elif d.startswith("a:unban:"):
        tid=int(d[8:]);db.unban(tid)
        edit(cid,mid,f"✅ کاربر `{tid}` از مسدودی خارج شد.",kb_back())
        try: bot.send_message(tid,"✅ مسدودیت شما رفع شد. می‌توانید استفاده کنید.")
        except: pass

    elif d.startswith("a:gvip:"):
        tid=int(d[7:]);st_set(uid,S.VIP,vip_target=tid)
        edit(cid,mid,f"⭐ چند روز VIP برای `{tid}`؟ (عدد وارد کنید):")

    elif d.startswith("a:rvip:"):
        tid=int(d[7:]);db.revoke_vip(tid)
        edit(cid,mid,f"✅ VIP کاربر `{tid}` لغو شد.",kb_back())
        try: bot.send_message(tid,"❌ دسترسی VIP شما لغو شد.")
        except: pass

    elif d.startswith("a:note:"):
        tid=int(d[7:]);st_set(uid,S.NOTE,note_target=tid)
        edit(cid,mid,f"📝 یادداشت برای `{tid}` را بنویسید:")

    elif d.startswith("a:notes:"):
        tid=int(d[8:]);notes=db.get_notes(tid)
        if not notes: bot.answer_callback_query(call.id,"یادداشتی وجود ندارد.",show_alert=True);return
        lines=[f"📝 *یادداشت‌ها ({len(notes)}):*\n"]
        for n in notes[:10]: lines.append(f"#{n['id']} | {ft(n['added_at'])}\n  {n['note']}")
        edit(cid,mid,"\n".join(lines),kb_back())

    elif d=="a:bc": edit(cid,mid,"📢 *ارسال همگانی*\n\nگروه هدف را انتخاب کنید:",kb_bc_target())

    elif d.startswith("a:bc:") and d.count(":")==2:
        tgt=d[5:];cnt=len(db.all_ids(tgt))
        st_set(uid,S.BC_WAIT,bc_target=tgt)
        edit(cid,mid,f"📢 *ارسال به {tgt}* ({cnt:,} کاربر)\n\nپیام (متن/عکس/ویدیو/فایل...) ارسال کنید.\n❌ /cancel")

    elif d=="a:bcgo":
        ctx=st_ctx(uid);st_clr(uid)
        tgt=ctx.get("bc_target","all");bc_cid=ctx.get("bc_cid");bc_mid=ctx.get("bc_mid")
        prev=ctx.get("bc_prev","");mt=ctx.get("bc_type","text")
        if not bc_mid: bot.answer_callback_query(call.id,"خطا: پیامی یافت نشد.",show_alert=True);return
        ids=db.all_ids(tgt)
        sm=bot.send_message(cid,f"📢 در حال ارسال به {len(ids):,} کاربر...")
        def do_bc():
            ok=fail=0
            for tid in ids:
                if tid==uid: continue
                try: bot.forward_message(tid,bc_cid,bc_mid);ok+=1
                except: fail+=1
            db.log_bc(uid,prev,mt,tgt,ok,fail)
            try:
                bot.edit_message_text(
                    f"✅ *ارسال همگانی تمام شد*\n\n✅ موفق: `{ok:,}`\n❌ ناموفق: `{fail:,}`\n📊 موفقیت: `{100*ok//(ok+fail) if ok+fail else 0}%`",
                    cid,sm.message_id)
            except: pass
            log.info(f"BC by {uid} [{tgt}]: ok={ok} fail={fail}")
        threading.Thread(target=do_bc,daemon=True).start()

    elif d=="a:logs":
        msgs=db.recent_msgs(15)
        if not msgs: edit(cid,mid,"هیچ پیامی ثبت نشده.",kb_back());return
        lines=["📝 *۱۵ پیام اخیر:*\n"]
        for m in msgs: lines.append(f"#{m['id']}[{m['msg_type']}] {ft(m['sent_at'])}\n  `{m['sender_id']}`→`{m['receiver_id']}`")
        edit(cid,mid,"\n".join(lines),kb_back())

    elif d=="a:bch":
        h=db.bc_hist()
        if not h: edit(cid,mid,"تاریخچه‌ای ندارید.",kb_back());return
        lines=["📡 *تاریخچه ارسال همگانی:*\n"]
        for b in h: lines.append(f"🕐{ft(b['sent_at'])} [{b['target']}]\n  ✅{b['sent_ok']} ❌{b['failed']}\n  📝{b['preview'] or '—'}")
        edit(cid,mid,"\n".join(lines),kb_back())

    elif d=="a:wf":
        words=db.list_words();ws=", ".join(r["word"] for r in words[:30]) or "—"
        edit(cid,mid,f"🔞 *فیلتر کلمات* ({len(words)}):\n`{ws}`",_kb_wf_full(words))

    elif d=="a:wfa":
        st_set(uid,S.WORD_ADD)
        edit(cid,mid,"➕ کلمه(های) جدید (با ویرگول جدا):\nمثال: `کلمه۱، کلمه۲`")

    elif d=="a:admins":
        admins=db.list_admins()
        edit(cid,mid,f"👑 *مدیریت ادمین‌ها ({len(admins)}):*",kb_admins(admins))

    elif d=="a:adda":
        st_set(uid,S.ADD_ADMIN)
        edit(cid,mid,"👑 آیدی عددی کاربر جدید را وارد کنید:")

    elif d=="a:cfg": edit(cid,mid,"⚙️ *تنظیمات ربات*",kb_cfg())
    elif d.startswith("a:cm:"):
        v=d[-1];db.set_cfg("maintenance",v)
        bot.answer_callback_query(call.id,"🔴 تعمیر فعال شد." if v=="1" else "🟢 تعمیر غیرفعال شد.",show_alert=True)
        edit(cid,mid,"⚙️ *تنظیمات ربات*",kb_cfg())
    elif d.startswith("a:clf:"):
        v=d[-1];db.set_cfg("link_filter",v)
        bot.answer_callback_query(call.id,"✅ فیلتر لینک بروز شد.")
        edit(cid,mid,"⚙️ *تنظیمات ربات*",kb_cfg())
    elif d.startswith("a:cnr:"):
        v=d[-1];db.set_cfg("notify_reaction",v)
        bot.answer_callback_query(call.id,"✅ اعلان ری‌اکشن بروز شد.")
        edit(cid,mid,"⚙️ *تنظیمات ربات*",kb_cfg())
    elif d=="a:crl":
        st_set(uid,S.SET_RL)
        edit(cid,mid,"⏱ محدودیت عادی:\nفرمت: `تعداد:ثانیه` مثال: `10:60`")
    elif d=="a:cvrl":
        st_set(uid,S.SET_VRL)
        edit(cid,mid,"⭐ محدودیت VIP:\nفقط تعداد. مثال: `50`")
    elif d=="a:cw":
        st_set(uid,S.SET_WELCOME)
        edit(cid,mid,"💬 پیام خوش‌آمد جدید را بنویسید:")

    elif d=="a:backup":
        try:
            bp=f"/tmp/bk_{int(time.time())}.db";shutil.copy2(DB_PATH,bp)
            with open(bp,"rb") as f: bot.send_document(cid,f,caption="💾 پشتیبان دیتابیس",visible_file_name=f"anon_{datetime.now():%Y%m%d}.db")
            import os;os.remove(bp)
        except Exception as e: bot.send_message(cid,f"❌ خطا: {e}")

    elif d=="a:csv":
        bot.send_document(cid,io.BytesIO(db.export_csv()),caption="📊 خروجی کاربران",visible_file_name=f"users_{datetime.now():%Y%m%d}.csv")

# ─── DAILY REPORT ─────────────────────────────────────────────
def _daily():
    while True:
        time.sleep(86400)
        s=db.stats()
        txt=(f"📅 *گزارش روزانه*\n\n👥`{s['users']:,}` | 🆕`{s['new_today']:,}` | 🟢`{s['active']:,}`\n"
             f"📩 امروز: `{s['msgs_day']:,}` | ⭐ VIP: `{s['vip']:,}`\n"
             f"📋 گزارش معلق: `{s['reports']:,}` | ⏱ {uptime()}")
        for aid in ROOT_ADMINS:
            try: bot.send_message(aid,txt)
            except: pass
        log.info("Daily report sent.")

threading.Thread(target=_daily,daemon=True).start()

# ─── MAIN ─────────────────────────────────────────────────────
if __name__=="__main__":
    log.info("═"*55)
    log.info("  ربات پیام ناشناس v3.0 — telebot edition")
    log.info("═"*55)
    bot.infinity_polling(timeout=10,long_polling_timeout=5)
