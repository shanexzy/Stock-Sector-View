# -*- coding: utf-8 -*-
"""
用 Tushare 抓取板块与指数日线，增量写入 data/raw_ts/<组>/<代码>.csv（列：date,open,high,low,close）。
  宽基指数   index_daily
  申万一/二级 sw_daily（首次按代码抓历史，之后按交易日一次拿全部）
  同花顺行业/概念 ths_daily（同上）
  个股日线（算广度用，只保留最近 80 个交易日） daily
  成分股     index_member_all（申万）、ths_member（同花顺，每周刷新）
token 从环境变量 TUSHARE_TOKEN 读取。本地运行：先设置环境变量，再 python scripts/fetch_ts.py
"""
import os, sys, time, datetime as dt
import pandas as pd
import tushare as ts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw_ts')
START = '20140101'
STK_KEEP = 80
INDEXES = [('000985.CSI', '中证全指'), ('000001.SH', '上证指数'), ('000300.SH', '沪深300'), ('000905.SH', '中证500'),
           ('000852.SH', '中证1000'), ('932000.CSI', '中证2000'), ('399001.SZ', '深证成指'), ('399006.SZ', '创业板指'),
           ('000688.SH', '科创50'), ('000922.CSI', '中证红利')]

pro = ts.pro_api(os.environ.get('TUSHARE_TOKEN', ''))
NCALL = 0

def log(*a): print(*a, flush=True)

def q(api, **kw):
    global NCALL
    err = None
    for i in range(4):
        try:
            NCALL += 1
            df = pro.query(api, **kw)
            time.sleep(0.12)
            return df
        except Exception as e:
            err = e; time.sleep(3 + 10 * i)
    raise err

def today(): return dt.date.today().strftime('%Y%m%d')

def chunks(start, end, years=5):
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    while s <= e:
        t = min(e, s + pd.DateOffset(years=years) - pd.Timedelta(days=1))
        yield s.strftime('%Y%m%d'), t.strftime('%Y%m%d')
        s = t + pd.Timedelta(days=1)

def path(group, code): return os.path.join(RAW, group, f'{code}.csv')

def load(group, code):
    p = path(group, code)
    if not os.path.exists(p): return None
    try: return pd.read_csv(p, dtype={'date': str})
    except Exception: return None

def norm(df, date_col='trade_date'):
    df = df.rename(columns={date_col: 'date'})
    df['date'] = pd.to_datetime(df['date'].astype(str)).dt.strftime('%Y-%m-%d')
    return df[['date', 'open', 'high', 'low', 'close']]

def save(group, code, new, old=None):
    if new is None or new.empty: return
    os.makedirs(os.path.join(RAW, group), exist_ok=True)
    df = new if old is None else pd.concat([old, new])
    df = df.dropna(subset=['close']).drop_duplicates('date', keep='last').sort_values('date')
    for c in ['open', 'high', 'low', 'close']: df[c] = pd.to_numeric(df[c], errors='coerce').round(3)
    df.to_csv(path(group, code), index=False)

def history(api, code, start):
    parts = [q(api, ts_code=code, start_date=a, end_date=b) for a, b in chunks(start, today())]
    parts = [p for p in parts if p is not None and len(p)]
    return norm(pd.concat(parts)) if parts else None

def update_group(group, api, codes, cal):
    """codes: list of ts_code。缺历史的按代码抓；其余按交易日批量补。"""
    old = {c: load(group, c) for c in codes}
    for c in codes:
        if old[c] is None or old[c].empty:
            save(group, c, history(api, c, START)); old[c] = load(group, c)
    lasts = [d['date'].max() for d in old.values() if d is not None and len(d)]
    if not lasts: return
    lo = min(lasts).replace('-', '')
    need = [d for d in cal if d > lo]
    if len(need) > 60:                       # 落后太多：逐个代码从最后日期补
        for c in codes:
            d = old[c]; s = (pd.Timestamp(d['date'].max()) - pd.Timedelta(days=5)).strftime('%Y%m%d')
            save(group, c, history(api, c, s), d)
        return
    got = []
    for d in need:
        df = q(api, trade_date=d)
        if df is not None and len(df): got.append(df)
    if not got: return
    allnew = norm(pd.concat(got))
    allnew['ts_code'] = pd.concat(got)['ts_code'].values
    for c, g in allnew.groupby('ts_code'):
        if c in old: save(group, c, g.drop(columns='ts_code'), old[c])

def main():
    t0 = time.time(); os.makedirs(RAW, exist_ok=True)
    cal = q('trade_cal', exchange='SSE', start_date=START, end_date=today(), is_open='1')['cal_date'].astype(str).sort_values().tolist()
    log('最近交易日', cal[-1])
    names = []

    # 宽基
    for code, name in INDEXES:
        d = load('idx', code)
        s = START if d is None or d.empty else (pd.Timestamp(d['date'].max()) - pd.Timedelta(days=10)).strftime('%Y%m%d')
        try:
            df = history('index_daily', code, s)
            save('idx', code, df, d); names.append(('宽基指数', 'idx', code, name, ''))
        except Exception as e:
            log('宽基失败', name, e)
    log(f'宽基 done {time.time()-t0:.0f}s calls={NCALL}')

    # 申万一/二级
    l1 = q('index_classify', level='L1', src='SW2021'); l2 = q('index_classify', level='L2', src='SW2021')
    l1name = dict(zip(l1['industry_code'], l1['industry_name']))
    for _, r in l1.iterrows(): names.append(('申万一级', 'sw1', r.index_code, r.industry_name, ''))
    for _, r in l2.iterrows(): names.append(('申万二级', 'sw2', r.index_code, r.industry_name, l1name.get(r.parent_code, '')))
    update_group('sw1', 'sw_daily', l1['index_code'].tolist(), cal)
    update_group('sw2', 'sw_daily', l2['index_code'].tolist(), cal)
    log(f'申万 done {time.time()-t0:.0f}s calls={NCALL}')

    # 同花顺：行业取 881 开头（同花顺行业指数），概念取 type=N
    ti = q('ths_index', exchange='A', type='I'); tn = q('ths_index', exchange='A', type='N')
    ti881 = ti[ti['ts_code'].str.startswith('881')]
    if len(ti881) >= 20: ti = ti881
    for _, r in ti.iterrows(): names.append(('同花顺行业', 'thi', r.ts_code, r['name'], ''))
    for _, r in tn.iterrows(): names.append(('同花顺概念', 'thc', r.ts_code, r['name'], ''))
    update_group('thi', 'ths_daily', ti['ts_code'].tolist(), cal)
    log(f'同花顺行业 {len(ti)} done {time.time()-t0:.0f}s calls={NCALL}')
    update_group('thc', 'ths_daily', tn['ts_code'].tolist(), cal)
    log(f'同花顺概念 {len(tn)} done {time.time()-t0:.0f}s calls={NCALL}')

    pd.DataFrame(names, columns=['group_label', 'group', 'code', 'name', 'parent']) \
        .drop_duplicates(['group', 'code']).to_csv(os.path.join(RAW, 'names.csv'), index=False)

    # 个股日线（最近 STK_KEEP 个交易日，每天一个文件），用来算广度
    sd = os.path.join(RAW, 'stk'); os.makedirs(sd, exist_ok=True)
    keep = cal[-STK_KEEP:]
    for d in keep:
        p = os.path.join(sd, f'{d}.csv')
        if os.path.exists(p) and d != cal[-1]: continue
        df = q('daily', trade_date=d)
        if df is not None and len(df): df[['ts_code', 'pct_chg']].to_csv(p, index=False)
    for f in os.listdir(sd):
        if f[:8] not in keep: os.remove(os.path.join(sd, f))
    log(f'个股 done {time.time()-t0:.0f}s calls={NCALL}')

    # 成分股：每周刷新一次
    mp = os.path.join(RAW, 'members.csv')
    fresh = os.path.exists(mp) and time.time() - os.path.getmtime(mp) < 6 * 86400
    if not fresh:
        rows = []
        for code in l1['index_code']:
            m = q('index_member_all', l1_code=code, is_new='Y')
            if m is None: continue
            rows += [('sw1', a, b) for a, b in zip(m['l1_code'], m['ts_code'])]
            rows += [('sw2', a, b) for a, b in zip(m['l2_code'], m['ts_code'])]
        for grp, lst in [('thi', ti), ('thc', tn)]:
            for code in lst['ts_code']:
                try:
                    m = q('ths_member', ts_code=code)
                    if m is not None: rows += [(grp, code, c) for c in m['con_code']]
                except Exception as e:
                    log('成分失败', code, e)
        pd.DataFrame(rows, columns=['group', 'code', 'con_code']).drop_duplicates().to_csv(mp, index=False)
    log(f'成分 done {time.time()-t0:.0f}s calls={NCALL}')
    log(f'完成，用时 {time.time()-t0:.0f}s，请求 {NCALL} 次')

if __name__ == '__main__':
    if not os.environ.get('TUSHARE_TOKEN'):
        print('没有读到 TUSHARE_TOKEN'); sys.exit(1)
    main()
