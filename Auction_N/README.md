# Auction.N — Sports Auction Management

A locally hosted multi-user sports auction manager built with Flask, SQLite, HTML, CSS and JavaScript.

## Features
- User registration and login (passwords are hashed).
- Separate user-owned tournament workspaces.
- Choose 2–200 teams during setup; add more teams later.
- Multiple tournaments per account.
- Player register with image uploads, roles, categories, base price and notes.
- Cricket, football, kabaddi, basketball, hockey, volleyball and custom sport labels.
- Auction floor with bid validation, configurable increments, team purse checks, sold and unsold actions.
- Team purse tracking, activity log, player outcome history and CSV export.
- SQLite database and uploaded photos persist in the `data/` folder.

## Windows quick start
1. Install Python 3.10 or newer.
2. Extract the ZIP to a normal folder (not inside the ZIP preview).
3. Double-click `run_windows.bat`.
4. Wait for installation, then open `http://127.0.0.1:5000`.
5. Register a username and password, then configure the tournament and team count.

## macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open `http://127.0.0.1:5000`.

## Data storage and backup
- Database: `data/auction_n.db`
- Player photos: `data/uploads/`
- Back up the complete `data/` folder to preserve user accounts, tournaments, teams, players, bids, activity and images.
- Do not delete or rename the `data/` folder while the app is running.

## Important notes
- This is a complete runnable starter application for local use and demonstrations. It is not yet a hardened public production deployment.
- The auction is operated by the signed-in workspace owner. Team-owner multi-login, live multi-device WebSocket bidding, timer automation, password reset, cloud backup and deployment hardening are future production enhancements.
- The local Flask development server is not intended for public internet hosting. Before deployment, set a long random `AUCTION_N_SECRET`, use HTTPS, configure a production WSGI server, and add rate limiting, CSRF protection and secure upload scanning.
- Team count is configurable from 2 to 200 at tournament creation, and additional teams can be added from Teams.

## Tournament fixtures & match center
Open **Fixtures & matches** from the sidebar after creating teams. Supported generators include round robin, double round robin, single-elimination knockout, group stage with playoffs, and league with playoffs. Edit team assignments, dates, venues and notes; record scores and winners. League/group points update automatically (win 3, draw 1, loss 0). Knockout/playoff winners move into the next available bracket slot. Use **Reset schedule** before generating a different format.
