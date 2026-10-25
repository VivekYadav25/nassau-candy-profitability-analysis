
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# ==========================================================
# 1. PAGE CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title="Nassau Candy | Profitability Dashboard",
    page_icon="🍫",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "Nassau Candy Distributor.csv"
OUTPUT_DIR = BASE_DIR / "analysis_outputs"

st.title("🍫 Nassau Candy Distributor")
st.subheader("Product Line Profitability & Margin Performance Analysis")
st.caption("MCA Project | Python • Pandas • Streamlit • Matplotlib")


# ==========================================================
# 2. LOAD DATA AND REPORTS
# ==========================================================

@st.cache_data
def load_data():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset nahi mili: {DATA_FILE.name}. "
            "CSV file ko app.py ke saath same folder mein rakho."
        )

    data = pd.read_csv(DATA_FILE)
    data.columns = data.columns.str.strip()

    required = [
        "Order Date", "Ship Date", "Product Name", "Division",
        "Sales", "Units", "Gross Profit", "Cost",
        "Region", "State/Province"
    ]

    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Required columns missing: {missing}")

    data["Order Date"] = pd.to_datetime(
        data["Order Date"], format="%d-%m-%Y", errors="coerce"
    )
    data["Ship Date"] = pd.to_datetime(
        data["Ship Date"], format="%d-%m-%Y", errors="coerce"
    )

    for col in ["Sales", "Units", "Gross Profit", "Cost"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(
        subset=[
            "Order Date", "Product Name", "Division", "Sales",
            "Units", "Gross Profit", "Cost", "Region", "State/Province"
        ]
    ).copy()

    data = data[
        (data["Sales"] > 0) &
        (data["Units"] > 0) &
        (data["Cost"] >= 0)
    ].copy()

    data["Gross Margin %"] = data["Gross Profit"] / data["Sales"] * 100
    data["Cost Ratio %"] = data["Cost"] / data["Sales"] * 100
    data["Profit Per Unit"] = data["Gross Profit"] / data["Units"]
    data["Order Month"] = data["Order Date"].dt.to_period("M").astype(str)

    return data


# Intentionally not cached: newly uploaded reports should be detected.
def load_report(filename):
    path = OUTPUT_DIR / filename

    if not path.exists():
        return None, f"File missing: {path}"

    try:
        return pd.read_csv(path), None
    except Exception as error:
        return None, f"Could not read {filename}: {error}"


try:
    df = load_data()
except Exception as error:
    st.error(f"Dataset load karne mein problem: {error}")
    st.stop()

if df.empty:
    st.error("Analysis ke liye koi valid record nahi mila.")
    st.stop()


# ==========================================================
# 3. SIDEBAR FILTERS
# ==========================================================

st.sidebar.title("Dashboard Filters")

min_date = df["Order Date"].min().date()
max_date = df["Order Date"].max().date()

date_range = st.sidebar.date_input(
    "Order Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

all_divisions = sorted(df["Division"].dropna().unique().tolist())

selected_divisions = st.sidebar.multiselect(
    "Select Division",
    options=all_divisions,
    default=all_divisions
)

search_text = st.sidebar.text_input(
    "Search Product",
    placeholder="Enter product name..."
)

margin_threshold = st.sidebar.slider(
    "Low Margin Threshold (%)",
    min_value=0,
    max_value=80,
    value=30,
    step=5
)

if isinstance(date_range, (tuple, list)):
    if len(date_range) == 2:
        start_date, end_date = date_range
    elif len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        start_date, end_date = min_date, max_date
else:
    start_date = end_date = date_range

filtered = df[
    (df["Order Date"].dt.date >= start_date) &
    (df["Order Date"].dt.date <= end_date) &
    (df["Division"].isin(selected_divisions))
].copy()

if search_text.strip():
    filtered = filtered[
        filtered["Product Name"].str.contains(
            search_text.strip(), case=False, na=False, regex=False
        )
    ].copy()

st.caption(f"Showing {len(filtered):,} of {len(df):,} valid records")

if filtered.empty:
    st.warning("Koi record nahi mila. Date, division ya product search badal kar dekho.")
    st.stop()


# ==========================================================
# 4. CALCULATE SUMMARY METRICS
# ==========================================================

total_sales = filtered["Sales"].sum()
total_cost = filtered["Cost"].sum()
total_profit = filtered["Gross Profit"].sum()
total_units = filtered["Units"].sum()

gross_margin = total_profit / total_sales * 100 if total_sales else 0
cost_ratio = total_cost / total_sales * 100 if total_sales else 0
profit_per_unit = total_profit / total_units if total_units else 0

product_data = (
    filtered.groupby(["Product Name", "Division"], as_index=False)
    .agg(
        Sales=("Sales", "sum"),
        Cost=("Cost", "sum"),
        Gross_Profit=("Gross Profit", "sum"),
        Units=("Units", "sum")
    )
)

product_data["Gross Margin %"] = (
    product_data["Gross_Profit"] / product_data["Sales"] * 100
)
product_data["Cost Ratio %"] = (
    product_data["Cost"] / product_data["Sales"] * 100
)
product_data["Profit Per Unit"] = (
    product_data["Gross_Profit"] / product_data["Units"]
)
product_data["Revenue Contribution %"] = (
    product_data["Sales"] / product_data["Sales"].sum() * 100
)
profit_denominator = product_data["Gross_Profit"].sum()
product_data["Profit Contribution %"] = (
    product_data["Gross_Profit"] / profit_denominator * 100
    if profit_denominator else 0
)
product_data["Margin Status"] = product_data["Gross Margin %"].apply(
    lambda x: "Low Margin" if x < margin_threshold else "At/Above Threshold"
)

product_data["Cost Risk"] = product_data.apply(
    lambda row: (
        "High Cost Ratio + Low Margin"
        if row["Cost Ratio %"] >= 70 and row["Gross Margin %"] < margin_threshold
        else "High Cost Ratio"
        if row["Cost Ratio %"] >= 70
        else "Low Margin"
        if row["Gross Margin %"] < margin_threshold
        else "No Current Flag"
    ),
    axis=1
)

division_data = (
    filtered.groupby("Division", as_index=False)
    .agg(
        Sales=("Sales", "sum"),
        Cost=("Cost", "sum"),
        Gross_Profit=("Gross Profit", "sum"),
        Units=("Units", "sum"),
        Records=("Product Name", "size")
    )
)

division_data["Gross Margin %"] = (
    division_data["Gross_Profit"] / division_data["Sales"] * 100
)
division_data["Cost Ratio %"] = (
    division_data["Cost"] / division_data["Sales"] * 100
)
division_data["Revenue Contribution %"] = (
    division_data["Sales"] / total_sales * 100 if total_sales else 0
)
division_data["Profit Contribution %"] = (
    division_data["Gross_Profit"] / total_profit * 100 if total_profit else 0
)
division_data["Revenue-Profit Share Gap (pp)"] = (
    division_data["Revenue Contribution %"] -
    division_data["Profit Contribution %"]
)

state_data = (
    filtered.groupby("State/Province", as_index=False)
    .agg(Sales=("Sales", "sum"), Gross_Profit=("Gross Profit", "sum"))
    .sort_values("Sales", ascending=False)
)
state_data["Revenue Contribution %"] = (
    state_data["Sales"] / total_sales * 100 if total_sales else 0
)

region_data = (
    filtered.groupby("Region", as_index=False)
    .agg(Sales=("Sales", "sum"), Gross_Profit=("Gross Profit", "sum"))
    .sort_values("Sales", ascending=False)
)
region_data["Revenue Contribution %"] = (
    region_data["Sales"] / total_sales * 100 if total_sales else 0
)


# ==========================================================
# 5. EXECUTIVE OVERVIEW
# ==========================================================

st.markdown("## Executive Overview")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Sales", f"${total_sales:,.2f}")
k2.metric("Total Cost", f"${total_cost:,.2f}")
k3.metric("Gross Profit", f"${total_profit:,.2f}")
k4.metric("Gross Margin", f"{gross_margin:.2f}%")

k5, k6, k7, k8 = st.columns(4)
k5.metric("Cost Ratio", f"{cost_ratio:.2f}%")
k6.metric("Units Sold", f"{total_units:,.0f}")
k7.metric("Profit per Unit", f"${profit_per_unit:,.2f}")
k8.metric("Products", f"{product_data['Product Name'].nunique()}")

st.caption("KPIs respond to the selected date range, division and product search.")

st.markdown("### Monthly Sales and Gross Profit")

monthly = (
    filtered.groupby("Order Month", as_index=False)
    .agg(Sales=("Sales", "sum"), Gross_Profit=("Gross Profit", "sum"))
    .sort_values("Order Month")
)

fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(monthly["Order Month"], monthly["Sales"], marker="o", label="Sales")
ax.plot(monthly["Order Month"], monthly["Gross_Profit"], marker="o", label="Gross Profit")
ax.set_ylabel("Amount ($)")
ax.set_xlabel("Order Month")
ax.tick_params(axis="x", rotation=45)
ax.legend()
fig.tight_layout()
st.pyplot(fig)
plt.close(fig)


# ==========================================================
# 6. DASHBOARD TABS
# ==========================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Product Profitability",
    "Division Performance",
    "Cost & Margin Diagnostics",
    "Profit Concentration",
    "Factory Performance",
    "Data & Export"
])


# ==========================================================
# TAB 1: PRODUCT PROFITABILITY
# ==========================================================

with tab1:
    st.markdown("## Product Profitability Overview")
    left, right = st.columns(2)

    with left:
        st.markdown("### Top Products by Gross Profit")
        top_profit = product_data.nlargest(10, "Gross_Profit").sort_values("Gross_Profit")
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh(top_profit["Product Name"], top_profit["Gross_Profit"])
        ax.set_xlabel("Gross Profit ($)")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with right:
        st.markdown("### Gross Margin Leaderboard")
        top_margin = product_data.nlargest(10, "Gross Margin %").sort_values("Gross Margin %")
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh(top_margin["Product Name"], top_margin["Gross Margin %"])
        ax.axvline(margin_threshold, linestyle="--", label="Margin Threshold")
        ax.set_xlabel("Gross Margin (%)")
        ax.legend()
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    st.markdown("### Complete Product Metrics")
    st.dataframe(
        product_data.sort_values("Gross_Profit", ascending=False).style.format({
            "Sales": "${:,.2f}", "Cost": "${:,.2f}",
            "Gross_Profit": "${:,.2f}", "Units": "{:,.0f}",
            "Gross Margin %": "{:.2f}%", "Cost Ratio %": "{:.2f}%",
            "Profit Per Unit": "${:,.2f}",
            "Revenue Contribution %": "{:.2f}%",
            "Profit Contribution %": "{:.2f}%"
        }),
        width="stretch", hide_index=True
    )

    st.markdown("### Sales vs Gross Margin")
    fig, ax = plt.subplots(figsize=(10, 5))
    for division_name in sorted(product_data["Division"].unique()):
        subset = product_data[product_data["Division"] == division_name]
        ax.scatter(subset["Sales"], subset["Gross Margin %"], label=division_name, s=65)
    ax.axhline(margin_threshold, linestyle="--", label="Margin Threshold")
    ax.set_xlabel("Product Sales ($)")
    ax.set_ylabel("Gross Margin (%)")
    ax.legend()
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    median_sales = product_data["Sales"].median()
    median_profit = product_data["Gross_Profit"].median()

    def classify_product(row):
        high_sales = row["Sales"] >= median_sales
        high_profit = row["Gross_Profit"] >= median_profit
        high_margin = row["Gross Margin %"] >= margin_threshold

        if high_profit and high_margin:
            return "High Profit / High Margin"
        if high_sales and not high_margin:
            return "High Sales / Low Margin"
        if not high_sales and not high_profit:
            return "Low Sales / Low Profit"
        if high_profit and not high_margin:
            return "High Profit / Low Margin"
        return "Other / Review"

    product_data["Product Classification"] = product_data.apply(classify_product, axis=1)

    st.markdown("### Product Portfolio Classification")
    st.dataframe(
        product_data[
            ["Product Name", "Division", "Sales", "Gross_Profit",
             "Gross Margin %", "Product Classification"]
        ].sort_values("Gross_Profit", ascending=False).style.format({
            "Sales": "${:,.2f}", "Gross_Profit": "${:,.2f}",
            "Gross Margin %": "{:.2f}%"
        }),
        width="stretch", hide_index=True
    )


# ==========================================================
# TAB 2: DIVISION PERFORMANCE
# ==========================================================

with tab2:
    st.markdown("## Division Performance Dashboard")
    left, right = st.columns(2)

    with left:
        st.markdown("### Sales vs Gross Profit")
        fig, ax = plt.subplots(figsize=(7, 4))
        division_data.plot(x="Division", y=["Sales", "Gross_Profit"], kind="bar", ax=ax)
        ax.set_ylabel("Amount ($)")
        ax.tick_params(axis="x", rotation=15)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    with right:
        st.markdown("### Gross Margin by Division")
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar(division_data["Division"], division_data["Gross Margin %"])
        ax.set_ylabel("Gross Margin (%)")
        ax.tick_params(axis="x", rotation=15)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    st.markdown("### Product Margin Distribution by Division")
    box_data = [
        product_data.loc[product_data["Division"] == div, "Gross Margin %"].dropna().values
        for div in sorted(product_data["Division"].unique())
    ]
    box_labels = sorted(product_data["Division"].unique())

    if any(len(values) > 0 for values in box_data):
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.boxplot(box_data, tick_labels=box_labels)
        ax.set_ylabel("Product Gross Margin (%)")
        ax.set_xlabel("Division")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    st.markdown("### Revenue vs Profit Contribution")
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(division_data["Division"], division_data["Revenue Contribution %"], label="Revenue Share")
    ax.plot(
        division_data["Division"], division_data["Profit Contribution %"],
        marker="o", label="Profit Share"
    )
    ax.set_ylabel("Contribution (%)")
    ax.legend()
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.dataframe(
        division_data.style.format({
            "Sales": "${:,.2f}", "Cost": "${:,.2f}",
            "Gross_Profit": "${:,.2f}", "Units": "{:,.0f}",
            "Gross Margin %": "{:.2f}%", "Cost Ratio %": "{:.2f}%",
            "Revenue Contribution %": "{:.2f}%",
            "Profit Contribution %": "{:.2f}%",
            "Revenue-Profit Share Gap (pp)": "{:.2f}"
        }),
        width="stretch", hide_index=True
    )


# ==========================================================
# TAB 3: COST AND MARGIN DIAGNOSTICS
# ==========================================================

with tab3:
    st.markdown("## Cost vs Margin Diagnostics")
    st.caption("Cost-sales relationship apne aap pricing inefficiency prove nahi karta.")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(product_data["Sales"], product_data["Cost"], s=70)
    ax.set_xlabel("Product Sales ($)")
    ax.set_ylabel("Product Cost ($)")
    ax.set_title("Product Cost vs Sales")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("### Cost Ratio vs Gross Margin")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.scatter(product_data["Cost Ratio %"], product_data["Gross Margin %"], s=75)
    ax.axhline(margin_threshold, linestyle="--", label="Margin Threshold")
    ax.axvline(70, linestyle=":", label="70% Cost Ratio")
    ax.set_xlabel("Cost Ratio (%)")
    ax.set_ylabel("Gross Margin (%)")
    ax.legend()
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("### Products for Cost / Pricing Review")
    risk_data = product_data[
        (product_data["Gross Margin %"] < margin_threshold) |
        (product_data["Cost Ratio %"] >= 70)
    ].copy()

    if risk_data.empty:
        st.success("Current filters mein defined rules se koi product flag nahi hua.")
    else:
        st.warning(f"{len(risk_data)} product(s) review rules se flag hue.")
        st.dataframe(
            risk_data[
                ["Product Name", "Division", "Sales", "Cost", "Gross_Profit",
                 "Gross Margin %", "Cost Ratio %", "Profit Per Unit", "Cost Risk"]
            ].sort_values("Gross Margin %").style.format({
                "Sales": "${:,.2f}", "Cost": "${:,.2f}",
                "Gross_Profit": "${:,.2f}",
                "Gross Margin %": "{:.2f}%", "Cost Ratio %": "{:.2f}%",
                "Profit Per Unit": "${:,.2f}"
            }),
            width="stretch", hide_index=True
        )

    st.info(
        "Review flags investigation ke liye hain. Pricing ya discontinuation se pehle "
        "supplier costs, discounts, demand aur product strategy verify karein."
    )

    st.markdown("### Monthly Gross Margin Volatility")
    monthly_product = (
        filtered.groupby(["Order Month", "Product Name"], as_index=False)
        .agg(Sales=("Sales", "sum"), Gross_Profit=("Gross Profit", "sum"))
    )
    monthly_product["Gross Margin %"] = (
        monthly_product["Gross_Profit"] / monthly_product["Sales"] * 100
    )

    volatility = (
        monthly_product.groupby("Product Name")["Gross Margin %"]
        .agg(["std", "mean", "min", "max", "count"])
        .reset_index()
        .rename(columns={
            "std": "Margin Volatility (pp)", "mean": "Average Margin %",
            "min": "Minimum Margin %", "max": "Maximum Margin %",
            "count": "Months Observed"
        })
    )
    volatility = volatility[
        volatility["Months Observed"] >= 2
    ].dropna(subset=["Margin Volatility (pp)"])

    if volatility.empty:
        st.info("Selected range mein volatility calculate karne ke liye kisi product ke kam-se-kam do monthly observations nahi mile.")
    else:
        volatility = volatility.sort_values("Margin Volatility (pp)", ascending=False)
        chart_data = volatility.head(10).sort_values("Margin Volatility (pp)")
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.barh(chart_data["Product Name"], chart_data["Margin Volatility (pp)"])
        ax.set_xlabel("Standard Deviation (percentage points)")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        st.dataframe(
            volatility.style.format({
                "Margin Volatility (pp)": "{:.2f}",
                "Average Margin %": "{:.2f}%",
                "Minimum Margin %": "{:.2f}%",
                "Maximum Margin %": "{:.2f}%"
            }),
            width="stretch", hide_index=True
        )


# ==========================================================
# TAB 4: PROFIT CONCENTRATION
# ==========================================================

with tab4:
    st.markdown("## Profit Concentration Analysis")

    def show_pareto(metric_col, title, y_label):
        pareto = product_data.sort_values(metric_col, ascending=False).copy()
        total = pareto[metric_col].sum()

        if total <= 0:
            st.warning(f"{title}: positive values available nahi hain.")
            return

        pareto["Contribution %"] = pareto[metric_col] / total * 100
        pareto["Cumulative %"] = pareto["Contribution %"].cumsum()
        count_to_80 = min(int((pareto["Cumulative %"] < 80).sum()) + 1, len(pareto))

        st.metric(f"Products needed for 80% of {title}", f"{count_to_80} of {len(pareto)}")

        fig, ax1 = plt.subplots(figsize=(11, 5))
        ax1.bar(pareto["Product Name"], pareto[metric_col])
        ax1.set_ylabel(y_label)
        ax1.set_xlabel("Products ranked from highest to lowest")
        ax1.tick_params(axis="x", rotation=65)

        ax2 = ax1.twinx()
        ax2.plot(range(len(pareto)), pareto["Cumulative %"], marker="o")
        ax2.axhline(80, linestyle="--", label="80% Threshold")
        ax2.set_ylabel("Cumulative Contribution (%)")
        ax2.set_ylim(0, 105)
        ax2.legend(loc="lower right")

        ax1.set_title(title)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

        st.dataframe(
            pareto[
                ["Product Name", "Division", metric_col, "Contribution %", "Cumulative %"]
            ].style.format({
                metric_col: "${:,.2f}",
                "Contribution %": "{:.2f}%",
                "Cumulative %": "{:.2f}%"
            }),
            width="stretch", hide_index=True
        )

    left, right = st.columns(2)
    with left:
        show_pareto("Sales", "Revenue Pareto", "Sales ($)")
    with right:
        show_pareto("Gross_Profit", "Gross Profit Pareto", "Gross Profit ($)")

    st.divider()
    st.markdown("### State Revenue Concentration")
    top_states = state_data.head(10).sort_values("Sales")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(top_states["State/Province"], top_states["Sales"])
    ax.set_xlabel("Sales ($)")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.dataframe(
        state_data.style.format({
            "Sales": "${:,.2f}", "Gross_Profit": "${:,.2f}",
            "Revenue Contribution %": "{:.2f}%"
        }),
        width="stretch", hide_index=True
    )

    st.markdown("### Region Revenue Concentration")
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(region_data["Region"], region_data["Revenue Contribution %"])
    ax.set_ylabel("Revenue Contribution (%)")
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.dataframe(
        region_data.style.format({
            "Sales": "${:,.2f}", "Gross_Profit": "${:,.2f}",
            "Revenue Contribution %": "{:.2f}%"
        }),
        width="stretch", hide_index=True
    )

    st.caption(
        "State/region revenue share sales concentration dikhata hai, delivery congestion nahi. "
        "Logistics conclusions ke liye validated data chahiye."
    )


# ==========================================================
# TAB 5: FACTORY PERFORMANCE
# ==========================================================

with tab5:
    st.markdown("## Factory Performance Dashboard")
    st.write(
        "Factory performance supplied product-to-factory mapping par based hai. "
        "Factory-wise results mapping reports se load hote hain."
    )

    required_factory_reports = {
        "factory_performance.csv": "Factory summary",
        "factory_product_performance.csv": "Product-level factory performance",
        "factory_product_mapping.csv": "Product-to-factory mapping",
        "unmatched_factory_products.csv": "Unmatched products",
        "factory_mapping_coverage.csv": "Mapping coverage"
    }

    reports = {}
    report_errors = []

    for filename, description in required_factory_reports.items():
        reports[filename], error = load_report(filename)
        if error:
            report_errors.append(f"{description}: {error}")

    factory_summary = reports["factory_performance.csv"]
    factory_products = reports["factory_product_performance.csv"]
    factory_mapping = reports["factory_product_mapping.csv"]
    unmatched_products = reports["unmatched_factory_products.csv"]
    coverage = reports["factory_mapping_coverage.csv"]

    if report_errors:
        st.error("Factory reports load karne mein dikkat hai:")
        for message in report_errors:
            st.write(f"- {message}")

        st.info(
            "GitHub repository ke root mein app.py aur dataset rakho. "
            "Factory CSV files analysis_outputs folder ke andar honi chahiye. "
            "Filename aur capitalisation bilkul match honi chahiye."
        )

    if factory_summary is None or factory_products is None:
        st.warning(
            "Factory summary ya product performance report missing hai. "
            "Upar dikhayi gayi exact file error ko check karo."
        )
    else:
        needed_columns = {
            "factory_performance.csv": [
                "Factory", "Sales", "Gross_Profit"
            ],
            "factory_product_performance.csv": [
                "Factory", "Product Name", "Sales", "Gross_Profit"
            ]
        }

        report_column_errors = []
        for filename, columns in needed_columns.items():
            report = reports[filename]
            if report is not None:
                missing_cols = [col for col in columns if col not in report.columns]
                if missing_cols:
                    report_column_errors.append(
                        f"{filename} mein columns missing hain: {missing_cols}"
                    )

        if report_column_errors:
            for message in report_column_errors:
                st.error(message)
        else:
            visible_product_names = set(
                filtered["Product Name"].astype(str).str.strip()
            )

            visible_factory_products = factory_products[
                factory_products["Product Name"].astype(str).str.strip().isin(
                    visible_product_names
                )
            ].copy()

            product_factory_map = None

            if factory_mapping is not None and {
                "Product Name", "Factory"
            }.issubset(factory_mapping.columns):
                map_columns = [
                    col for col in ["Product Name", "Factory", "Latitude", "Longitude"]
                    if col in factory_mapping.columns
                ]
                product_factory_map = (
                    factory_mapping[map_columns]
                    .drop_duplicates("Product Name")
                )

            # Prefer current transaction data plus mapping so all filters work.
            if product_factory_map is not None:
                factory_transactions = filtered.merge(
                    product_factory_map,
                    on="Product Name",
                    how="inner",
                    validate="many_to_one"
                )

                grouping_columns = ["Factory"]
                for col in ["Latitude", "Longitude"]:
                    if col in factory_transactions.columns:
                        grouping_columns.append(col)

                factory_view = (
                    factory_transactions.groupby(grouping_columns, as_index=False)
                    .agg(
                        Sales=("Sales", "sum"),
                        Cost=("Cost", "sum"),
                        Gross_Profit=("Gross Profit", "sum"),
                        Units=("Units", "sum"),
                        Unique_Products=("Product Name", "nunique")
                    )
                )

                product_view = (
                    factory_transactions.groupby(
                        grouping_columns + ["Product Name"], as_index=False
                    )
                    .agg(
                        Sales=("Sales", "sum"),
                        Cost=("Cost", "sum"),
                        Gross_Profit=("Gross Profit", "sum"),
                        Units=("Units", "sum")
                    )
                )

            else:
                # Fallback: use the precomputed reports if mapping file is absent.
                factory_view = (
                    visible_factory_products.groupby("Factory", as_index=False)
                    .agg(
                        Sales=("Sales", "sum"),
                        Gross_Profit=("Gross_Profit", "sum"),
                        Unique_Products=("Product Name", "nunique")
                    )
                )
                product_view = visible_factory_products.copy()
                st.warning(
                    "Mapping file load nahi hui. Factory metrics precomputed report se dikh rahe hain."
                )

            if factory_view.empty:
                st.warning(
                    "Selected filters ke products factory mapping report mein nahi mile."
                )
            else:
                if "Cost" not in factory_view.columns:
                    factory_view["Cost"] = (
                        factory_view["Sales"] - factory_view["Gross_Profit"]
                    )

                if "Units" not in factory_view.columns:
                    factory_view["Units"] = 0

                if "Unique_Products" not in factory_view.columns:
                    factory_view["Unique_Products"] = 0

                factory_view["Gross Margin %"] = (
                    factory_view["Gross_Profit"] / factory_view["Sales"] * 100
                )
                factory_view["Cost Ratio %"] = (
                    factory_view["Cost"] / factory_view["Sales"] * 100
                )
                factory_view["Profit Per Unit"] = factory_view.apply(
                    lambda r: r["Gross_Profit"] / r["Units"] if r["Units"] else 0,
                    axis=1
                )

                visible_sales = factory_view["Sales"].sum()
                visible_profit = factory_view["Gross_Profit"].sum()

                factory_view["Revenue Contribution %"] = (
                    factory_view["Sales"] / visible_sales * 100
                    if visible_sales else 0
                )
                factory_view["Profit Contribution %"] = (
                    factory_view["Gross_Profit"] / visible_profit * 100
                    if visible_profit else 0
                )

                f1, f2, f3, f4 = st.columns(4)
                f1.metric("Mapped Factories", len(factory_view))
                f2.metric("Mapped Sales", f"${visible_sales:,.2f}")
                f3.metric("Mapped Gross Profit", f"${visible_profit:,.2f}")
                f4.metric(
                    "Mapped Gross Margin",
                    f"{visible_profit / visible_sales * 100:.2f}%"
                    if visible_sales else "0.00%"
                )

                st.markdown("### Factory-wise Sales vs Gross Profit")
                chart = factory_view.sort_values("Sales", ascending=False)
                fig, ax = plt.subplots(figsize=(10, 5))
                x = range(len(chart))
                width = 0.38
                ax.bar(
                    [i - width / 2 for i in x], chart["Sales"],
                    width=width, label="Sales"
                )
                ax.bar(
                    [i + width / 2 for i in x], chart["Gross_Profit"],
                    width=width, label="Gross Profit"
                )
                ax.set_xticks(list(x))
                ax.set_xticklabels(chart["Factory"], rotation=25, ha="right")
                ax.set_ylabel("Amount ($)")
                ax.legend()
                fig.tight_layout()
                st.pyplot(fig)
                plt.close(fig)

                st.markdown("### Factory-wise Gross Margin")
                margin_chart = factory_view.sort_values("Gross Margin %")
                fig, ax = plt.subplots(figsize=(9, 4))
                ax.barh(margin_chart["Factory"], margin_chart["Gross Margin %"])
                ax.set_xlabel("Gross Margin (%)")
                fig.tight_layout()
                st.pyplot(fig)
                plt.close(fig)

                st.markdown("### Factory Performance Summary")
                st.dataframe(
                    factory_view.sort_values(
                        "Gross_Profit", ascending=False
                    ).style.format({
                        "Sales": "${:,.2f}", "Cost": "${:,.2f}",
                        "Gross_Profit": "${:,.2f}", "Units": "{:,.0f}",
                        "Gross Margin %": "{:.2f}%", "Cost Ratio %": "{:.2f}%",
                        "Profit Per Unit": "${:,.2f}",
                        "Revenue Contribution %": "{:.2f}%",
                        "Profit Contribution %": "{:.2f}%"
                    }),
                    width="stretch", hide_index=True
                )

                st.markdown("### Product-to-Factory Mapping")
                if factory_mapping is not None:
                    if "Product Name" in factory_mapping.columns:
                        visible_mapping = factory_mapping[
                            factory_mapping["Product Name"].astype(str).str.strip().isin(
                                visible_product_names
                            )
                        ].copy()
                        st.dataframe(
                            visible_mapping, width="stretch", hide_index=True
                        )
                    else:
                        st.warning("Factory mapping report mein Product Name column nahi hai.")

                st.markdown("### Product-level Factory Performance")
                if "Gross_Profit" in product_view.columns:
                    product_view = product_view.copy()

                    if "Sales" in product_view.columns:
                        product_view["Gross Margin %"] = (
                            product_view["Gross_Profit"] / product_view["Sales"] * 100
                        )

                    if "Units" in product_view.columns:
                        product_view["Profit Per Unit"] = product_view.apply(
                            lambda r: r["Gross_Profit"] / r["Units"]
                            if r["Units"] else 0,
                            axis=1
                        )

                    st.dataframe(
                        product_view.sort_values(
                            "Gross_Profit", ascending=False
                        ).style.format({
                            "Sales": "${:,.2f}", "Cost": "${:,.2f}",
                            "Gross_Profit": "${:,.2f}", "Units": "{:,.0f}",
                            "Gross Margin %": "{:.2f}%",
                            "Profit Per Unit": "${:,.2f}"
                        }),
                        width="stretch", hide_index=True
                    )
                else:
                    st.warning(
                        "Product-level report mein Gross_Profit column nahi mila."
                    )

    if coverage is not None:
        st.markdown("### Factory Mapping Coverage")
        st.dataframe(coverage, width="stretch", hide_index=True)

    if unmatched_products is not None:
        st.markdown("### Unmatched Products")
        if unmatched_products.empty:
            st.success("Factory mapping report ke mutabik koi unmatched product nahi hai.")
        else:
            st.warning("Kuch products ko factory assign nahi ki gayi.")
            st.dataframe(unmatched_products, width="stretch", hide_index=True)

    st.info(
        "Factory assignment supplied mapping par based hai. Coordinates factory "
        "locations ko represent karte hain; is analysis se production capacity, "
        "actual shipping route ya delivery efficiency prove nahi hoti."
    )


# ==========================================================
# TAB 6: DATA AND EXPORT
# ==========================================================

with tab6:
    st.markdown("## Filtered Transaction Data")

    st.dataframe(
        filtered.drop(columns=["Order Month"], errors="ignore"),
        width="stretch", hide_index=True
    )

    transaction_csv = filtered.to_csv(index=False).encode("utf-8")
    product_csv = product_data.to_csv(index=False).encode("utf-8")
    division_csv = division_data.to_csv(index=False).encode("utf-8")
    state_csv = state_data.to_csv(index=False).encode("utf-8")
    region_csv = region_data.to_csv(index=False).encode("utf-8")

    e1, e2, e3 = st.columns(3)

    with e1:
        st.download_button(
            "Download Transactions CSV",
            transaction_csv,
            "filtered_transactions.csv",
            "text/csv"
        )
        st.download_button(
            "Download Product Metrics CSV",
            product_csv,
            "product_profitability.csv",
            "text/csv"
        )

    with e2:
        st.download_button(
            "Download Division Summary CSV",
            division_csv,
            "division_performance.csv",
            "text/csv"
        )
        st.download_button(
            "Download State Summary CSV",
            state_csv,
            "state_concentration.csv",
            "text/csv"
        )

    with e3:
        st.download_button(
            "Download Region Summary CSV",
            region_csv,
            "region_concentration.csv",
            "text/csv"
        )

    st.markdown("### Data Quality Notes")
    st.write(f"- Valid records included after required-field checks: {len(df):,}.")
    st.write("- Gross Margin = Gross Profit / Sales × 100.")
    st.write("- Cost Ratio = Cost / Sales × 100.")
    st.write("- Profit per Unit = Gross Profit / Units.")
    st.write("- Product contribution percentages are calculated against the currently filtered product set.")
    st.write("- Invalid or incomplete financial records are excluded.")
    st.write("- Gross profit was validated separately against Sales minus Cost.")
    st.write("- Gross profit is not necessarily net profit; source Cost field coverage should be confirmed.")
    st.write("- Shipping efficiency is not evaluated because date fields require verification.")


# ==========================================================
# 7. FOOTER
# ==========================================================

st.divider()
st.caption(
    "Nassau Candy Distributor | Product Line Profitability & Margin "
    "Performance Analysis | MCA Project"
)
