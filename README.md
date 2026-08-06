# 📄 Conversor DOCX → MD

Aplicação web em Python/Streamlit que converte **documentos Word (.docx) em Markdown (.md)**, usando o LibreOffice em modo headless.

## 🎯 O que faz

| Entrada | Saída |
| --- | --- |
| `.docx` | **`.md`** (Markdown) |

- Interface de tela única (upload → converter → baixar)
- Processamento em diretórios temporários — nenhum arquivo é armazenado

## ⚙️ Como a conversão funciona

A conversão é feita em duas camadas, sempre usando o motor do LibreOffice:

1. **Filtro nativo `Markdown` do Writer** (`--convert-to md:Markdown`), disponível a partir do **LibreOffice 26.2** (fev/2026), que implementa o CommonMark nativamente.
2. **Fallback automático:** se o filtro nativo não existir na versão instalada (caso do LibreOffice distribuído via `apt` no Debian/Ubuntu, ainda em versões mais antigas), o app converte o `.docx` para `.html` com o próprio LibreOffice e depois transforma esse HTML em Markdown com a biblioteca Python `markdownify` (preserva títulos, negrito/itálico, listas, links e tabelas).

Na prática, é o caminho 2 que roda na maioria dos deploys hoje — o caminho 1 passa a ser usado automaticamente assim que a distribuição do sistema operacional atualizar o pacote do LibreOffice.

**Limitação conhecida:** imagens incorporadas no `.docx` não são empacotadas junto ao `.md` baixado (o app entrega um único arquivo de texto). Referências de imagem podem aparecer no Markdown apontando para um caminho que não existe.

## 🚀 Rodar localmente

Pré-requisitos: Python 3.8+ e LibreOffice instalado.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## ☁️ Deploy no Streamlit Cloud

1. Faça push para o GitHub
2. Em [share.streamlit.io](https://share.streamlit.io), conecte o repositório
3. O `packages.txt` (incluído) instala o LibreOffice Writer automaticamente
4. Deploy

## 📋 Estrutura

```
docx-para-md/
├── app.py            # Aplicação principal
├── requirements.txt  # Dependências Python (streamlit, markdownify)
├── packages.txt      # Pacotes do sistema (LibreOffice Writer)
└── README.md
```

## 🛠️ Tecnologias

- **Streamlit** — interface web
- **LibreOffice** (headless) — motor de conversão (DOCX → MD nativo ou DOCX → HTML)
- **markdownify** — conversão HTML → Markdown (fallback)
- **subprocess** — execução do LibreOffice

## 🔒 Privacidade

Os arquivos são processados em diretórios temporários e removidos após a conversão. Nada é armazenado permanentemente.

---

Desenvolvido com ❤️ usando Python e Streamlit.
