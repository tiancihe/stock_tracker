import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
from config import STOCKS
from database import (
    init_db, query_daily, query_fund_flow, query_margin, query_intraday,
)
from export_pdf import generate_pdf

st.set_page_config(
    page_title="股票追踪看板",
    page_icon="📈",
    layout="wide",
)

init_db()


def fmt_num(v):
    if v is None:
        return "-"
    return f"{v:,.2f}"


def fmt_pct(v):
    if v is None:
        return "-"
    return f"{v:+.2f}%"


def fmt_yi(v):
    if v is None:
        return "-"
    return f"{v/1e8:.2f}"


def row_to_dict(r):
    return dict(r)


def fmt_date(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def fmt_dates(rows):
    return [fmt_date(r["date"]) for r in rows]


def calc_kdj(highs, lows, closes, n=9):
    highs_s = pd.Series(highs).rolling(n, min_periods=1).max()
    lows_s = pd.Series(lows).rolling(n, min_periods=1).min()
    rsv = (pd.Series(closes) - lows_s) / (highs_s - lows_s) * 100
    rsv = rsv.fillna(50)
    k = [50.0]
    d = [50.0]
    for i in range(1, len(closes)):
        k.append(2/3 * k[-1] + 1/3 * (rsv.iloc[i] if pd.notna(rsv.iloc[i]) else 50))
        d.append(2/3 * d[-1] + 1/3 * k[-1])
    j = [3*ki - 2*di for ki, di in zip(k, d)]
    return pd.Series(k), pd.Series(d), pd.Series(j)


def calc_macd(closes, fast=12, slow=26, signal=9):
    ema_fast = pd.Series(closes).ewm(span=fast, adjust=False).mean()
    ema_slow = pd.Series(closes).ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = 2 * (dif - dea)
    return dif, dea, macd


def _init_from_query():
    params = st.query_params
    codes = list(STOCKS.keys())
    default_code = codes[0]

    q_code = params.get("code", default_code)
    q_code = q_code if q_code in STOCKS else default_code

    today = datetime.now()
    default_start = today - timedelta(days=60)

    q_start = params.get("start", default_start.strftime("%Y-%m-%d"))
    try:
        parsed_start = datetime.strptime(str(q_start), "%Y-%m-%d")
    except:
        parsed_start = default_start

    q_end = params.get("end", today.strftime("%Y-%m-%d"))
    try:
        parsed_end = datetime.strptime(str(q_end), "%Y-%m-%d")
    except:
        parsed_end = today

    return codes, default_code, q_code, parsed_start, parsed_end, today


def main():
    st.title("📊 股票追踪与数据分析看板")

    codes, default_code, init_code, init_start, init_end, today = _init_from_query()

    code = st.sidebar.selectbox(
        "选择股票", codes,
        format_func=lambda c: f"{c} - {STOCKS[c]}",
        index=codes.index(init_code),
    )
    start_date = st.sidebar.date_input("开始日期", init_start)
    end_date = st.sidebar.date_input("结束日期", init_end)

    st.query_params["code"] = code
    st.query_params["start"] = str(start_date)
    st.query_params["end"] = str(end_date)

    stock_name = STOCKS[code]

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    daily_raw = query_daily(code, start_str, end_str)
    daily = [row_to_dict(r) for r in daily_raw]
    fund_raw = query_fund_flow(code, start_str, end_str)
    fund = [row_to_dict(r) for r in fund_raw]
    intra_raw = query_intraday(code, start_str, end_str)
    intra = [row_to_dict(r) for r in intra_raw]
    margin_raw = query_margin(code, start_str, end_str)
    margin = [row_to_dict(r) for r in margin_raw]

    st.sidebar.divider()
    st.sidebar.caption("数据源状态")
    status_daily = "✅" if daily else "⏳"
    status_fund = "✅" if fund else "❌"
    status_margin = "✅" if margin else "❌"
    status_intra = "✅" if intra else "⏳"
    st.sidebar.caption(f"{status_daily} 日K线  {status_intra} 上下午拆分")
    st.sidebar.caption(f"{status_fund} 资金流向  {status_margin} 融资融券")

    if st.sidebar.button("🔄 刷新数据"):
        from collector import collect_all
        with st.spinner("正在采集数据..."):
            collect_all()
        st.sidebar.success("数据采集完成！")
        st.rerun()

    up_color = "red"
    down_color = "green"

    col1, col2, col3, col4 = st.columns(4)

    if daily:
        latest = daily[-1]
        prev = daily[-2] if len(daily) > 1 else latest
        change = latest["change_pct"] or 0
        is_up = change >= 0
        arrow = "📈" if is_up else "📉"
        col1.metric(
            f"{arrow} 最新收盘",
            f"¥{fmt_num(latest['close'])}",
            f"{fmt_pct(change)}",
        )
        col2.metric("开盘价", f"¥{fmt_num(latest['open'])}")
        vol_val = (latest["volume"] or 0) / 1e4
        col3.metric("成交量", f"{vol_val:.2f} 万手")
        amt_val = (latest["amount"] or 0) / 1e8
        col4.metric("成交额", f"{amt_val:.2f} 亿元")
    else:
        for c in [col1, col2, col3, col4]:
            c.metric("暂无数据", "-")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📈 行情数据", "💰 资金流向", "⏰ 上下午成交", "📋 数据汇总", "🏢 基本面"]
    )

    with tab1:
        if daily:
            dates = fmt_dates(daily)
            closes = [r["close"] for r in daily]
            opens = [r["open"] for r in daily]
            highs = [r["high"] for r in daily]
            lows = [r["low"] for r in daily]
            amounts = [r["amount"] for r in daily]

            ma5 = pd.Series(closes).rolling(5).mean()
            ma10 = pd.Series(closes).rolling(10).mean()
            ma20 = pd.Series(closes).rolling(20).mean()
            k_val, d_val, j_val = calc_kdj(highs, lows, closes)
            dif, dea, macd = calc_macd(closes)

            fig = make_subplots(
                rows=4, cols=1, shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.35, 0.15, 0.20, 0.30],
            )

            fig.add_trace(
                go.Candlestick(
                    x=dates, open=opens, high=highs,
                    low=lows, close=closes, name="K线",
                    increasing_line_color=up_color,
                    decreasing_line_color=down_color,
                ),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=ma5, name="MA5",
                           line=dict(color="orange", width=1)),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=ma10, name="MA10",
                           line=dict(color="blue", width=1)),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=ma20, name="MA20",
                           line=dict(color="purple", width=1, dash="dot")),
                row=1, col=1,
            )

            colors = [up_color if c >= o else down_color for c, o in zip(closes, opens)]
            fig.add_trace(
                go.Bar(x=dates, y=[a/1e8 for a in amounts],
                       name="成交额", marker_color=colors,
                       hovertemplate="%{x}<br>成交额: %{y:.2f}亿元<extra></extra>"),
                row=2, col=1,
            )

            fig.add_trace(
                go.Scatter(x=dates, y=k_val, name="K",
                           line=dict(color="blue", width=1.5)),
                row=3, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=d_val, name="D",
                           line=dict(color="orange", width=1.5)),
                row=3, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=j_val, name="J",
                           line=dict(color="purple", width=1.5)),
                row=3, col=1,
            )
            fig.add_hline(y=80, line_width=1, line_color="gray",
                          line_dash="dash", row=3, col=1)
            fig.add_hline(y=20, line_width=1, line_color="gray",
                          line_dash="dash", row=3, col=1)

            macd_colors = [up_color if v >= 0 else down_color for v in macd]
            fig.add_trace(
                go.Bar(x=dates, y=macd, name="MACD",
                       marker_color=macd_colors),
                row=4, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=dif, name="DIF",
                           line=dict(color="blue", width=1.5)),
                row=4, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=dea, name="DEA",
                           line=dict(color="orange", width=1.5)),
                row=4, col=1,
            )
            fig.add_hline(y=0, line_width=1, line_color="gray", row=4, col=1)

            fig.update_layout(
                title=f"{stock_name} ({code}) 行情数据",
                height=800,
                hovermode="x unified",
                xaxis_rangeslider_visible=False,
            )
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            fig.update_yaxes(title_text="价格", row=1, col=1)
            fig.update_yaxes(title_text="成交额(亿元)", row=2, col=1)
            fig.update_yaxes(title_text="KDJ", row=3, col=1)
            fig.update_yaxes(title_text="MACD", row=4, col=1)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无日K线数据，请先采集")

    with tab2:
        if fund:
            dates = fmt_dates(fund)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=dates,
                y=[r["super_large_net_flow"] / 1e8 for r in fund],
                name="超大单",
                hovertemplate="%{x}<br>%{y:.2f}亿元<extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=dates,
                y=[r["large_net_flow"] / 1e8 for r in fund],
                name="大单",
                hovertemplate="%{x}<br>%{y:.2f}亿元<extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=dates,
                y=[r["medium_net_flow"] / 1e8 for r in fund],
                name="中单",
                hovertemplate="%{x}<br>%{y:.2f}亿元<extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=dates,
                y=[r["small_net_flow"] / 1e8 for r in fund],
                name="小单",
                hovertemplate="%{x}<br>%{y:.2f}亿元<extra></extra>",
            ))
            fig.update_layout(
                title=f"{stock_name} - 资金流向(亿元)",
                barmode="group",
                height=450,
                hovermode="x unified",
            )
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            fig.add_hline(y=0, line_width=1, line_color="gray")
            st.plotly_chart(fig, use_container_width=True)

            main_raw = [r["main_net_flow"] / 1e8 for r in fund]
            fig2 = go.Figure(go.Bar(
                x=dates, y=main_raw,
                name="主力净流入",
                marker_color=[up_color if v >= 0 else down_color for v in main_raw],
                hovertemplate="%{x}<br>%{y:.2f}亿元<extra></extra>",
            ))
            fig2.update_layout(
                title=f"{stock_name} - 主力净流入(亿元)",
                height=350,
                hovermode="x unified",
            )
            fig2.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            fig2.add_hline(y=0, line_width=1, line_color="gray")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("暂无资金流向数据，请先采集")

    with tab3:
        if intra:
            dates = fmt_dates(intra)
            morning_amt = [r["morning_amount"] / 1e8 for r in intra]
            afternoon_amt = [r["afternoon_amount"] / 1e8 for r in intra]
            total_amt = [m + a for m, a in zip(morning_amt, afternoon_amt)]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=dates, y=morning_amt,
                name="上午成交额",
                marker_color="orange",
                hovertemplate="%{x}<br>上午: %{y:.2f}亿元<extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=dates, y=afternoon_amt,
                name="下午成交额",
                marker_color="steelblue",
                hovertemplate="%{x}<br>下午: %{y:.2f}亿元<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=dates, y=total_amt,
                name="总成交额",
                mode="lines+markers",
                line=dict(color="black", width=2),
                hovertemplate="%{x}<br>总计: %{y:.2f}亿元<extra></extra>",
            ))
            fig.update_layout(
                title=f"{stock_name} - 上下午成交额对比(亿元)",
                barmode="stack",
                height=450,
                hovermode="x unified",
            )
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            st.plotly_chart(fig, use_container_width=True)

            fig2 = go.Figure()
            morning_ratio = [
                m / (m + a) * 100 if (m + a) > 0 else 50
                for m, a in zip(morning_amt, afternoon_amt)
            ]
            fig2.add_trace(go.Scatter(
                x=dates, y=morning_ratio,
                mode="lines+markers",
                name="上午成交占比(%)",
                line=dict(color="orange", width=2),
                hovertemplate="%{x}<br>占比: %{y:.1f}%<extra></extra>",
            ))
            fig2.update_layout(
                title=f"{stock_name} - 上午成交占比趋势",
                yaxis=dict(
                    title="占比(%)",
                    range=[0, 100],
                    ticksuffix="%",
                ),
                height=350,
                hovermode="x unified",
            )
            fig2.add_hline(y=50, line_width=1, line_color="gray", line_dash="dash")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("暂无日内数据，采集时会尝试获取最近10个交易日的分钟数据")

    with tab4:
        st.subheader("日K线数据")
        if daily:
            df = pd.DataFrame(daily)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date", ascending=False)
            display_cols = {
                "date": "日期", "open": "开盘", "close": "收盘",
                "high": "最高", "low": "最低",
                "change_pct": "涨跌幅%", "turnover_rate": "换手率%",
            }
            df_display = df[list(display_cols.keys())].rename(columns=display_cols)
            df_display["日期"] = df_display["日期"].dt.strftime("%Y-%m-%d")
            for col in ["开盘", "收盘", "最高", "最低"]:
                df_display[col] = df_display[col].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "-")
            df_display["涨跌幅%"] = df_display["涨跌幅%"].apply(lambda v: f"{v:+.2f}%" if pd.notna(v) else "-")
            df_display["换手率%"] = df_display["换手率%"].apply(lambda v: f"{v:.2f}%" if pd.notna(v) else "-")
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            st.subheader("成交额明细")
            df_amt = df[["date", "volume", "amount"]].copy()
            df_amt["成交量(万手)"] = (df_amt["volume"] / 1e4).apply(lambda v: f"{v:.2f}")
            df_amt["成交额(亿元)"] = (df_amt["amount"] / 1e8).apply(lambda v: f"{v:.2f}")
            df_amt["日期"] = df_amt["date"].dt.strftime("%Y-%m-%d")
            st.dataframe(
                df_amt[["日期", "成交量(万手)", "成交额(亿元)"]],
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("暂无数据")

        st.subheader("资金流向数据")
        if fund:
            df_fund = pd.DataFrame(fund)
            df_fund["date"] = pd.to_datetime(df_fund["date"])
            df_fund = df_fund.sort_values("date", ascending=False)
            fund_cols = {
                "date": "日期", "close": "收盘价",
                "main_net_flow": "主力净流入",
                "super_large_net_flow": "超大单净流入",
                "large_net_flow": "大单净流入",
                "medium_net_flow": "中单净流入",
                "small_net_flow": "小单净流入",
            }
            df_fund_display = df_fund[list(fund_cols.keys())].rename(columns=fund_cols)
            df_fund_display["日期"] = df_fund_display["日期"].dt.strftime("%Y-%m-%d")
            for col in ["主力净流入", "超大单净流入", "大单净流入", "中单净流入", "小单净流入"]:
                df_fund_display[col] = df_fund_display[col].apply(
                    lambda v: f"{v/1e8:+.2f}亿元" if pd.notna(v) else "-"
                )
            df_fund_display["收盘价"] = df_fund_display["收盘价"].apply(
                lambda v: f"{v:.2f}" if pd.notna(v) else "-"
            )
            st.dataframe(df_fund_display, use_container_width=True, hide_index=True)
        else:
            st.info("暂无数据")

        st.subheader("融资融券数据")
        if margin:
            df_margin = pd.DataFrame(margin)
            df_margin["date"] = pd.to_datetime(df_margin["date"])
            df_margin = df_margin.sort_values("date", ascending=False)
            margin_cols = {
                "date": "日期", "margin_balance": "融资余额",
                "margin_buy": "融资买入", "margin_sell": "融资偿还",
            }
            df_margin_display = df_margin[list(margin_cols.keys())].rename(columns=margin_cols)
            df_margin_display["日期"] = df_margin_display["日期"].dt.strftime("%Y-%m-%d")
            for col in ["融资余额", "融资买入", "融资偿还"]:
                df_margin_display[col] = df_margin_display[col].apply(
                    lambda v: f"{v/1e8:.2f}亿元" if pd.notna(v) else "-"
                )
            st.dataframe(df_margin_display, use_container_width=True, hide_index=True)
        else:
            st.info("暂无数据")

        st.subheader("导出报告")
        col_pdf, col_png = st.columns(2)
        with col_pdf:
            if st.button("📄 导出 PDF 报告", use_container_width=True):
                with st.spinner("正在生成 PDF..."):
                    try:
                        start_label = start_date.strftime("%Y%m%d")
                        end_label = end_date.strftime("%Y%m%d")
                        pdf_bytes = generate_pdf(
                            daily, fund, intra, margin,
                            stock_name, start_label, end_label,
                        )
                        st.download_button(
                            label="⬇️ 点击下载 PDF",
                            data=pdf_bytes,
                            file_name=f"{stock_name}_{start_label}_{end_label}.pdf",
                            mime="application/pdf",
                        )
                    except Exception as e:
                        st.error(f"PDF 生成失败: {e}")

        with col_png:
            st.info("Plotly 图表自带截图功能，悬停图表右上角点击相机图标即可保存 PNG")

    with tab5:
        st.subheader(f"{stock_name} ({code}) 公司基本面")

        from cloak_fetcher import fetch_fundamentals_via_cloak
        import baostock as bs

        cache_key = f"fundamentals_{code}"
        if cache_key not in st.session_state:
            with st.spinner("正在获取基本面数据..."):
                fd_raw = fetch_fundamentals_via_cloak(code)
                st.session_state[cache_key] = fd_raw

        fd_raw = st.session_state[cache_key]

        if not fd_raw:
            st.warning("暂未获取到基本面数据")
            if st.button("获取基本面数据", key="fetch_fund"):
                with st.spinner("正在获取..."):
                    fd_raw = fetch_fundamentals_via_cloak(code)
                    st.session_state[cache_key] = fd_raw
                    st.rerun()
        else:
            FUND_FIELD_MAP = {
                "f43": ("最新价", 0),
                "f44": ("最高", 0),
                "f45": ("最低", 0),
                "f46": ("开盘", 0),
                "f60": ("昨收", 0),
                "f47": ("量比", 1),
                "f48": ("换手率", 2),
                "f162": ("市盈率(动态)", 1),
                "f168": ("市盈率(TTM)", 1),
                "f100": ("市盈率(静态)", 1),
                "f167": ("市净率(LYR)", 1),
                "f169": ("市净率(MRQ)", 1),
                "f172": ("每股收益", 4),
                "f175": ("每股净资产", 4),
                "f177": ("每股营业收入", 4),
                "f37": ("净资产收益率(ROE)", 2),
                "f198": ("毛利率", 2),
                "f84": ("总市值", 3),
                "f85": ("流通市值", 3),
                "f116": ("总股本", 3),
                "f117": ("流通股本", 3),
                "f39": ("每股未分配利润", 4),
                "f40": ("每股公积金", 4),
            }

            def fmt_fund(v, label, fmt_type):
                if v is None:
                    return "-"
                if not isinstance(v, (int, float)):
                    return str(v)
                if fmt_type == 0:
                    return f"{v:.2f}"
                elif fmt_type == 1:
                    return f"{v:.2f}"
                elif fmt_type == 2:
                    return f"{v:.2f}%"
                elif fmt_type == 3:
                    return f"{v/1e8:.2f}亿"
                elif fmt_type == 4:
                    return f"{v:.3f}"
                return f"{v:.2f}"

            items = []
            for field_id, (label, fmt_type) in FUND_FIELD_MAP.items():
                val = fd_raw.get(field_id)
                if val is not None:
                    items.append((label, fmt_fund(val, label, fmt_type)))

            # also add basic info from baostock
            try:
                bs.login()
                rs = bs.query_stock_basic(code)
                if rs.next():
                    r = rs.get_row_data()
                    items.insert(0, ("上市日期", r[2]))
                    items.insert(0, ("股票类型", r[3]))
                rs_industry = bs.query_stock_industry(code)
                if rs_industry.next():
                    r2 = rs_industry.get_row_data()
                    items.insert(0, ("所属行业", r2[2]))
                bs.logout()
            except:
                pass

            cols = st.columns(3)
            for i, (label, val) in enumerate(items):
                with cols[i % 3]:
                    st.metric(label=label, value=val)

            if st.button("🔄 刷新基本面数据", key="refresh_fund"):
                with st.spinner("正在获取..."):
                    fd_raw = fetch_fundamentals_via_cloak(code)
                    st.session_state[cache_key] = fd_raw
                    st.rerun()


if __name__ == "__main__":
    main()
