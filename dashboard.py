import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
from config import STOCKS
from database import (
    init_db, query_daily, query_fund_flow, query_margin, query_intraday,
)
from export_pdf import generate_pdf
from fetcher import fetch_hourly_breakdown

st.set_page_config(
    page_title="股票追踪看板",
    page_icon="📈",
    layout="wide",
)

init_db()

st.markdown("""
<style>
.custom-metric {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
    background: #fff;
}
.metric-label {
    font-size: 14px;
    color: #555;
    margin-bottom: 4px;
}
.metric-value {
    font-size: 26px;
    font-weight: bold;
    margin: 6px 0;
}
.metric-delta {
    display: inline-block;
    padding: 2px 12px;
    border-radius: 5px;
    font-size: 14px;
    font-weight: 600;
    color: #fff;
}
.metric-delta.up { background-color: #d32f2f; }
.metric-delta.down { background-color: #2e7d32; }
</style>
""", unsafe_allow_html=True)


def fmt_num(v):
    if v is None:
        return "-"
    return f"{v:,.2f}"


def fmt_pct(v):
    if v is None:
        return "-"
    return f"{v:+.2f}%"


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
    if "qs_start" not in st.session_state:
        st.session_state.qs_start = init_start
    if "qs_end" not in st.session_state:
        st.session_state.qs_end = init_end

    start_date = st.sidebar.date_input("开始日期", st.session_state.qs_start)
    end_date = st.sidebar.date_input("结束日期", st.session_state.qs_end)

    st.sidebar.caption("快捷范围")
    sc1, sc2, sc3, sc4 = st.sidebar.columns(4)
    if sc1.button("今天", width='stretch'):
        st.session_state.qs_start = today
        st.session_state.qs_end = today
        st.rerun()
    if sc2.button("10天", width='stretch'):
        st.session_state.qs_start = today - timedelta(days=10)
        st.session_state.qs_end = today
        st.rerun()
    if sc3.button("20天", width='stretch'):
        st.session_state.qs_start = today - timedelta(days=20)
        st.session_state.qs_end = today
        st.rerun()
    if sc4.button("30天", width='stretch'):
        st.session_state.qs_start = today - timedelta(days=30)
        st.session_state.qs_end = today
        st.rerun()

    st.query_params["code"] = code
    st.query_params["start"] = str(start_date)
    st.query_params["end"] = str(end_date)

    stock_name = STOCKS[code]

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    def nonnull(rows, key="close"):
        return [r for r in rows if r.get(key) is not None]

    daily_raw = query_daily(code, start_str, end_str)
    daily = nonnull([row_to_dict(r) for r in daily_raw])
    fund_raw = query_fund_flow(code, start_str, end_str)
    fund = nonnull([row_to_dict(r) for r in fund_raw], "main_net_flow")
    intra_raw = query_intraday(code, start_str, end_str)
    intra = nonnull([row_to_dict(r) for r in intra_raw], "morning_amount")
    margin_raw = query_margin(code, start_str, end_str)
    margin = nonnull([row_to_dict(r) for r in margin_raw], "margin_balance")

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
        change = latest["change_pct"] or 0
        delta_up = change >= 0
        vol_val = (latest["volume"] or 0) / 1e4
        amt_val = (latest["amount"] or 0) / 1e8
        arrow = "📈" if delta_up else "📉"
        delta_cls = "up" if delta_up else "down"

        with col1:
            st.markdown(f"""
            <div class="custom-metric">
                <div class="metric-label">{arrow} 最新收盘</div>
                <div class="metric-value">¥{fmt_num(latest['close'])}</div>
                <div><span class="metric-delta {delta_cls}">{fmt_pct(change)}</span></div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="custom-metric">
                <div class="metric-label">开盘价</div>
                <div class="metric-value">¥{fmt_num(latest['open'])}</div>
                <div style="height:24px"></div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="custom-metric">
                <div class="metric-label">成交量</div>
                <div class="metric-value">{vol_val:.2f}</div>
                <div style="font-size:13px;color:#888">万手</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="custom-metric">
                <div class="metric-label">成交额</div>
                <div class="metric-value">{amt_val:.2f}</div>
                <div style="font-size:13px;color:#888">亿元</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        for c in [col1, col2, col3, col4]:
            c.markdown("""
            <div class="custom-metric">
                <div class="metric-value" style="color:#999">暂无数据</div>
            </div>
            """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 行情数据", "💰 资金流向", "⏰ 上下午成交", "📋 数据汇总"]
    )

    with tab1:
        if daily:
            dates = fmt_dates(daily)
            closes = [r["close"] for r in daily]
            opens = [r["open"] for r in daily]
            highs = [r["high"] for r in daily]
            lows = [r["low"] for r in daily]
            amounts = [r["amount"] for r in daily]
            volumes = [r["volume"] for r in daily]

            ma5 = pd.Series(closes).rolling(5).mean()
            ma10 = pd.Series(closes).rolling(10).mean()
            ma20 = pd.Series(closes).rolling(20).mean()
            k_val, d_val, j_val = calc_kdj(highs, lows, closes)
            dif, dea, macd = calc_macd(closes)

            fig = make_subplots(
                rows=5, cols=1, shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.30, 0.10, 0.10, 0.20, 0.30],
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
                go.Bar(x=dates, y=[v/1e4 for v in volumes],
                       name="成交量", marker_color=colors,
                       hovertemplate="%{x}<br>成交量: %{y:.2f}万手<extra></extra>"),
                row=3, col=1,
            )

            fig.add_trace(
                go.Scatter(x=dates, y=k_val, name="K",
                           line=dict(color="blue", width=1.5)),
                row=4, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=d_val, name="D",
                           line=dict(color="orange", width=1.5)),
                row=4, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=j_val, name="J",
                           line=dict(color="purple", width=1.5)),
                row=4, col=1,
            )
            fig.add_hline(y=80, line_width=1, line_color="gray",
                          line_dash="dash", row=4, col=1)
            fig.add_hline(y=20, line_width=1, line_color="gray",
                          line_dash="dash", row=4, col=1)

            macd_colors = [up_color if v >= 0 else down_color for v in macd]
            fig.add_trace(
                go.Bar(x=dates, y=macd, name="MACD",
                       marker_color=macd_colors),
                row=5, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=dif, name="DIF",
                           line=dict(color="blue", width=1.5)),
                row=5, col=1,
            )
            fig.add_trace(
                go.Scatter(x=dates, y=dea, name="DEA",
                           line=dict(color="orange", width=1.5)),
                row=5, col=1,
            )
            fig.add_hline(y=0, line_width=1, line_color="gray", row=5, col=1)

            fig.update_layout(
                title=f"{stock_name} ({code}) 行情数据",
                height=850,
                hovermode="x unified",
                xaxis_rangeslider_visible=False,
            )
            fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
            fig.update_yaxes(title_text="价格", row=1, col=1)
            fig.update_yaxes(title_text="成交额(亿元)", row=2, col=1)
            fig.update_yaxes(title_text="成交量(万手)", row=3, col=1)
            fig.update_yaxes(title_text="KDJ", row=4, col=1)
            fig.update_yaxes(title_text="MACD", row=5, col=1)
            st.plotly_chart(fig, width='stretch')
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
            st.plotly_chart(fig, width='stretch')

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
            st.plotly_chart(fig2, width='stretch')

            st.divider()
            st.subheader("当日资金分布")
            latest_f = fund[-1]
            date_label = fmt_date(latest_f["date"])
            pie_labels = []
            pie_values = []
            pie_colors = []
            for key, lbl in [
                ("super_large_net_flow", "超大单"),
                ("large_net_flow", "大单"),
                ("medium_net_flow", "中单"),
                ("small_net_flow", "小单"),
            ]:
                v = latest_f[key] or 0
                pie_labels.append(lbl)
                pie_values.append(abs(v))
                pie_colors.append(up_color if v >= 0 else down_color)

            fig3 = go.Figure(go.Pie(
                labels=pie_labels, values=pie_values,
                marker=dict(colors=pie_colors),
                textinfo="label+percent",
                hovertemplate="%{label}<br>净额: %{customdata:.2f}亿元<extra></extra>",
                customdata=[
                    (latest_f["super_large_net_flow"] or 0) / 1e8,
                    (latest_f["large_net_flow"] or 0) / 1e8,
                    (latest_f["medium_net_flow"] or 0) / 1e8,
                    (latest_f["small_net_flow"] or 0) / 1e8,
                ],
            ))
            fig3.update_layout(
                title=f"{stock_name} - {date_label} 资金分布",
                height=400,
            )
            st.plotly_chart(fig3, width='stretch')
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
            st.plotly_chart(fig, width='stretch')

            st.divider()
            st.subheader("分时成交额明细")

            intra_dates = sorted(set(r["date"] for r in intra), reverse=True)
            default_sel = intra_dates[0] if intra_dates else ""
            sel_date = st.selectbox(
                "选择日期", intra_dates,
                format_func=lambda d: fmt_date(d),
                index=0,
                key="hourly_date",
            )

            cache_key = f"hourly_{code}_{sel_date}"
            if cache_key not in st.session_state:
                with st.spinner("正在获取分时数据..."):
                    hourly_data = fetch_hourly_breakdown(code, sel_date)
                    st.session_state[cache_key] = hourly_data
            hourly_data = st.session_state[cache_key]

            if hourly_data:
                hours = [f"{r[2]}:00" for r in hourly_data]
                hourly_amt = [r[4] / 1e8 for r in hourly_data]

                fig3 = go.Figure()
                fig3.add_trace(go.Bar(
                    x=hours, y=hourly_amt,
                    name="成交额",
                    marker_color="steelblue",
                    hovertemplate="%{x}<br>成交额: %{y:.2f}亿元<extra></extra>",
                ))
                fig3.add_trace(go.Scatter(
                    x=hours, y=hourly_amt,
                    name="趋势",
                    mode="lines+markers",
                    line=dict(color="red", width=2),
                    hovertemplate="%{x}<br>成交额: %{y:.2f}亿元<extra></extra>",
                ))
                fig3.update_layout(
                    title=f"{stock_name} - {fmt_date(sel_date)} 小时成交额",
                    height=350,
                    hovermode="x unified",
                    xaxis=dict(title="时间"),
                    yaxis=dict(title="成交额(亿元)"),
                )
                st.plotly_chart(fig3, width='stretch')
            else:
                st.info("暂无该日分时数据")
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
            st.dataframe(df_display, width='stretch', hide_index=True)

            st.subheader("成交额明细")
            df_amt = df[["date", "volume", "amount"]].copy()
            df_amt["成交量(万手)"] = (df_amt["volume"] / 1e4).apply(lambda v: f"{v:.2f}")
            df_amt["成交额(亿元)"] = (df_amt["amount"] / 1e8).apply(lambda v: f"{v:.2f}")
            df_amt["日期"] = df_amt["date"].dt.strftime("%Y-%m-%d")
            st.dataframe(
                df_amt[["日期", "成交量(万手)", "成交额(亿元)"]],
                width='stretch', hide_index=True,
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
            st.dataframe(df_fund_display, width='stretch', hide_index=True)
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
            st.dataframe(df_margin_display, width='stretch', hide_index=True)
        else:
            st.info("暂无数据")

        st.subheader("导出报告")
        col_pdf, col_png = st.columns(2)
        with col_pdf:
            if st.button("📄 导出 PDF 报告", width='stretch'):
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


if __name__ == "__main__":
    main()
