import os, sqlite3, uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

ROOT=os.path.dirname(os.path.abspath(__file__))
DATA=os.path.join(ROOT,"data")
UPLOAD=os.path.join(DATA,"uploads")
os.makedirs(UPLOAD,exist_ok=True)
app=Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get("AUCTION_N_SECRET","change-this-secret-before-deploying"), MAX_CONTENT_LENGTH=5*1024*1024)
DB=os.path.join(DATA,"auction_n.db")
ALLOWED={"png","jpg","jpeg","webp","gif"}

def db():
    if "db" not in g:
        g.db=sqlite3.connect(DB)
        g.db.row_factory=sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db
@app.teardown_appcontext
def close_db(e=None):
    c=g.pop("db",None)
    if c: c.close()

def init_db():
    c=sqlite3.connect(DB)
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tournaments(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, name TEXT NOT NULL, sport TEXT NOT NULL, currency TEXT NOT NULL DEFAULT '₹', purse REAL NOT NULL DEFAULT 10000000, max_players INTEGER NOT NULL DEFAULT 25, bid_increment REAL NOT NULL DEFAULT 100000, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY, tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE, name TEXT NOT NULL, short_name TEXT NOT NULL, owner TEXT DEFAULT '', color TEXT DEFAULT '#5b8cff', purse REAL NOT NULL, spent REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY, tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE, name TEXT NOT NULL, role TEXT NOT NULL, category TEXT DEFAULT 'Open', nationality TEXT DEFAULT '', age INTEGER, base_price REAL NOT NULL DEFAULT 100000, photo TEXT DEFAULT '', stats TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Available', sold_team_id INTEGER REFERENCES teams(id), sold_price REAL DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS bids(id INTEGER PRIMARY KEY, tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE, player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE, team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE, amount REAL NOT NULL, bidder TEXT DEFAULT '', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY, tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE, message TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS fixtures(id INTEGER PRIMARY KEY, tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE, round_name TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'League', group_name TEXT DEFAULT '', match_no INTEGER NOT NULL, home_team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL, away_team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL, match_date TEXT DEFAULT '', venue TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Scheduled', home_score TEXT DEFAULT '', away_score TEXT DEFAULT '', winner_team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL, notes TEXT DEFAULT '', created_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_fixtures_tournament ON fixtures(tournament_id, stage, match_no);
    """)
    c.commit(); c.close()

def now(): return datetime.utcnow().isoformat(timespec="seconds")
def active_tournament():
    tid=session.get("tournament_id")
    if not tid: return None
    return db().execute("SELECT * FROM tournaments WHERE id=? AND user_id=?",(tid,session["user_id"])).fetchone()
def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not session.get("user_id"): return redirect(url_for("login"))
        return fn(*a,**kw)
    return wrapper
def log(message):
    t=active_tournament()
    if t: db().execute("INSERT INTO activity(tournament_id,message,created_at) VALUES(?,?,?)",(t["id"],message,now())); db().commit()
@app.context_processor
def inject():
    return {"active":active_tournament(),"currency":(active_tournament()["currency"] if active_tournament() else "₹")}

@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        username=request.form.get("username","").strip()
        password=request.form.get("password","")
        if len(username)<3 or len(password)<8:
            flash("Use a username with at least 3 characters and password with at least 8 characters.","error")
        else:
            try:
                c=db(); c.execute("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",(username,generate_password_hash(password),now())); c.commit()
                user=c.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()
                session.clear(); session["user_id"]=user["id"]; session["username"]=username
                flash("Account created. Set up your first auction workspace.","success")
                return redirect(url_for("setup"))
            except sqlite3.IntegrityError: flash("That username is already in use.","error")
    return render_template("auth.html",mode="register")
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=db().execute("SELECT * FROM users WHERE username=?",(request.form.get("username","").strip(),)).fetchone()
        if u and check_password_hash(u["password_hash"],request.form.get("password","")):
            session.clear(); session["user_id"]=u["id"]; session["username"]=u["username"]
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.","error")
    return render_template("auth.html",mode="login")
@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/setup",methods=["GET","POST"])
@login_required
def setup():
    if request.method=="POST":
        name=request.form.get("name","").strip() or "My Sports Auction"
        sport=request.form.get("sport","Cricket")
        try: count=max(2,min(200,int(request.form.get("team_count",8))))
        except: count=8
        try: purse=max(1,float(request.form.get("purse",10000000)))
        except: purse=10000000
        try: maxp=max(1,min(100,int(request.form.get("max_players",25))))
        except: maxp=25
        try: inc=max(1,float(request.form.get("bid_increment",100000)))
        except: inc=100000
        c=db(); cur=c.execute("INSERT INTO tournaments(user_id,name,sport,purse,max_players,bid_increment,created_at) VALUES(?,?,?,?,?,?,?)",(session["user_id"],name,sport,purse,maxp,inc,now()))
        tid=cur.lastrowid
        for i in range(count):
            n=f"Team {i+1}"
            c.execute("INSERT INTO teams(tournament_id,name,short_name,purse,created_at) VALUES(?,?,?,?,?)",(tid,n,f"T{i+1:02}",purse,now()))
        c.commit(); session["tournament_id"]=tid
        return redirect(url_for("dashboard"))
    return render_template("setup.html")
@app.route("/dashboard")
@login_required
def dashboard():
    ts=db().execute("SELECT * FROM tournaments WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall()
    if not ts: return redirect(url_for("setup"))
    if not active_tournament(): session["tournament_id"]=ts[0]["id"]
    t=active_tournament()
    teams=db().execute("SELECT * FROM teams WHERE tournament_id=? ORDER BY id",(t["id"],)).fetchall()
    players=db().execute("SELECT * FROM players WHERE tournament_id=?",(t["id"],)).fetchall()
    sold=sum(1 for p in players if p["status"]=="Sold")
    spent=sum(x["spent"] for x in teams)
    activity=db().execute("SELECT * FROM activity WHERE tournament_id=? ORDER BY id DESC LIMIT 8",(t["id"],)).fetchall()
    return render_template("dashboard.html",teams=teams,players=players,sold=sold,spent=spent,activity=activity,tournaments=ts)
@app.route("/switch/<int:tid>")
@login_required
def switch(tid):
    t=db().execute("SELECT id FROM tournaments WHERE id=? AND user_id=?",(tid,session["user_id"])).fetchone()
    if t: session["tournament_id"]=tid
    return redirect(url_for("dashboard"))
@app.route("/tournament/new",methods=["GET","POST"])
@login_required
def new_tournament():
    if request.method=="POST":
        session.pop("tournament_id",None)
        return redirect(url_for("setup"))
    return render_template("new_tournament.html")

@app.route("/teams")
@login_required
def teams():
    t=active_tournament()
    if not t: return redirect(url_for("setup"))
    rows=db().execute("SELECT tm.*,COUNT(p.id) AS player_count FROM teams tm LEFT JOIN players p ON p.sold_team_id=tm.id AND p.status='Sold' WHERE tm.tournament_id=? GROUP BY tm.id ORDER BY tm.id",(t["id"],)).fetchall()
    return render_template("teams.html",teams=rows)
@app.route("/teams/add",methods=["POST"])
@login_required
def add_team():
    t=active_tournament()
    if not t: return redirect(url_for("setup"))
    name=request.form.get("name","").strip()
    if name:
        short=request.form.get("short_name","").strip().upper()[:5] or f"T{db().execute('SELECT COUNT(*) n FROM teams WHERE tournament_id=?',(t['id'],)).fetchone()['n']+1}"
        db().execute("INSERT INTO teams(tournament_id,name,short_name,owner,color,purse,created_at) VALUES(?,?,?,?,?,?,?)",(t["id"],name,short,request.form.get("owner",""),request.form.get("color","#5b8cff"),t["purse"],now())); db().commit(); log(f"Team {name} created.")
    return redirect(url_for("teams"))
@app.route("/teams/<int:team_id>/edit",methods=["POST"])
@login_required
def edit_team(team_id):
    t=active_tournament()
    db().execute("UPDATE teams SET name=?,short_name=?,owner=?,color=? WHERE id=? AND tournament_id=?",(request.form.get("name","").strip(),request.form.get("short_name","").strip().upper(),request.form.get("owner",""),request.form.get("color","#5b8cff"),team_id,t["id"])); db().commit()
    return redirect(url_for("teams"))

@app.route("/players")
@login_required
def players():
    t=active_tournament()
    if not t:return redirect(url_for("setup"))
    rows=db().execute("SELECT p.*,tm.name team_name FROM players p LEFT JOIN teams tm ON tm.id=p.sold_team_id WHERE p.tournament_id=? ORDER BY p.id DESC",(t["id"],)).fetchall()
    return render_template("players.html",players=rows)
def save_photo(file):
    if not file or not file.filename: return ""
    ext=file.filename.rsplit(".",1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED: return None
    filename=f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD,filename))
    return filename
@app.route("/players/add",methods=["POST"])
@login_required
def add_player():
    t=active_tournament()
    if not t:return redirect(url_for("setup"))
    photo=save_photo(request.files.get("photo"))
    if photo is None: flash("Photo must be PNG, JPG, JPEG, WEBP or GIF.","error"); return redirect(url_for("players"))
    name=request.form.get("name","").strip()
    if name:
        db().execute("INSERT INTO players(tournament_id,name,role,category,nationality,age,base_price,photo,stats,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(t["id"],name,request.form.get("role","Player"),request.form.get("category","Open"),request.form.get("nationality",""),request.form.get("age") or None,float(request.form.get("base_price") or 0),photo,request.form.get("stats",""),now()))
        db().commit(); log(f"Player {name} registered.")
    return redirect(url_for("players"))
@app.route("/players/<int:pid>/delete",methods=["POST"])
@login_required
def delete_player(pid):
    t=active_tournament(); p=db().execute("SELECT photo FROM players WHERE id=? AND tournament_id=?",(pid,t["id"])).fetchone()
    if p:
        db().execute("DELETE FROM players WHERE id=?",(pid,)); db().commit()
        if p["photo"]:
            try: os.remove(os.path.join(UPLOAD,p["photo"]))
            except OSError: pass
    return redirect(url_for("players"))
@app.route("/uploads/<path:filename>")
@login_required
def uploads(filename): return send_from_directory(UPLOAD,filename)

@app.route("/auction")
@login_required
def auction():
    t=active_tournament()
    if not t:return redirect(url_for("setup"))
    p=db().execute("SELECT * FROM players WHERE tournament_id=? AND status='Available' ORDER BY id LIMIT 1",(t["id"],)).fetchone()
    teams=db().execute("SELECT * FROM teams WHERE tournament_id=? ORDER BY id",(t["id"],)).fetchall()
    bids=[]
    if p: bids=db().execute("SELECT b.*,tm.name team_name FROM bids b JOIN teams tm ON tm.id=b.team_id WHERE b.player_id=? ORDER BY b.amount DESC,b.id DESC",(p["id"],)).fetchall()
    current=bids[0] if bids else None
    return render_template("auction.html",player=p,teams=teams,bids=bids,current=current)
@app.route("/auction/bid",methods=["POST"])
@login_required
def bid():
    t=active_tournament(); pid=request.form.get("player_id",type=int); team_id=request.form.get("team_id",type=int)
    p=db().execute("SELECT * FROM players WHERE id=? AND tournament_id=? AND status='Available'",(pid,t["id"])).fetchone()
    tm=db().execute("SELECT * FROM teams WHERE id=? AND tournament_id=?",(team_id,t["id"])).fetchone()
    if not p or not tm: flash("Player or team is no longer available.","error"); return redirect(url_for("auction"))
    top=db().execute("SELECT MAX(amount) m FROM bids WHERE player_id=?",(pid,)).fetchone()["m"]
    amount=float(request.form.get("amount") or 0)
    minimum=(top+t["bid_increment"]) if top else p["base_price"]
    if amount<minimum: flash(f"Bid must be at least {minimum:,.0f}.","error")
    elif tm["purse"]-tm["spent"]<amount: flash("This team does not have enough remaining budget.","error")
    else:
        db().execute("INSERT INTO bids(tournament_id,player_id,team_id,amount,bidder,created_at) VALUES(?,?,?,?,?,?)",(t["id"],pid,team_id,amount,session["username"],now())); db().commit(); log(f"{tm['name']} bid {t['currency']}{amount:,.0f} for {p['name']}.")
    return redirect(url_for("auction"))
@app.route("/auction/sold",methods=["POST"])
@login_required
def sold():
    t=active_tournament(); pid=request.form.get("player_id",type=int)
    top=db().execute("SELECT b.*,tm.name team_name FROM bids b JOIN teams tm ON tm.id=b.team_id WHERE b.player_id=? AND b.tournament_id=? ORDER BY b.amount DESC,b.id DESC LIMIT 1",(pid,t["id"])).fetchone()
    p=db().execute("SELECT * FROM players WHERE id=? AND tournament_id=? AND status='Available'",(pid,t["id"])).fetchone()
    if p and top:
        db().execute("UPDATE players SET status='Sold',sold_team_id=?,sold_price=? WHERE id=?",(top["team_id"],top["amount"],pid))
        db().execute("UPDATE teams SET spent=spent+? WHERE id=?",(top["amount"],top["team_id"]))
        db().commit(); log(f"{p['name']} SOLD to {top['team_name']} for {t['currency']}{top['amount']:,.0f}.")
    elif p: flash("No valid bid exists. Mark the player unsold instead.","error")
    return redirect(url_for("auction"))
@app.route("/auction/unsold",methods=["POST"])
@login_required
def unsold():
    t=active_tournament(); pid=request.form.get("player_id",type=int)
    db().execute("UPDATE players SET status='Unsold' WHERE id=? AND tournament_id=? AND status='Available'",(pid,t["id"])); db().commit(); log("Player marked unsold."); return redirect(url_for("auction"))
@app.route("/auction/next",methods=["POST"])
@login_required
def next_player():
    t=active_tournament()
    db().execute("UPDATE players SET status='Available' WHERE tournament_id=? AND status='Unsold'",(t["id"],)); db().commit()
    return redirect(url_for("auction"))
@app.route("/history")
@login_required
def history():
    t=active_tournament()
    rows=db().execute("SELECT p.*,tm.name team_name FROM players p LEFT JOIN teams tm ON tm.id=p.sold_team_id WHERE p.tournament_id=? ORDER BY p.id DESC",(t["id"],)).fetchall()
    activity=db().execute("SELECT * FROM activity WHERE tournament_id=? ORDER BY id DESC",(t["id"],)).fetchall()
    return render_template("history.html",players=rows,activity=activity)

@app.route("/fixtures", methods=["GET", "POST"])
@login_required
def fixtures():
    t=active_tournament()
    if not t: return redirect(url_for("setup"))
    c=db(); teams=c.execute("SELECT * FROM teams WHERE tournament_id=? ORDER BY id",(t["id"],)).fetchall()
    if request.method=="POST":
        action=request.form.get("action")
        if action=="generate":
            if c.execute("SELECT COUNT(*) n FROM fixtures WHERE tournament_id=?",(t["id"],)).fetchone()["n"]:
                flash("Fixtures already exist. Clear the schedule before generating a new format.","error"); return redirect(url_for("fixtures"))
            fmt=request.form.get("format","round_robin")
            if len(teams)<2: flash("Add at least two teams before generating fixtures.","error"); return redirect(url_for("fixtures"))
            ids=[x["id"] for x in teams]; date=request.form.get("start_date",""); venue=request.form.get("venue","").strip(); rows=[]
            def add_round(pairs, round_name, stage, group=""):
                for a,b in pairs: rows.append((t["id"],round_name,stage,group,len(rows)+1,a,b,date,venue,now()))
            if fmt in ("round_robin","double_round_robin"):
                pool=ids[:]
                if len(pool)%2: pool.append(None)
                n=len(pool)
                for rnd in range(n-1):
                    pairs=[]
                    for i in range(n//2):
                        a,b=pool[i],pool[n-1-i]
                        if a and b: pairs.append((a,b) if rnd%2==0 else (b,a))
                    add_round(pairs,f"Round {rnd+1}","League"); pool=[pool[0]]+[pool[-1]]+pool[1:-1]
                if fmt=="double_round_robin":
                    for row in list(rows): rows.append((t["id"],row[1]+" · Return",row[2],row[3],len(rows)+1,row[6],row[5],date,venue,now()))
            elif fmt=="knockout":
                import math
                size=2**math.ceil(math.log2(len(ids))); pool=ids[:]+[None]*(size-len(ids)); first_label={2:"Final",4:"Semi-finals",8:"Quarter-finals"}.get(size,f"Round of {size}"); add_round([(pool[i],pool[i+1]) for i in range(0,size,2)],first_label,"Knockout")
                count=size//4; rnd=2
                while count>=1:
                    for j in range(count): rows.append((t["id"],{1:"Final",2:"Semi-finals",4:"Quarter-finals"}.get(count,f"Knockout Round {rnd}"),"Knockout","",len(rows)+1,None,None,date,venue,now()))
                    if count==1: break
                    count//=2; rnd+=1
            elif fmt in ("groups_knockout","league_playoff"):
                import math
                gc=max(2,min(len(ids),int(request.form.get("groups",2) or 2))); buckets=[[] for _ in range(gc)]
                for i,tid in enumerate(ids): buckets[i%gc].append(tid)
                for gi,bucket in enumerate(buckets):
                    pool=bucket[:]
                    if len(pool)%2: pool.append(None)
                    n=len(pool)
                    for rnd in range(n-1):
                        pairs=[]
                        for i in range(n//2):
                            a,b=pool[i],pool[n-1-i]
                            if a and b:pairs.append((a,b))
                        add_round(pairs,f"Group {chr(65+gi)} · Round {rnd+1}","Group",f"Group {chr(65+gi)}"); pool=[pool[0]]+[pool[-1]]+pool[1:-1]
                size=2**math.ceil(math.log2(max(2,gc*2)))
                for i in range(size//2): rows.append((t["id"],"Quarter-final" if size>=8 else "Semi-final","Playoff","",len(rows)+1,None,None,date,venue,now()))
                for i in range(size//4): rows.append((t["id"],"Semi-final","Playoff","",len(rows)+1,None,None,date,venue,now()))
                rows.append((t["id"],"Final","Playoff","",len(rows)+1,None,None,date,venue,now()))
            else: flash("Choose a supported tournament format.","error"); return redirect(url_for("fixtures"))
            c.executemany("INSERT INTO fixtures(tournament_id,round_name,stage,group_name,match_no,home_team_id,away_team_id,match_date,venue,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",rows); c.commit(); log(f"Generated {len(rows)} fixtures using {fmt.replace('_',' ')} format."); flash(f"Generated {len(rows)} fixtures successfully.","success"); return redirect(url_for("fixtures"))
        if action=="clear":
            c.execute("DELETE FROM fixtures WHERE tournament_id=?",(t["id"],)); c.commit(); log("Fixture schedule cleared."); flash("Fixture schedule cleared.","success"); return redirect(url_for("fixtures"))
        if action=="update":
            fid=request.form.get("fixture_id",type=int); home=request.form.get("home_team_id",type=int) or None; away=request.form.get("away_team_id",type=int) or None
            c.execute("UPDATE fixtures SET home_team_id=?,away_team_id=?,match_date=?,venue=?,notes=? WHERE id=? AND tournament_id=?",(home,away,request.form.get("match_date",""),request.form.get("venue",""),request.form.get("notes",""),fid,t["id"])); c.commit(); flash("Fixture details updated.","success"); return redirect(url_for("fixtures"))
        if action=="result":
            fid=request.form.get("fixture_id",type=int); hs=request.form.get("home_score","").strip(); aws=request.form.get("away_score","").strip(); winner=request.form.get("winner_team_id",type=int) or None
            f=c.execute("SELECT * FROM fixtures WHERE id=? AND tournament_id=?",(fid,t["id"])).fetchone()
            if f and (not winner or winner in (f["home_team_id"],f["away_team_id"])):
                c.execute("UPDATE fixtures SET home_score=?,away_score=?,winner_team_id=?,status=? WHERE id=?",(hs,aws,winner,"Completed" if winner else "Completed · Draw",fid))
                if winner and f["stage"] in ("Knockout","Playoff"):
                    nxt=c.execute("SELECT * FROM fixtures WHERE tournament_id=? AND stage=? AND id>? AND (home_team_id IS NULL OR away_team_id IS NULL) ORDER BY id LIMIT 1",(t["id"],f["stage"],fid)).fetchone()
                    if nxt:
                        col="home_team_id" if nxt["home_team_id"] is None else "away_team_id"; c.execute(f"UPDATE fixtures SET {col}=? WHERE id=?",(winner,nxt["id"]))
                c.commit(); log(f"Match {f['match_no']} result recorded."); flash("Match result saved.","success")
            else: flash("Choose a valid winner from the teams in this fixture.","error")
            return redirect(url_for("fixtures"))
    rows=c.execute("SELECT f.*,h.name home_name,h.short_name home_short,a.name away_name,a.short_name away_short,w.name winner_name FROM fixtures f LEFT JOIN teams h ON h.id=f.home_team_id LEFT JOIN teams a ON a.id=f.away_team_id LEFT JOIN teams w ON w.id=f.winner_team_id WHERE f.tournament_id=? ORDER BY f.id",(t["id"],)).fetchall()
    return render_template("fixtures.html",fixtures=rows,teams=teams,completed=sum(1 for x in rows if x["status"].startswith("Completed")))

@app.route("/fixtures/standings")
@login_required
def standings():
    t=active_tournament()
    if not t:return redirect(url_for("setup"))
    teams=db().execute("SELECT * FROM teams WHERE tournament_id=? ORDER BY name",(t["id"],)).fetchall(); matches=db().execute("SELECT * FROM fixtures WHERE tournament_id=? AND stage IN ('League','Group') AND status LIKE 'Completed%'",(t["id"],)).fetchall(); table=[]
    for tm in teams:
        played=wins=draws=losses=points=0
        for m in matches:
            if tm["id"] not in (m["home_team_id"],m["away_team_id"]):continue
            played+=1
            if not m["winner_team_id"]:draws+=1;points+=1
            elif m["winner_team_id"]==tm["id"]:wins+=1;points+=3
            else:losses+=1
        table.append(dict(team=tm,played=played,wins=wins,draws=draws,losses=losses,points=points))
    table.sort(key=lambda x:(-x["points"],-x["wins"],x["team"]["name"])); return render_template("standings.html",table=table)

@app.route("/export/players.csv")
@login_required
def export_csv():
    import csv,io
    t=active_tournament(); rows=db().execute("SELECT name,role,category,nationality,age,base_price,status,sold_price FROM players WHERE tournament_id=?",(t["id"],)).fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(["Player","Role","Category","Nationality","Age","Base price","Status","Sold price"])
    for r in rows:w.writerow(list(r))
    from flask import Response
    return Response("\ufeff"+out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=auction_n_players.csv"})
@app.route("/api/summary")
@login_required
def summary():
    t=active_tournament()
    teams=db().execute("SELECT COUNT(*) n FROM teams WHERE tournament_id=?",(t["id"],)).fetchone()["n"]
    players=db().execute("SELECT COUNT(*) n FROM players WHERE tournament_id=?",(t["id"],)).fetchone()["n"]
    sold=db().execute("SELECT COUNT(*) n FROM players WHERE tournament_id=? AND status='Sold'",(t["id"],)).fetchone()["n"]
    return jsonify(teams=teams,players=players,sold=sold)
@app.errorhandler(413)
def too_large(e): return "Image is too large. Maximum upload size is 5 MB.",413

if __name__=="__main__":
    init_db()
    app.run(host="127.0.0.1",port=5000,debug=True)
