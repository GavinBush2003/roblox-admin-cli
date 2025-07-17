import os, json, time, threading, bcrypt, requests
from flask import Flask, request, jsonify
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import track
from datetime import datetime

# Paths
ACCOUNTS_FILE = "accounts.json"
SESSION_FILE = "session.json"
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

console = Console()
app = Flask(__name__)
queues = {}
game_status = {}

# --- Flask Server ---
@app.route("/sendCommand", methods=["POST"])
def send_command():
    data = request.get_json()
    user, game, command = data.get("user"), data.get("game"), data.get("command")
    if not user or not game or not command:
        return jsonify({"error": "invalid data"}), 400
    queues.setdefault(user, {}).setdefault(game, []).append({"cmd": command, "time": time.time()})
    return jsonify({"status": "queued"})

@app.route("/getCommand", methods=["GET"])
def get_command():
    user, game = request.args.get("user"), request.args.get("game")
    q = queues.get(user, {}).get(game, [])
    if q:
        cmd = q.pop(0)["cmd"]
        return jsonify({"command": cmd})
    return jsonify({"command": None})

@app.route("/ping", methods=["GET"])
def ping():
    user, game = request.args.get("user"), request.args.get("game")
    game_status.setdefault(user, {})[game] = datetime.now().isoformat()
    return jsonify({"status": "alive"})

@app.route("/report", methods=["POST"])
def report():
    data = request.get_json()
    user, game = data.get("user"), data.get("game")
    log(f"[{user}/{game} REPORT]: {data.get('message')}")
    return jsonify({"status": "logged"})

def run_server():
    app.run(host="127.0.0.1", port=5000)

# --- Utility Functions ---
def log(msg):
    with open(f"{LOGS_DIR}/log.txt", "a") as f:
        f.write(f"{datetime.now()} | {msg}\n")

def hash_pw(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_pw(pw, hash):
    return bcrypt.checkpw(pw.encode(), hash.encode())

# --- User System ---
def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_accounts(data):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(data, f)

def save_session(user):
    with open(SESSION_FILE, "w") as f:
        json.dump({"user": user}, f)

def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return json.load(f)["user"]
    return None

def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

# --- CLI Interface ---
def splash():
    banner = """
[bold cyan]
██████╗  ██████╗ ██████╗ ██╗      ██████╗ ██╗  ██╗
██╔══██╗██╔═══██╗██╔══██╗██║     ██╔═══██╗╚██╗██╔╝
██████╔╝██║   ██║██████╔╝██║     ██║   ██║ ╚███╔╝ 
██╔══██╗██║   ██║██╔══██╗██║     ██║   ██║ ██╔██╗ 
██║  ██║╚██████╔╝██████╔╝███████╗╚██████╔╝██╔╝ ██╗
╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝  ╚═╝[/bold cyan]"""
    console.print(banner)
    console.print("       [bold green]Roblox CLI Admin Tool[/bold green]\n")

def login_system():
    accounts = load_accounts()
    user = load_session()
    if user and user in accounts:
        console.print(f"🔑 Logged in as [bold]{user}[/bold]")
        return user

    console.print("[yellow]No active session.[/yellow]")
    action = Prompt.ask("[1] Login\n[2] Register", choices=["1", "2"])

    if action == "2":
        user = Prompt.ask("New Username")
        pw = Prompt.ask("New Password", password=True)
        accounts[user] = hash_pw(pw)
        save_accounts(accounts)
        save_session(user)
        console.print("[green]Account created and logged in![/green]")
        return user

    user = Prompt.ask("Username")
    pw = Prompt.ask("Password", password=True)
    if user in accounts and verify_pw(pw, accounts[user]):
        save_session(user)
        console.print("[green]Logged in successfully![/green]")
        return user
    else:
        console.print("[red]Invalid login.[/red]")
        return login_system()

def main_cli(user):
    threading.Thread(target=run_server, daemon=True).start()
    current_game = None

    for _ in track(range(100), description="Loading CLI..."):
        time.sleep(0.01)

    splash()
    while True:
        cmd = Prompt.ask(f"[bold cyan]{user}[/bold cyan] ➜ ", default="").strip()

        if cmd.startswith("connect "):
            current_game = cmd.split(" ",1)[1]
            console.print(f"[green]Connected to:[/green] {current_game}")

        elif cmd.startswith("kick ") or cmd.startswith("announce "):
            if not current_game:
                console.print("[red]Connect to a game first.[/red]")
                continue
            data = {"user": user, "game": current_game, "command": cmd}
            requests.post("http://127.0.0.1:5000/sendCommand", json=data)
            console.print(f"[yellow]Queued:[/yellow] {cmd}")
            log(f"{user}@{current_game}: {cmd}")

        elif cmd == "games":
            games = game_status.get(user, {})
            console.print("[bold green]Active games:[/bold green]")
            for game, time_seen in games.items():
                console.print(f"{game} - Last ping: {time_seen}")

        elif cmd == "logout":
            clear_session()
            console.print("[yellow]Logged out.[/yellow]")
            break

        elif cmd == "help":
            console.print("""
[cyan]Commands:[/cyan]
[green]connect [game][/green]      - Connect to your game
[green]kick [player][/green]       - Kick a player
[green]announce [msg][/green]      - Announce a message
[green]games[/green]               - Show active games
[green]logout[/green]              - Logout
[green]exit[/green]                - Exit CLI
""")
        elif cmd == "exit":
            break
        elif cmd == "":
            continue
        else:
            console.print("[red]Unknown command.[/red] Type 'help'.")

    console.print("[cyan]CLI Shutting down...[/cyan]")

if __name__ == "__main__":
    user = login_system()
    main_cli(user)
