# streamlit_app.py
# Run using: streamlit run streamlit_app.py

import time
import streamlit as st
from jira_client import get_ticket_details
from vector_query import query_vector_db

st.set_page_config(page_title="Smart STRO", layout="wide")
st.title("⚡ Smart STRO Workflow")

uid = st.text_input("Enter Ticket ID", placeholder="Enter Jira Ticket ID")

if st.button("Start Workflow"):
    if not uid:
        st.error("⚠️ Please enter a Ticket ID before starting workflow")
    else:
        progress_text = st.empty()
        progress_bar = st.progress(0)
        status_box = st.container()

        steps = [
            "Step 1: Collect ticket from Jira",
            "Step 2: Identifying the Issue and collecting related info from Vector DB",
            "Step 3: Validating with documents (mock)",
            "Step 4: Generating output (mock)"
        ]

        jira_description = None

        for i, step in enumerate(steps):
            progress_text.text(f"🔄 {step} ...")
            with status_box:
                st.write(f"🔄 {step} ...")

            # Step 1 → Fetch from Jira
            if i == 0:
                result = get_ticket_details(uid)
                if "error" in result:
                    st.error(f"❌ Jira fetch failed: {result['error']}")
                    break
                jira_description = result.get("description", "No description found")
                st.info(f"📋 Jira Description: {jira_description}")

            # Step 2 → Vector DB retrieval
            elif i == 1:
                st.info("🔍 Searching Vector DB for relevant information ...")

                query_result = query_vector_db(jira_description)
                print(query_result)
                if "error" in query_result:
                    st.error(f"❌ Vector DB error: {query_result['error']}")
                    break

                matches = query_result.get("matches", [])
                if not matches:
                    st.warning("⚠️ No matching documents found.")
                else:
                    st.success("✅ Retrieved relevant documents:")
                    for m in matches:
                        st.markdown(f"""
                        **Match (Score: {m['score']})**
                        ```
                        {m['document']}
                        ```
                        """)

            # Step 3 → Mock validation
            elif i == 2:
                time.sleep(1)

            # Step 4 → Mock result
            elif i == 3:
                time.sleep(1)

            with status_box:
                st.success(f"✅ {step} completed")
            progress_bar.progress((i + 1) / len(steps))

        else:
            progress_text.text("🎉 All steps completed successfully!")

            st.markdown("---")
            st.subheader("🧠 Workflow Summary")

            with st.chat_message("assistant"):
                st.markdown(f"""
                Based on Ticket **{uid}**,  
                - 📄 Jira Description: *{jira_description}*  
                - 🔍 Retrieved related documents from Vector DB  
                - ✅ Workflow completed successfully
                """)
