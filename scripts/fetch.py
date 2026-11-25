# -*- coding: utf-8 -*-
"""
抓取板块与指数日线，增量写入 data/raw/<组>/<代码>.csv（列：date,open,high,low,close）。
数据源：
  申万一级/二级  -> 申万宏源官网（akshare.index_hist_sw）
  东财行业/概念  -> 东方财富 K 线接口（板块代码 BKxxxx）
  宽基指数      -> 东方财富 K 线接口
本地和 GitHub Actions 都能跑：python scripts/fetch.py
"""
import os, sys, time, json, datetime as dt
import pandas as pd, requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
START = '20140101'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
      'Referer': 'https://quote.eastmoney.com/'}
S = requests.Session(); S.headers.update(UA)

INDEXES = [  # (东财 secid, 代码, 名称)
    ('1.000985', 'sh000985', '中证全指'), ('1.000001', 'sh000001', '上证指数'), ('1.000300', 'sh000300', '沪深300'),
    ('1.000905', 'sh000905', '中证500'), ('1.000852', 'sh000852', '中证1000'), ('0.399001', 'sz399001', '深证成指'),
    ('0.399006', 'sz399006', '创业板指'), ('1.000688', 'sh000688', '科创50'), ('2.932000', 'csi932000', '中证2000'),
    ('1.000922', 'sh000922', '中证红利'),
]

def log(*a): print(*a, flush=True)

def retry(fn, *a, tries=3, **k):
    err = None
    for i in range(tries):
        try:
            return fn(*a, **k)
        except Exception as e:
            err = e; time.sleep(2 + 4 * i)
    raise err

def last_date(group, code):
    p = os.path.join(RAW, group, f'{code}.csv')
    if not os.path.exists(p): return None
    try:
        return pd.read_csv(p, usecols=['date'])['date'].max()
    except Exception:
        return None

def save(group, code, df):
    if df is None or df.empty: return 0
    os.makedirs(os.path.join(RAW, group), exist_ok=True)
    p = os.path.join(RAW, group, f'{code}.csv')
    df = df[['date', 'open', 'high', 'low', 'close']].copy()
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    for c in ['open', 'high', 'low', 'close']: df[c] = pd.to_numeric(df[c], errors='coerce').round(3)
    df = df.dropna(subset=['close'])
    if os.path.exists(p):
        df = pd.concat([pd.read_csv(p), df]).drop_duplicates('date', keep='last')
    df.sort_values('date').to_csv(p, index=False)
    return len(df)

def beg_for(group, code):
    d = last_date(group, code)
    if not d: return START
    return (pd.Timestamp(d) - pd.Timedelta(days=10)).strftime('%Y%m%d')

# ---------- 东方财富 K 线 ----------
def em_kline(secid, beg):
    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
    params = {'secid': secid, 'fields1': 'f1,f2,f3,f4,f5,f6', 'fields2': 'f51,f52,f53,f54,f55,f56,f57',
              'klt': '101', 'fqt': '0', 'beg': beg, 'end': '20500101', 'lmt': '1000000'}
    r = S.get(url, params=params, timeout=20); r.raise_for_status()
    kl = ((r.json() or {}).get('data') or {}).get('klines') or []
    rows = [k.split(',')[:5] for k in kl]
    return pd.DataFrame(rows, columns=['date', 'open', 'close', 'high', 'low'])

def em_board_list(fs):
    """fs: m:90+t:2 行业, m:90+t:3 概念"""
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    out, pn = [], 1
    while True:
        params = {'pn': pn, 'pz': 100, 'po': 1, 'np': 1, 'fltt': 2, 'invt': 2, 'fid': 'f3', 'fs': fs, 'fields': 'f12,f14'}
        r = S.get(url, params=params, timeout=20); r.raise_for_status()
        d = (r.json() or {}).get('data') or {}
        diff = d.get('diff') or []
        if isinstance(diff, dict): diff = list(diff.values())
        out += [(x['f12'], x['f14']) for x in diff]
        if not diff or len(out) >= d.get('total', 0): break
        pn += 1; time.sleep(0.3)
    return out

# ---------- 申万 ----------
def sw_hist(code):
    import akshare as ak
    df = ak.index_hist_sw(symbol=code, period='day')
    return df.rename(columns={'日期': 'date', '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close'})

def main():
    names, ok, fail = [], 0, []
    t0 = time.time()

    for secid, code, name in INDEXES:
        try:
            n = save('idx', code, retry(em_kline, secid, beg_for('idx', code))); ok += 1
            names.append(('宽基指数', 'idx', code, name, ''))
        except Exception as e:
            fail.append(f'idx {name}: {e}')
    log(f'宽基 done ok={ok} fail={len(fail)} {time.time()-t0:.0f}s')

    sw = pd.read_csv(os.path.join(ROOT, 'scripts', 'sw_codes.csv'), dtype=str).fillna('')
    for _, r in sw.iterrows():
        grp = 'sw1' if r.level == '1' else 'sw2'
        try:
            save(grp, r.code, retry(sw_hist, r.code)); ok += 1
            names.append(('申万一级' if grp == 'sw1' else '申万二级', grp, r.code, r['name'], r.parent))
        except Exception as e:
            fail.append(f'{grp} {r["name"]}: {e}')
        time.sleep(0.4)
    log(f'申万 done ok={ok} fail={len(fail)} {time.time()-t0:.0f}s')

    for grp, label, fs in [('emi', '东财行业', 'm:90+t:2'), ('emc', '东财概念', 'm:90+t:3')]:
        try:
            boards = retry(em_board_list, fs)
        except Exception as e:
            fail.append(f'{label} 列表: {e}'); boards = []
        log(f'{label} {len(boards)} 个')
        for code, name in boards:
            try:
                save(grp, code, retry(em_kline, f'90.{code}', beg_for(grp, code))); ok += 1
                names.append((label, grp, code, name, ''))
            except Exception as e:
                fail.append(f'{grp} {name}: {e}')
            time.sleep(0.25)
        log(f'{label} done ok={ok} fail={len(fail)} {time.time()-t0:.0f}s')

    # 名称表：保留以前抓到过的（本次失败的也不丢）
    p = os.path.join(RAW, 'names.csv')
    new = pd.DataFrame(names, columns=['group_label', 'group', 'code', 'name', 'parent'])
    if os.path.exists(p):
        old = pd.read_csv(p, dtype=str).fillna('')
        new = pd.concat([old, new]).drop_duplicates(['group', 'code'], keep='last')
    new.to_csv(p, index=False)

    log(f'完成：成功 {ok}，失败 {len(fail)}，用时 {time.time()-t0:.0f}s')
    for f in fail[:30]: log('  失败', f)
    total = ok + len(fail)
    if total == 0 or ok / total < 0.5:
        log('超过一半失败，数据源可能拦截了当前网络'); sys.exit(1)

if __name__ == '__main__':
    main()
