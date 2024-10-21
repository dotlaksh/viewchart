import pandas as pd
import streamlit as st
import sqlite3
import yfinance as yf
from lightweight_charts.widgets import StreamlitChart
from contextlib import contextmanager
import math
from datetime import datetime, timedelta
# Database connection management
@contextmanager
def get_db_connection():
    conn = sqlite3.connect('stocks1.db', check_same_thread=False)
    try:
        yield conn
    finally:
        conn.close()

@st.cache_data
def get_tables():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [table[0] for table in cursor.fetchall()]
    return tables

@st.cache_data
def get_stocks_from_table(table_name):
    with get_db_connection() as conn:
        query = f"SELECT DISTINCT symbol, stock_name FROM {table_name} ORDER BY symbol;"
        stocks_df = pd.read_sql_query(query, conn)
    return stocks_df

def calculate_pivot_points(high, low, close):
    """Calculate monthly pivot points and support/resistance levels"""
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    
    return {
        'P': round(pivot, 2),
        'R1': round(r1, 2),
        'R2': round(r2, 2),
        'R3': round(r3, 2),
        'S1': round(s1, 2),
        'S2': round(s2, 2),
        'S3': round(s3, 2)
    }

@st.cache_data
def load_chart_data(symbol):
    ticker = f"{symbol}.NS"
    try:
        # Get data for the current month and previous month
        end_date = datetime.now()
        start_date = (end_date - timedelta(days=60)).strftime('%Y-%m-%d')
        df = yf.download(ticker, period='ytd', interval='1d')
        df.reset_index(inplace=True)
        
        if not df.empty:
            # Calculate previous month's high, low, close for pivot points
            current_month = datetime.now().strftime('%Y-%m')
            prev_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
            prev_month_data = df[df['Date'].dt.strftime('%Y-%m') == prev_month]
            
            if len(prev_month_data) > 0:
                monthly_high = prev_month_data['High'].max()
                monthly_low = prev_month_data['Low'].min()
                monthly_close = prev_month_data['Close'].iloc[-1]
                
                # Calculate pivot points using previous month's data
                pivot_points = calculate_pivot_points(monthly_high, monthly_low, monthly_close)
            else:
                pivot_points = None

            chart_data = pd.DataFrame({
                "time": df["Date"].dt.strftime("%Y-%m-%d"),
                "open": df["Open"],
                "high": df["High"],
                "low": df["Low"],
                "close": df["Close"],
                "volume": df["Volume"]
            })
            
            # Calculate daily percentage change
            current_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            daily_change = ((current_price - prev_price) / prev_price) * 100
            
            return chart_data, current_price, df['Volume'].iloc[-1], daily_change, pivot_points
        return None, None, None, None, None
    except Exception as e:
        print(f"Error loading data: {e}")
        return None, None, None, None, None

def create_chart(chart_data, name, symbol, current_price, volume, daily_change, pivot_points):
    if chart_data is not None:
        chart_height = 450
        chart = StreamlitChart(height=chart_height)

        change_color = '#00ff55' if daily_change >= 0 else '#ed4807'
        change_symbol = '▲' if daily_change >= 0 else '▼'      
        
        st.markdown(f"""
        <div class="stock-info">
            <span style='font-size: 16px; font-weight: bold;'>{name}</span>
            <span style='color: #00ff55;'>₹{current_price:.2f}</span> | 
            <span style='color: {change_color};'>{change_symbol} {abs(daily_change):.2f}%</span> | 
            Vol: {volume:,.0f}
        </div>
        """, unsafe_allow_html=True)

        chart.layout(
            background_color='#1E222D',
            text_color='#FFFFFF',
            font_size=12,
            font_family='Helvetica'
        )
        
        chart.candle_style(
            up_color='#00ff55',
            down_color='#ed4807',
            wick_up_color='#00ff55',
            wick_down_color='#ed4807'
        )
    
        if pivot_points:
            chart.horizontal_line(pivot_points['P'], color='#227cf4', width=1, style='solid')
            chart.horizontal_line(pivot_points['R1'], color='#ed4807', width=1, style='dashed')
            chart.horizontal_line(pivot_points['R2'], color='#ed4807', width=1, style='dashed')
            chart.horizontal_line(pivot_points['R3'], color='#ed4807', width=1, style='dashed')
            chart.horizontal_line(pivot_points['S1'], color='#00ff55', width=1, style='dashed')
            chart.horizontal_line(pivot_points['S2'], color='#00ff55', width=1, style='dashed')
            chart.horizontal_line(pivot_points['S3'], color='#00ff55', width=1, style='dashed')

        chart.volume_config(
            up_color='#00ff55',
            down_color='#ed4807'
        )
        
        chart.crosshair(
            mode='normal',
            vert_color='#FFFFFF',
            vert_style='dotted',
            horz_color='#FFFFFF',
            horz_style='dotted'
        )
        
        chart.time_scale(right_offset=5, min_bar_spacing=10)
        chart.grid(vert_enabled=False, horz_enabled=False)
        chart.set(chart_data)
        return chart
    return None

# Page setup
st.set_page_config(layout="wide", page_title="ChartView 2.0", page_icon="📈")

# Custom CSS for better styling
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    .stSelectbox, .stTextInput {
        background-color: #262730;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
    }
    .stock-info {
        background-color: #1E222D;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session states
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1

# Sidebar
with st.sidebar:
    st.title("📊 ChartView 2.0")
    st.markdown("---")
    tables = get_tables()
    selected_table = st.selectbox("📁 Select a table:", tables, key='table_selector')
    
    # Add a search box for stocks
    search_term = st.text_input("🔍 Search for a stock:", "")

# Reset page when table changes
if 'previous_table' not in st.session_state:
    st.session_state.previous_table = selected_table
if st.session_state.previous_table != selected_table:
    st.session_state.current_page = 1
    st.session_state.previous_table = selected_table

# Get stocks data and display charts
if selected_table:
    stocks_df = get_stocks_from_table(selected_table)
    
    # Filter stocks based on search term
    if search_term:
        stocks_df = stocks_df[stocks_df['stock_name'].str.contains(search_term, case=False) | 
                              stocks_df['symbol'].str.contains(search_term, case=False)]
    
    CHARTS_PER_PAGE = 12
    total_pages = math.ceil(len(stocks_df) / CHARTS_PER_PAGE)

    # Pagination controls
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        if st.button("← Previous", key='prev', disabled=(st.session_state.current_page == 1)):
            st.session_state.current_page -= 1
            st.rerun()

    with col2:
        st.write(f"Page {st.session_state.current_page} of {total_pages}")

    with col3:
        if st.button("Next →", key='next', disabled=(st.session_state.current_page == total_pages)):
            st.session_state.current_page += 1
            st.rerun()

    # Determine start and end indices for pagination
    start_idx = (st.session_state.current_page - 1) * CHARTS_PER_PAGE
    end_idx = min(start_idx + CHARTS_PER_PAGE, len(stocks_df))

    # Display charts in a loop
    for i in range(start_idx, end_idx, 2):
        col1, col2 = st.columns([1, 1], gap='small')

        # First chart
        with col1:
            with st.spinner(f"Loading {stocks_df['stock_name'].iloc[i]}..."):
                symbol = stocks_df['symbol'].iloc[i]
                name = stocks_df['stock_name'].iloc[i]
                chart_data, current_price, volume, daily_change, pivot_points = load_chart_data(symbol)
                if chart_data is not None:
                    chart = create_chart(chart_data, name, symbol, current_price, volume, daily_change, pivot_points)
                    if chart:
                        chart.load()

        # Second chart (if available)
        with col2:
            if i + 1 < end_idx:
                with st.spinner(f"Loading {stocks_df['stock_name'].iloc[i + 1]}..."):
                    symbol = stocks_df['symbol'].iloc[i + 1]
                    name = stocks_df['stock_name'].iloc[i + 1]
                    chart_data, current_price, volume, daily_change, pivot_points = load_chart_data(symbol)
                    if chart_data is not None:
                        chart = create_chart(chart_data, name, symbol, current_price, volume, daily_change, pivot_points)
                        if chart:
                            chart.load()

    # Add a footer
    st.markdown("---")
    st.markdown("Developed by Laksh | Data provided by Yahoo Finance")