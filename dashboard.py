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


def row_to_dict(r):
    return dict(r)


def main():
    st.title("📊 股票追踪与数据分析看板")

    codes = list(STOCKS.keys())
    default_code = codes[0]
    code = st.sidebar.selectbox(
        "选择股票", codes,
        format_func=lambda c: f"{c} - {STOCKS[c]}",
        index=codes.index(default_code),
    )
    stock_name = STOCKS[code]

    today = datetime.now()
    default_start = today - timedelta(days=60)
    start_date = st.sidebar.date_input("开始日期", default_start)
    end_date = st.sidebar.date_input("结束日期", today)

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

    tab1, tab2, tab3, tab4 = st.tabs(["📈 价格走势", "💰 资金流向", "⏰ 上下午成交", "📋 数据汇总"])

    with tab1:
        if daily:
            dates = [r["date"] for r in daily]
            closes = [r["close"] for r in daily]
            opens = [r["open"] for r in daily]
            highs = [r["high"] for r in daily]
            lows = [r["low"] for r in daily]
            volumes = [r["volume"] for r in daily]

            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                vertical_spacing=0.05,
                row_heights=[0.7, 0.3],
            )
            fig.add_trace(
                go.Candlestick(
                    x=dates, open=opens, high=highs,
                    low=lows, close=closes, name="K线",
                    increasing_line_color="red", decreasing_line_color="green",
                ),
                row=1, col=1,
            )
            colors = ["red" if c >= o else "green" for c, o in zip(closes, opens)]
            fig.add_trace(
                go.Bar(x=dates, y=volumes, name="成交量", marker_color=colors),
                row=2, col=1,
            )
            fig.update_layout(
                title=f"{stock_name} ({code}) 日K线走势",
                xaxis_title="日期",
                yaxis_title="价格",
                height=600,
                hovermode="x unified",
                xaxis_rangeslider_visible=False,
            )
            fig.update_yaxes(title_text="价格", row=1, col=1)
            fig.update_yaxes(title_text="成交量", row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无日K线数据，请先采集")

    with tab2:
        if fund:
            dates = [r["date"] for r in fund]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=dates,
                y=[r["super_large_net_flow"] / 1e8 for r in fund],
                name="超大单",
            ))
            fig.add_trace(go.Bar(
                x=dates,
                y=[r["large_net_flow"] / 1e8 for r in fund],
                name="大单",
            ))
            fig.add_trace(go.Bar(
                x=dates,
                y=[r["medium_net_flow"] / 1e8 for r in fund],
                name="中单",
            ))
            fig.add_trace(go.Bar(
                x=dates,
                y=[r["small_net_flow"] / 1e8 for r in fund],
                name="小单",
            ))
            fig.update_layout(
                title=f"{stock_name} - 资金流向(亿元)",
                barmode="group",
                height=450,
                hovermode="x unified",
            )
            fig.add_hline(y=0, line_width=1, line_color="gray")
            st.plotly_chart(fig, use_container_width=True)

            main_raw = [r["main_net_flow"] / 1e8 for r in fund]
            fig2 = go.Figure(go.Bar(
                x=dates, y=main_raw,
                name="主力净流入",
                marker_color=["red" if v >= 0 else "green" for v in main_raw],
            ))
            fig2.update_layout(
                title=f"{stock_name} - 主力净流入(亿元)",
                height=350,
                hovermode="x unified",
            )
            fig2.add_hline(y=0, line_width=1, line_color="gray")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("暂无资金流向数据，请先采集")

    with tab3:
        if intra:
            dates = [r["date"] for r in intra]
            morning_amt = [r["morning_amount"] / 1e8 for r in intra]
            afternoon_amt = [r["afternoon_amount"] / 1e8 for r in intra]
            total_amt = [m + a for m, a in zip(morning_amt, afternoon_amt)]

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=dates, y=morning_amt,
                name="上午成交额",
                marker_color="orange",
            ))
            fig.add_trace(go.Bar(
                x=dates, y=afternoon_amt,
                name="下午成交额",
                marker_color="steelblue",
            ))
            fig.add_trace(go.Scatter(
                x=dates, y=total_amt,
                name="总成交额",
                mode="lines+markers",
                line=dict(color="black", width=2),
            ))
            fig.update_layout(
                title=f"{stock_name} - 上下午成交额对比(亿元)",
                barmode="stack",
                height=450,
                hovermode="x unified",
            )
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
            display_cols = {
                "date": "日期", "open": "开盘", "close": "收盘",
                "high": "最高", "low": "最低", "volume": "成交量",
                "amount": "成交额", "change_pct": "涨跌幅%",
                "turnover_rate": "换手率%",
            }
            df_display = df[list(display_cols.keys())].rename(columns=display_cols)
            df_display["日期"] = df_display["日期"].dt.strftime("%Y-%m-%d")
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("暂无数据")

        st.subheader("资金流向数据")
        if fund:
            df_fund = pd.DataFrame(fund)
            fund_cols = {
                "date": "日期", "close": "收盘价",
                "main_net_flow": "主力净流入",
                "super_large_net_flow": "超大单净流入",
                "large_net_flow": "大单净流入",
                "medium_net_flow": "中单净流入",
                "small_net_flow": "小单净流入",
            }
            df_fund_display = df_fund[list(fund_cols.keys())].rename(columns=fund_cols)
            df_fund_display["日期"] = pd.to_datetime(df_fund_display["日期"]).dt.strftime("%Y-%m-%d")
            st.dataframe(df_fund_display, use_container_width=True, hide_index=True)
        else:
            st.info("暂无数据")

        st.subheader("融资融券数据")
        if margin:
            df_margin = pd.DataFrame(margin)
            margin_cols = {
                "date": "日期", "margin_balance": "融资余额",
                "margin_buy": "融资买入", "margin_sell": "融资偿还",
            }
            df_margin_display = df_margin[list(margin_cols.keys())].rename(columns=margin_cols)
            df_margin_display["日期"] = pd.to_datetime(df_margin_display["日期"]).dt.strftime("%Y-%m-%d")
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


if __name__ == "__main__":
    main()
