import os
import requests
import pandas as pd
import numpy as np

def fetch_weather(lat, lon, start_date, end_date):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,RH2M,PRECTOTCORR,WS10M",
        "community": "RE",
        "longitude": lon,
        "latitude": lat,
        "start": start_date,
        "end": end_date,
        "format": "JSON"
    }
    
    response = requests.get(url, params=params, timeout=35)
    response.raise_for_status()
    data = response.json()
    
    params_data = data["properties"]["parameter"]
    df = pd.DataFrame(params_data)
    
    df = df.replace(-999.0, np.nan)
    
    df.index = pd.to_datetime(df.index, format='%Y%m%d')
    df.index.name = 'date'
    
    iso_cal = df.index.isocalendar()
    df['year'] = iso_cal['year']
    df['epi_week'] = iso_cal['week']
    
    weekly_df = df.groupby(['year', 'epi_week']).agg({
        'T2M': 'mean',
        'RH2M': 'mean',
        'PRECTOTCORR': 'sum',
        'WS10M': 'mean'
    }).reset_index()
    
    weekly_df = weekly_df.rename(columns={
        'T2M': 'T2M_mean',
        'RH2M': 'RH2M_mean',
        'PRECTOTCORR': 'PRECTOTCORR_sum',
        'WS10M': 'WS10M_mean'
    })
    
    # reorder columns to match the request
    # "year, epi_week, T2M_mean, RH2M_mean, PRECTOTCORR_sum, WS10M_mean"
    weekly_df = weekly_df[['year', 'epi_week', 'T2M_mean', 'RH2M_mean', 'PRECTOTCORR_sum', 'WS10M_mean']]
    
    return weekly_df

if __name__ == "__main__":
    lat = 31.5204
    lon = 74.3587
    start_date = "20100101"
    end_date = "20231231"
    
    weekly_data = fetch_weather(lat, lon, start_date, end_date)
    
    os.makedirs("data/raw", exist_ok=True)
    weekly_data.to_csv("data/raw/nasa_power_raw.csv", index=False)
