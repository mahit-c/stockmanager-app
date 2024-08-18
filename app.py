import streamlit as st
import requests
import sqlite3
import pandas as pd

#Creating a local DB with SQLITE for data persistance:

DB_FILE = "stock_portfolio.db"

# Function to create a table if it doesn't exist
def create_table():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    #Cash Balance Table:
    c.execute('''CREATE TABLE IF NOT EXISTS balance (id INTEGER PRIMARY KEY, user_cash_balance REAL)''')
    
    #Portfolio table:
    c.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_cash_balance REAL,
            symbol TEXT,
            quantity INTEGER
        )
    ''')
    conn.commit()
    conn.close()


# Function to load cash balance from the database
def load_balance():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_cash_balance FROM balance WHERE id = 1")
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        return 0  # If there's no record, starting with a balance of 0


# Function to save cash balance to the database
def save_cash_balance(balance):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO balance (id, user_cash_balance) VALUES (1, ?)", (balance,))
    conn.commit()
    conn.close()

#Funciton to load user portfolio:
def load_portfolio():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT symbol, quantity FROM portfolio")
    rows = c.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

#Function for updating user portfolio:
def update_portfolio(symbol, quantity):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if quantity == 0:
        c.execute("DELETE FROM portfolio WHERE symbol = ?", (symbol,))
    else:
        c.execute("INSERT OR REPLACE INTO portfolio (symbol, quantity) VALUES (?, ?)", (symbol, quantity))
    conn.commit()
    conn.close()

# Initialising the SQLite database and table
create_table()



TIINGO_API_KEY = st.secrets["API_KEY"]


#Session state variables to manage user session data:
if 'user_cash_balance' not in st.session_state:
    st.session_state.user_cash_balance = load_balance()
if 'user_portfolio' not in st.session_state:
    st.session_state.user_portfolio = load_portfolio()
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = ""
if 'selected_ticker_price' not in st.session_state:
    st.session_state.selected_ticker_price = ""
if 'cash_amount' not in st.session_state:
    st.session_state.cash_amount = 0  # Initialize cash_amount


def get_stock_price (symbol): #Getting current/weekly ticker price
    
    #Getting current price:
    try:
        url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices?token={TIINGO_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        # Check if the response is successful
        if response.status_code == 200:
            data = response.json()

            # Ensure the data is valid
            if isinstance(data, list) and len(data) > 0:
                return data[0]['close']
            else:
                st.error("Invalid response from the API. Please try again.")
                return None
        else:
            # Handle specific API errors
            if response.status_code == 429:  # Rate limit exceeded
                st.error("You have run over your hourly request allocation. Please try again later.")
            elif response.status_code == 404:  # Symbol not found
                st.error(f"The symbol '{symbol}' is not valid. Please check and try again.")
            else:
                st.error("An error occurred while fetching stock data. Please try again.")
            return None

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return None
    


def update_cash_balance(amount, action):
    if (action == "Add"):
        st.session_state.user_cash_balance += amount #Adding to balance
    else:
        st.session_state.user_cash_balance =  max(0, st.session_state.user_cash_balance - amount) #Removing balance >=0

    save_cash_balance(st.session_state.user_cash_balance) #Saving user cash balance to DB
    

def execute_share_purchase(price, quantity, action, symbol):
    total_cost= price * quantity  #Calculating share buy cost
    
    if action == "Buy": #Handling share purchases
        
        if total_cost <= st.session_state.user_cash_balance:
            st.session_state.user_cash_balance -= total_cost #Updating user cash balance based on share purchase value
            new_quantity = st.session_state.user_portfolio.get(symbol, 0) + quantity
            st.session_state.user_portfolio[symbol] = new_quantity#Updating user portfolio
            update_portfolio(symbol, new_quantity)
            save_cash_balance(st.session_state.user_cash_balance)
            
            return True, f"Bought {quantity} shares of {symbol}"
        else:
            return False, "Insufficient funds! Please add more cash balance"
    
    else:
        if symbol in st.session_state.user_portfolio:
            current_quantity = st.session_state.user_portfolio[symbol]
            if quantity <= current_quantity:
                st.session_state.user_cash_balance += total_cost  # Adding sale value to cash balance
                new_quantity = current_quantity - quantity
                
                if new_quantity == 0:
                    del st.session_state.user_portfolio[symbol]  # Removing stock from portfolio if fully sold
                else:
                    st.session_state.user_portfolio[symbol] = new_quantity  # Updating user portfolio
                
                update_portfolio(symbol, new_quantity)
                save_cash_balance(st.session_state.user_cash_balance)
                
                return True, f"Sold {quantity} shares of {symbol}"
            else:
                return False, f"Insufficient shares! You only own {current_quantity} shares of {symbol}"
        else:
            return False, f"You don't own any shares of {symbol}"
        
    
    
    




st.set_page_config(page_title="Stock Portfolio Manager", page_icon="📈")
st.title ("Stock Portfolio Manager 📈")
# st.markdown(get_stock_price("GOOG"))


#Implementing cash balance management:
st.header("Cash Balance")
cash_col1, cash_col2 = st.columns(2)

with cash_col1:
    cash_action = st.selectbox("Selection Action", ["Add", "Remove"])
    st.session_state.cash_amount = st.number_input("Amount (USD):", min_value= 0.0, step= 0.01, max_value= 1000.0)
    button = st.button("Update Cash Balance")
    
with cash_col2:
    
    if button:
        update_cash_balance( st.session_state.cash_amount, cash_action) #Updating user's cash balance based on input
        st.session_state.cash_amount = 0
        
    st.subheader(f"Current Cash Balance: ${st.session_state.user_cash_balance:.2f}")
        
#Implementing stock trading functionality:
st.header("Trade Stock")
stock_col1, stock_col2 = st.columns(2)

with stock_col1:
    stock_action = st.selectbox("Action", ["Buy", "Sell"])
    if stock_action == "Buy":
        symbol = st.text_input("Enter Stock Symbol").upper()
        
        if symbol:
            stock_price = get_stock_price(symbol)
            
            if stock_price:
            
                st.session_state.selected_ticker = symbol
                st.session_state.selected_ticker_price = f"${stock_price}"
                
            else:
                st.write(f"Unable to fetch current price for {symbol}")
            
            
        # Display quantity input only if there's a current stock price
        if st.session_state.selected_ticker and st.session_state.selected_ticker_price:
            quantity = st.number_input("Quantity", min_value=1, step=1)
            if st.button("Execute Buy Order"):
                if symbol and stock_price:
                    success,message = execute_share_purchase(stock_price, quantity, stock_action, symbol) #Executing share purchase and storing return for success/error message
                    print(st.session_state.user_portfolio.items())
                    
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
    
    else:
        if st.session_state.user_portfolio:
                stock_sell = st.selectbox(
                    "Select Stock to Sell", 
                    options=list(st.session_state.user_portfolio.keys())
                )
                stock_price = get_stock_price(stock_sell)
                
                if stock_price:
                    st.session_state.selected_ticker = stock_sell
                    st.session_state.selected_ticker_price = f"${stock_price}"
                    
                    quantity = st.number_input("Quantity", min_value=1, max_value=st.session_state.user_portfolio[stock_sell], step=1)
                    if st.button("Execute Sell Order"):
                        success, message = execute_share_purchase(stock_price, quantity, stock_action, stock_sell)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
        else:
                st.write("You don't have any stocks to sell.") 
            
                
with stock_col2:    
    st.metric(label=st.session_state.selected_ticker, value=st.session_state.selected_ticker_price)

#Implementing total asset portfolio:
st.header("Current Portfolio")
if st.session_state.user_portfolio:
   # Fetch prices once for each symbol
    prices = {}
    for symbol in st.session_state.user_portfolio.keys():
        if symbol not in prices:
            prices[symbol] = get_stock_price(symbol)  # Fetch the stock price only once per symbol

    # Create portfolio data using the cached prices
    portfolio_data = {
        'Symbol': list(st.session_state.user_portfolio.keys()),
        'Quantity': [round(q, 2) for q in st.session_state.user_portfolio.values()],
        'Current Price': [prices[symbol] for symbol in st.session_state.user_portfolio.keys()],
        'Total Value': [round(prices[symbol] * st.session_state.user_portfolio[symbol], 2) for symbol in st.session_state.user_portfolio.keys()]
    }
    portfolio_df = pd.DataFrame(portfolio_data)
    st.dataframe(portfolio_df)
    
    # Calculating the total asset value
    total_asset_value = portfolio_df['Total Value'].sum()

    # Displaying the total asset value
    st.text(f"Total Asset Value: ${total_asset_value:.2f}")
    
else:
    st.write("Your portfolio is empty.")
    
    



