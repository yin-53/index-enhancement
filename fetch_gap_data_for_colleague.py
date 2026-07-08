"""
Standalone Wind data-fetch script - no other files or setup needed beyond
WindPy / Wind Terminal already being installed and logged in on this machine.

WHAT THIS DOES
--------------
Fetches 2 years of fund NAV data (2023-07-01 to 2025-06-30) and the matching
benchmark index data, for 5 benchmark groups used in an index-enhanced fund
analysis project (CSI500 / CSI800 / CSI1000 / CSI2000 / CNI2000).

HOW TO RUN
----------
Just run this file top to bottom - e.g. `python fetch_gap_data_for_colleague.py`,
or open it in Jupyter/Spyder and run all. No edits needed.

If it stops partway through with a Wind error (most likely a quota limit),
that's fine - whatever finished before the error is already saved. Just say
which group it stopped at when you send the files back.

WHAT TO SEND BACK
------------------
Once it's done (or stops), zip up this whole folder and send it back - every
CSV file it created is needed, named like:
    fund_nav_data_csi500_gap.csv
    index_daily_returns_csi500_gap.csv
    ... (one pair per group)
"""

from WindPy import *
import pandas as pd
import os

w.start()

GAP_START = "2023-07-01"
GAP_END = "2025-06-30"
CHUNK_MONTHS = 1  # fetches in small monthly pieces so a tight quota doesn't kill the whole run

# --- fund universe (must match the main project's lists exactly) ---

fund_codes_CSI500 = [
    "006729.OF", "006730.OF", "014305.OF", "014306.OF", "004945.OF", "561550.OF", "001556.OF", "001557.OF", "159610.OF",
    "006682.OF", "016935.OF", "012080.OF", "012081.OF", "002316.OF", "006048.OF", "007413.OF", "003016.OF", "014344.OF", "014155.OF", "003578.OF",
    "003986.OF", "014156.OF", "006593.OF", "006594.OF", "502000.OF", "009300.OF", "015508.OF", "005994.OF", "002906.OF", "007089.OF", "002907.OF", "005062.OF",
    "000478.OF", "161017.OF", "004192.OF", "013332.OF", "004193.OF", "001050.OF", "016854.OF", "021186.OF"
]

fund_codes_CSI800 = ["016276.OF", "022513.OF", "010673.OF"]

fund_codes_CSI1000 = [
    "018013.OF", "018014.OF", "015466.OF", "017094.OF", "017095.OF", "017953.OF", "017954.OF", "019240.OF", "019241.OF", "005313.OF",
    "017644.OF", "005314.OF", "017645.OF", "017846.OF", "006165.OF", "015867.OF", "017847.OF", "006166.OF", "015868.OF", "019555.OF", "014201.OF",
    "014202.OF", "018157.OF", "018158.OF", "159680.OF", "161039.OF", "013331.OF", "017919.OF", "017920.OF", "016936.OF", "016937.OF", "016785.OF", "016942.OF", "016943.OF",
    "004194.OF", "004195.OF", "015784.OF"
]

fund_codes_CSI2000 = ["019918.OF", "019919.OF", "159552.OF"]

fund_codes_CNI2000 = ["019318.OF", "019319.OF", "018653.OF"]

FUND_GROUPS = {
    "CSI500":  {"fund_codes": fund_codes_CSI500,  "index_code": "000905.SH"},
    "CSI800":  {"fund_codes": fund_codes_CSI800,  "index_code": "000906.SH"},
    "CSI1000": {"fund_codes": fund_codes_CSI1000, "index_code": "000852.SH"},
    "CSI2000": {"fund_codes": fund_codes_CSI2000, "index_code": "932000.CSI"},
    "CNI2000": {"fund_codes": fund_codes_CNI2000, "index_code": "399303.SZ"},
}

# --- fetch functions (identical output format to the main project, so the
#     files combine cleanly with the requester's existing CSVs) ---


def get_fund_nav_data(fund_codes, start_date, end_date, save_path=None):
    error_code, nav_data = w.wsd(fund_codes, "NAV_acc", start_date, end_date, "", usedf=True)
    if error_code != 0:
        print(error_code)
        print(nav_data)
        return None

    name_error_code, name_data = w.wss(fund_codes, "sec_name", usedf=True)
    if name_error_code != 0:
        print(name_error_code)
        print(name_data)
        return None

    chart = nav_data.T
    chart.index.name = "fund_code"
    chart.columns = [pd.Timestamp(col).strftime("%Y-%m-%d") for col in chart.columns]

    fund_names = name_data.iloc[:, 0].reindex(chart.index)
    chart = pd.concat([fund_names.rename("fund_name"), chart], axis=1)

    if save_path:
        chart.to_csv(save_path, index=True)

    return chart


def get_index_daily_returns(index_code, start_date, end_date, save_path=None):
    error_code, data = w.wsd(index_code, "pct_chg", start_date, end_date, "", usedf=True)
    if error_code != 0:
        print(error_code)
        print(data)
        return None

    if save_path:
        data.to_csv(save_path, index=True)

    return data


# --- chunked fetch: small monthly pieces, auto-stitched into one final file ---


def date_chunks(start_date, end_date, chunk_months=CHUNK_MONTHS):
    chunks = []
    current_start = pd.Timestamp(start_date)
    final_end = pd.Timestamp(end_date)
    while current_start <= final_end:
        current_end = min(
            current_start + pd.DateOffset(months=chunk_months) - pd.Timedelta(days=1),
            final_end,
        )
        chunks.append((current_start.strftime("%Y-%m-%d"), current_end.strftime("%Y-%m-%d")))
        current_start = current_end + pd.Timedelta(days=1)
    return chunks


def fetch_nav_chunked(fund_codes, start_date, end_date, final_save_path):
    if os.path.exists(final_save_path):
        print(f"  {final_save_path} already exists - skipping (delete it if you want to refetch).")
        return pd.read_csv(final_save_path, index_col=0)

    chunks = date_chunks(start_date, end_date)
    chunk_frames = []
    for i, (c_start, c_end) in enumerate(chunks):
        chunk_path = f"{final_save_path.replace('.csv', '')}_chunk{i:03d}.csv"
        if os.path.exists(chunk_path):
            print(f"  chunk {i + 1}/{len(chunks)} ({c_start} to {c_end}): already cached")
            chunk_data = pd.read_csv(chunk_path, index_col=0)
        else:
            print(f"  chunk {i + 1}/{len(chunks)} ({c_start} to {c_end}): fetching...")
            chunk_data = get_fund_nav_data(fund_codes, c_start, c_end, save_path=chunk_path)
            if chunk_data is None:
                print(f"  Stopped at chunk {i + 1}/{len(chunks)} - see Wind error above.")
                return None
        chunk_frames.append(chunk_data)

    fund_names = chunk_frames[0]["fund_name"]
    date_frames = [cf.drop(columns=["fund_name"]) for cf in chunk_frames]
    combined_dates = pd.concat(date_frames, axis=1)
    combined = pd.concat([fund_names, combined_dates[sorted(combined_dates.columns)]], axis=1)
    combined.to_csv(final_save_path, index=True)
    print(f"  All chunks complete -> {final_save_path}")
    return combined


def fetch_index_chunked(index_code, start_date, end_date, final_save_path):
    if os.path.exists(final_save_path):
        print(f"  {final_save_path} already exists - skipping (delete it if you want to refetch).")
        return pd.read_csv(final_save_path, index_col=0)

    chunks = date_chunks(start_date, end_date)
    chunk_frames = []
    for i, (c_start, c_end) in enumerate(chunks):
        chunk_path = f"{final_save_path.replace('.csv', '')}_chunk{i:03d}.csv"
        if os.path.exists(chunk_path):
            print(f"  chunk {i + 1}/{len(chunks)} ({c_start} to {c_end}): already cached")
            chunk_data = pd.read_csv(chunk_path, index_col=0)
        else:
            print(f"  chunk {i + 1}/{len(chunks)} ({c_start} to {c_end}): fetching...")
            chunk_data = get_index_daily_returns(index_code, c_start, c_end, save_path=chunk_path)
            if chunk_data is None:
                print(f"  Stopped at chunk {i + 1}/{len(chunks)} - see Wind error above.")
                return None
        chunk_frames.append(chunk_data)

    combined = pd.concat(chunk_frames, axis=0).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    combined.to_csv(final_save_path, index=True)
    print(f"  All chunks complete -> {final_save_path}")
    return combined


# --- run the fetch for every group ---

if __name__ == "__main__":
    for group_name, group in FUND_GROUPS.items():
        print(f"=== {group_name} ===")

        print("Fund NAV data:")
        fetch_nav_chunked(
            group["fund_codes"], GAP_START, GAP_END,
            final_save_path=f"fund_nav_data_{group_name.lower()}_gap.csv",
        )

        print("Benchmark index data:")
        fetch_index_chunked(
            group["index_code"], GAP_START, GAP_END,
            final_save_path=f"index_daily_returns_{group_name.lower()}_gap.csv",
        )
        print()

    print("Done (or stopped on an error above). Zip this whole folder and send it back.")
