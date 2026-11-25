"""Streamlit entry point for the desktop shell. shacl-py owns the catalogue UI."""

import runpy
from pathlib import Path

import streamlit as st

assets = Path(__file__).resolve().parent
runpy.run_module("shacl_py.app", run_name="__main__")
st.html(assets / "desktop-fonts.css")
st.components.v2.component(
    "ds_view_controls", js=(assets / "desktop_controls.js").read_text(encoding="utf-8")
)(key="desktop_controls")
