import streamlit as st
import subprocess
import os
import tempfile
import shutil
import uuid
from pathlib import Path
import platform
import time
import random

from markdownify import markdownify

# ---------------------------------------------------------------------------
# SETUP DO PATH DO LIBREOFFICE
# ---------------------------------------------------------------------------
def setup_libreoffice_path():
    """Adiciona o LibreOffice ao PATH do sistema se necessário."""
    if platform.system() == "Windows":
        possible_paths = [
            r"C:\Program Files\LibreOffice\program",
            r"C:\Program Files (x86)\LibreOffice\program",
        ]
    elif platform.system() == "Darwin":
        possible_paths = ["/Applications/LibreOffice.app/Contents/MacOS"]
    else:
        possible_paths = ["/usr/bin", "/usr/local/bin"]

    for path in possible_paths:
        if os.path.exists(path) and path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
            break

setup_libreoffice_path()

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DE PÁGINA E CSS (compacto, para caber no lightbox do AtlasDocs)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Conversor de Formatos Antigos",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .main {
        background-color: #ffffff;
        color: #333333;
    }
    .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        max-width: 28rem !important;
    }
    header {display: none !important;}
    footer {display: none !important;}
    #MainMenu {display: none !important;}
    div[data-testid="stAppViewBlockContainer"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    .element-container {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    .stDownloadButton button {
        width: 100% !important;
        padding: 0.6rem 2rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# CONVERSÃO SUPORTADA: DOCX → MD (Markdown)
# ---------------------------------------------------------------------------
MD_MIME = "text/markdown"

# ---------------------------------------------------------------------------
# EXECUÇÃO DO LIBREOFFICE COM BACKOFF EXPONENCIAL
# ---------------------------------------------------------------------------
def run_lo_subprocess_with_backoff(cmd_args, env, max_retries=3, base_delay=0.5, max_delay=3.0):
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            if result.returncode == 0:
                return result
        except (subprocess.TimeoutExpired, OSError):
            pass

        if attempt < max_retries - 1:
            calculated_delay = min(max_delay, base_delay * (2 ** attempt))
            jitter = random.uniform(0, 0.3)
            time.sleep(calculated_delay + jitter)

    return None

# ---------------------------------------------------------------------------
# CONVERSÃO DE DOCX PARA MARKDOWN
# ---------------------------------------------------------------------------
def convert_docx_to_md(input_file, output_dir):
    """Converte um arquivo .docx para Markdown (.md), sempre usando o motor
    do LibreOffice, em duas camadas:

    1) Filtro nativo "Markdown" do Writer (--convert-to md:Markdown).
       Disponível a partir do LibreOffice 26.2 (fev/2026), que implementa
       o CommonMark nativamente. É o caminho mais direto quando existe.

    2) Fallback: o LibreOffice converte o .docx para .html (suportado por
       qualquer versão do LO, inclusive as mais antigas distribuídas via
       apt em ambientes como o Streamlit Community Cloud) e o HTML
       resultante é convertido para Markdown com a biblioteca
       `markdownify`. Na prática, é esse o caminho que roda em produção
       na maioria dos deploys, já que o LibreOffice 26.2 ainda não chegou
       aos repositórios padrão do Debian/Ubuntu.
    """
    input_path = Path(input_file)
    profile_dir = Path(tempfile.gettempdir()) / f"lo_profile_{uuid.uuid4().hex}"

    try:
        env = os.environ.copy()

        # --- Camada 1: filtro nativo "Markdown" (LibreOffice >= 26.2) ---
        result = None
        for cmd in ("soffice", "libreoffice"):
            cmd_args = [
                cmd,
                "--headless",
                "--norestore",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to", "md:Markdown",
                "--outdir", str(output_dir),
                str(input_path),
            ]
            result = run_lo_subprocess_with_backoff(cmd_args, env=env)
            if result and result.returncode == 0:
                break

        native_output = Path(output_dir) / (input_path.stem + ".md")
        if result and result.returncode == 0 and native_output.exists() and native_output.stat().st_size > 0:
            return str(native_output)

        # --- Camada 2 (fallback): DOCX -> HTML (LibreOffice) -> MD (markdownify) ---
        result = None
        for cmd in ("soffice", "libreoffice"):
            cmd_args = [
                cmd,
                "--headless",
                "--norestore",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to", "html:HTML (StarWriter)",
                "--outdir", str(output_dir),
                str(input_path),
            ]
            result = run_lo_subprocess_with_backoff(cmd_args, env=env)
            if result and result.returncode == 0:
                break

        if result is None or result.returncode != 0:
            error_msg = result.stderr.strip() if result and result.stderr else "Erro na conversão"
            st.error(f"❌ Erro na conversão: {error_msg}")
            return None

        html_file = Path(output_dir) / (input_path.stem + ".html")
        if not html_file.exists():
            st.error("❌ Erro na conversão: arquivo HTML intermediário não foi gerado.")
            return None

        html_content = html_file.read_text(encoding="utf-8", errors="ignore")
        md_content = markdownify(html_content, heading_style="ATX", bullets="-").strip() + "\n"

        md_output = Path(output_dir) / (input_path.stem + ".md")
        md_output.write_text(md_content, encoding="utf-8")

        if md_output.exists() and md_output.stat().st_size > 0:
            return str(md_output)

        return None

    except Exception as e:
        st.error(f"❌ Erro ao converter: {str(e)}")
        return None
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)

# ---------------------------------------------------------------------------
# INTERFACE PRINCIPAL
# ---------------------------------------------------------------------------
def main():
    uploaded_file = st.file_uploader(
        "Arraste e solte seu arquivo aqui",
        type=["docx"],
        help="Documento do Word (.docx). Máximo: 200MB",
        label_visibility="collapsed",
    )

    if uploaded_file is None:
        return

    if (uploaded_file.size / (1024 * 1024)) > 200:
        st.error("❌ Arquivo muito grande! Máximo: 200MB")
        st.stop()

    ext = Path(uploaded_file.name).suffix.lower()
    if ext != ".docx":
        st.error("❌ Formato não suportado. Envie um arquivo .docx.")
        return

    target_ext, mime = "md", MD_MIME

    with st.spinner(f"Convertendo para {target_ext.upper()}..."):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / uploaded_file.name
            input_path.write_bytes(uploaded_file.getbuffer())

            output_path = convert_docx_to_md(str(input_path), temp_dir)
            if output_path is None:
                return

            output_bytes = Path(output_path).read_bytes()

    st.success("✅ Conversão concluída!")
    st.download_button(
        label=f"📥 Baixar {target_ext.upper()}",
        data=output_bytes,
        file_name=Path(uploaded_file.name).stem + "." + target_ext,
        mime=mime,
        type="primary",
        use_container_width=True,
    )

if __name__ == "__main__":
    main()
