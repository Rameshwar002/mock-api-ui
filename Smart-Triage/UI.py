import time
import streamlit as st
from jira_client import get_ticket_details

st.set_page_config(page_title="Smart STRO", layout="wide")
st.title("⚡ Smart Workflow")

# --- Input Section ---
uid = st.text_input("Enter Ticket ID", placeholder="Enter Jira Ticket ID")

if st.button("Start Workflow"):
    if not uid:
        st.error("⚠️ Please enter a Ticket ID before starting workflow")
    else:
        # Progress bar + status
        progress_text = st.empty()
        progress_bar = st.progress(0)
        status_box = st.container()

        steps = [
            "Step 1: Collect ticket from Jira",
            "Step 2: Identifying the Issue and collecting logs",
            "Step 3: Validating with documents",
            "Step 4: Generating output"
        ]

        jira_description = None

        for i, step in enumerate(steps):
            progress_text.text(f"🔄 {step} ...")
            with status_box:
                st.write(f"🔄 {step} ...")

            # Step 1 → Jira API call
            if i == 0:
                result = get_ticket_details(uid)
                if "error" in result:
                    st.error(f"❌ Jira fetch failed: {result['error']}")
                    break
                jira_description = result.get("description", "No description found")
                print(f"📌 Jira Ticket Description: {jira_description}")

            # Step 2 → Simulate DB Logs fetch
            elif i == 1:
                time.sleep(2)

            # Step 3 → Simulate KB/VectorDB validation
            elif i == 2:
                time.sleep(2)

            # Step 4 → Simulate LLM response generation
            elif i == 3:
                time.sleep(2)

            # Mark step completed
            with status_box:
                st.success(f"✅ {step} completed")
            progress_bar.progress((i + 1) / len(steps))

        else:
            progress_text.text("🤝 All steps completed successfully!")

            # --- Final LLM Chat Response ---
            st.markdown("---")
            st.subheader("🤖 Final Response")

            with st.chat_message("assistant"):
                st.markdown(f"""
                Based on the Ticket ID **{uid}**, the workflow has been completed ✅  
                - 📌 **Jira Description:** {jira_description}  
                - 🗂️ Logs collected and analyzed  
                - 📚 Documents validated  
                - 🤖 Final resolution drafted  
                """)
