import requests
import pandas as pd
import time
from datetime import datetime

# ========== 获取全市场代码 ==========
def get_all_stock_list():
    print("[INFO] 获取全市场股票列表...")
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": 1, "pz": 5000, "po": 1, "np": 1,
        "fltt": 2, "invt": 2, "fid": "f12",
        "fs": "m:1 t:2,m:0 t:6,m:0 t:80",  # 主板+北交所
        "fields": "f12,f14"
    }
    r = requests.get(url, params=params)
    data = r.json()["data"]["diff"]
    df = pd.DataFrame(data)
    df = df.rename(columns={"f12": "code", "f14": "name"})
    df = df[~df["name"].str.contains("ST")]
    df = df[~df["code"].str.startswith(("30", "68"))]
    return df


# ========== 获取单只股票近20日K线 ==========
def get_kline(code, limit=20):
    secid = f"{'0' if code.startswith('6') else '1'}.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": 101,
        "fqt": 1,
        "end": "",
        "lmt": limit
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json().get("data", {})
        klines = data.get("klines", [])
        if not klines:
            return None
        df = pd.DataFrame([k.split(",") for k in klines],
                          columns=["date", "open", "close", "high", "low", "volume", "amount", "pct_chg"])
        df[["open", "close", "volume"]] = df[["open", "close", "volume"]].astype(float)
        return df
    except:
        return None


# ========== 筛选逻辑 ==========
def pick_potential_stocks(date_str):
    all_stocks = get_all_stock_list()
    results = []
    total = len(all_stocks)
    print(f"[INFO] 共 {total} 支股票，将逐一分析 {date_str} 的数据...")

    for idx, row in all_stocks.iterrows():
        code, name = row["code"], row["name"]
        df = get_kline(code, limit=30)
        if df is None or len(df) < 10:
            continue

        df["MA5"] = df["close"].rolling(5).mean()
        df["MA10"] = df["close"].rolling(10).mean()
        df["VOL5"] = df["volume"].rolling(5).mean()

        # 找出指定日期
        day_row = df[df["date"] == datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")]
        if day_row.empty:
            continue

        i = day_row.index[0]
        if i < 10:  # 数据不足以计算均线
            continue

        today = df.loc[i]
        yesterday = df.loc[i - 1]

        if (
            today["MA5"] >= today["MA10"] and
            yesterday["MA5"] <= yesterday["MA10"] and  # 金叉
            today["volume"] > 1.5 * today["VOL5"] and
            1 < (today["volume"] / today["VOL5"]) < 10 and
            today["close"] > today["open"]
        ):
            results.append({
                "代码": code,
                "名称": name,
                "日期": today["date"],
                "收盘价": today["close"],
                "成交量": today["volume"],
                "5日均量": today["VOL5"],
                "MA5": today["MA5"],
                "MA10": today["MA10"]
            })

        if idx % 200 == 0:
            print(f"  → 已处理 {idx}/{total} ({len(results)} 命中)")
        time.sleep(0.05)

    df_result = pd.DataFrame(results)
    if df_result.empty:
        print("\n[RESULT] 没有股票符合筛选条件。")
    else:
        df_result = df_result.sort_values("收盘价", ascending=False)
        df_result.to_csv(f"potential_stocks_{date_str}.csv", index=False, encoding="utf-8-sig")
        print(f"\n[RESULT] {date_str} 次日潜力股：{len(df_result)} 只")
        print(df_result)
        print(f"\n已保存至 potential_stocks_{date_str}.csv")


if __name__ == "__main__":
    date_str = input("请输入日期（如 20251016）：").strip()
    pick_potential_stocks(date_str)
