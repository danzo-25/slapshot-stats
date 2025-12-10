import streamlit as st
from data_loader import load_nhl_data

st.set_page_config(page_title="Fantasy Hockey Edge", layout="wide")
st.title("🏒 Fantasy Hockey Edge Tool (Direct API)")

# Load Data
with st.spinner('Fetching live data from NHL.com...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data loaded. Please check your internet connection or try again later.")
    st.stop()

# --- Sidebar Filters ---
st.sidebar.header("Filter Players")

# Position Filter
unique_pos = ['All'] + sorted(df['Pos'].unique().tolist())
pos_filter = st.sidebar.selectbox("Position", unique_pos)

# Team Filter
unique_teams = ['All'] + sorted(df['Team'].unique().tolist())
team_filter = st.sidebar.selectbox("Team", unique_teams)

# --- Apply Filters ---
filtered_df = df.copy()

if pos_filter != 'All':
    filtered_df = filtered_df[filtered_df['Pos'] == pos_filter]

if team_filter != 'All':
    filtered_df = filtered_df[filtered_df['Team'] == team_filter]

# --- Display Data ---
st.metric("Players Found", len(filtered_df))

st.dataframe(
    filtered_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Player": st.column_config.TextColumn("Player", width="medium"),
        "Pts": st.column_config.NumberColumn("Pts", format="%d"),
        "Sh%": st.column_config.NumberColumn("Sh%", format="%.1f%%"),
        "FO%": st.column_config.NumberColumn("FO%", format="%.1f%%"),
    }
)