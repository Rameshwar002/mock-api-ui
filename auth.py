import streamlit as st
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_hasher = PasswordHasher()

# Hardcoded credentials
INITIAL_USERNAME = "admin"
INITIAL_PASSWORD_HASH = _hasher.hash("123")

def authenticate(username: str, password: str):
    if not username or not password:
        return False, "Enter both username and password."
    if username.strip() != INITIAL_USERNAME:
        return False, "Invalid username or password."
    try:
        if _hasher.verify(INITIAL_PASSWORD_HASH, password):
            return True, "Authenticated."
    except (VerifyMismatchError, InvalidHashError):
        pass
    return False, "Invalid username or password."

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]