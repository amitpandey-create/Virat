# inventory_app.py
# Streamlit + MongoDB Inventory Management System (full file)
# Save as inventory_app.py
#
# Features:
# - Connects to MongoDB via st.secrets['mongodb']['uri']
# - Lists inventory
# - Add / Update / Delete products
# - Low-stock alert
# - Simple charts (category distribution, stock levels)
# - One-click seed of 20 sample products
# - CSV export, cleaning, transform, analysis

import streamlit as st
from bson.objectid import ObjectId
import pandas as pd
from datetime import datetime
import os
import io
import matplotlib.pyplot as plt

st.set_page_config(page_title="Inventory Management", layout="wide")
st.title("Inventory Management System — Streamlit + MongoDB")

# ---------- MongoDB connection helper ----------
@st.experimental_singleton
def get_client(uri: str):
    client = MongoClient(uri)
    try:
        client.admin.command("ping")
    except ConnectionFailure as e:
        raise ConnectionFailure(f"MongoDB ping failed: {e}")
    return client

if 'mongodb' not in st.secrets:
    st.error("MongoDB secrets not found. Add your MongoDB URI to .streamlit/secrets.toml")
    st.stop()

uri = st.secrets['mongodb'].get('uri')
if not uri:
    st.error("st.secrets['mongodb']['uri'] is empty")
    st.stop()

try:
    client = get_client(uri)
except Exception as e:
    st.error(f"Could not connect to MongoDB: {e}")
    st.stop()

DB_NAME = st.sidebar.text_input("Database name", value="inventory_db")
COLL_NAME = st.sidebar.text_input("Collection name", value="products")

db = client[DB_NAME]
coll = db[COLL_NAME]

st.sidebar.markdown("---")
action = st.sidebar.selectbox("Choose action", ["View inventory", "Add product", "Update product", "Delete product", "Seed sample data"]) 

# ---------- Sample data (20 items) ----------
SAMPLE_PRODUCTS = [
    {"sku": "SKU1001", "name": "Classic T-Shirt", "category": "Apparel", "quantity": 120, "price": 399.0, "supplier": "Textile Co", "last_restock": "2025-10-01"},
    {"sku": "SKU1002", "name": "Slim Jeans", "category": "Apparel", "quantity": 45, "price": 1299.0, "supplier": "Denim Inc", "last_restock": "2025-09-15"},
    {"sku": "SKU1003", "name": "Running Shoes", "category": "Footwear", "quantity": 60, "price": 2199.0, "supplier": "RunFast", "last_restock": "2025-10-20"},
    {"sku": "SKU1004", "name": "Formal Shoes", "category": "Footwear", "quantity": 25, "price": 2499.0, "supplier": "LeatherWorks", "last_restock": "2025-08-30"},
    {"sku": "SKU1005", "name": "Baseball Cap", "category": "Accessories", "quantity": 200, "price": 199.0, "supplier": "CapMakers", "last_restock": "2025-11-01"},
    {"sku": "SKU1006", "name": "Wrist Watch", "category": "Accessories", "quantity": 30, "price": 3499.0, "supplier": "TimeKeep", "last_restock": "2025-07-10"},
    {"sku": "SKU1007", "name": "Leather Belt", "category": "Accessories", "quantity": 80, "price": 499.0, "supplier": "BeltCo", "last_restock": "2025-10-05"},
    {"sku": "SKU1008", "name": "Hoodie", "category": "Apparel", "quantity": 70, "price": 999.0, "supplier": "WarmWear", "last_restock": "2025-09-25"},
    {"sku": "SKU1009", "name": "Socks (Pack of 3)", "category": "Apparel", "quantity": 300, "price": 249.0, "supplier": "SockHouse", "last_restock": "2025-10-11"},
    {"sku": "SKU1010", "name": "Backpack", "category": "Bags", "quantity": 40, "price": 1599.0, "supplier": "BagWorld", "last_restock": "2025-09-01"},
    {"sku": "SKU1011", "name": "Laptop Sleeve", "category": "Bags", "quantity": 75, "price": 699.0, "supplier": "CaseWorks", "last_restock": "2025-08-20"},
    {"sku": "SKU1012", "name": "Water Bottle", "category": "Home", "quantity": 150, "price": 299.0, "supplier": "HydroLtd", "last_restock": "2025-10-18"},
    {"sku": "SKU1013", "name": "Wireless Earbuds", "category": "Electronics", "quantity": 55, "price": 3299.0, "supplier": "SoundTech", "last_restock": "2025-11-02"},
    {"sku": "SKU1014", "name": "Phone Charger", "category": "Electronics", "quantity": 180, "price": 399.0, "supplier": "ChargeIt", "last_restock": "2025-10-28"},
    {"sku": "SKU1015", "name": "Notebook A4", "category": "Stationery", "quantity": 500, "price": 49.0, "supplier": "PaperGoods", "last_restock": "2025-09-10"},
    {"sku": "SKU1016", "name": "Ballpoint Pen", "category": "Stationery", "quantity": 1000, "price": 19.0, "supplier": "WriteWell", "last_restock": "2025-11-03"},
    {"sku": "SKU1017", "name": "Desk Lamp", "category": "Home", "quantity": 35, "price": 899.0, "supplier": "BrightHome", "last_restock": "2025-08-27"},
    {"sku": "SKU1018", "name": "Coffee Mug", "category": "Home", "quantity": 220, "price": 249.0, "supplier": "CeramicArt", "last_restock": "2025-10-30"},
    {"sku": "SKU1019", "name": "USB Flash Drive 32GB", "category": "Electronics", "quantity": 95, "price": 599.0, "supplier": "StoragePlus", "last_restock": "2025-09-05"},
    {"sku": "SKU1020", "name": "Travel Adapter", "category": "Electronics", "quantity": 60, "price": 349.0, "supplier": "GlobeTech", "last_restock": "2025-10-12"},
]

# ---------- Utilities ----------
def fetch_products(filter_q=None, limit=1000):
    q = filter_q or {}
    docs = list(coll.find(q).limit(limit))
    for d in docs:
        d['id'] = str(d['_id'])
        d.pop('_id', None)
    return docs

def docs_to_dataframe(docs, drop_fields=None):
    """Convert Mongo docs to DataFrame and sanitize."""
    if drop_fields is None:
        drop_fields = []
    if not docs:
        return pd.DataFrame()
    clean_docs = []
    for d in docs:
        doc = d.copy()
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
            doc.pop('_id', None)
        for f in drop_fields:
            if f in doc:
                doc.pop(f, None)
        clean_docs.append(doc)
    df = pd.DataFrame(clean_docs)
    if 'id' in df.columns:
        cols = ['id'] + [c for c in df.columns if c != 'id']
        df = df[cols]
    return df

def dataframe_to_csv_bytes(df, include_bom=True):
    """Return CSV as bytes for Streamlit download_button (UTF-8)."""
    if df.empty:
        return "".encode('utf-8')
    csv_str = df.to_csv(index=False)
    csv_bytes = csv_str.encode('utf-8-sig') if include_bom else csv_str.encode('utf-8')
    return csv_bytes

def save_csv_to_server(df, path):
    """Save DataFrame to server disk. Returns True on success."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding='utf-8')
    return os.path.exists(path)

# ---------- Actions ----------
if action == "Seed sample data":
    st.header("Seed 20 sample products into the collection")
    st.write("This will insert 20 predefined sample products if the collection is empty or if you choose to force insert.")
    force = st.checkbox("Force insert even if collection not empty")
    if st.button("Seed sample data"):
        existing = coll.count_documents({})
        if existing > 0 and not force:
            st.warning(f"Collection already has {existing} documents. Check 'Force insert' to insert anyway.")
        else:
            to_insert = []
            for p in SAMPLE_PRODUCTS:
                copy = p.copy()
                copy['quantity'] = int(copy['quantity'])
                copy['price'] = float(copy['price'])
                try:
                    copy['last_restock'] = datetime.fromisoformat(copy['last_restock']).date().isoformat()
                except:
                    pass
                to_insert.append(copy)
            res = coll.insert_many(to_insert)
            st.success(f"Inserted {len(res.inserted_ids)} products.")

# ----------------------------
# Replaced: View inventory block
# ----------------------------
elif action == "View inventory":
    st.header("Inventory List — export, clean, transform & analyze")
    cols = st.columns([3,1])
    with cols[0]:
        search = st.text_input("Search by name or sku or category")
    with cols[1]:
        low_stock_thresh = st.number_input("Low stock threshold", min_value=0, value=30)

    # Local helpers
    def raw_docs_to_df(docs):
        """Convert raw mongo docs list to DataFrame and coerce top-level types."""
        if not docs:
            return pd.DataFrame()
        clean = []
        for d in docs:
            doc = d.copy()
            if '_id' in doc:
                doc['id'] = str(doc['_id'])
                doc.pop('_id', None)
            clean.append(doc)
        df = pd.DataFrame(clean)
        return df

    def clean_and_transform(df):
        """Perform cleaning and add useful columns."""
        if df.empty:
            return df
        if 'quantity' in df.columns:
            df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
        else:
            df['quantity'] = 0
        if 'price' in df.columns:
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0).astype(float)
        else:
            df['price'] = 0.0

        if 'last_restock' in df.columns:
            df['last_restock'] = pd.to_datetime(df['last_restock'], errors='coerce')
        else:
            df['last_restock'] = pd.NaT

        df['name'] = df.get('name', pd.Series()).fillna('Unknown')
        df['sku'] = df.get('sku', pd.Series()).fillna('')

        df['value'] = df['quantity'] * df['price']
        today = pd.Timestamp(datetime.today().date())
        df['days_since_restock'] = (today - df['last_restock']).dt.days
        df['days_since_restock'] = df['days_since_restock'].fillna(-1).astype(int)
        return df

    def dataframe_to_csv_bytes_local(df, include_bom=True):
        if df.empty:
            return "".encode('utf-8')
        csv = df.to_csv(index=False)
        return csv.encode('utf-8-sig') if include_bom else csv.encode('utf-8')

    # Export / analysis controls
    st.markdown("**Export & Analysis Controls**")
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        prepare_filtered = st.button("Prepare filtered CSV (download appears below)")
    with c2:
        download_all_now = st.button("Download FULL CSV (immediate)")
    with c3:
        save_server = st.button("Save full CSV on server (exports/inventory_export.csv)")

    # Build query and fetch
    q = {}
    if search:
        q = {"$or": [{"name": {"$regex": search, "$options": "i"}},
                     {"sku": {"$regex": search, "$options": "i"}},
                     {"category": {"$regex": search, "$options": "i"}}]}
    raw_products = list(coll.find(q).limit(2000))
    df_raw = raw_docs_to_df(raw_products)

    if df_raw.empty:
        st.info("No products found.")
    else:
        df = clean_and_transform(df_raw)

        display_cols = [c for c in ['sku','name','category','quantity','price','value','supplier','last_restock','days_since_restock','id'] if c in df.columns]
        st.dataframe(df[display_cols])

        # Export filtered view
        if prepare_filtered:
            csv_bytes = dataframe_to_csv_bytes_local(df[display_cols])
            st.download_button(
                label="⬇️ Download CURRENT view as CSV",
                data=csv_bytes,
                file_name="inventory_filtered_cleaned.csv",
                mime="text/csv"
            )

        # Immediate download full CSV
        if download_all_now:
            all_docs = list(coll.find({}))
            df_all = clean_and_transform(raw_docs_to_df(all_docs))
            csv_bytes = dataframe_to_csv_bytes_local(df_all)
            st.download_button(
                label="⬇️ Download FULL inventory CSV",
                data=csv_bytes,
                file_name="inventory_full_cleaned.csv",
                mime="text/csv"
            )

        # Save server copy
        if save_server:
            all_docs = list(coll.find({}))
            df_all = clean_and_transform(raw_docs_to_df(all_docs))
            try:
                os.makedirs("exports", exist_ok=True)
                df_all.to_csv("exports/inventory_export.csv", index=False, encoding='utf-8')
                st.success("Saved exports/inventory_export.csv on server")
            except Exception as e:
                st.error(f"Failed to save CSV on server: {e}")

        # Summary metrics
        st.subheader("Summary metrics")
        total_products = len(df)
        total_quantity = int(df['quantity'].sum()) if 'quantity' in df.columns else 0
        total_value = float(df['value'].sum()) if 'value' in df.columns else 0.0
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Products shown", total_products)
        col_b.metric("Total quantity", f"{total_quantity:,}")
        col_c.metric("Total inventory value", f"₹{total_value:,.2f}")

        # Visualizations
        st.subheader("Visualizations")

        # Category aggregates
        if 'category' in df.columns:
            cat_agg = df.groupby('category').agg(total_qty=('quantity','sum'), total_value=('value','sum')).reset_index()
            st.markdown("**Total quantity by category**")
            st.bar_chart(cat_agg.set_index('category')['total_qty'])
            st.markdown("**Total value by category**")
            st.bar_chart(cat_agg.set_index('category')['total_value'])

        # Top 10 by value
        if 'value' in df.columns and 'name' in df.columns:
            st.markdown("**Top 10 products by inventory value**")
            top_by_value = df.sort_values('value', ascending=False).head(10).set_index('name')[['value']]
            st.bar_chart(top_by_value)

        # Price distribution
        if 'price' in df.columns:
            st.markdown("**Price distribution**")
            price_hist = df['price'].dropna()
            hist = pd.cut(price_hist, bins=10).value_counts().sort_index()
            st.bar_chart(hist)

        # Quantity vs Price scatter
        if {'quantity','price'}.issubset(df.columns):
            st.markdown("**Quantity vs Price (scatter)**")
            fig, ax = plt.subplots()
            ax.scatter(df['price'], df['quantity'], alpha=0.7)
            ax.set_xlabel('Price')
            ax.set_ylabel('Quantity')
            ax.set_title('Quantity vs Price')
            st.pyplot(fig)

        # Restock timeline
        if 'last_restock' in df.columns and not df['last_restock'].isna().all():
            st.markdown("**Restock timeline (monthly)**")
            df_rest = df.dropna(subset=['last_restock']).copy()
            df_rest['restock_month'] = df_rest['last_restock'].dt.to_period('M').dt.to_timestamp()
            restock_monthly = df_rest.groupby('restock_month').agg(total_qty=('quantity','sum')).reset_index().set_index('restock_month')
            if not restock_monthly.empty:
                st.line_chart(restock_monthly['total_qty'])
            else:
                st.info("No restock dates available for timeline.")

        # Low stock table
        if 'quantity' in df.columns:
            low = df[df['quantity'] <= low_stock_thresh].sort_values('quantity').head(20)
            st.markdown(f"**Low stock items (<= {low_stock_thresh}) — {len(low)}**")
            if not low.empty:
                st.table(low[['sku','name','quantity','supplier','days_since_restock']])

# ----------------------------
# Add product
# ----------------------------
elif action == "Add product":
    st.header("Add new product")
    with st.form('add_form'):
        sku = st.text_input('SKU')
        name = st.text_input('Product name')
        category = st.text_input('Category')
        quantity = st.number_input('Quantity', min_value=0, value=10)
        price = st.number_input('Price', min_value=0.0, value=100.0)
        supplier = st.text_input('Supplier')
        last_restock = st.date_input('Last restock date', value=datetime.today())
        submitted = st.form_submit_button('Add product')
    if submitted:
        doc = {
            'sku': sku,
            'name': name,
            'category': category,
            'quantity': int(quantity),
            'price': float(price),
            'supplier': supplier,
            'last_restock': last_restock.isoformat()
        }
        try:
            res = coll.insert_one(doc)
            st.success(f"Inserted product with id {res.inserted_id}")
        except Exception as e:
            st.error(f"Insert failed: {e}")

# ----------------------------
# Update product
# ----------------------------
elif action == "Update product":
    st.header("Update product")
    prod_id = st.text_input("Paste product id to update (use View inventory to copy 'id' column)")
    if st.button("Load product") and prod_id:
        try:
            prod = coll.find_one({"_id": ObjectId(prod_id)})
            if not prod:
                st.info("No product found with that id")
            else:
                prod_display = {k: (str(v) if k == '_id' else v) for k,v in prod.items()}
                st.json(prod_display)
        except Exception as e:
            st.error(f"Load failed: {e}")

    with st.form('update_form'):
        field = st.selectbox('Field to update', ['name','category','quantity','price','supplier','last_restock','sku'])
        new_val = st.text_input('New value')
        upd = st.form_submit_button('Apply update')
    if upd:
        if not prod_id:
            st.error('Provide a product id first')
        else:
            try:
                value = new_val
                if field in ['quantity']:
                    value = int(new_val)
                if field in ['price']:
                    value = float(new_val)
                if field == 'last_restock':
                    try:
                        value = datetime.fromisoformat(new_val).date().isoformat()
                    except:
                        pass
                res = coll.update_one({'_id': ObjectId(prod_id)}, {'$set': {field: value}})
                st.success(f"Matched {res.matched_count}, modified {res.modified_count}")
            except Exception as e:
                st.error(f"Update failed: {e}")

# ----------------------------
# Delete product
# ----------------------------
elif action == "Delete product":
    st.header("Delete product")
    del_id = st.text_input('Product id to delete')
    if st.button('Delete') and del_id:
        try:
            res = coll.delete_one({'_id': ObjectId(del_id)})
            st.success(f"Deleted {res.deleted_count} product(s)")
        except Exception as e:
            st.error(f"Delete failed: {e}")

# ---------- Footer notes ----------
st.sidebar.markdown("---")
st.sidebar.markdown("Tips: Use the 'Seed sample data' action to populate 20 items for testing. Do not store secrets in source control.")

# End of file
