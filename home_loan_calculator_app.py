import streamlit as st
import pandas as pd
from firebase_admin import credentials, initialize_app, auth, firestore # Import Firebase Admin SDK components
import json # To parse firebase config

# --- Firebase Initialization (น่ารักมากๆ เลยค่ะ!) ---
# This part initializes Firebase only once per Streamlit session.
# We use st.session_state to store the Firebase app and Firestore client.

# Check if Firebase is already initialized in session state
if 'firebase_app' not in st.session_state:
    try:
        # Global variables provided by the Canvas environment
        app_id = st.secrets.get('__app_id', 'default-app-id') # Use st.secrets for __app_id
        firebase_config_str = st.secrets.get('__firebase_config', '{}') # Use st.secrets for __firebase_config
        initial_auth_token = st.secrets.get('__initial_auth_token', None) # Use st.secrets for __initial_auth_token

        firebase_config = json.loads(firebase_config_str)

        # Initialize Firebase Admin SDK
        # Note: In a real deployment, you'd use a service account key.
        # For Canvas, the config might be sufficient for client-side access or through a backend.
        # This is a simplified client-side initialization.
        if not firebase_config:
            st.error("Firebase configuration is missing. Please ensure __firebase_config is set.")
            st.stop() # Stop execution if config is missing

        # Initialize Firebase App
        # Use a dummy credential if no specific service account is provided, as it's client-side
        if not credentials._get_app_instance(): # Check if an app is already initialized
             firebase_app = initialize_app(options=firebase_config)
        else:
             firebase_app = credentials._get_app_instance() # Get existing app instance

        db = firestore.client(firebase_app) # Get Firestore client
        firebase_auth = auth.Client(firebase_app) # Get Auth client

        st.session_state['firebase_app'] = firebase_app
        st.session_state['db'] = db
        st.session_state['firebase_auth'] = firebase_auth
        st.session_state['user_id'] = None # Initialize user_id

        # Authenticate user (anonymously if no custom token)
        if initial_auth_token:
            try:
                user = firebase_auth.verify_id_token(initial_auth_token)
                st.session_state['user_id'] = user['uid']
            except Exception as e:
                st.warning(f"Failed to verify custom token: {e}. Signing in anonymously.")
                # Fallback to anonymous sign-in if custom token fails
                try:
                    anon_user = auth.sign_in_anonymously(firebase_auth)
                    st.session_state['user_id'] = anon_user['uid']
                except Exception as anon_e:
                    st.error(f"Failed to sign in anonymously: {anon_e}")
                    st.stop()
        else:
            try:
                anon_user = auth.sign_in_anonymously(firebase_auth)
                st.session_state['user_id'] = anon_user['uid']
            except Exception as e:
                st.error(f"Failed to sign in anonymously: {e}")
                st.stop()

        # Increment user count on app load
        user_count_ref = db.collection(f"artifacts/{app_id}/public/data/user_counts").document("app_access_counter")
        try:
            user_count_ref.update({"count": firestore.Increment(1)}, firestore.CreateIfMissing(True))
            st.session_state['user_count_initialized'] = True
        except Exception as e:
            st.warning(f"Failed to increment user count: {e}. Please check Firestore rules.")

    except Exception as e:
        st.error(f"Error initializing Firebase: {e}")
        st.stop() # Stop execution if Firebase fails to initialize

# Retrieve Firebase instances from session state
db = st.session_state['db']
user_id = st.session_state['user_id']
app_id = st.secrets.get('__app_id', 'default-app-id') # Ensure app_id is available

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="เครื่องคำนวณสินเชื่อที่อยู่อาศัย (Home Loan Calculator)",
    page_icon="🏡",
    layout="centered", # Set layout to centered for better mobile display
    initial_sidebar_state="collapsed"
)

# Apply custom CSS for a light gray background color and black text color
st.markdown(
    """
    <style>
    .stApp {
        background-color: #F0F0F0; /* Light gray background color */
        color: #333333; /* Dark gray/near black for general text */
    }
    /* Ensure all text elements are dark for contrast */
    h1, h2, h3, h4, h5, h6, p, div, span, label {
        color: #333333;
    }
    .stMarkdown, .stText {
        color: #333333;
    }
    /* Adjust specific Streamlit components if needed for text color */
    .stNumberInput, .stSelectbox, .stTextInput {
        color: #333333; /* Ensure input text is also dark */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Display User ID and Live User Count ---
st.sidebar.header("ข้อมูลผู้ใช้งาน (User Info)")
st.sidebar.write(f"User ID: `{user_id}`")

# Live user count display
user_count_ref = db.collection(f"artifacts/{app_id}/public/data/user_counts").document("app_access_counter")
try:
    user_count_doc = user_count_ref.get()
    current_user_count = user_count_doc.get("count") if user_count_doc.exists else 0
    st.sidebar.info(f"จำนวนผู้เข้าใช้งาน: **{current_user_count}** ครั้ง (Total Accesses)")
except Exception as e:
    st.sidebar.warning(f"ไม่สามารถโหลดจำนวนผู้เข้าใช้งานได้: {e}")


# Set the main title of the application
st.title("🏡 เครื่องคำนวณสินเชื่อที่อยู่อาศัย (Home Loan Calculator) 💖")

# Greeting and explanation text
st.write("ยินดีต้อนรับสู่เครื่องคำนวณสินเชื่อที่อยู่อาศัย (Welcome to the Home Loan Calculator)")
st.write("กรุณากรอกข้อมูลเพื่อคำนวณยอดผ่อนชำระและดูรายละเอียดการผ่อนชำระ (Please fill in the information to calculate monthly payments and view amortization details)")

# --- Input section for loan details ---
st.header("✨ ข้อมูลสินเชื่อ (Loan Information) ✨")

# Use st.container to group input fields for better organization
with st.container(border=True):
    # Input field for home price
    home_price = st.number_input(
        "🏠 ราคาบ้าน (Home Price) (USD):",
        min_value=10000.0,
        max_value=10000000.0,
        value=250000.0, # Default value for home price
        step=1000.0,
        format="%.2f",
        help="ราคาซื้อขายของที่อยู่อาศัย (Purchase price of the residence)"
    )

    # Input field for down payment
    down_payment = st.number_input(
        "💰 เงินดาวน์ (Down Payment) (USD):",
        min_value=0.0,
        max_value=10000000.0,
        value=50000.0, # Default value for down payment
        step=1000.0,
        format="%.2f",
        help="จำนวนเงินดาวน์ที่ชำระ (Amount of down payment made)"
    )

    # Input field for annual interest rate
    interest_rate_annual = st.number_input(
        "📊 อัตราดอกเบี้ยต่อปี (Annual Interest Rate) (%):",
        min_value=0.1,
        max_value=20.0,
        value=4.5, # Default value
        step=0.1,
        format="%.2f",
        help="อัตราดอกเบี้ยต่อปี (เช่น 4.5 สำหรับ 4.5%) (Annual interest rate, e.g., 4.5 for 4.5%)"
    )

    # Input field for loan term in years
    loan_term_years = st.number_input(
        "🗓️ ระยะเวลาผ่อน (Loan Term) (ปี/Years):",
        min_value=1,
        max_value=50,
        value=30, # Default value
        step=1,
        help="ระยะเวลาผ่อนชำระทั้งหมดเป็นปี (Total repayment period in years)"
    )

    # Input field for additional principal payment per month
    additional_principal_payment = st.number_input(
        "💸 ยอดโปะเพิ่มต่อเดือน (Additional Principal Payment per Month) (USD):",
        min_value=0.0,
        value=0.0, # Default to 0
        step=10.0,
        format="%.2f",
        help="จำนวนเงินต้นที่ต้องการชำระเพิ่มในแต่ละงวด (Amount of additional principal to pay each installment)"
    )

    # Input field for annual property tax
    annual_property_tax = st.number_input(
        "🏡 ภาษีที่อยู่อาศัยรายปี (Annual Property Tax) (USD):",
        min_value=0.0,
        value=3000.0, # Default value
        step=100.0,
        format="%.2f",
        help="ภาษีที่อยู่อาศัยที่ต้องชำระต่อปี (Property tax payable per year)"
    )

    # Input field for annual home insurance
    annual_home_insurance = st.number_input(
        "🛡️ ค่าประกันบ้านรายปี (Annual Home Insurance) (USD):",
        min_value=0.0,
        value=1200.0, # Default value
        step=50.0,
        format="%.2f",
        help="ค่าเบี้ยประกันบ้านที่ต้องชำระต่อปี (Home insurance premium payable per year)"
    )

    # Input field for annual mortgage insurance
    annual_mortgage_insurance = st.number_input(
        "💲 ค่าประกันสินเชื่อที่อยู่อาศัยรายปี (Annual Mortgage Insurance) (USD):",
        min_value=0.0,
        value=0.0, # Default to 0 as it's not always required
        step=10.0,
        format="%.2f",
        help="ค่าประกันสินเชื่อที่อยู่อาศัยที่ต้องชำระต่อปี (Mortgage insurance payable per year)"
    )

# --- Calculate button ---
st.write("") # Add a small vertical space
if st.button("คำนวณยอดผ่อนชำระ (Calculate Payment) ✨", use_container_width=True, type="primary"):
    # Calculate actual loan amount from home price and down payment
    calculated_loan_amount = home_price - down_payment

    # Input validation
    if home_price <= 0 or down_payment < 0 or calculated_loan_amount <= 0 or interest_rate_annual < 0 or loan_term_years <= 0:
        st.error("กรุณากรอกข้อมูลสินเชื่อให้ถูกต้องและเป็นจำนวนบวก ตรวจสอบให้แน่ใจว่าราคาบ้านมากกว่าเงินดาวน์ (Please enter valid and positive loan information. Ensure home price is greater than down payment.)")
    elif annual_property_tax < 0 or annual_home_insurance < 0 or annual_mortgage_insurance < 0:
        st.error("กรุณากรอกภาษีที่อยู่อาศัย, ค่าประกันบ้าน และค่าประกันสินเชื่อที่อยู่อาศัยให้ถูกต้องและเป็นจำนวนบวก (Please enter valid and positive property tax, home insurance, and mortgage insurance amounts.)")
    else:
        # Convert annual interest rate to monthly rate
        monthly_interest_rate = (interest_rate_annual / 100) / 12
        # Calculate total number of payments in months
        number_of_payments = loan_term_years * 12

        # --- Formula for base monthly loan payment (excluding tax/insurance) ---
        # Formula: M = P [ i(1 + i)^n ] / [ (1 + i)^n – 1]
        # Where:
        # M = Monthly Payment
        # P = Principal Loan Amount
        # i = Monthly Interest Rate
        # n = Total Number of Payments (months)

        if monthly_interest_rate == 0: # Handle 0% interest rate
            monthly_payment_base = calculated_loan_amount / number_of_payments
        else:
            monthly_payment_base = calculated_loan_amount * (monthly_interest_rate * (1 + monthly_interest_rate)**number_of_payments) / \
                              ((1 + monthly_interest_rate)**number_of_payments - 1)

        # --- Calculate original total interest paid (without additional principal payments) ---
        original_remaining_balance = calculated_loan_amount
        total_interest_paid_original = 0.0
        for _ in range(number_of_payments):
            if original_remaining_balance <= 0:
                break
            interest_for_month_original = original_remaining_balance * monthly_interest_rate
            total_interest_paid_original += interest_for_month_original
            principal_for_month_original = monthly_payment_base - interest_for_month_original
            original_remaining_balance -= principal_for_month_original
            if original_remaining_balance < 0: # Adjust for the final payment
                original_remaining_balance = 0

        # --- Calculate additional monthly expenses ---
        monthly_property_tax = annual_property_tax / 12
        monthly_home_insurance = annual_home_insurance / 12
        monthly_mortgage_insurance = annual_mortgage_insurance / 12 # Monthly mortgage insurance
        total_additional_monthly_cost = monthly_property_tax + monthly_home_insurance + monthly_mortgage_insurance # Include MI

        # --- Display calculation results ---
        st.header("💖 ผลการคำนวณ (Calculation Results) 💖")
        st.success(f"จำนวนเงินกู้ (หลังหักเงินดาวน์) (Loan Amount after Down Payment): **${calculated_loan_amount:,.2f} USD**") # Display calculated loan amount
        st.success(f"ยอดผ่อนชำระต่อเดือน (เงินต้นและดอกเบี้ย) (Monthly Payment (Principal & Interest)): **${monthly_payment_base:,.2f} USD**") # Clarified this label
        st.info(f"จำนวนงวดผ่อนชำระทั้งหมด (เดิม) (Total Number of Payments (Original)): {number_of_payments} เดือน (Months)")

        # Display monthly breakdown of additional costs
        st.write(f"ภาษีที่อยู่อาศัยต่อเดือน (Monthly Property Tax): **${monthly_property_tax:,.2f} USD**")
        st.write(f"ค่าประกันบ้านต่อเดือน (Monthly Home Insurance): **${monthly_home_insurance:,.2f} USD**")
        st.write(f"ค่าประกันสินเชื่อที่อยู่อาศัยต่อเดือน (Monthly Mortgage Insurance): **${monthly_mortgage_insurance:,.2f} USD**")
        st.markdown(f"## ยอดรวมที่ต้องจ่ายต่อเดือน (Total Monthly Payment): **${monthly_payment_base + total_additional_monthly_cost:,.2f} USD**")

        # --- Generate and display amortization table ---
        st.header("📊 รายละเอียดการผ่อนชำระ (รวมยอดโปะเพิ่ม) (Amortization Details (with Additional Principal)) 📊")

        amortization_data = []
        remaining_balance = calculated_loan_amount # Start with calculated loan amount
        total_interest_paid_with_additional = 0.0
        actual_payments_made = 0

        for month in range(1, number_of_payments + 1):
            if remaining_balance <= 0: # Break if loan is paid off
                break

            actual_payments_made += 1

            # Calculate interest for the current month
            interest_for_month = remaining_balance * monthly_interest_rate
            total_interest_paid_with_additional += interest_for_month

            # Calculate principal paid from the base payment
            principal_from_base_payment = monthly_payment_base - interest_for_month

            # Calculate total principal paid this month (from base payment + additional payment)
            principal_paid_this_month = principal_from_base_payment + additional_principal_payment

            # Adjust principal payment for the final installment precisely
            if remaining_balance < principal_paid_this_month:
                principal_paid_this_month = remaining_balance

            # Calculate new remaining balance
            remaining_balance -= principal_paid_this_month

            amortization_data.append({
                "งวดที่ (Installment)": month,
                "เงินต้นคงเหลือ (เริ่มต้น) (Beginning Balance)": f"{remaining_balance + principal_paid_this_month:,.2f}",
                "ยอดผ่อนต่อเดือน (เงินต้น+ดอกเบี้ย) (Monthly Payment (P&I))": f"{monthly_payment_base:,.2f}", # Only P&I
                "ยอดโปะเพิ่ม (Additional Principal)": f"{additional_principal_payment:,.2f}", # Separate column for additional principal
                "ดอกเบี้ยที่จ่าย (Interest Paid)": f"{interest_for_month:,.2f}",
                "เงินต้นที่จ่าย (Principal Paid)": f"{principal_paid_this_month:,.2f}",
                "เงินต้นคงเหลือ (สิ้นสุด) (Ending Balance)": f"{max(0, remaining_balance):,.2f}", # Ensure balance doesn't go negative
                "ค่าประกันสินเชื่อ (Mortgage Insurance)": f"{monthly_mortgage_insurance:,.2f}" # Separate column for MI
            })

        # Use st.expander to initially hide the table, preventing a long page on mobile
        with st.expander("คลิกเพื่อดูตารางรายละเอียดการผ่อนชำระ (Click to view Amortization Table)"):
            df_amortization = pd.DataFrame(amortization_data)
            st.dataframe(df_amortization, use_container_width=True) # Streamlit displays an interactive table

        st.write("") # Add a small vertical space
        if actual_payments_made < number_of_payments:
            st.success(f"ยอดผ่อนชำระหมดภายใน: **{actual_payments_made} เดือน** (ประหยัดไป {number_of_payments - actual_payments_made} เดือน!) (Loan paid off in: **{actual_payments_made} months** (Saved {number_of_payments - actual_payments_made} months!)) 🎉")
        else:
            st.info("คุณไม่ได้โปะเพิ่ม หรือโปะแล้วแต่ระยะเวลาผ่อนยังคงเดิม (No additional principal payment made, or loan term remains the same.)")

        # Calculate interest saved
        interest_saved = total_interest_paid_original - total_interest_paid_with_additional
        if interest_saved > 0:
            st.success(f"ประหยัดดอกเบี้ยไปได้: **${interest_saved:,.2f} USD** ค่ะ! ยอดเยี่ยมไปเลย! (Interest Saved: **${interest_saved:,.2f} USD**! Excellent!) 💸")
        else:
            st.info("ไม่มีการประหยัดดอกเบี้ยจากการโปะเพิ่ม (No interest saved from additional principal payment.)")

        st.success(f"รวมดอกเบี้ยที่จ่ายตลอดสัญญา (รวมโปะเพิ่ม) (Total Interest Paid (with Additional Principal)): **${total_interest_paid_with_additional:,.2f} USD**")

st.write("\n")
st.markdown("---")
st.write("สร้างโดย: Ikyusung")
