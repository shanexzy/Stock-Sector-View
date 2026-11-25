# -*- coding: utf-8 -*-
"""把 data/raw 下的日线整理成网页用的 JSON，输出到 _site/（GitHub Pages 发布这个文件夹）。"""
import os, json, shutil, datetime as dt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, '_site')
RECENT = 750          # 左侧排行用的最近交易日数（约3年）
ORDER = ['宽基指数', '申万一级', '申万二级', '同花顺行业', '同花顺概念']

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
    cal_key = 'idx_sh000985'
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
