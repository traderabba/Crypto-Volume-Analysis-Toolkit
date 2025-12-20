from flask import Blueprint, request, redirect, render_template_string, url_for
from utils import update_config_file, load_config_from_file
import config
from templates import SETUP_TEMPLATE, SETTINGS_TEMPLATE

setup_bp = Blueprint('setup', __name__)

@setup_bp.route("/setup")
def setup_page():
    return render_template_string(SETUP_TEMPLATE, 
        cmc=config.CMC_API_KEY, lcw=config.LIVECOINWATCH_API_KEY, 
        cr=config.COINRANKINGS_API_KEY, html2pdf=config.HTML2PDF_API_KEY, vtmr=config.COINALYZE_VTMR_URL)

@setup_bp.route("/settings")
def settings_page():
    return render_template_string(SETTINGS_TEMPLATE, 
        cmc=config.CMC_API_KEY, lcw=config.LIVECOINWATCH_API_KEY, 
        cr=config.COINRANKINGS_API_KEY, html2pdf=config.HTML2PDF_API_KEY, vtmr=config.COINALYZE_VTMR_URL)

@setup_bp.route("/save-config", methods=["POST"])
def save_config():
    update_config_file({
        "CMC_API_KEY": request.form.get("cmc_key"),
        "LIVECOINWATCH_API_KEY": request.form.get("lcw_key"),
        "COINRANKINGS_API_KEY": request.form.get("cr_key"),
        "HTML2PDF_API_KEY": request.form.get("html2pdf_key"),
        "COINALYZE_VTMR_URL": request.form.get("vtmr_url")
    })
    return redirect('/')