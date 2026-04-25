import numpy as np
import pandas as pd


#======================================================================================

def lag_features(df):

    df=df.sort_values(by=["district", "epi_week","year"]).reset_index(drop=True)

    df["t1_cases"]=df.groupby("district")["cases"].shift(1)
    df["t2_cases"]=df.groupby("district")["cases"].shift(2)
    
    df["T2m_lag1"]=df.groupby("district")["T2M_mean"].shift(1)

    df["PRECTOTCORR_lag1"]=df.groupby("district")["PRECTOTCORR_sum"].shift(1)
    df["PRECTOTCORR_lag2"]=df.groupby("district")["PRECTOTCORR_sum"].shift(2)

    df=df.dropna(subset=["t1_cases", "t2_cases"]).reset_index(drop=True)
    return df



#===========================================================================================

def water_proxy(df):

    df=df.sort_values(by=["district", "epi_week","year"]).reset_index(drop=True)

    df["water_proxy"]=(df.groupby("district")["PROCTOTCORR_sum"]
                        .transform(lambda elem:elem.rolling(window=2,min_periods=1).sum()))
    
    return df

#===========================================================================================

def HandleDataInconsistency(data):
        
    data["district"] = data["district"].ffill()
    data["month"] = data["month"].ffill()

    data["cases"] = data["cases"].interpolate(method="linear")
    data["deaths"] = data["deaths"].interpolate(method="linear")


    data = data.drop_duplicates()

    data["district"] = data["district"].str.lower().str.strip()


    data["cases"] = data["cases"].clip(lower=0)
    data["deaths"] = data["deaths"].clip(lower=0)


    data = data[(data["epi_week"] >= 1) & (data["epi_week"] <= 52)]
    data = data[(data["month_num"] >= 1) & (data["month_num"] <= 12)]


    data = data.sort_values(["district", "year", "epi_week"])


    assert data["month_num"].between(1, 12).all()
    assert data["epi_week"].between(1, 52).all()

    return data

#===========================================================================================

def encyclicEncoding(data):

    data["month_sin"] = np.sin(2 * np.pi * data["month_num"] / 12)
    data["month_cos"] = np.cos(2 * np.pi * data["month_num"] / 12)
    data["week_sin"] = np.sin(2 * np.pi * data["epi_week"] / 52)
    data["week_cos"] = np.cos(2 * np.pi * data["epi_week"] / 52)

    return data