# -*- coding: utf-8 -*-
"""把 data/raw 下的日线整理成网页用的 JSON，输出到 _site/（GitHub Pages 发布这个文件夹）。"""
import os, json, shutil, datetime as dt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw_ts') if os.path.exists(os.path.join(ROOT, 'data', 'raw_ts', 'names.csv')) else os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, '_site')
RECENT = 750          # 左侧排行用的最近交易日数（约3年）
ORDER = ['宽基指数', '申万一级', '申万二级', '同花顺行业', '同花顺概念']

def breadth(frames, cal_key):
    """广度：成分股里近 N 日涨幅跑赢中证全指的比例。返回 {series_id: {'5':x,'20':y,'60':z}}"""
    sd = os.path.join(RAW, 'stk'); mp = os.path.join(RAW, 'members.csv')
    if not (os.path.isdir(sd) and os.path.exists(mp) and cal_key in frames): return {}
    files = sorted(f for f in os.listdir(sd) if f.endswith('.csv'))
    if len(files) < 6: return {}
    P = pd.concat([pd.read_csv(os.path.join(sd, f)).set_index('ts_code')['pct_chg'].rename(f[:8]) for f in files], axis=1)
    G = (1 + P.fillna(0) / 100)
    mk = frames[cal_key][1]['close']
    mem = pd.read_csv(mp, dtype=str)
    out = {}
    for L in (5, 20, 60):
        if len(files) < L: continue
        r = G.iloc[:, -L:].prod(axis=1) - 1
        r = r[P.iloc[:, -L:].notna().sum(axis=1) >= L * 0.8]          # 期间大部分时间在交易
        m = mk.iloc[-1] / mk.iloc[-1 - L] - 1
        win = (r > m)
        for (g, c), sub in mem.groupby(['group', 'code']):
            v = win.reindex(sub['con_code']).dropna()
            if len(v) >= 3: out.setdefault(f'{g}_{c}', {})[str(L)] = round(float(v.mean()), 3)
    return out

def main():
    if os.path.exists(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'data', 's'))
    shutil.copy(os.path.join(ROOT, 'site', 'index.html'), OUT)

    names = pd.read_csv(os.path.join(RAW, 'names.csv'), dtype=str).fillna('')
    frames = {}
    for _, r in names.iterrows():
        p = os.path.join(RAW, r.group, f'{r.code}.csv')
        if not os.path.exists(p): continue
        df = pd.read_csv(p).dropna(subset=['close'])
        if len(df) < 5: continue
        frames[f'{r.group}_{r.code}'] = (r, df.set_index('date'))

    # 交易日历：用中证全指；没有就用所有日期的并集
    cal_key = 'idx_000985.CSI' if 'idx_000985.CSI' in frames else 'idx_sh000985'
    cal = sorted(frames[cal_key][1].index) if cal_key in frames else sorted(set().union(*[set(f.index) for _, f in frames.values()]))
    pos = {d: i for i, d in enumerate(cal)}
    n = len(cal); r0 = max(0, n - RECENT)

    lst, recent = [], {}
    rnd = lambda v: None if pd.isna(v) else round(float(v), 3)
    for sid, (r, df) in frames.items():
        df = df[df.index.isin(pos)]
        if df.empty: continue
        i0 = pos[df.index.min()]
        arr = {k: [None] * (n - i0) for k in 'ohlc'}
        for d, row in df.iterrows():
            j = pos[d] - i0
            arr['o'][j], arr['h'][j], arr['l'][j], arr['c'][j] = rnd(row.open), rnd(row.high), rnd(row.low), rnd(row.close)
        with open(os.path.join(OUT, 'data', 's', f'{sid}.json'), 'w', encoding='utf-8') as f:
            json.dump({'i0': i0, **arr}, f, separators=(',', ':'))
        lst.append({'id': sid, 'n': r['name'], 'g': r.group_label, 'p': r.parent, 'last': df.index.max()})
        c = [None] * (n - r0)
        for d, v in df['close'].items():
            if pos[d] >= r0: c[pos[d] - r0] = rnd(v)
        recent[sid] = c

    br = breadth(frames, cal_key)
    for x in lst:
        if x['id'] in br: x['br'] = br[x['id']]
    lst.sort(key=lambda x: (ORDER.index(x['g']) if x['g'] in ORDER else 99, x['p'], x['n']))
    meta = {'asof': cal[-1], 'built': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), 'cal': cal, 'r0': r0, 'list': lst}
    with open(os.path.join(OUT, 'data', 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT, 'data', 'recent.json'), 'w', encoding='utf-8') as f:
        json.dump(recent, f, separators=(',', ':'))
    with open(os.path.join(ROOT, 'last_update.txt'), 'w') as f:
        f.write(f"{cal[-1]} built {meta['built']} series {len(lst)}\n")
    print('built', len(lst), 'series; asof', cal[-1])

if __name__ == '__main__':
    main()
