name: 测试Tushare

on:
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: 安装依赖
        run: pip install tushare pandas six
      - name: 测试Tushare接口
        run: python scripts/test_tushare.py
