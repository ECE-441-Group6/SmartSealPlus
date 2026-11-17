"""SmartSeal+ Streamlit dashboard for the existing Gateway/smartseal.db.

Run from the repository root:
    streamlit run streamlit_dashboard.py
"""
from pathlib import Path
import csv
import re
import sqlite3

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'Gateway' / 'smartseal.db'
ARCHIVES = ROOT / 'Gateway' / 'archives'
IMAGES = ROOT / 'Gateway' / 'images'
COLUMNS = ['id','timestamp','seal_id','event_sequence','temperature','tamper','vibration','movement_type','image_path','ai_analysis']
ARCHIVE_PATTERN = re.compile(r'SmartSeal_Events_(?:\d{2}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-[AP]M|\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d+)\.csv')

st.set_page_config(page_title='SmartSeal+ Monitoring', page_icon='📦', layout='wide')
st.title('SmartSeal+ Monitoring Dashboard')
st.caption('Reads the existing SQLite database. No changes to gateway packet processing.')

@st.cache_data(ttl=2, show_spinner=False)
def load_live():
    if not DB.is_file():
        return pd.DataFrame(columns=COLUMNS)
    try:
        with sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True, timeout=3) as conn:
            return pd.read_sql_query('SELECT id, timestamp, seal_id, event_sequence, temperature, tamper, vibration, movement_type, image_path, ai_analysis FROM events ORDER BY timestamp DESC, id DESC', conn)
    except sqlite3.Error as exc:
        st.error(f'Could not read database: {exc}')
        return pd.DataFrame(columns=COLUMNS)

@st.cache_data(ttl=2, show_spinner=False)
def load_archive(filename):
    path = ARCHIVES / filename
    if not ARCHIVE_PATTERN.fullmatch(filename) or not path.is_file() or path.resolve().parent != ARCHIVES.resolve():
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = pd.read_csv(path)
        for col in COLUMNS:
            if col not in df:
                df[col] = None
        return df[COLUMNS]
    except (OSError, ValueError, csv.Error) as exc:
        st.error(f'Could not read archive: {exc}')
        return pd.DataFrame(columns=COLUMNS)

def status(value, positive='DETECTED', negative='NORMAL'):
    return positive if pd.notna(value) and bool(value) else negative

def safe_image_path(filename):
    if not isinstance(filename, str) or not filename.strip():
        return None
    path = (IMAGES / filename).resolve()
    if path.parent == IMAGES.resolve() and path.is_file():
        return path
    return None

archives = sorted((p.name for p in ARCHIVES.glob('*.csv') if p.is_file() and ARCHIVE_PATTERN.fullmatch(p.name)), reverse=True) if ARCHIVES.is_dir() else []
source = st.selectbox('Event history', ['Current gateway session'] + archives)
refresh = st.toggle('Auto-refresh every 5 seconds', value=True, disabled=(source != 'Current gateway session'))
if st.button('Refresh now'):
    load_live.clear()
    load_archive.clear()
    st.rerun()

@st.fragment(run_every='5s' if refresh and source == 'Current gateway session' else None)
def dashboard():
    df = load_live() if source == 'Current gateway session' else load_archive(source)
    if df.empty:
        st.info('No events found in this source. If the gateway is running, check that it writes to Gateway/smartseal.db.')
        return
    for col in ('temperature','tamper','vibration','movement_type','seal_id'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['timestamp_dt'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
    latest = df.iloc[0]
    a,b,c,d = st.columns(4)
    a.metric('Latest temperature', f"{latest['temperature']:.1f} °C" if pd.notna(latest['temperature']) else 'Unknown')
    b.metric('Latest tamper', status(latest['tamper'], 'DETECTED', 'SECURE'))
    c.metric('Latest vibration', status(latest['vibration']))
    d.metric('Latest movement', status(latest['movement_type']))
    st.caption(f'{len(df)} stored events · Latest record: {latest["timestamp"]} (database timestamp)')

    with st.expander('Temperature history', expanded=True):
        seals = sorted(df['seal_id'].dropna().unique().tolist())
        choice = st.selectbox('Seal', ['All seals'] + [str(int(s)) for s in seals], key='seal_choice')
        chart_df = df.dropna(subset=['timestamp_dt','temperature']).copy()
        if choice != 'All seals':
            chart_df = chart_df[chart_df['seal_id'] == int(choice)]
        if chart_df.empty:
            st.info('No temperature readings for this selection.')
        else:
            chart_df = chart_df.sort_values('timestamp_dt')
            chart_df['seal'] = chart_df['seal_id'].apply(lambda x: f'Seal {int(x)}' if pd.notna(x) else 'Unknown seal')
            wide = chart_df.pivot_table(index='timestamp_dt', columns='seal', values='temperature', aggfunc='last')
            wide['Low limit (2°C)'] = 2.0
            wide['High limit (8°C)'] = 8.0
            st.line_chart(wide, y_label='Temperature (°C)', x_label='Time (UTC)')

    display = df.copy()
    def temp_status(v):
        if pd.isna(v): return 'Unknown'
        return f'{v:.1f} °C - LOW' if v < 2 else f'{v:.1f} °C - HIGH' if v > 8 else f'{v:.1f} °C - NORMAL'
    display['Temp'] = display['temperature'].map(temp_status)
    display['Tamper'] = display['tamper'].map(lambda v: status(v, 'DETECTED', 'SECURE'))
    display['Vibration'] = display['vibration'].map(status)
    display['Movement'] = display['movement_type'].map(lambda v: f'DETECTED ({int(v)})' if pd.notna(v) and v != 0 else 'NORMAL')
    st.subheader('Event history')
    st.dataframe(display.rename(columns={'timestamp':'Time','seal_id':'Seal ID','event_sequence':'Event','ai_analysis':'AI analysis'})[['Time','Seal ID','Event','Temp','Tamper','Vibration','Movement','image_path','AI analysis']], use_container_width=True, hide_index=True)

    image_rows = df[df['image_path'].notna() & (df['image_path'].astype(str).str.strip() != '')]
    if not image_rows.empty:
        with st.expander('Camera evidence'):
            options = list(image_rows.index)
            chosen = st.selectbox('Event with image', options, format_func=lambda i: f"{df.loc[i, 'timestamp']} — Seal {df.loc[i, 'seal_id']} — {df.loc[i, 'image_path']}")
            path = safe_image_path(df.loc[chosen, 'image_path'])
            if path:
                st.image(str(path), caption=str(df.loc[chosen, 'ai_analysis'] or ''))
            else:
                st.warning('Image file not found in Gateway/images.')

dashboard()

st.caption('Archives are read-only in this dashboard. The existing Flask login and archive deletion permissions are not reused.')
