# -*- coding: utf-8 -*-
"""
Created on Mon Apr 14 22:43:53 2025

@author: alann
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import altair as alt
import plotly.express as px
import glob
import os
import streamlit as st
from datetime import timedelta

#%%

# Page Config & Theme Settings

st.set_page_config(
    page_title="Dashboard for Operations Managers",
    page_icon=":trophy:",
    layout="wide",
    initial_sidebar_state="expanded"
)

alt.theme.enable("dark")

#%%

# Load Data
@st.cache_data
def load_data():
    path = './data/*.csv'
    csv_files = sorted(glob.glob(path))  
    dfs = [pd.read_csv(file) for file in csv_files]
    
    return dfs

#%%

# Set up input widgets
st.logo(
        image="./images/baywa-ag-seeklogo.png",
        icon_image="./images/baywa-seeklogo.png"
)

#%%

#                   Data Loading & Organization
dfs = load_data()

# Store mapping: Store A: 0,1,2,3; Store G: 4,5,6,7; Store J: 8,9,10,11
store_map = {'A': (0,1,2,3), 'G': (4,5,6,7), 'J': (8,9,10,11)}

#%%#                        Retrieve data for selected store(s)
    
    
def get_store_data(dfs, store):
    
    if store == "All":
        
        # Combine each type of file across all stores
        inv_dfs = [dfs[store_map[s][0]] for s in store_map]
        prod_dfs = [dfs[store_map[s][1]] for s in store_map]
        pur_dfs = [dfs[store_map[s][2]] for s in store_map]
        sales_dfs = [dfs[store_map[s][3]] for s in store_map]
        
        
        # Combines a list of DataFrames (here called inv_dfs) into a single DataFrame, 
        # stacking them vertically (row-wise) by default
        df_inventory = pd.concat(inv_dfs, ignore_index=True)
        df_products = pd.concat(prod_dfs, ignore_index=True)
        df_purchase = pd.concat(pur_dfs, ignore_index=True)
        df_sales = pd.concat(sales_dfs, ignore_index=True)
    
    else:
        idx0, idx1, idx2, idx3 = store_map[store]
        df_inventory = dfs[idx0]
        df_products = dfs[idx1]
        df_purchase = dfs[idx2]
        df_sales = dfs[idx3]
    
    return df_inventory, df_products, df_purchase, df_sales

#%%

@st.cache_data
def filter_df(df, start, end):
    df = df.copy()
    df['tranDate'] = pd.to_datetime(df['tranDate'], errors='coerce')
    
    return df[(df['tranDate'] >= start) & (df['tranDate'] <= end)]  

   

#%%

# Data aggregation based on time frame
def aggregate_timeframe(df, freq):
    """ 
    freq can be a pandas offset alias like:

    'D' – daily
    
    'W' – weekly
    
    'M' – monthly
    
    'Q' – quarterly
    
    'Y' – yearly
    """
    
    df = df.copy()
    df['tranDate'] = pd.to_datetime(df['tranDate'], errors='coerce')
    # When using altair charts you may prefer to have the date as the index
    df = df.set_index('tranDate')
    return df.resample(freq).sum(numeric_only=True) # groups data based on freq datetime index.


def get_daily_data(df):
    df = df.copy()
    df['tranDate'] = pd.to_datetime(df['tranDate'], errors='coerce')
    return df.set_index('tranDate')

def get_weekly_data(df):
    return aggregate_timeframe(df, 'W-MON')

def get_monthly_data(df):
    return aggregate_timeframe(df, 'M')

def get_quarterly_data(df):
    return aggregate_timeframe(df, 'Q')
#%%

def calc_fulfillment_rate(df):
    """Calculate order fulfillment rate using shipments data."""
    
    if df.empty:
        return 0.0
    
    total_ordered = df['qtyOrdered'].sum()
    total_received = df['qtyReceived'].sum()
    
    if total_ordered == 0:
        fulfillment_rate = 0  # Avoid division by zero
    else:
        fulfillment_rate = (total_received / total_ordered) * 100
        
    return round(fulfillment_rate, 2) 

#%%

#           Helper Functions
# -----------------------------
def format_number(num, unit=None):
    """Format number with optional unit or magnitude suffix (K, M, B)."""
    if unit in ("percentage", "days", "money"):
        rounded = round(num)
        if unit == "percentage":
            return f"{rounded}%"
        elif unit == "days":
            return f"{rounded} Days"
        elif unit == "money":
            return f"€ {rounded}"
    else:
        abs_num = abs(num)
        if abs_num >= 1_000_000_000:
            return f"{num / 1_000_000_000:.1f} B"
        elif abs_num >= 1_000_000:
            return f"{num / 1_000_000:.1f} M"
        elif abs_num >= 1_000:
            return f"{num / 1_000:.1f} K"
        else:
            return f"{num:.2f}"


#%%
def compute_delta(df, column):
    # Ensure at least two records exist
    if len(df) < 2:
        return 0, 0
    cur_val = df[column].iloc[-1]
    prev_val = df[column].iloc[-2]
    delta = cur_val - prev_val
    delta_pct = (delta / prev_val) * 100 if prev_val != 0 else 0
    return delta, delta_pct

#%%

def calculate_processing_time(df):
    """
    Calculate processing time in minutes between 'plannedDate' and 'tranDate'.
    Drops rows with missing dates.
    
    If something was completed 3 days late, that's +3

    If something was completed 2 days early, that's -2

    But in both cases, completion took time — and for "Avg Completion Time", you care about the time difference, not the direction.
    """
    df = df.copy()  
    df['tranDate'] = pd.to_datetime(df['tranDate'], errors='coerce')
    df['plannedDate'] = pd.to_datetime(df['plannedDate'], errors='coerce')
    
    ord_clean = df.dropna(subset=['plannedDate', 'tranDate'])
    processing_times = (ord_clean['tranDate'] - ord_clean['plannedDate']).dt.days
    
    # Use absolute values to get duration regardless of early/late
    process_time_mean = processing_times.abs().mean()
    return process_time_mean


#%%

def calculate_avg_order_value(df, column='amount'):
    """
    Calculate the median of the specified column (default is 'amount').

    Parameters:
        df (pd.DataFrame): DataFrame containing the data.
        column (str): Column name to calculate median from.

    Returns:
        float: Median value rounded to 2 decimal places, or None if not computable.
    """
    if column not in df.columns:
        return None

    # Drop NaN values in the column
    clean_values = df[column].dropna()

    if clean_values.empty:
        return None

    median_value = round(clean_values.median(), 2)
    return median_value

#%%




def generate_inventory_chart(df_inventory, df_items, drop_unmatched=True, verbose=False):
    """
    Cleans and merges inventory data with item details, summarizes inventory levels by store,
    and generates an Altair bar chart.

    Parameters:
        df_inventory (DataFrame): Inventory data with itemGuid and quantities.
        df_items (DataFrame): Item metadata keyed by 'guid'.
        verbose (bool): If True, prints how many unmatched rows were found.

    Returns:
        inv_chart (Altair Chart): Bar chart showing inventory levels per store.
    """
    
    # Create a working copy of inventory
    inv_df = df_inventory.copy()
    
    # Drop exact duplicates based on subset, if any
    dedup_subset=['guid', 'itemGuid', 'SubsidiaryID']
    inv_df = inv_df.drop_duplicates(subset=dedup_subset)

    # Merge inventory with item details
    inv_full = inv_df.merge(df_items, left_on='itemGuid', right_on='guid', how='left')

    # Check and handle unmatched items
    unmatched = inv_full['itemId'].isna()
    if verbose:
        st.write(f"🔍 Unmatched inventory items: {unmatched.sum()} of {len(inv_full)} rows")

    if drop_unmatched:
        inv_full = inv_full[~unmatched]

    # Summarize inventory levels by store
    inv_summary = inv_full.groupby('SubsidiaryID')[[
        'quantityAvailable', 'quantityOnHand', 'quantityBackOrdered', 'quantityOnOrder'
    ]].sum().reset_index()

    # Convert wide to long format for plotting
    inv_long = inv_summary.melt(
        id_vars='SubsidiaryID',
        var_name='Level',
        value_name='Total'
    )

    # Plot chart
    inv_chart = alt.Chart(inv_long).mark_bar().encode(
        x=alt.X('SubsidiaryID:N', title='Store', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Total:Q', title='Inventory Units'),
        color=alt.Color('Level:N', title='Inventory Type')
    ).properties(
        title='Inventory Levels by Store',
        width=600,
        height=438
    )

    return inv_chart, inv_full



#%%

def get_low_stock_items(df, quantile):
    """
    Returns items considered low in stock based on the given quantile threshold.
    
    Parameters:
        df (pd.DataFrame): Inventory DataFrame.
        quantile (float): Quantile threshold to define low stock (e.g., 0.1 for 10th percentile).
    
    Returns:
        pd.DataFrame: Filtered DataFrame of low stock items.
    """
    non_zero_stock = df[df['quantityAvailable'] > 0]
    threshold = non_zero_stock['quantityAvailable'].quantile(quantile)
    low_stock = non_zero_stock[non_zero_stock['quantityAvailable'] <= threshold][
        ['itemGuid', 'quantityAvailable', 'itemCategory', 'manufacturerID', 'SubsidiaryID']
    ]
    return low_stock.sort_values(by='quantityAvailable', ascending=False)


#%%

def manufacturer_fulfillment_time_series(df: pd.DataFrame, df_items: pd.DataFrame, freq: str) -> pd.DataFrame:
    df = df.copy()
    df['tranDate'] = pd.to_datetime(df['tranDate'], errors='coerce')

    # Merge item metadata
    merge_cols = ['guid', 'manufacturerID', 'itemCategory', 'batteryCapacityWh', 'itemWatt']
    df_items = df_items[[col for col in merge_cols if col in df_items.columns]]
    df = df.merge(df_items, left_on='itemGuid', right_on='guid', how='left')

    df['qtyOrdered'] = pd.to_numeric(df['qtyOrdered'], errors='coerce')
    df['qtyReceived'] = pd.to_numeric(df['qtyReceived'], errors='coerce')
    df = df.dropna(subset=['tranDate', 'qtyOrdered', 'qtyReceived', 'manufacturerID'])

    df = df[df['qtyOrdered'] > 0]
    df.set_index('tranDate', inplace=True)

    # Group by time, manufacturer, and category (or others)
    grouped = df.groupby([pd.Grouper(freq=freq), 'manufacturerID', 'itemCategory'])

    result = grouped.agg({
        'qtyOrdered': 'sum',
        'qtyReceived': 'sum',
        'batteryCapacityWh': 'median',
        'itemWatt': 'median'
    }).reset_index()

    result['FulfillmentRate'] = (result['qtyReceived'] / result['qtyOrdered']) * 100

    return result




#%%



def create_supplier_delta_chart(comparison_df: pd.DataFrame, item_count_df: pd.DataFrame):
    """
    Creates two Altair charts:
    1. Difference in Fulfillment Rate (Current - Previous) per manufacturer.
    2. Number of unique items per manufacturer.

    Parameters:
    - comparison_df (pd.DataFrame): Must contain 'manufacturerID', 'CurrentRate', 'PreviousRate'.
    - item_count_df (pd.DataFrame): Must contain 'manufacturerID' and 'NumItems'.

    Returns:
    - Tuple (delta_chart, item_chart)
    """
    # Drop rows with missing values
    comparison_df = comparison_df.dropna(subset=['CurrentRate', 'PreviousRate'])

    # Calculate difference
    comparison_df['RateChange'] = comparison_df['CurrentRate'] - comparison_df['PreviousRate']

    # Fulfillment rate delta chart
    delta_chart = alt.Chart(comparison_df).mark_bar().encode(
        x=alt.X('manufacturerID:N', title='Manufacturer'),
        y=alt.Y('RateChange:Q', title='Change in Outbound Fulfillment Rate (%)'),
        color=alt.condition(
            "datum.RateChange > 0",
            alt.value("green"),
            alt.value("red")
        ),
        tooltip=['manufacturerID', 'CurrentRate', 'PreviousRate', 'RateChange']
    ).properties(
        title='Change in Outbound Fulfillment Rate (Current - Previous)',
        width=600,
        height=400
    )

    # Item count chart
    item_chart = alt.Chart(item_count_df).mark_bar().encode(
        x=alt.X('manufacturerID:N', title='Manufacturer'),
        y=alt.Y('NumItems:Q', title='Number of Unique Items'),
        tooltip=['manufacturerID', 'NumItems']
    ).properties(
        title='Unique Products (SKUs) per Manufacturer',
        width=600,
        height=400
    )

    return delta_chart, item_chart

#%%

def plot_store_inventory_chart(df_inventory, df_items, drop_unmatched=True, verbose=False):
    """
    Plots a stacked bar chart of inventory quantities by type and item category.

    Parameters:
        df_inventory (DataFrame): Inventory data with 'itemGuid' and quantity fields.
        df_items (DataFrame): Item metadata with 'guid' and 'itemCategory'.
        drop_unmatched (bool): If True, drops inventory rows without a matching item record.
        verbose (bool): If True, displays count of unmatched rows.

    Returns:
        inv_chart (Altair Chart): Stacked bar chart of inventory units by type and category.
        inv_full (DataFrame): Merged inventory and item data.
    """
    # Clean and deduplicate
    inv_df = df_inventory.copy()
    dedup_subset = ['guid', 'itemGuid', 'SubsidiaryID']
    inv_df = inv_df.drop_duplicates(subset=dedup_subset)

    # Merge inventory with item details
    inv_full = inv_df.merge(df_items, left_on='itemGuid', right_on='guid', how='left')

    # Handle unmatched items
    unmatched = inv_full['itemId'].isna()
    if verbose:
        st.write(f"🔍 Unmatched inventory items: {unmatched.sum()} of {len(inv_full)} rows")

    if drop_unmatched:
        inv_full = inv_full[~unmatched]

    # Ensure quantity columns are numeric
    quantity_cols = ['quantityAvailable', 'quantityOnHand', 'quantityBackOrdered', 'quantityOnOrder']
    for col in quantity_cols:
        inv_full[col] = pd.to_numeric(inv_full[col], errors='coerce').fillna(0)

    # Melt data to long format for stacking
    inv_long = inv_full.melt(
        id_vars=['SubsidiaryID', 'itemCategory'],
        value_vars=quantity_cols,
        var_name='InventoryType',
        value_name='Units'
    )

    # Aggregate if needed (group by category + type)
    inv_summary = inv_long.groupby(['InventoryType', 'itemCategory']).agg({'Units': 'sum'}).reset_index()
    
    # Threshold to hide text on very small bars
    inv_summary['text_label'] = inv_summary['Units'].apply(lambda x: f"{int(x):,}" if x > 20000 else '')

    
    # Base stacked horizontal bar chart
    bar_chart = alt.Chart(inv_summary).mark_bar().encode(
        y=alt.Y('InventoryType:N', title='Inventory Type', sort='-x'),
        x=alt.X('Units:Q', title='Inventory Units'),
        color=alt.Color('itemCategory:N', title='Item Category'),
        tooltip=['InventoryType', 'itemCategory', 'Units']
    ).properties(
        title='Inventory Units by Type and Product Category',
        width=800,
        height=400
    )
        
    # Text on each stack — show only if big enough
    # text = alt.Chart(inv_summary).mark_text(dx=3, dy=0, color='black', fontSize=11).encode(
    #     y=alt.Y('InventoryType:N', sort='-x'),
    #     x=alt.X('Units:Q', stack='zero'),
    #     text='text_label:N',
    #     detail='itemCategory:N'
    # )   
    
    # Total per InventoryType — as extra annotation at the bar ends
    totals = inv_summary.groupby('InventoryType', as_index=False)['Units'].sum()
    totals['text'] = totals['Units'].apply(lambda x: f"Total: {int(x):,}")
    
    # total_labels = alt.Chart(totals).mark_text(
    #     align='left', dx=5, fontSize=12, fontWeight='bold', color='white'
    # ).encode(
    #     y=alt.Y('InventoryType:N', sort='-x'),
    #     x=alt.X('Units:Q'),
    #     text='text:N'
    # )

    
    # Combine all
    final_chart = (bar_chart).configure_view(stroke=None)


    return final_chart, inv_full



#%%
# def prepare_item_level_analysis_df(shipments_df, products_df):
#     df = shipments_df.copy()
#     df = df.merge(products_df, left_on='itemGuid', right_on='guid', how='left')

#     df['tranDate'] = pd.to_datetime(df['tranDate'], errors='coerce')
#     df['qtyOrdered'] = pd.to_numeric(df['qtyOrdered'], errors='coerce')
#     df['qtyReceived'] = pd.to_numeric(df['qtyReceived'], errors='coerce')

#     # Filter out rows with invalid or missing values
#     df = df.dropna(subset=['qtyOrdered', 'qtyReceived', 'manufacturerID'])
    
#     # Remove rows where qtyOrdered is zero or negative to avoid divide-by-zero or nonsense rates
#     df = df[df['qtyOrdered'] > 0]

#     # Compute Fulfillment Rate
#     df['FulfillmentRate'] = (df['qtyReceived'] / df['qtyOrdered']) * 100

#     return df


#%%

# =============================================================================
#                       Sidebar Controls
# =============================================================================


with st.sidebar:
    st.title('💻 Operations Dashboard')
    st.header("⚙️ Settings")
    
    
    # Select view mode: Combined or individual store
    view_mode = st.radio("Select view mode", options=["All Stores", "Individual Store"])
    if view_mode == "Individual Store":
        selected_store = st.selectbox("Select a store", options=list(store_map.keys()))
    else:
        selected_store = "All"
        
    
    # Get the global date range across all orders and shipments CSVs (indices 2, 3, 6, 7, 10, 11)
    def get_global_date_range(dfs):
        dates = []
        for idx in [2, 3, 6, 7, 10, 11]:
            df_temp = dfs[idx].copy()
            df_temp['tranDate'] = pd.to_datetime(df_temp['tranDate'], errors='coerce')
            dates += list(df_temp['tranDate'].dropna())
        return min(dates), max(dates)
       

    global_start, global_end = get_global_date_range(dfs)
    
    
    default_start_date = global_end - timedelta(days=365)  # Show a year by default
    default_end_date = global_end
    start = st.date_input("Start date", default_start_date, min_value=global_start, max_value=global_end)
    end = st.date_input("End date", default_end_date, min_value=global_start, max_value=global_end)
    start_date = pd.to_datetime(start)
    end_date = pd.to_datetime(end)
    
    
    # Time frame 
    time_frame = st.selectbox("Select time frame", ("Daily", "Weekly", "Monthly", "Quarterly"))
    
    
  
    df_inventory, df_products, df_purchase, df_shipments = get_store_data(dfs, selected_store) 
    
    
    
    #               Inventory summary 
    inv_chart, inv_full = generate_inventory_chart(df_inventory, df_products)
    
    
    threshold_quantile = st.slider("Set low stock threshold", 
                      min_value=0.0, 
                      max_value=1.0, 
                      value=0.3,
                      step=0.01
                      )
    
   
    
    # For delta computation: define a previous period with the same duration
    period_delta = end_date - start_date # duration of the current period
    prev_start = start_date - period_delta - timedelta(days=1) # Compute the previous period of the same duration
    prev_end = start_date - timedelta(days=1)
    # st.markdown(f"**Comparison Period:**<br>{prev_start} to {prev_end}", unsafe_allow_html=True)


    #                        Filter dfs
    sales_current = filter_df(df_shipments, start_date, end_date)
    sales_prev = filter_df(df_shipments, prev_start, prev_end)


    orders_current = filter_df(df_purchase, start_date, end_date)
    orders_prev = filter_df(df_purchase, prev_start, prev_end)
    
    # Map time frame to pandas frequency
    freq_map = {'Daily': 'D', 'Weekly': 'W-MON', 'Monthly': 'M', 'Quarterly': 'Q'}

    # Choose correct frequency
    selected_freq = freq_map[time_frame]
    

    #           Product / Item-Level Performance
    # Supplier Evaluation
    # 1. Time series over full period
    ts_current = manufacturer_fulfillment_time_series(sales_current, df_products, selected_freq)
    ts_prev = manufacturer_fulfillment_time_series(sales_prev, df_products, selected_freq)
    
    # 2. Aggregate to single fulfillment rate per manufacturer for the entire time window
    fulfill_manuf_current = ts_current.groupby('manufacturerID')['FulfillmentRate'].mean().reset_index()
    fulfill_manuf_current.rename(columns={'FulfillmentRate': 'CurrentRate'}, inplace=True)
    
    fulfill_manuf_prev = ts_prev.groupby('manufacturerID')['FulfillmentRate'].mean().reset_index()
    fulfill_manuf_prev.rename(columns={'FulfillmentRate': 'PreviousRate'}, inplace=True)

      
    
    # Fulfillment Rate (Manufacturer × Category
    selected_mfgs = st.multiselect(
        "Select Manufacturer(s)", 
        ts_current['manufacturerID'].dropna().unique().tolist()
    )
    selected_cats = st.multiselect(
        "Select Product Category", 
        ts_current['itemCategory'].dropna().unique().tolist()
    )
    
    
    
    # Battery Capacity vs Fulfillment Rate
    # if 'batteryCapacityWh' in ts_current.columns:
    #     battery_options = sorted(ts_current['batteryCapacityWh'].dropna().unique().tolist())
        
    #     if battery_options:
    #         battery_range = st.select_slider(
    #             "Select Battery Capacity Range (Wh)",
    #             options=battery_options,
    #             value=(battery_options[0], battery_options[-1])
    #         )
    #     else:
    #         st.warning("No battery capacity data available.")
    # else:
    #     st.warning("'batteryCapacityWh' column not found in data.")










    
#%%





filtered_df = ts_current.copy()
if selected_mfgs:
    filtered_df = filtered_df[filtered_df['manufacturerID'].isin(selected_mfgs)]

if selected_cats:
    filtered_df = filtered_df[filtered_df['itemCategory'].isin(selected_cats)]

# if 'wattage' in filtered_df.columns:
#     filtered_df = filtered_df[(filtered_df['wattage'] >= wattage_range[0]) & (filtered_df['wattage'] <= wattage_range[1])]

# if 'batteryCapacityWh' in filtered_df.columns:
#     filtered_df = filtered_df[(filtered_df['batteryCapacityWh'] >= battery_range[0]) & (filtered_df['batteryCapacityWh'] <= battery_range[1])]






# =============================================================================
#  #            Layout & Main Dashboard
# =============================================================================



# Combined Metrics (for both Combined and Individual views)
if selected_store == "All" or view_mode == "Combined All Stores":
    st.markdown("## All Stores Metrics")
    
    
    #                   Metrics
    # Fulfillment Rate from shipments
    fulfillment_rate = calc_fulfillment_rate(sales_current)
    fulfillment_rate_prev = calc_fulfillment_rate(sales_prev)
    delta_fulfillment, delta_fulfillment_pct = compute_delta(pd.DataFrame({"amount": [fulfillment_rate, fulfillment_rate_prev]}), "amount")
    
    # Total Orders Delivered
    units_ordered = orders_current['qtyReceived'].sum()
    units_ordered_prev = orders_prev['qtyReceived'].sum()
    delta_units_ordered, delta_units_ordered_pct = compute_delta(pd.DataFrame({"amount": [units_ordered, units_ordered_prev]}), "amount")
    
    
    # Processing Time
    avg_processing_times = calculate_processing_time(orders_current)
    avg_processing_times_prev = calculate_processing_time(orders_prev)
    delta_units_proc, delta_units_proc_pct = compute_delta(
        pd.DataFrame(
            {"amount": [avg_processing_times, avg_processing_times_prev]}), "amount"
        
        
        )
    
    # Average Order Value
    avg_order_val = calculate_avg_order_value(sales_current)
    avg_order_val_prev = calculate_avg_order_value(sales_prev)
    delta_avg_order, delta_avg_order_pct = compute_delta(
        pd.DataFrame(
            {"amount": [avg_order_val, avg_order_val_prev]}), "amount"
        
        
        )
    

      
    # 3. Product count per manufacturer
    product_count = inv_full.groupby('manufacturerID')['itemGuid'].nunique().reset_index(name='NumItems')
    
    
    # Merge and Prepare Data for Plotting
    comparison_df = pd.merge(fulfill_manuf_current, fulfill_manuf_prev, on='manufacturerID', how='outer')
    delta_chart, item_chart = create_supplier_delta_chart(comparison_df, product_count)



    # ---- Column 1: KPI Metrics and Order Analysis ---
    cols = st.columns(4)
    
    with cols[0]:
        with st.container(border=True):
            st.metric("Inbound Order Processing Time", format_number(avg_processing_times, "days"),
                      delta=f"{format_number(delta_units_proc)} ({delta_units_proc_pct:+.2f}%)")
    
    with cols[1]:
        with st.container(border=True):
            
            time_frame = (end_date - start_date).days
            st.metric(f"Outbound Fulfillment Rate {format_number(time_frame, "days")}", format_number(fulfillment_rate, "percentage"),
                      delta=f"{format_number(delta_fulfillment)} ({delta_fulfillment_pct:+.2f}%)")
    
    with cols[2]:
        with st.container(border=True):
            st.metric("Units Shipped", format_number(units_ordered),
                      delta=f"{format_number(delta_units_ordered)} ({delta_units_ordered_pct:+.2f}%)")
    
    
    with cols[3]:
        with st.container(border=True):
            st.metric("Average Inbound Order Value", format_number(avg_order_val, "money"),
                      delta=f"{format_number(delta_avg_order)} ({delta_avg_order_pct:+.2f}%)")
    
    
            
            
     
    
    # 2nd Row

    cols = st.columns(2)
    
    with cols[0]:
        with st.container(border=True):
            st.altair_chart(inv_chart, use_container_width=True)
            
    with cols[1]:
        with st.container(border=True):
            st.markdown("###### Low Stock Items")
            low_stock = get_low_stock_items(inv_full, threshold_quantile)
            low_stock = low_stock.drop_duplicates(subset=["itemCategory", "manufacturerID", "SubsidiaryID", "quantityAvailable"])

            min_val = 0
            max_val =int(max(low_stock.quantityAvailable)) if not low_stock.empty else 1

            # Ensure max > min
            if max_val <= min_val:
                max_val = min_val + 1
                
            st.dataframe(low_stock,
                          column_order=("itemCategory", "manufacturerID", "SubsidiaryID","quantityAvailable"),
                          hide_index=True,
                          width=None,
                          column_config={
                            "itemCategory": st.column_config.TextColumn(
                                "Product Category",
                            ),
                            "manufacturerID": st.column_config.TextColumn(
                                "Manufacturer",
                            ),
                            "SubsidiaryID": st.column_config.TextColumn(
                                "Store",
                            ),
                            "quantityAvailable": st.column_config.ProgressColumn(
                                "Low Stocks Products",
                                format="%d",
                                min_value=min_val,
                                max_value=max_val,
                              )} 
                          )
    
    # 3rd Row
    cols = st.columns(1)
    
    with cols[0]:
        with st.container(border=True):
            st.markdown("#### Supplier Evaluation")
            st.altair_chart(delta_chart, use_container_width=True)
            st.altair_chart(item_chart, use_container_width=True)
            
            
    # 4th Row
    cols = st.columns(1)
    
    with cols[0]:
        with st.container(border=True):
            dot_chart = alt.Chart(filtered_df).mark_circle(size=100).encode(
                x=alt.X('mean(FulfillmentRate):Q', title='Avg Fulfillment Rate (%)'),
                y=alt.Y('manufacturerID:N', title='Manufacturer'),
                color='itemCategory:N',
                tooltip=['manufacturerID', 'itemCategory', 'mean(FulfillmentRate):Q']
            ).properties(
                title='Outbound Fulfillment Rate by Manufacturer and Category',
                width=700,
                height=400
            )
            st.altair_chart(dot_chart, use_container_width=True)
            
            
    
    # 5th Row
    # cols = st.columns(1)
    
    # with cols[0]:
    #     with st.container(border=True):
    #         # Remove non-positive values
    #         filtered_df = filtered_df[filtered_df['batteryCapacityWh'] > 0]
    #         # prevent the chart from being dominated by outliers
    #         clip_threshold = filtered_df['batteryCapacityWh'].quantile(0.99)
    #         filtered_df_viz = filtered_df[filtered_df['batteryCapacityWh'] <= clip_threshold]
            
    #         filtered_df_viz['battery_bin'] = pd.cut(
    #             filtered_df_viz['batteryCapacityWh'],
    #             bins=[0, 100, 500, 1000, 2000, clip_threshold],
    #             labels=["0-100", "100-500", "500-1000", "1000-2000", ">2000"]
    #         )
            
    #         bar_chart = alt.Chart(filtered_df_viz).mark_bar().encode(
    #             x=alt.X('battery_bin:N', title='Battery Capacity Range (Wh)', axis=alt.Axis(labelAngle=0)),
    #             y=alt.Y('mean(FulfillmentRate):Q', title='Avg Fulfillment Rate (%)'),
    #             color=alt.Color('battery_bin:N', legend=None),
    #             tooltip=['battery_bin', 'mean(FulfillmentRate):Q']
    #         ).properties(
    #             title='Avg Outbound Fulfillment Rate by Battery Capacity Range',
    #             width=600
    #         )
            
    #         st.altair_chart(bar_chart, use_container_width=True)
            
            #st.write(filtered_df.sort_values(by='batteryCapacityWh', ascending=False))




#%%

#               Store Level Dashboard (if Individual Store)

if view_mode == "Individual Store":
    st.markdown(f"## Store-{selected_store} Metrics" )
    
    # Processing Time
    avg_processing_times = calculate_processing_time(orders_current)
    avg_processing_times_prev = calculate_processing_time(orders_prev)
    delta_units_proc, delta_units_proc_pct = compute_delta(
        pd.DataFrame(
            {"amount": [avg_processing_times, avg_processing_times_prev]}), "amount"
        
        
        )
    
    # Average Order Value
    avg_order_val = calculate_avg_order_value(sales_current)
    avg_order_val_prev = calculate_avg_order_value(sales_prev)
    delta_avg_order, delta_avg_order_pct = compute_delta(
        pd.DataFrame(
            {"amount": [avg_order_val, avg_order_val_prev]}), "amount"
        
        
        )
    
    # Fulfillment Rate from shipments
    fulfillment_rate = calc_fulfillment_rate(sales_current)
    fulfillment_rate_prev = calc_fulfillment_rate(sales_prev)
    delta_fulfillment, delta_fulfillment_pct = compute_delta(pd.DataFrame({"amount": [fulfillment_rate, fulfillment_rate_prev]}), "amount")
    
    
    
    # Total Units Shipped
    units_ordered = orders_current['qtyReceived'].sum()
    units_ordered_prev = orders_prev['qtyReceived'].sum()
    delta_units_ordered, delta_units_ordered_pct = compute_delta(pd.DataFrame({"amount": [units_ordered, units_ordered_prev]}), "amount")
    
    
    # Inventory summary by store
    inv_chart, inv_full= plot_store_inventory_chart(df_inventory, df_products)
    
    
    # Product count per manufacturer
    product_count = inv_full.groupby('manufacturerID')['itemGuid'].nunique().reset_index(name='NumItems')
    
    
    # Merge and Prepare Data for Plotting
    comparison_df = pd.merge(fulfill_manuf_current, fulfill_manuf_prev, on='manufacturerID', how='outer')
    delta_chart, item_chart = create_supplier_delta_chart(comparison_df, product_count)

    

    
    
    # ---- Column 1: KPI Metrics and Order Analysis ---
    cols = st.columns(4)
    
    with cols[0]:
        with st.container(border=True):
            st.metric("Inbound Order Processing Time", format_number(avg_processing_times, "days"),
                      delta=f"{format_number(delta_units_proc)} ({delta_units_proc_pct:+.2f}%)")
    
    with cols[1]:
        with st.container(border=True):
            st.metric("Average Inbound Order Value", format_number(avg_order_val, "money"),
                      delta=f"{format_number(delta_avg_order)} ({delta_avg_order_pct:+.2f}%)")
            
    with cols[2]:
        with st.container(border=True):
            
            time_frame = (end_date - start_date).days
            st.metric(f"Outbound Fulfillment Rate {format_number(time_frame, "days")}", format_number(fulfillment_rate, "percentage"),
                      delta=f"{format_number(delta_fulfillment)} ({delta_fulfillment_pct:+.2f}%)")
            
    with cols[3]:
        with st.container(border=True):
            st.metric("Units Shipped", format_number(units_ordered),
                      delta=f"{format_number(delta_units_ordered)} ({delta_units_ordered_pct:+.2f}%)")
    
    
    
            
    # 2nd Row
    cols = st.columns(1)  
    with cols[0]:
        with st.container(border=True):
            st.altair_chart(inv_chart, use_container_width=True)
    
  
    with st.expander('Low Stock Items',expanded=True):
        
        low_stock = get_low_stock_items(inv_full, threshold_quantile)
        low_stock = low_stock.drop_duplicates(subset=["itemCategory", "manufacturerID", "SubsidiaryID", "quantityAvailable"])

        min_val = 0
        max_val =int(max(low_stock.quantityAvailable)) if not low_stock.empty else 1

        # Ensure max > min
        if max_val <= min_val:
            max_val = min_val + 1
            
        st.dataframe(low_stock,
                      column_order=("itemCategory", "manufacturerID", "SubsidiaryID","quantityAvailable"),
                      hide_index=True,
                      width=None,
                      column_config={
                        "itemCategory": st.column_config.TextColumn(
                            "Product Category",
                        ),
                        "manufacturerID": st.column_config.TextColumn(
                            "Manufacturer",
                        ),
                        "SubsidiaryID": st.column_config.TextColumn(
                            "Store",
                        ),
                        "quantityAvailable": st.column_config.ProgressColumn(
                            "Low Stocks Products",
                            format="%d",
                            min_value=min_val,
                            max_value=max_val,
                          )} 
                      )
            
            
    # 3rd Row
    cols = st.columns(1)
    
    with cols[0]:
        with st.container(border=True):
            st.markdown("#### Supplier Evaluation")
            st.altair_chart(delta_chart, use_container_width=True)
            st.altair_chart(item_chart, use_container_width=True)
    
    
    # 4th Row
    cols = st.columns(1)
    
    with cols[0]:
        with st.container(border=True):
            dot_chart = alt.Chart(filtered_df).mark_circle(size=100).encode(
                x=alt.X('mean(FulfillmentRate):Q', title='Avg Fulfillment Rate (%)'),
                y=alt.Y('manufacturerID:N', title='Manufacturer'),
                color='itemCategory:N',
                tooltip=['manufacturerID', 'itemCategory', 'mean(FulfillmentRate):Q']
            ).properties(
                title='Outbound Fulfillment Rate by Manufacturer and Category',
                width=700,
                height=400
            )
            st.altair_chart(dot_chart, use_container_width=True)
            
            
    # 5th Row
    # cols = st.columns(1)
    
    # with cols[0]:
    #     with st.container(border=True):
    #         # Remove non-positive values
    #         filtered_df = filtered_df[filtered_df['batteryCapacityWh'] > 0]
    #         # prevent the chart from being dominated by outliers
    #         clip_threshold = filtered_df['batteryCapacityWh'].quantile(0.99)
    #         filtered_df_viz = filtered_df[filtered_df['batteryCapacityWh'] <= clip_threshold]
            
    #         filtered_df_viz['battery_bin'] = pd.cut(
    #             filtered_df_viz['batteryCapacityWh'],
    #             bins=[0, 100, 500, 1000, 2000, clip_threshold],
    #             labels=["0-100", "100-500", "500-1000", "1000-2000", ">2000"]
    #         )
            
    #         bar_chart = alt.Chart(filtered_df_viz).mark_bar().encode(
    #             x=alt.X('battery_bin:N', title='Battery Capacity Range (Wh)', axis=alt.Axis(labelAngle=0)),
    #             y=alt.Y('mean(FulfillmentRate):Q', title='Avg Fulfillment Rate (%)'),
    #             color=alt.Color('battery_bin:N', legend=None),
    #             tooltip=['battery_bin', 'mean(FulfillmentRate):Q']
    #         ).properties(
    #             title='Avg Outbound Fulfillment Rate by Battery Capacity Range',
    #             width=600
    #         )
            
    #         st.altair_chart(bar_chart, use_container_width=True)
            
    
        


