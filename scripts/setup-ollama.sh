#!/usr/bin/env bash
# setup-ollama.sh — pré-checks do VLM local para PlayIA.
#
# Verifica se Ollama está instalado, se o daemon responde em :11434
# e se o modelo qwen2.5vl:7b está disponível.
#
# Exit codes:
#   0 — tudo certo
#   1 — Ollama não instalado ou daemon offline
#   2 — daemon up mas modelo qwen2.5vl:7b ausente

set -u

REQUIRED_MODEL="qwen2.5vl:7b"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"

color() {
    # $1 = código ANSI, $2 = texto
    if [ -t 1 ]; then
        printf '\033[%sm%s\033[0m' "$1" "$2"
    else
        printf '%s' "$2"
    fi
}

ok()   { printf '%s %s\n' "$(color '32' '✓')" "$*"; }
warn() { printf '%s %s\n' "$(color '33' '!')" "$*"; }
err()  { printf '%s %s\n' "$(color '31' '✗')" "$*" >&2; }
info() { printf '%s %s\n' "$(color '36' '·')" "$*"; }

detect_os() {
    case "$(uname -s 2>/dev/null)" in
        Darwin)              echo "macos" ;;
        Linux)               echo "linux" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)                   echo "unknown" ;;
    esac
}

OS="$(detect_os)"
info "SO detectado: $OS"

# ---------------------------------------------------------------------------
# 1) Binário do Ollama
# ---------------------------------------------------------------------------
if ! command -v ollama >/dev/null 2>&1; then
    err "Ollama não encontrado no PATH."
    case "$OS" in
        macos)
            if command -v brew >/dev/null 2>&1; then
                warn "Instale com: brew install ollama"
            else
                warn "Baixe em: https://ollama.com/download (ou instale Homebrew antes)"
            fi
            ;;
        linux)
            warn "Instale com: curl -fsSL https://ollama.com/install.sh | sh"
            ;;
        windows)
            warn "Baixe o instalador oficial: https://ollama.com/download/windows"
            ;;
        *)
            warn "Veja https://ollama.com/download para o seu SO."
            ;;
    esac
    exit 1
fi
ok "ollama instalado ($(ollama --version 2>/dev/null | head -n1))"

# ---------------------------------------------------------------------------
# 2) Daemon respondendo em :11434
# ---------------------------------------------------------------------------
TAGS_URL="${OLLAMA_HOST%/}/api/tags"
TAGS_JSON=""
if ! TAGS_JSON="$(curl -fsS --max-time 3 "$TAGS_URL" 2>/dev/null)"; then
    err "Daemon do Ollama não responde em $OLLAMA_HOST."
    warn "Inicie com: ollama serve   (em outro terminal, deixe rodando)"
    exit 1
fi
ok "daemon up em $OLLAMA_HOST"

# ---------------------------------------------------------------------------
# 3) Modelo presente
# ---------------------------------------------------------------------------
# Procura "name":"qwen2.5vl:7b" na resposta JSON (sem depender de jq).
if printf '%s' "$TAGS_JSON" | grep -q "\"name\":\"$REQUIRED_MODEL\""; then
    ok "modelo $REQUIRED_MODEL disponível"
else
    err "Modelo $REQUIRED_MODEL não encontrado."
    warn "Baixe com: ollama pull $REQUIRED_MODEL   (~5GB)"
    exit 2
fi

echo
ok "OK: Ollama rodando em $OLLAMA_HOST com $REQUIRED_MODEL disponível."
