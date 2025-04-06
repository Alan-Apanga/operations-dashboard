# -*- coding: utf-8 -*-
"""
Created on Fri Apr  4 15:06:17 2025

@author: alann
"""

import pandas as pd

import glob

import streamlit as st
import altair as alt


#%%


st.set_page_config(
    page_title="Dashboard for Operations Managers",
    page_icon=":trophy:",
    layout="wide",
    initial_sidebar_state="expanded")

alt.themes.enable("dark")



#%%

path = './data/*.csv'
csv_files = sorted(glob.glob(path))  
dfs = [pd.read_csv(file) for file in csv_files]



# Assuming dfs is a list containing the DataFrames
df_inventory = dfs[0]  # Inventory Data
df_orders = dfs[2]  # Purchase Order Data
df_shipments = dfs[3]  # Shipment Data



# check for duplicates
# df_inventory.duplicated().sum() 
# df_orders.duplicated().sum() 
# df_shipments.duplicated().sum() 

#%%

with st.sidebar:
    st.title('💻 Operations Dashboard')
    
    
    # Store selection
    store_list = ['A', 'G', 'J']
    selected_store = st.selectbox('Select a store', store_list)
    
    
    # Load DataFrames based on store selection
    if selected_store == 'A':
        df_inventory = dfs[0]  # Inventory Data
        df_orders = dfs[2]  # Purchase Order Data
        df_shipments = dfs[3]  # Shipment Data
        
    elif selected_store == 'G':
        df_inventory = dfs[4]  # Inventory Data
        df_orders = dfs[6]  # Purchase Order Data
        df_shipments = dfs[7]  # Shipment Data
        
    elif selected_store == 'J':
        df_inventory = dfs[8]  # Inventory Data
        df_orders = dfs[10]  # Purchase Order Data
        df_shipments = dfs[11]  # Shipment Data
    
    
    
    # Convert tranDate column to datetime format for filtering
    df_orders['createdDate'] = pd.to_datetime(df_orders['createdDate'], errors='coerce')
    df_orders['tranDate'] = pd.to_datetime(df_orders['tranDate'], errors='coerce')
    df_orders['plannedDate'] = pd.to_datetime(df_orders['plannedDate'], errors='coerce')
    
    df_shipments['createdDate'] = pd.to_datetime(df_shipments['createdDate'], errors='coerce')
    df_shipments['tranDate'] = pd.to_datetime(df_shipments['tranDate'], errors='coerce')
    df_shipments['expectedReceiptDate'] = pd.to_datetime(df_shipments['expectedReceiptDate'], errors='coerce')
    df_shipments['shipDate'] = pd.to_datetime(df_shipments['shipDate'], errors='coerce')

    
    
    
    year_list = sorted(
    set(df_orders['tranDate'].dt.year.dropna().unique()).union(
        set(df_shipments['tranDate'].dt.year.dropna().unique())
    ),
    reverse=True
    )

    # Year selection
    selected_year = st.selectbox('Select a year', year_list, index=len(year_list)-1)
    
    
    
    
    # # Filter sales orders for the selected year
    # df_selected = df_sales_orders[df_sales_orders['tranDate'].dt.year == selected_year]
    
    
    
    # # Sort the filtered dataframe by 'tranDate'
    # df_selected_sorted = df_selected.sort_values(by="tranDate", ascending=False)
    
#%%



#               Order Fulfillment Rate



def fulfillment_rate_calc(df_shipments, year):
    """
    Calculate the order fulfillment rate for a given year based on `tranDate`.

    Parameters:
    df_shipments (DataFrame): Shipment data
    year (int): Year to filter the data

    Returns:
    float: Order fulfillment rate in percentage
    """

    # Ensure date columns are in datetime format
    date_columns = ['createdDate', 'tranDate', 'expectedReceiptDate', 'shipDate']
    for col in date_columns:
        if col in df_shipments.columns:
            df_shipments[col] = pd.to_datetime(df_shipments[col], errors='coerce')
    
    
    # Filter data for the given year based on `tranDate`
    df_filtered = df_shipments[df_shipments['tranDate'].dt.year == year]
    
    if df_filtered.empty:
        return 0.0  # Return 0% if no shipments exist for the year
    
    
    # Calculate fulfillment rate safely
    total_ordered = df_filtered['qtyOrdered'].sum()
    total_received = df_filtered['qtyReceived'].sum()

    if total_ordered == 0:
        fulfillment_rate = 0  # Avoid division by zero
    else:
        fulfillment_rate = (total_received / total_ordered) * 100

    return round(fulfillment_rate, 2)  # Return rounded percentage

    
#%%


def format_number(num, unit=None):
    """
    Format a number by appending a unit (% or hours).

    Parameters:
    - num (float or int): The number to format.
    - unit (str or None): Choose 'percentage' for %, 'hours' for " hours", or None for plain numbers.

    Returns:
    - str: Formatted number with the chosen unit.
    """
    rounded_num = round(num)
    formatted = str(rounded_num)  # Keep number as is

    if unit == "percentage":
        return f"{formatted}%"
    elif unit == "hours":
        return f"{formatted} Hrs"
    
    return formatted  # Return without any unit if `unit=None`



#%%

def on_rate_calc(df_shipments, year):
    
    # Ensure date columns are in datetime format
    date_columns = ['createdDate', 'tranDate', 'expectedReceiptDate', 'shipDate']
    for col in date_columns:
        if col in df_shipments.columns:
            df_shipments[col] = pd.to_datetime(df_shipments[col], errors='coerce')
    
    # Filter data for the given year based on `tranDate`
    df_filtered = df_shipments[df_shipments['tranDate'].dt.year == year]
    
    if df_filtered.empty:
        return 0.0  # Avoid division by zero if no data
    
    # Calculate on-time delivery rate (avoiding NaT issues)
    df_filtered['on_time'] = df_filtered['shipDate'] <= df_filtered['expectedReceiptDate']
    
    on_time_rate = (df_filtered['on_time'].sum() / len(df_filtered)) * 100
    
    
    return round(on_time_rate, 2)  # Return rounded percentage


#%%



def average_leadtime_calc(df_shipments, year):
    """
    Calculate the average lead time (in hours) for a given year.

    Parameters:
    - df_shipments (DataFrame): Shipment data
    - year (int): Year to filter the data by tranDate

    Returns:
    - float: Average lead time in hours (can be negative if shipped early)
    """

    # Ensure relevant date columns are datetime
    # date_columns = ['createdDate', 'tranDate', 'expectedReceiptDate', 'shipDate']
    # for col in date_columns:
    #     if col in df_shipments.columns:
    #         df_shipments[col] = pd.to_datetime(df_shipments[col], errors='coerce')

    # Filter by year based on tranDate
    df_filtered = df_shipments[df_shipments['tranDate'].dt.year == year]

    if df_filtered.empty:
        return 0.0  # Avoid division by zero if no data

    # Calculate delay time (as timedelta)
    df_filtered['delay_time'] = df_filtered['shipDate'] - df_filtered['expectedReceiptDate']

    # Drop rows where delay_time is NaT (due to missing dates)
    df_valid = df_filtered[df_filtered['delay_time'].notna()]

    if df_valid.empty:
        return 0.0

    # Compute average lead time in hours
    avg_lead_time_hours = df_valid['delay_time'].mean().total_seconds() / 3600

    return round(avg_lead_time_hours, 2)

#%%






def plot_inventory(df, period):
    """
    This method calculates inventory totals and plots a color-encoded
    stacked bar chart using Altair.
    
    Parameters:
    df (pd.DataFrame): Input dataframe with inventory columns.
    """
    
    
    # Calculate summary totals
    cols = ['quantityAvailable', 'quantityBackOrdered', 'quantityOnHand', 'quantityOnOrder']
    inv_summary = df[cols].sum().sort_values(ascending=False)
    
    # Prepare data for Altair
    summary_df = inv_summary.reset_index()
    summary_df.columns = ['Inventory Level', 'Total']
    
    # Create Altair stacked bar chart (mimicking heatmap stacking by x-axis)
    chart = alt.Chart(summary_df).mark_bar().encode(
        x=alt.X('Inventory Level:N', title='Inventory Type'),
        y=alt.Y('Total:Q', title='Total Quantity'),
        color=alt.Color('Inventory Level:N', legend=None)
    ).properties(
        width=600,
        height=400,
        title=f'Period of {period[0]} '
    )
    
    text = chart.mark_text(
        align='center',
        baseline='bottom',
        dy=-5  # offset
    ).encode(
        text='Total:Q'
    )
    
    return chart + text



#%%


def plot_lead_time_distribution(df, year):
    """
    Filters data for a given year and plots the lead time distribution using Altair.

    Parameters:
    df (pd.DataFrame): DataFrame with 'createdDate' and 'tranDate' columns (datetime format).
    year (int): Year to filter on based on 'createdDate'.

    Returns:
    alt.Chart: An Altair chart showing lead time distribution.
    """
    # Ensure datetime format
    df['createdDate'] = pd.to_datetime(df['createdDate'], errors='coerce')
    df['tranDate'] = pd.to_datetime(df['tranDate'], errors='coerce')

    # Filter by year
    df_year = df[df['createdDate'].dt.year == year].copy()

    # Compute lead time
    df_year['leadTime'] = (df_year['tranDate'] - df_year['createdDate']).dt.days

    # Drop rows with missing or negative lead times
    df_clean = df_year.dropna(subset=['leadTime'])
    df_clean = df_clean[df_clean['leadTime'] >= 0]

    if df_clean.empty:
        print(f"No valid lead time data for the year {year}.")
        return None

    # Altair histogram
    chart = alt.Chart(df_clean).mark_bar(color='steelblue').encode(
        alt.X('leadTime:Q', bin=alt.Bin(maxbins=20), title='Lead Time (Days)'),
        alt.Y('count()', title='Frequency')
    ).properties(
        width=600,
        height=400,
        title=f'Lead Time Distribution for Orders in {year}'
    )

    return chart






#%%
# =============================================================================
#              Main Page Display(App layout)
# =============================================================================

# st.title("📊 Filtered Dataframes")

# df_sel = df_orders[df_orders['tranDate'].dt.year == selected_year]

# st.dataframe(df_sel) 



col = st.columns((2, 4.5, 2), gap='medium')



with col[0]:
       
    # Fulfillment Rate
    st.markdown('#### <u>KPI</u>', unsafe_allow_html=True)
    order_fulfillment_rate = fulfillment_rate_calc(df_shipments, selected_year)
    
    if order_fulfillment_rate is None or order_fulfillment_rate < 0:
        fulfillment_rate = '-'  # Prevent errors
        
    elif selected_year > 2021:
        fulfillment_rate = format_number(order_fulfillment_rate, "percentage")
        
    else:
        fulfillment_rate = '-'

    
    st.metric(label="Outbound Fulfillment Rate", value=fulfillment_rate, delta=None )
    
    
    
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        
     
    
    
    
    # On-Time Delivery Rate
    rate = on_rate_calc(df_shipments, selected_year)
    if rate is None or rate < 0:
        ontime_delivery_rate = '-'  # Prevent errors
        
    elif selected_year > 2021:
        ontime_delivery_rate = format_number(rate, "percentage")
        
    else:
        ontime_delivery_rate = '-'

    
    st.metric(label="Outbound On-Time Delivery Rate", value=ontime_delivery_rate, delta=None )
        
    
    st.markdown("<br>", unsafe_allow_html=True)  # Spacing
    
    
    
    
    
    # Average Lead Time
    lead_time = average_leadtime_calc(df_shipments, selected_year)
    if lead_time is None or rate < 0:
        ontime_delivery_rate = '-'  # Prevent errors
        
    elif selected_year > 2021:
        avg_lead_time = format_number(lead_time, "hours")
        
    else:
        avg_lead_time = '-'

    
    st.metric(label="Inbound Average Lead Time in Hours", value=avg_lead_time, delta=None )

#%%
    

with col[1]:
    # st.markdown('#### Inventory Levels')
    st.markdown("<h4 style='text-align: center;'><u>Inventory Level</u></h4>", unsafe_allow_html=True)
    
    if selected_year > 2021: 
        bar_chart = plot_inventory(df_inventory, year_list)
        st.altair_chart(bar_chart, use_container_width=True)
    
    else:
        st.error("Please select a valid year from the list in the sidebar.")

    
    
    #st.markdown("<br>", unsafe_allow_html=True)  # Spacing
    st.markdown("<hr>", unsafe_allow_html=True)

    chart = plot_lead_time_distribution(df_orders, selected_year)
    
    if chart and (selected_year > 2021):
        st.altair_chart(chart, use_container_width=True)
   

#%%


with col[2]:
    st.markdown("<h4 style='text-align: center;'><u>Extras</u></h4>", unsafe_allow_html=True)
    
    with st.expander('About', expanded=True):
        st.write('''
            - Inventory: Assumed to be of latest period `2023`.
            - :orange[**Missing Data**]: `actualShipDate` used instead of `shipDate` to calculate `Outbound On-Time Rate` for the selected year. Negative values indicate that the item was shipped earlier than expected.
            - :orange[**Inbound Lead Time**]: Calculated using `createdDate` and `tranDate` from purchase orders data.
            - :orange[**Filtering**]: Data is filtered for the **selected year**.
        ''')



































#%%








































