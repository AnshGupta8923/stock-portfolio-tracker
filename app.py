import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime

# ── Database Setup ──────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS portfolio
                 (id INTEGER PRIMARY KEY, username TEXT, symbol TEXT, 
                  quantity REAL, buy_price REAL, date TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (NULL, ?, ?)", 
                  (username, hash_password(password)))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?",
              (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result

def save_stock(username, symbol, quantity, buy_price):
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute("INSERT INTO portfolio VALUES (NULL, ?, ?, ?, ?, ?)",
              (username, symbol, quantity, buy_price, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def get_portfolio(username):
    conn = sqlite3.connect("portfolio.db")
    df = pd.read_sql_query("SELECT * FROM portfolio WHERE username=?", 
                            conn, params=(username,))
    conn.close()
    return df

def delete_stock(stock_id):
    conn = sqlite3.connect("portfolio.db")
    c = conn.cursor()
    c.execute("DELETE FROM portfolio WHERE id=?", (stock_id,))
    conn.commit()
    conn.close()

# ── Initialize ───────────────────────────────────────────────
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# ── Login / Register Page ────────────────────────────────────
if not st.session_state.logged_in:
    st.title("📈 Stock Portfolio Tracker")
    st.markdown("### Please login or register to continue")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password!")

    with tab2:
        st.subheader("Register")
        new_user = st.text_input("Choose Username", key="reg_user")
        new_pass = st.text_input("Choose Password", type="password", key="reg_pass")
        if st.button("Register"):
            if register_user(new_user, new_pass):
                st.success("Account created! Please login.")
            else:
                st.error("Username already exists!")

# ── Main App ─────────────────────────────────────────────────
else:
    st.set_page_config(page_title="Stock Portfolio Tracker", page_icon="📈", layout="wide")
    st.title(f"📈 Welcome, {st.session_state.username}!")

    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.rerun()

    menu = st.sidebar.radio("Navigation", 
                             ["📊 Dashboard", "➕ Add Stock", "📰 Stock News", "📈 Compare Stocks"])

    # ── Dashboard ──
    if menu == "📊 Dashboard":
        st.subheader("Your Portfolio")
        df = get_portfolio(st.session_state.username)

        if df.empty:
            st.info("No stocks yet! Go to 'Add Stock' to get started.")
        else:
            results = []
            for _, row in df.iterrows():
                ticker = yf.Ticker(row["symbol"])
                hist = ticker.history(period="1d")
                if not hist.empty:
                    current = round(hist["Close"].iloc[-1], 2)
                    invested = round(row["buy_price"] * row["quantity"], 2)
                    current_val = round(current * row["quantity"], 2)
                    pnl = round(current_val - invested, 2)
                    results.append({
                        "ID": row["id"],
                        "Stock": row["symbol"],
                        "Qty": row["quantity"],
                        "Buy Price": f"${row['buy_price']}",
                        "Current Price": f"${current}",
                        "Invested": f"${invested}",
                        "Current Value": f"${current_val}",
                        "P&L": f"${pnl}",
                        "Date Added": row["date"]
                    })

            result_df = pd.DataFrame(results)
            st.dataframe(result_df.drop(columns=["ID"]), use_container_width=True)

            total_invested = sum([float(r["Invested"].replace("$","")) for r in results])
            total_current = sum([float(r["Current Value"].replace("$","")) for r in results])
            total_pnl = round(total_current - total_invested, 2)

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Invested", f"${total_invested:,.2f}")
            col2.metric("Current Value", f"${total_current:,.2f}")
            col3.metric("Total P&L", f"${total_pnl:,.2f}", 
                       delta=f"${total_pnl:,.2f}")

            fig = px.pie(result_df, values=[float(r["Current Value"].replace("$","")) 
                         for r in results], names="Stock", title="Portfolio Allocation")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Delete a Stock")
            del_id = st.number_input("Enter Stock ID to delete", min_value=1, step=1)
            if st.button("🗑️ Delete"):
                delete_stock(del_id)
                st.success("Deleted!")
                st.rerun()

    # ── Add Stock ──
    elif menu == "➕ Add Stock":
        st.subheader("Add Stock to Portfolio")
        symbol = st.text_input("Stock Symbol (e.g. AAPL, TSLA, GOOGL)").upper()
        quantity = st.number_input("Quantity", min_value=1, value=1)
        buy_price = st.number_input("Buy Price ($)", min_value=0.01, value=100.0)

        if st.button("➕ Add to Portfolio"):
            if symbol:
                save_stock(st.session_state.username, symbol, quantity, buy_price)
                st.success(f"{symbol} added to your portfolio!")

                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="6mo")
                if not hist.empty:
                    fig = px.line(hist, x=hist.index, y="Close",
                                  title=f"{symbol} - 6 Month Price History")
                    st.plotly_chart(fig, use_container_width=True)

    # ── Stock News ──
   
    elif menu == "📰 Stock News":
        st.subheader("Latest Stock News")
        symbol = st.text_input("Enter Stock Symbol for News (e.g. AAPL)").upper()
        if st.button("Get News"):
            ticker = yf.Ticker(symbol)
            news = ticker.news
            if news:
                for article in news[:8]:
                    content = article.get("content", {})
                    title = content.get("title") or article.get("title") or "No Title Available"
                    link = content.get("canonicalUrl", {}).get("url") or article.get("link") or "#"
                    publisher = content.get("provider", {}).get("displayName") or "Unknown Source"
                    st.markdown(f"### {title}")
                    st.markdown(f"🗞️ *{publisher}*")
                    st.markdown(f"[Read More ➡️]({link})")
                    st.divider()
            else:
                st.info("No news found for this stock!")
    # ── Compare Stocks ──
    elif menu == "📈 Compare Stocks":
        st.subheader("Compare Multiple Stocks")
        symbols = st.text_input("Enter symbols separated by comma (e.g. AAPL,TSLA,GOOGL)")
        period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y"])

        if st.button("Compare"):
            fig = go.Figure()
            for sym in symbols.split(","):
                sym = sym.strip().upper()
                hist = yf.Ticker(sym).history(period=period)
                if not hist.empty:
                    fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name=sym))
            fig.update_layout(title="Stock Price Comparison", 
                            xaxis_title="Date", yaxis_title="Price ($)")
            st.plotly_chart(fig, use_container_width=True)