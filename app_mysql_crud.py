# app_mysql_crud.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date, datetime

# ========= DB CONFIG =========
DB_USER = "root"              # <- change
DB_PASS = "vishwapriya"     # <- change
DB_HOST = "localhost"
DB_NAME = "food_wastage_mgt_system"

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}", pool_pre_ping=True, future=True)

st.set_page_config(page_title="Food Wastage Management (MySQL)", layout="wide")
st.title("🍲 Local Food Wastage Management System — MySQL")

# ========= HELPERS =========
@st.cache_data(ttl=300)
def load_joined_listings():
    q = """
    SELECT f.Food_ID, f.Food_Name, f.Quantity, f.Expiry_Date, f.Location AS City,
           f.Food_Type, f.Meal_Type,
           p.Provider_ID, p.Name AS Provider_Name, p.Type AS Provider_Type, p.Contact, p.Address
    FROM food_listings f
    LEFT JOIN providers p ON f.Provider_ID = p.Provider_ID
    ORDER BY f.Expiry_Date ASC, f.Food_ID DESC
    """
    return pd.read_sql_query(q, engine)

@st.cache_data(ttl=300)
def table_df(table):
    return pd.read_sql_query(f"SELECT * FROM {table}", engine)

def invalidate_cache():
    load_joined_listings.clear()
    table_df.clear()

def run_select(sql, params=None):
    with engine.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)

def exec_write(sql, params=None):
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})

# ========= NAV =========
menu = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Browse & Filter", "Providers", "Receivers", "Listings", "Claim Food", "Manage Claims", "Analytics"]
)

# ========= DASHBOARD =========
if menu == "Dashboard":
    c1, c2, c3, c4 = st.columns(4)
    try:
        prov_ct = run_select("SELECT COUNT(*) c FROM providers").iloc[0,0]
        recv_ct = run_select("SELECT COUNT(*) c FROM receivers").iloc[0,0]
        list_ct = run_select("SELECT COUNT(*) c FROM food_listings").iloc[0,0]
        claim_ct = run_select("SELECT COUNT(*) c FROM claims").iloc[0,0]
    except Exception as e:
        st.error(f"DB error: {e}")
        st.stop()
    c1.metric("Providers", prov_ct)
    c2.metric("Receivers", recv_ct)
    c3.metric("Active Listings", list_ct)
    c4.metric("Total Claims", claim_ct)

    st.subheader("Latest Listings")
    df = load_joined_listings().head(20)
    st.dataframe(df)

# ========= BROWSE & FILTER =========
elif menu == "Browse & Filter":
    st.subheader("🔎 Filter Listings + Contact Providers")
    df = load_joined_listings()

    cities = ["All"] + sorted(df["City"].dropna().unique().tolist())
    providers = ["All"] + sorted(df["Provider_Name"].dropna().unique().tolist())
    food_types = ["All"] + sorted(df["Food_Type"].dropna().unique().tolist())
    meal_types = ["All"] + sorted(df["Meal_Type"].dropna().unique().tolist())

    col1, col2, col3, col4 = st.columns(4)
    with col1: city = st.selectbox("City", cities)
    with col2: prov = st.selectbox("Provider", providers)
    with col3: ftype = st.selectbox("Food Type", food_types)
    with col4: mtype = st.selectbox("Meal Type", meal_types)

    filt = df.copy()
    if city != "All": filt = filt[filt["City"] == city]
    if prov != "All": filt = filt[filt["Provider_Name"] == prov]
    if ftype != "All": filt = filt[filt["Food_Type"] == ftype]
    if mtype != "All": filt = filt[filt["Meal_Type"] == mtype]

    st.write(f"Found **{len(filt)}** listing(s).")
    st.dataframe(filt[["Food_ID","Food_Name","Quantity","Expiry_Date","City","Food_Type","Meal_Type","Provider_Name","Contact","Address"]])

    st.markdown("### 📞 Provider Contact Details")
    if len(filt) > 0:
        contacts = filt[["Provider_Name","Contact","Address"]].drop_duplicates().reset_index(drop=True)
        st.table(contacts)
    else:
        st.info("No provider contact details to display.")

# ========= PROVIDERS CRUD =========
elif menu == "Providers":
    st.subheader("🏪 Providers — Create / Update / Delete")
    df = table_df("providers")
    st.dataframe(df)

    tab1, tab2, tab3 = st.tabs(["➕ Add", "✏️ Update", "🗑️ Delete"])

    with tab1:
        with st.form("add_provider"):
            name = st.text_input("Name", "")
            ptype = st.text_input("Type (Restaurant, Grocery, etc.)", "")
            addr  = st.text_input("Address", "")
            city  = st.text_input("City", "")
            contact = st.text_input("Contact (+countrycode...)", "")
            submitted = st.form_submit_button("Add Provider")
        if submitted:
            exec_write("""
                INSERT INTO providers (Name, Type, Address, City, Contact)
                VALUES (:n, :t, :a, :c, :p)
            """, {"n":name, "t":ptype, "a":addr, "c":city, "p":contact})
            st.success("Provider added.")
            invalidate_cache()

    with tab2:
        ids = df["Provider_ID"].tolist()
        if ids:
            pid = st.selectbox("Select Provider_ID to update", ids)
            row = df[df["Provider_ID"]==pid].iloc[0]
            with st.form("upd_provider"):
                name = st.text_input("Name", row["Name"])
                ptype = st.text_input("Type", row["Type"] or "")
                addr = st.text_input("Address", row["Address"] or "")
                city = st.text_input("City", row["City"] or "")
                contact = st.text_input("Contact", row["Contact"] or "")
                upd = st.form_submit_button("Update")
            if upd:
                exec_write("""
                    UPDATE providers
                    SET Name=:n, Type=:t, Address=:a, City=:c, Contact=:p
                    WHERE Provider_ID=:id
                """, {"n":name, "t":ptype, "a":addr, "c":city, "p":contact, "id":int(pid)})
                st.success("Provider updated.")
                invalidate_cache()
        else:
            st.info("No providers to update.")

    with tab3:
        ids = df["Provider_ID"].tolist()
        if ids:
            pid = st.selectbox("Select Provider_ID to delete", ids, key="del_prov")
            if st.button("Delete Provider"):
                exec_write("DELETE FROM providers WHERE Provider_ID=:id", {"id": int(pid)})
                st.success("Provider deleted.")
                invalidate_cache()
        else:
            st.info("No providers to delete.")

# ========= RECEIVERS CRUD =========
elif menu == "Receivers":
    st.subheader("👥 Receivers — Create / Update / Delete")
    df = table_df("receivers")
    st.dataframe(df)

    tab1, tab2, tab3 = st.tabs(["➕ Add", "✏️ Update", "🗑️ Delete"])

    with tab1:
        with st.form("add_receiver"):
            name = st.text_input("Name", "")
            rtype = st.text_input("Type (NGO, Individual, etc.)", "")
            city = st.text_input("City", "")
            contact = st.text_input("Contact", "")
            sub = st.form_submit_button("Add Receiver")
        if sub:
            exec_write("""
                INSERT INTO receivers (Name, Type, City, Contact)
                VALUES (:n, :t, :c, :p)
            """, {"n":name, "t":rtype, "c":city, "p":contact})
            st.success("Receiver added.")
            invalidate_cache()

    with tab2:
        ids = df["Receiver_ID"].tolist()
        if ids:
            rid = st.selectbox("Select Receiver_ID to update", ids)
            row = df[df["Receiver_ID"]==rid].iloc[0]
            with st.form("upd_receiver"):
                name = st.text_input("Name", row["Name"])
                rtype = st.text_input("Type", row["Type"] or "")
                city = st.text_input("City", row["City"] or "")
                contact = st.text_input("Contact", row["Contact"] or "")
                upd = st.form_submit_button("Update")
            if upd:
                exec_write("""
                    UPDATE receivers
                    SET Name=:n, Type=:t, City=:c, Contact=:p
                    WHERE Receiver_ID=:id
                """, {"id": int(rid), "n":name, "t":rtype, "c":city, "p":contact})
                st.success("Receiver updated.")
                invalidate_cache()
        else:
            st.info("No receivers to update.")

    with tab3:
        ids = df["Receiver_ID"].tolist()
        if ids:
            rid = st.selectbox("Select Receiver_ID to delete", ids, key="del_recv")
            if st.button("Delete Receiver"):
                exec_write("DELETE FROM receivers WHERE Receiver_ID=:id", {"id": int(rid)})
                st.success("Receiver deleted.")
                invalidate_cache()
        else:
            st.info("No receivers to delete.")

# ========= LISTINGS CRUD =========
elif menu == "Listings":
    st.subheader("📦 Food Listings — Create / Update / Delete")
    df = table_df("food_listings")
    st.dataframe(df)

    providers = table_df("providers")
    provider_map = {f"{r.Provider_ID} - {r.Name}": int(r.Provider_ID) for r in providers.itertuples()} if len(providers) else {}

    tab1, tab2, tab3 = st.tabs(["➕ Add", "✏️ Update", "🗑️ Delete"])

    with tab1:
        with st.form("add_listing"):
            fname = st.text_input("Food Name", "")
            qty = st.number_input("Quantity", min_value=1, value=1, step=1)
            exp = st.date_input("Expiry Date", value=date.today())
            prov_sel = st.selectbox("Provider", ["None"] + list(provider_map.keys()))
            provider_id = provider_map.get(prov_sel, None)
            prov_type = ""
            city = st.text_input("Location/City", "")
            ftype = st.text_input("Food Type (Veg/Non-Veg/Vegan)", "")
            mtype = st.text_input("Meal Type (Breakfast/Lunch/Dinner/Snacks)", "")
            sub = st.form_submit_button("Add Listing")
        if sub:
            if provider_id:
                prov_type = providers.loc[providers["Provider_ID"]==provider_id, "Type"].iloc[0] or ""
            exec_write("""
                INSERT INTO food_listings (Food_Name, Quantity, Expiry_Date, Provider_ID, Provider_Type, Location, Food_Type, Meal_Type)
                VALUES (:n, :q, :e, :pid, :pt, :loc, :ft, :mt)
            """, {"n":fname, "q":int(qty), "e":exp.isoformat(), "pid":provider_id, "pt":prov_type,
                  "loc":city, "ft":ftype, "mt":mtype})
            st.success("Listing added.")
            invalidate_cache()

    with tab2:
        ids = df["Food_ID"].tolist()
        if ids:
            fid = st.selectbox("Select Food_ID to update", ids)
            row = df[df["Food_ID"]==fid].iloc[0]
            with st.form("upd_listing"):
                fname = st.text_input("Food Name", row["Food_Name"])
                qty = st.number_input("Quantity", min_value=0, value=int(row["Quantity"] or 0), step=1)
                exp = st.date_input("Expiry Date", value=pd.to_datetime(row["Expiry_Date"]).date() if row["Expiry_Date"] else date.today())
                city = st.text_input("Location/City", row["Location"] if "Location" in row else "")
                ftype = st.text_input("Food Type", row["Food_Type"] or "")
                mtype = st.text_input("Meal Type", row["Meal_Type"] or "")
                upd = st.form_submit_button("Update")
            if upd:
                exec_write("""
                    UPDATE food_listings
                    SET Food_Name=:n, Quantity=:q, Expiry_Date=:e, Location=:loc, Food_Type=:ft, Meal_Type=:mt
                    WHERE Food_ID=:id
                """, {"id": int(fid), "n":fname, "q":int(qty), "e":exp.isoformat(),
                      "loc":city, "ft":ftype, "mt":mtype})
                st.success("Listing updated.")
                invalidate_cache()
        else:
            st.info("No listings to update.")

    with tab3:
        ids = df["Food_ID"].tolist()
        if ids:
            fid = st.selectbox("Select Food_ID to delete", ids, key="del_list")
            if st.button("Delete Listing"):
                exec_write("DELETE FROM claims WHERE Food_ID=:id", {"id": int(fid)})  # clean dependent
                exec_write("DELETE FROM food_listings WHERE Food_ID=:id", {"id": int(fid)})
                st.success("Listing deleted (and related claims).")
                invalidate_cache()
        else:
            st.info("No listings to delete.")

# ========= CLAIM FLOW =========
elif menu == "Claim Food":
    st.subheader("🛒 Create a Claim (Quantity-safe)")
    listings = table_df("food_listings")
    receivers = table_df("receivers")

    if listings.empty or receivers.empty:
        st.warning("Need at least one listing and one receiver.")
        st.stop()

    st.dataframe(listings[["Food_ID","Food_Name","Quantity","Expiry_Date","Location"]].head(20))

    fid = st.number_input("Food_ID", min_value=1, step=1)
    rec_map = {f"{r.Receiver_ID} - {r.Name}": int(r.Receiver_ID) for r in receivers.itertuples()}
    rec_sel = st.selectbox("Receiver", list(rec_map.keys()))
    rid = rec_map[rec_sel]
    qty = st.number_input("Quantity to claim", min_value=1, step=1, value=1)

    if st.button("Create Claim"):
        try:
            with engine.begin() as conn:
                # Lock row (MySQL InnoDB): SELECT ... FOR UPDATE
                q = conn.execute(text("SELECT Quantity FROM food_listings WHERE Food_ID=:fid FOR UPDATE"), {"fid": int(fid)}).scalar()
                if q is None:
                    st.error("Food_ID not found.")
                elif q < int(qty):
                    st.error(f"Not enough quantity. Available: {q}")
                else:
                    # insert claim
                    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(text("""
                        INSERT INTO claims (Food_ID, Receiver_ID, Quantity, Status, Timestamp)
                        VALUES (:fid, :rid, :qty, 'Pending', :ts)
                    """), {"fid": int(fid), "rid": int(rid), "qty": int(qty), "ts": ts})
                    # decrement
                    conn.execute(text("UPDATE food_listings SET Quantity=Quantity-:q WHERE Food_ID=:fid"),
                                 {"q": int(qty), "fid": int(fid)})
            st.success("Claim created. Status = Pending; listing quantity updated.")
            invalidate_cache()
        except Exception as e:
            st.error(f"Error: {e}")

# ========= MANAGE CLAIMS =========
elif menu == "Manage Claims":
    st.subheader("📑 Claims — Update / Delete")
    df = table_df("claims")
    st.dataframe(df)

    if not df.empty:
        cid = st.selectbox("Select Claim_ID", df["Claim_ID"].tolist())
        row = df[df["Claim_ID"]==cid].iloc[0]
        new_status = st.selectbox("New Status", ["Pending","Completed","Cancelled"], index=["Pending","Completed","Cancelled"].index(row["Status"]) if row["Status"] in ["Pending","Completed","Cancelled"] else 0)
        if st.button("Update Status"):
            exec_write("UPDATE claims SET Status=:s WHERE Claim_ID=:id", {"s": new_status, "id": int(cid)})
            st.success("Claim status updated.")
            invalidate_cache()

        if st.button("Delete Claim"):
            exec_write("DELETE FROM claims WHERE Claim_ID=:id", {"id": int(cid)})
            st.success("Claim deleted.")
            invalidate_cache()
    else:
        st.info("No claims yet.")

# ========= ANALYTICS =========
elif menu == "Analytics":
    st.subheader("📈 Analytics")
    q1 = """
    SELECT City, COUNT(*) AS providers_count
    FROM providers
    GROUP BY City
    ORDER BY providers_count DESC;
    """
    q2 = "SELECT COALESCE(SUM(Quantity),0) AS total_available FROM food_listings;"
    q3 = """
    SELECT Food_Type, COUNT(*) AS cnt
    FROM food_listings
    GROUP BY Food_Type
    ORDER BY cnt DESC;
    """
    q4 = """
    SELECT f.Meal_Type, SUM(c.Quantity) AS total_claimed
    FROM claims c
    JOIN food_listings f ON c.Food_ID=f.Food_ID
    GROUP BY f.Meal_Type
    ORDER BY total_claimed DESC;
    """

    try:
        df1 = run_select(q1); st.write("Providers by City"); st.table(df1)
        df2 = run_select(q2); st.write("Total Quantity Available"); st.table(df2)
        df3 = run_select(q3); st.write("Most Common Food Types"); st.table(df3.head(10))
        df4 = run_select(q4); st.write("Claims by Meal Type"); st.table(df4)
    except Exception as e:
        st.error(f"DB error: {e}")
