import streamlit as st
from data_loader import load_nhl_data

# Set page config
st.set_page_config(layout="wide", page_title="NHL Stats Dashboard")
st.title("🏒 NHL 2025-26 Fantasy Tool")

# --- LOAD DATA ---
with st.spinner('Loading NHL Data...'):
    df = load_nhl_data()

if df.empty:
    st.warning("No data found. The API might be busy or the season hasn't started.")
else:
    tab1, tab2 = st.tabs(["🏆 League Leaders", "⚔️ My Fantasy Team"])

    # ==========================================
    # TAB 1: LEAGUE LEADERS
    # ==========================================
    with tab1:
        st.header("League Leaders")
        
        with st.expander("Filter Options", expanded=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                if 'Team' in df.columns:
                    unique_teams = sorted(df['Team'].dropna().unique())
                    selected_teams = st.multiselect("Filter by Team", unique_teams, default=unique_teams)
            with col_f2:
                if 'Pos' in df.columns:
                    unique_pos = sorted(df['Pos'].dropna().unique())
                    selected_positions = st.multiselect("Filter by Position", unique_pos, default=unique_pos)

        # Apply Filters
        filtered_df = df.copy()
        if selected_teams and 'Team' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Team'].isin(selected_teams)]
        if selected_positions and 'Pos' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Pos'].isin(selected_positions)]

        # Leader Metrics
        st.markdown("### Top Performers")
        m1, m2, m3, m4 = st.columns(4)
        
        def get_top(d, col):
            if d.empty or col not in d.columns: return "N/A", 0
            row = d.sort_values(by=col, ascending=False).iloc[0]
            return row['Player'], row[col]

        p_name, p_val = get_top(filtered_df, 'Pts')
        g_name, g_val = get_top(filtered_df, 'G')
        a_name, a_val = get_top(filtered_df, 'A')
        gwg_name, gwg_val = get_top(filtered_df, 'GWG')

        m1.metric("Points", str(p_val), p_name)
        m2.metric("Goals", str(g_val), g_name)
        m3.metric("Assists", str(a_val), a_name)
        m4.metric("GWG", str(gwg_val), gwg_name)

        # Config
        column_config = {
            "Player": st.column_config.TextColumn("Player", pinned=True),
            "Team": st.column_config.TextColumn("Team", help="Team Abbreviation"),
            "Pos": st.column_config.TextColumn("Pos", help="Position"),
            "GP": st.column_config.NumberColumn("GP", help="Games Played"),
            "G": st.column_config.NumberColumn("G", help="Goals"),
            "A": st.column_config.NumberColumn("A", help="Assists"),
            "Pts": st.column_config.NumberColumn("Pts", help="Points"),
            "+/-": st.column_config.NumberColumn("+/-", help="Plus/Minus"),
            "PIM": st.column_config.NumberColumn("PIM", help="Penalty Minutes"),
            "PPP": st.column_config.NumberColumn("PPP", help="Power Play Points"),
            "PPG": st.column_config.NumberColumn("PPG", help="Power Play Goals"),
            "SHP": st.column_config.NumberColumn("SHP", help="Shorthanded Points"),
            "GWG": st.column_config.NumberColumn("GWG", help="Game Winning Goals"),
            "SOG": st.column_config.NumberColumn("SOG", help="Shots on Goal"),
            "Sh%": st.column_config.NumberColumn("Sh%", help="Shooting %", format="%.1f%%"),
            "FO%": st.column_config.NumberColumn("FO%", help="Faceoff Win %", format="%.1f%%"),
            "TOI": st.column_config.TextColumn("TOI", help="Time On Ice")
        }

        st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=600, column_config=column_config)

    # ==========================================
    # TAB 2: MY FANTASY TEAM (URL SAVING)
    # ==========================================
    with tab2:
        st.header("⚔️ My Roster")
        st.info("💡 **Pro Tip:** Bookmark this page after selecting your team to save it!")

        all_player_names = sorted(df['Player'].unique())

        # 1. GET ROSTER FROM URL
        # We read the 'roster' query param from the URL (e.g., ?roster=Player1,Player2)
        query_params = st.query_params
        url_roster_str = query_params.get("roster", "")
        
        # Convert string back to list, ensuring players exist in our dataset
        default_roster = []
        if url_roster_str:
            default_roster = [p for p in url_roster_str.split(",") if p in all_player_names]

        # 2. DEFINE CALLBACK TO UPDATE URL
        def update_url():
            # Join the selected list into a string "Player1,Player2"
            selected_str = ",".join(st.session_state.my_team_selector)
            st.query_params["roster"] = selected_str

        # 3. MULTISELECT WIDGET
        my_team_list = st.multiselect(
            "Search and Add Players:", 
            all_player_names, 
            default=default_roster,
            key="my_team_selector",
            on_change=update_url,
            placeholder="Type a name (e.g. McDavid)..."
        )

        if my_team_list:
            my_team_df = df[df['Player'].isin(my_team_list)]

            st.markdown("### Team Totals")
            t1, t2, t3, t4 = st.columns(4)
            
            t1.metric("Total Goals", int(my_team_df['G'].sum()))
            t2.metric("Total Assists", int(my_team_df['A'].sum()))
            t3.metric("Total Points", int(my_team_df['Pts'].sum()))
            t4.metric("Total PPP", int(my_team_df['PPP'].sum()))

            st.markdown("### Roster Breakdown")
            st.dataframe(
                my_team_df, 
                use_container_width=True, 
                hide_index=True, 
                column_config=column_config
            )
        else:
            st.write("Your roster is empty. Add players above to get started!")


